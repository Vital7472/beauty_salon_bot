"""
Обработчики профиля пользователя.
История записей, заказов, адреса, бонусы, реферальная программа.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import (
    get_user, get_addresses, get_bonus_balance,
    get_loyalty_transactions, count_referrals, set_default_address, delete_address,
    get_salon_appointments, get_flower_orders, is_profile_filled, update_user_profile,
    get_user_active_subscription
)
from utils.helpers import format_price, format_datetime
from config import ADMIN_ID

logger = logging.getLogger(__name__)


async def profile_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать профиль пользователя"""

    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_data = get_user(user.id)

    if not user_data:
        await query.edit_message_text(
            "Профиль не найден. Нажмите /start для регистрации."
        )
        return

    bonus_balance = get_bonus_balance(user.id)
    referral_code = user_data[6] if len(user_data) > 6 else "Нет"
    referrals_count = count_referrals(user.id)

    # Проверить индексы для birthday
    birthday = None
    if len(user_data) > 16:  # birthday должен быть после profile_filled
        birthday = user_data[16]

    # Получить активную подписку
    active_sub = get_user_active_subscription(user.id)

    text = (
        "👤 МОЙ ПРОФИЛЬ\n\n"
        f"Имя: {user.first_name}\n"
    )

    if user.username:
        text += f"Telegram: @{user.username}\n"

    if user_data[3]:  # phone
        text += f"📞 Телефон: {user_data[3]}\n"

    if birthday:
        text += f"🎂 День рождения: {birthday}\n"

    text += f"\n🎁 Бонусов: {bonus_balance}\n"

    # Показать активную подписку если есть
    if active_sub:
        text += f"💎 Подписка: {active_sub['plan_name']}\n"
        text += f"📅 Действует до: {active_sub['end_date']}\n"

        # Показать доступные преимущества кратко
        if active_sub['monthly_flowers_included'] > 0:
            used = active_sub['flowers_used_this_month']
            total = active_sub['monthly_flowers_included']
            text += f"🌹 Букетов: {total - used}/{total}\n"

        if active_sub['monthly_service_included'] and not active_sub['service_used_this_month']:
            text += f"💅 Услуга: Доступна\n"

    text += (
        f"\n💎 Реферальный код: {referral_code}\n"
        f"👥 Приглашено друзей: {referrals_count}"
    )

    keyboard = [
        [InlineKeyboardButton("📋 Мои записи", callback_data="profile_appointments")],
        [InlineKeyboardButton("🛍️ Мои заказы", callback_data="profile_orders")],
        [InlineKeyboardButton("📍 Мои адреса", callback_data="profile_addresses")],
        [InlineKeyboardButton("🎁 История бонусов", callback_data="profile_bonuses")],
        [InlineKeyboardButton("👥 Пригласить друга", callback_data="profile_referral")],
    ]

    # Добавить кнопку "Моя подписка" если есть активная
    if active_sub:
        keyboard.append([InlineKeyboardButton("💎 Моя подписка", callback_data="subscriptions")])

    # Добавить кнопку редактирования, если профиль еще не заполнен
    if not is_profile_filled(user.id):
        keyboard.append([InlineKeyboardButton("✏️ Заполнить профиль", callback_data="profile_edit")])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_menu")])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def profile_view_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать записи в салон"""

    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    try:
        # Получить записи пользователя из БД
        appointments = get_salon_appointments(user_id=user_id)

        if not appointments:
            text = "📋 У вас пока нет записей в салон"
        else:
            # Разделить на активные и завершенные
            active = [a for a in appointments if a.get('status') in ['pending', 'confirmed']]
            completed = [a for a in appointments if a.get('status') == 'completed']

            text = "📋 МОИ ЗАПИСИ\n\n"

            if active:
                text += "Активные:\n━━━━━━━━━━━━━━━\n"
                for appt in active[:5]:
                    status_emoji = "✅" if appt.get('status') == 'confirmed' else "⏳"
                    date_time = f"{appt.get('appointment_date')} {appt.get('time_slot')}"
                    text += (
                        f"#{appt.get('id')} | {date_time}\n"
                        f"💅 {appt.get('service_name')}\n"
                        f"Статус: {status_emoji}\n\n"
                    )

            if completed:
                text += "\nИстория:\n━━━━━━━━━━━━━━━\n"
                for appt in completed[:3]:
                    date_time = f"{appt.get('appointment_date')} {appt.get('time_slot')}"
                    text += (
                        f"#{appt.get('id')} | {date_time}\n"
                        f"💅 {appt.get('service_name')} ✅\n\n"
                    )

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="profile")]]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Ошибка получения записей: {e}")
        await query.edit_message_text(
            "❌ Ошибка загрузки записей",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="profile")
            ]])
        )


async def profile_view_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать заказы цветов"""

    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    try:
        # Получить заказы пользователя из БД
        orders = get_flower_orders(user_id=user_id)

        if not orders:
            text = "🛍️ У вас пока нет заказов"
        else:
            active = [o for o in orders if o.get('status') in ['new', 'processing']]
            completed = [o for o in orders if o.get('status') == 'completed']

            text = "🛍️ МОИ ЗАКАЗЫ\n\n"

            if active:
                text += "Активные:\n━━━━━━━━━━━━━━━\n"
                for order in active[:5]:
                    items_text = order.get('items', '')[:40]
                    text += (
                        f"#{order.get('id')} | {order.get('created_at', '')[:10]}\n"
                        f"💐 {items_text}...\n"
                        f"💵 {format_price(order.get('total_amount', 0))}\n"
                        f"Статус: 🔄\n\n"
                    )

            if completed:
                text += "\nИстория:\n━━━━━━━━━━━━━━━\n"
                for order in completed[:3]:
                    items_text = order.get('items', '')[:40]
                    text += (
                        f"#{order.get('id')} | {order.get('created_at', '')[:10]}\n"
                        f"💐 {items_text}...\n"
                        f"💵 {format_price(order.get('total_amount', 0))} ✅\n\n"
                    )

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="profile")]]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Ошибка получения заказов: {e}")
        await query.edit_message_text(
            "❌ Ошибка загрузки заказов",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="profile")
            ]])
        )


async def profile_view_addresses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Управление адресами"""

    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    addresses = get_addresses(user_id)

    if not addresses:
        text = "📍 У вас нет сохраненных адресов"
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="profile")]]
    else:
        text = "📍 МОИ АДРЕСА\n\n"
        keyboard = []

        for addr_id, address, is_default in addresses:
            prefix = "✅ " if is_default else "   "
            text += f"{prefix}{address}\n\n"

            buttons = []
            if not is_default:
                buttons.append(InlineKeyboardButton(
                    "Сделать основным",
                    callback_data=f"set_default_addr_{addr_id}"
                ))
            buttons.append(InlineKeyboardButton(
                "🗑️",
                callback_data=f"delete_addr_{addr_id}"
            ))
            keyboard.append(buttons)

        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="profile")])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def profile_set_default_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Установить основной адрес"""

    query = update.callback_query
    await query.answer()

    addr_id = int(query.data.replace("set_default_addr_", ""))
    user_id = update.effective_user.id

    try:
        set_default_address(user_id, addr_id)
        await query.answer("✅ Адрес установлен основным", show_alert=True)
        return await profile_view_addresses(update, context)
    except Exception as e:
        logger.error(f"Ошибка установки адреса: {e}")
        await query.answer("❌ Ошибка", show_alert=True)


async def profile_delete_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Удалить адрес"""

    query = update.callback_query
    await query.answer()

    addr_id = int(query.data.replace("delete_addr_", ""))

    try:
        delete_address(addr_id)
        await query.answer("✅ Адрес удален", show_alert=True)
        return await profile_view_addresses(update, context)
    except Exception as e:
        logger.error(f"Ошибка удаления адреса: {e}")
        await query.answer("❌ Ошибка", show_alert=True)


async def profile_view_bonuses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """История бонусов"""

    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    balance = get_bonus_balance(user_id)
    transactions = get_loyalty_transactions(user_id, limit=10)

    text = f"🎁 БОНУСЫ\n\nВаш баланс: {balance}\n\n1 бонус = 1 рубль\n\n"

    if transactions:
        text += "История:\n━━━━━━━━━━━━━━━\n"
        for points, description, created_at in transactions:
            sign = "+" if points > 0 else ""
            text += f"{sign}{points} | {description}\n"
    else:
        text += "История пуста"

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="profile")]]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def profile_view_referral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Реферальная программа"""

    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_data = get_user(user.id)
    referral_code = user_data[6] if len(user_data) > 6 else "Нет"
    referrals_count = count_referrals(user.id)

    text = (
        "👥 ПРИГЛАСИ ДРУГА\n\n"
        f"Твой реферальный код: {referral_code}\n\n"
        "Отправь код другу, и когда он зарегистрируется:\n"
        "🎁 Ты получишь: 500 бонусов\n"
        "🎁 Друг получит: 500 бонусов\n\n"
        f"Приглашено друзей: {referrals_count}\n"
        f"Получено бонусов: {referrals_count * 500}\n\n"
        "Реферальная ссылка:\n"
        f"t.me/your_bot_username?start={referral_code}"
    )

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="profile")]]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ============================================================================
# РЕДАКТИРОВАНИЕ ПРОФИЛЯ (только 1 раз)
# ============================================================================

from telegram.ext import ConversationHandler

EDIT_NAME, EDIT_PHONE, EDIT_BIRTHDAY = range(3)


async def profile_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начать заполнение профиля"""

    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    # Проверить, был ли уже заполнен профиль
    if is_profile_filled(user_id):
        await query.edit_message_text(
            "❌ Вы уже заполняли профиль.\n\n"
            "Для изменения данных обратитесь к администратору.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="profile")
            ]])
        )
        return ConversationHandler.END

    await query.edit_message_text(
        "✏️ ЗАПОЛНЕНИЕ ПРОФИЛЯ\n\n"
        "Это можно сделать только один раз!\n\n"
        "Пожалуйста, введите ваше имя:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data="profile_edit_cancel")
        ]])
    )

    return EDIT_NAME


async def profile_edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получить имя"""

    name = update.message.text.strip()

    if len(name) < 2:
        await update.message.reply_text(
            "❌ Имя слишком короткое. Попробуйте еще раз:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="profile_edit_cancel")
            ]])
        )
        return EDIT_NAME

    context.user_data['edit_name'] = name

    await update.message.reply_text(
        f"✅ Имя: {name}\n\n"
        "Теперь введите ваш номер телефона\n"
        "(например: +7 900 123-45-67):",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data="profile_edit_cancel")
        ]])
    )

    return EDIT_PHONE


async def profile_edit_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получить телефон"""

    phone = update.message.text.strip()

    # Базовая валидация номера
    if len(phone) < 10:
        await update.message.reply_text(
            "❌ Некорректный номер телефона. Попробуйте еще раз:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="profile_edit_cancel")
            ]])
        )
        return EDIT_PHONE

    context.user_data['edit_phone'] = phone

    await update.message.reply_text(
        f"✅ Телефон: {phone}\n\n"
        "Теперь введите вашу дату рождения\n"
        "(формат: ДД.ММ.ГГГГ, например: 15.03.1990):",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data="profile_edit_cancel")
        ]])
    )

    return EDIT_BIRTHDAY


async def profile_edit_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получить день рождения и сохранить профиль"""

    birthday_text = update.message.text.strip()

    # Парсинг даты
    try:
        from datetime import datetime

        # Попробовать разные форматы
        for fmt in ['%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y']:
            try:
                birthday_date = datetime.strptime(birthday_text, fmt)
                break
            except:
                continue
        else:
            raise ValueError("Неверный формат")

        # Преобразовать в ISO формат для БД
        birthday_iso = birthday_date.strftime('%Y-%m-%d')

    except:
        await update.message.reply_text(
            "❌ Некорректная дата. Используйте формат ДД.ММ.ГГГГ\n"
            "Например: 15.03.1990\n\n"
            "Попробуйте еще раз:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="profile_edit_cancel")
            ]])
        )
        return EDIT_BIRTHDAY

    # Сохранить профиль
    user_id = update.effective_user.id
    name = context.user_data.get('edit_name')
    phone = context.user_data.get('edit_phone')

    success = update_user_profile(
        user_id=user_id,
        first_name=name,
        phone=phone,
        birthday=birthday_iso
    )

    if success:
        await update.message.reply_text(
            "✅ ПРОФИЛЬ УСПЕШНО ЗАПОЛНЕН!\n\n"
            f"Имя: {name}\n"
            f"Телефон: {phone}\n"
            f"День рождения: {birthday_text}\n\n"
            "Теперь вы можете пользоваться всеми функциями бота!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👤 Мой профиль", callback_data="profile")
            ]])
        )
    else:
        await update.message.reply_text(
            "❌ Ошибка сохранения профиля.\n"
            "Обратитесь к администратору.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👤 Мой профиль", callback_data="profile")
            ]])
        )

    # Очистить временные данные
    context.user_data.pop('edit_name', None)
    context.user_data.pop('edit_phone', None)

    return ConversationHandler.END


async def profile_edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменить заполнение профиля"""

    query = update.callback_query
    await query.answer()

    # Очистить временные данные
    context.user_data.pop('edit_name', None)
    context.user_data.pop('edit_phone', None)

    await query.edit_message_text(
        "❌ Заполнение профиля отменено",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("👤 Мой профиль", callback_data="profile")
        ]])
    )

    return ConversationHandler.END
