"""
Обработчики сертификатов.
Покупка и использование подарочных сертификатов.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import CERT_AMOUNT, CERT_RECIPIENT, CERT_CONFIRM
from database import add_certificate
from utils.helpers import format_price, generate_order_number, send_to_user_topic
import random
import string

logger = logging.getLogger(__name__)


def generate_certificate_code():
    """Генерация уникального кода сертификата"""
    part1 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    part2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"CERT-{part1}-{part2}"


async def certificate_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало покупки сертификата"""

    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    keyboard = [
        [
            InlineKeyboardButton("2000₽", callback_data="cert_amt_2000"),
            InlineKeyboardButton("3000₽", callback_data="cert_amt_3000")
        ],
        [
            InlineKeyboardButton("5000₽", callback_data="cert_amt_5000"),
            InlineKeyboardButton("✍️ Своя сумма", callback_data="cert_amt_custom")
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
    ]

    await query.edit_message_text(
        "🎁 ПОДАРОЧНЫЕ СЕРТИФИКАТЫ\n\n"
        "Выберите номинал:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return CERT_AMOUNT


async def certificate_select_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора номинала"""

    query = update.callback_query
    await query.answer()

    if query.data == "cert_amt_custom":
        await query.edit_message_text(
            "💰 Введите желаемую сумму сертификата:\n\n"
            "(минимум 1000₽)"
        )
        return CERT_AMOUNT

    # Стандартный номинал
    amount = int(query.data.replace("cert_amt_", ""))
    context.user_data['cert_amount'] = amount

    return await certificate_ask_recipient(update, context)


async def certificate_enter_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ввод пользовательской суммы"""

    try:
        amount = int(update.message.text)

        if amount < 1000:
            await update.message.reply_text(
                "❌ Минимальная сумма сертификата: 1000₽"
            )
            return CERT_AMOUNT

        if amount > 50000:
            await update.message.reply_text(
                "❌ Максимальная сумма сертификата: 50000₽"
            )
            return CERT_AMOUNT

        context.user_data['cert_amount'] = amount
        return await certificate_ask_recipient(update, context)

    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат. Введите число (например: 3500)"
        )
        return CERT_AMOUNT


async def certificate_ask_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Спросить для кого сертификат"""

    keyboard = [
        [InlineKeyboardButton("Для себя", callback_data="cert_self")],
        [InlineKeyboardButton("В подарок", callback_data="cert_gift")],
        [InlineKeyboardButton("◀️ Назад", callback_data="buy_certificate")]
    ]

    text = "👤 Для кого сертификат?"

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    return CERT_RECIPIENT


async def certificate_handle_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора получателя"""

    query = update.callback_query
    await query.answer()

    if query.data == "cert_self":
        context.user_data['cert_recipient'] = "Себе"
        context.user_data['cert_recipient_contact'] = ""
        return await certificate_show_confirmation(update, context)

    elif query.data == "cert_gift":
        await query.edit_message_text(
            "👤 Данные получателя:\n\n"
            "Укажите имя и телефон (необязательно):\n\n"
            "Формат: Имя, телефон\n"
            "Или просто имя"
        )
        return CERT_RECIPIENT

    return CERT_RECIPIENT


async def certificate_enter_recipient_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение данных получателя"""

    text = update.message.text.strip()
    context.user_data['cert_recipient'] = text
    context.user_data['cert_recipient_contact'] = text

    return await certificate_show_confirmation(update, context)


async def certificate_show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать подтверждение"""

    amount = context.user_data.get('cert_amount')
    recipient = context.user_data.get('cert_recipient', 'Не указан')

    text = (
        "✅ ПОДТВЕРДИТЕ ПОКУПКУ:\n\n"
        f"🎁 Сертификат на {format_price(amount)}\n\n"
        f"👤 Получатель: {recipient}\n\n"
        "💳 Оплата: при получении в салоне"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_certificate")],
        [InlineKeyboardButton("◀️ Изменить", callback_data="buy_certificate")]
    ]

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    return CERT_CONFIRM


async def certificate_confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Финальное подтверждение покупки"""

    query = update.callback_query
    await query.answer()

    user = update.effective_user
    amount = context.user_data.get('cert_amount')
    recipient = context.user_data.get('cert_recipient', 'Не указан')

    try:
        # Создать сертификат в БД (код генерируется автоматически)
        cert_code = add_certificate(amount, user.id)

        if not cert_code:
            raise Exception("Не удалось создать сертификат")

        # Уведомить админа
        from database import get_user
        user_data = get_user(user.id)
        phone = user_data[3] if user_data and user_data[3] else "Не указан"

        admin_text = (
            "🎁 <b>НОВЫЙ СЕРТИФИКАТ</b>\n\n"
            f"Код: <code>{cert_code}</code>\n"
            f"Номинал: {format_price(amount)}\n\n"
            f"Купил: {user.first_name}"
        )

        if user.username:
            admin_text += f" (@{user.username})"

        admin_text += (
            f"\nТелефон: {phone}\n"
            f"Получатель: {recipient}\n\n"
            "Оплата: при получении в салоне"
        )

        # Отправить в топик пользователя в админ-группе
        await send_to_user_topic(context, user.id, user.first_name, admin_text, None)

        # Ответ клиенту
        await query.edit_message_text(
            f"🎉 Сертификат успешно оформлен!\n\n"
            f"🎫 Код сертификата: <code>{cert_code}</code>\n"
            f"💰 Номинал: {format_price(amount)}\n\n"
            "Сертификат можно получить в салоне.\n"
            "Код можно использовать для оплаты любых услуг и товаров.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")
            ]]),
            parse_mode='HTML'
        )

        context.user_data.clear()
        logger.info(f"Создан сертификат {cert_code} для пользователя {user.id}")

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка создания сертификата: {e}")
        await query.edit_message_text(
            "❌ Произошла ошибка при создании сертификата.\n"
            "Попробуйте позже или свяжитесь с администратором.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 В меню", callback_data="main_menu")
            ]])
        )
        return ConversationHandler.END
