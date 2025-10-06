"""
Обработчики для модуля записи в салон красоты.
Полный цикл записи: от выбора услуги до подтверждения.
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

from config import (
    SALON_CATEGORY, SALON_SERVICE, SALON_DATE, SALON_TIME,
    SALON_PHONE, SALON_COMMENT, SALON_PAYMENT, SALON_CONFIRM,
    ADMIN_ID, ADMIN_GROUP_ID
)
from database import (
    get_user, update_user_phone, get_service_categories, get_services,
    get_service_by_id, add_salon_appointment, log_consent,
    schedule_feedback_request, check_and_award_referral_bonus, update_utm_campaign_stats
)
from utils.helpers import format_price, get_current_datetime, format_datetime, send_to_user_topic
from utils.calendar import create_calendar, handle_calendar_navigation
from utils.validators import validate_phone, format_phone

logger = logging.getLogger(__name__)


# =================================================================
# ШАГ 1: ВЫБОР КАТЕГОРИИ УСЛУГ
# =================================================================

async def salon_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало записи в салон - выбор категории услуг"""

    query = update.callback_query
    await query.answer()

    # Очистить предыдущие данные
    context.user_data.clear()

    try:
        # Получить категории из БД
        categories = get_service_categories()

        if not categories:
            await query.edit_message_text(
                "❌ К сожалению, сейчас нет доступных услуг.\n"
                "Попробуйте позже или свяжитесь с администратором.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="main_menu")
                ]])
            )
            return ConversationHandler.END

        # Создать клавиатуру с категориями
        keyboard = []
        for category in categories:
            keyboard.append([InlineKeyboardButton(
                category,
                callback_data=f"salon_cat_{category}"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_menu")])

        await query.edit_message_text(
            "💇‍♀️ ЗАПИСЬ В САЛОН\n\n"
            "Выберите категорию услуг:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return SALON_CATEGORY

    except Exception as e:
        logger.error(f"Ошибка в salon_start: {e}")
        await query.edit_message_text(
            "❌ Произошла ошибка. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ В меню", callback_data="main_menu")
            ]])
        )
        return ConversationHandler.END


# =================================================================
# ШАГ 2: ВЫБОР УСЛУГИ
# =================================================================

async def salon_select_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбор конкретной услуги из категории"""

    query = update.callback_query
    await query.answer()

    # Извлечь название категории из callback_data
    # Если это возврат назад (back_to_services), использовать сохраненную категорию
    if query.data == "back_to_services":
        category = context.user_data.get('salon_category')
        if not category:
            # Если категория не сохранена, вернуться к началу
            return await salon_start(update, context)
    else:
        category = query.data.replace("salon_cat_", "")
        context.user_data['salon_category'] = category

    try:
        # Получить услуги выбранной категории из БД
        services = get_services(category=category, active_only=True)

        if not services:
            await query.edit_message_text(
                f"❌ В категории '{category}' нет доступных услуг.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="salon_booking")
                ]])
            )
            return SALON_CATEGORY

        # Создать клавиатуру с услугами
        keyboard = []
        for service in services:
            text = f"{service['name']} - {format_price(service['price'])}"
            keyboard.append([InlineKeyboardButton(
                text,
                callback_data=f"salon_srv_{service['id']}"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="salon_booking")])

        await query.edit_message_text(
            f"Категория: {category}\n\n"
            "Выберите услугу:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return SALON_SERVICE

    except Exception as e:
        logger.error(f"Ошибка в salon_select_category: {e}")
        await query.edit_message_text("❌ Произошла ошибка.")
        return ConversationHandler.END


# =================================================================
# ШАГ 3: ВЫБОР ДАТЫ (КАЛЕНДАРЬ)
# =================================================================

async def salon_select_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбор даты записи - показать календарь"""

    query = update.callback_query
    await query.answer()

    # Извлечь ID услуги
    service_id = int(query.data.replace("salon_srv_", ""))

    try:
        # Получить выбранную услугу из БД
        service = get_service_by_id(service_id)

        if not service:
            await query.edit_message_text("❌ Услуга не найдена.")
            return ConversationHandler.END

        # Сохранить услугу
        context.user_data['salon_service'] = service

        # Создать календарь
        calendar_keyboard = create_calendar()

        text = (
            f"Вы выбрали:\n"
            f"💅 {service['name']}\n"
            f"💰 {format_price(service['price'])}\n"
            f"⏱️ {service['duration_minutes']} минут\n\n"
            f"Выберите желаемую дату:"
        )

        await query.edit_message_text(text, reply_markup=calendar_keyboard)

        return SALON_DATE

    except Exception as e:
        logger.error(f"Ошибка в salon_select_service: {e}")
        await query.edit_message_text("❌ Произошла ошибка.")
        return ConversationHandler.END


async def salon_select_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора даты из календаря"""

    query = update.callback_query
    await query.answer()

    callback_data = query.data

    # Навигация по календарю (Пред/След)
    if callback_data.startswith("calendar_prev_") or callback_data.startswith("calendar_next_"):
        parts = callback_data.split("_")
        year = int(parts[2])
        month = int(parts[3])

        new_year, new_month = handle_calendar_navigation(callback_data, year, month)
        calendar_keyboard = create_calendar(new_year, new_month)

        service = context.user_data.get('salon_service')
        text = (
            f"Вы выбрали:\n"
            f"💅 {service['name']}\n"
            f"💰 {format_price(service['price'])}\n"
            f"⏱️ {service['duration_minutes']} минут\n\n"
            f"Выберите желаемую дату:"
        )

        await query.edit_message_text(text, reply_markup=calendar_keyboard)
        return SALON_DATE

    # Возврат назад
    if callback_data == "back_to_services":
        return await salon_start(update, context)

    # Игнорировать неактивные даты
    if callback_data == "ignore":
        await query.answer("Эта дата недоступна")
        return SALON_DATE

    # Выбрана дата
    if callback_data.startswith("calendar_"):
        selected_date = callback_data.replace("calendar_", "")
        context.user_data['salon_date'] = selected_date

        # Показать временные слоты
        return await show_time_slots(update, context)

    return SALON_DATE


# =================================================================
# ШАГ 4: ВЫБОР ВРЕМЕНИ
# =================================================================

async def show_time_slots(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать временные слоты для выбора"""

    query = update.callback_query
    service = context.user_data.get('salon_service')
    selected_date = context.user_data.get('salon_date')

    keyboard = [
        [
            InlineKeyboardButton("09:00-12:00", callback_data="time_09-12"),
            InlineKeyboardButton("12:00-15:00", callback_data="time_12-15")
        ],
        [
            InlineKeyboardButton("15:00-18:00", callback_data="time_15-18"),
            InlineKeyboardButton("18:00-21:00", callback_data="time_18-21")
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_calendar")]
    ]

    # Форматировать дату для отображения
    dt = datetime.strptime(selected_date, "%Y-%m-%d")
    formatted_date = format_datetime(f"{selected_date} 00:00").split(',')[0]  # Только дату

    text = (
        f"Вы выбрали:\n"
        f"💅 {service['name']}\n"
        f"📅 Дата: {formatted_date}\n\n"
        f"Выберите желаемое время:"
    )

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    return SALON_TIME


async def salon_select_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора времени"""

    query = update.callback_query
    await query.answer()

    if query.data == "back_to_calendar":
        # Вернуться к выбору даты
        service = context.user_data.get('salon_service')
        calendar_keyboard = create_calendar()

        text = (
            f"Вы выбрали:\n"
            f"💅 {service['name']}\n"
            f"💰 {format_price(service['price'])}\n"
            f"⏱️ {service['duration_minutes']} минут\n\n"
            f"Выберите желаемую дату:"
        )

        await query.edit_message_text(text, reply_markup=calendar_keyboard)
        return SALON_DATE

    # Сохранить выбранное время
    time_slot = query.data.replace("time_", "")
    context.user_data['salon_time'] = time_slot

    # Проверить, есть ли телефон в БД
    user = get_user(update.effective_user.id)

    if user and user[3]:  # user[3] = phone
        context.user_data['salon_phone'] = user[3]
        # Сразу переходим к комментарию
        return await salon_ask_comment(update, context)

    # Запросить телефон с согласием на обработку данных
    keyboard = [[KeyboardButton("📱 Поделиться номером", request_contact=True)]]

    await query.message.reply_text(
        "📞 Укажите ваш номер телефона\n\n"
        "Вы можете:\n"
        "• Ввести номер вручную: +7 (XXX) XXX-XX-XX\n"
        "• Нажать кнопку 'Поделиться номером'\n\n"
        "⚠️ <b>Важно:</b> Нажимая кнопку 'Поделиться номером' или вводя номер телефона, "
        "вы соглашаетесь с <a href='https://example.com/privacy'>Политикой конфиденциальности</a> "
        "и даете <a href='https://example.com/consent'>Согласие на обработку персональных данных</a>.\n\n"
        "Ваше согласие будет зафиксировано с указанием даты и времени.",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode='HTML',
        disable_web_page_preview=True
    )

    return SALON_PHONE


# =================================================================
# ШАГ 5: ВВОД ТЕЛЕФОНА
# =================================================================

async def salon_enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ввод телефона текстом"""

    phone = update.message.text

    # Валидация телефона
    if not validate_phone(phone):
        await update.message.reply_text(
            "❌ Неверный формат телефона\n\n"
            "Используйте формат: +7 (XXX) XXX-XX-XX"
        )
        return SALON_PHONE

    # Форматировать и сохранить
    formatted_phone = format_phone(phone)
    context.user_data['salon_phone'] = formatted_phone

    # Обновить в БД
    update_user_phone(update.effective_user.id, formatted_phone)

    # Логировать согласие на обработку данных
    log_consent(
        user_id=update.effective_user.id,
        user_name=update.effective_user.first_name,
        phone=formatted_phone,
        consent_type='manual_phone_input'
    )

    # Перейти к комментарию
    return await salon_ask_comment(update, context)


async def salon_contact_shared(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение контакта через кнопку 'Поделиться номером'"""

    phone = update.message.contact.phone_number

    # Форматировать
    formatted_phone = format_phone(phone)

    context.user_data['salon_phone'] = formatted_phone
    update_user_phone(update.effective_user.id, formatted_phone)

    # Логировать согласие на обработку данных
    log_consent(
        user_id=update.effective_user.id,
        user_name=update.effective_user.first_name,
        phone=formatted_phone,
        consent_type='contact_share_button'
    )

    logger.info(f"Пользователь {update.effective_user.id} ({update.effective_user.first_name}) "
                f"согласился с политикой конфиденциальности через кнопку 'Поделиться номером'")

    return await salon_ask_comment(update, context)


# =================================================================
# ШАГ 6: КОММЕНТАРИЙ К ЗАПИСИ
# =================================================================

async def salon_ask_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрос комментария к записи"""

    keyboard = [[InlineKeyboardButton("Пропустить", callback_data="skip_comment")]]

    text = (
        "💬 Есть пожелания или комментарии к записи?\n\n"
        "Напишите сообщение или нажмите 'Пропустить':"
    )

    # Убрать клавиатуру с телефоном
    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.callback_query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    return SALON_COMMENT


async def salon_enter_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение комментария"""

    context.user_data['salon_comment'] = update.message.text
    return await salon_ask_payment(update, context)


async def salon_skip_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск комментария"""

    query = update.callback_query
    await query.answer()

    context.user_data['salon_comment'] = ""
    return await salon_ask_payment(update, context)


# =================================================================
# ШАГ 7: СПОСОБ ОПЛАТЫ
# =================================================================

async def salon_ask_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбор способа оплаты"""

    keyboard = [
        [InlineKeyboardButton("Оплачу на месте", callback_data="payment_onsite")],
        [InlineKeyboardButton("Внести предоплату онлайн", callback_data="payment_online")],
    ]

    text = "💳 Выберите способ оплаты:"

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.callback_query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    return SALON_PAYMENT


async def salon_select_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора оплаты"""

    query = update.callback_query
    await query.answer()

    payment = "На месте" if query.data == "payment_onsite" else "Онлайн (позже)"
    context.user_data['salon_payment'] = payment

    # Показать подтверждение
    return await show_booking_confirmation(update, context)


# =================================================================
# ШАГ 8: ПОДТВЕРЖДЕНИЕ И СОЗДАНИЕ ЗАПИСИ
# =================================================================

async def show_booking_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать подтверждение записи"""

    query = update.callback_query

    service = context.user_data.get('salon_service')
    date = context.user_data.get('salon_date')
    time_slot = context.user_data.get('salon_time')
    phone = context.user_data.get('salon_phone')
    comment = context.user_data.get('salon_comment', 'нет')
    payment = context.user_data.get('salon_payment')

    # Форматировать дату
    formatted_date = format_datetime(f"{date} 00:00").split(',')[0]

    text = (
        "✅ Подтвердите запись:\n\n"
        f"💅 Услуга: {service['name']}\n"
        f"💰 Стоимость: {format_price(service['price'])}\n"
        f"📅 Дата: {formatted_date}\n"
        f"⏰ Время: {time_slot}\n"
        f"📞 Телефон: {phone}\n"
        f"💬 Комментарий: {comment}\n"
        f"💳 Оплата: {payment}"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить запись", callback_data="confirm_salon_booking")],
        [InlineKeyboardButton("◀️ Изменить", callback_data="salon_booking")]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    return SALON_CONFIRM


async def salon_confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Финальное подтверждение - создание записи"""

    query = update.callback_query
    await query.answer()

    user = update.effective_user
    service = context.user_data.get('salon_service')
    date = context.user_data.get('salon_date')
    time_slot = context.user_data.get('salon_time')
    phone = context.user_data.get('salon_phone')
    comment = context.user_data.get('salon_comment', '')
    payment = context.user_data.get('salon_payment')

    try:
        # Создать запись в БД
        prepaid = False if payment == "На месте" else True

        appointment_id = add_salon_appointment(
            user_id=user.id,
            user_name=user.first_name,
            phone=phone,
            service_id=service['id'],
            service_name=service['name'],
            appointment_date=date,
            time_slot=time_slot,
            prepaid=prepaid,
            comment=comment
        )

        if not appointment_id:
            raise Exception("Не удалось создать запись в БД")

        # Запланировать запрос на отзыв
        schedule_feedback_request(user.id, 'appointment', appointment_id)

        # Проверить и начислить реферальный бонус
        try:
            check_and_award_referral_bonus(appointment_id, user.id, service['price'])
            logger.info(f"Проверен реферальный бонус для записи #{appointment_id}")
        except Exception as e:
            logger.error(f"Ошибка проверки реферального бонуса: {e}")

        # Обновить статистику конверсий UTM
        try:
            user_data = get_user(user.id)
            if user_data and len(user_data) > 9 and user_data[9]:  # utm_source exists
                utm_code = f"{user_data[9]}__{user_data[10] or ''}__{user_data[11] or ''}__{user_data[12] or ''}__{user_data[13] or ''}"
                update_utm_campaign_stats(utm_code, 'conversion', service['price'])
                logger.info(f"Обновлена UTM-статистика конверсии: {utm_code}")
        except Exception as e:
            logger.error(f"Ошибка обновления UTM-статистики: {e}")

        # Создать сообщение для админ-группы
        formatted_date = format_datetime(f"{date} {time_slot.split('-')[0]}:00")

        admin_text = (
            "🆕 <b>НОВАЯ ЗАПИСЬ В САЛОН</b>\n\n"
            f"📋 Номер: #{appointment_id}\n"
            f"👤 Клиент: {user.first_name}"
        )

        if user.username:
            admin_text += f" (@{user.username})"

        admin_text += (
            f"\n📞 Телефон: {phone}\n\n"
            f"💅 Услуга: {service['name']}\n"
            f"💰 Стоимость: {format_price(service['price'])}\n"
            f"📅 Дата: {formatted_date}\n"
            f"⏰ Желаемое время: {time_slot}\n"
            f"💬 Комментарий: {comment or 'нет'}\n\n"
            f"💳 Оплата: {payment}"
        )

        # Отправить в топик пользователя в админ-группе
        await send_to_user_topic(
            context,
            user.id,
            user.first_name,
            admin_text,
            None
        )

        # TODO: Запланировать напоминания (сделаем в следующих шагах)

        # Ответить клиенту
        await query.edit_message_text(
            f"🎉 Запись успешно создана!\n\n"
            f"Номер записи: #{appointment_id}\n\n"
            f"Администратор свяжется с вами в ближайшее время для уточнения деталей.\n\n"
            f"За 2 часа до визита вы получите напоминание.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")
            ]])
        )

        # Очистить данные
        context.user_data.clear()

        logger.info(f"Создана запись #{appointment_id} для пользователя {user.id}")

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка при создании записи: {e}")
        await query.edit_message_text(
            "❌ Произошла ошибка при создании записи.\n"
            "Попробуйте позже или свяжитесь с администратором.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 В меню", callback_data="main_menu")
            ]])
        )
        return ConversationHandler.END
