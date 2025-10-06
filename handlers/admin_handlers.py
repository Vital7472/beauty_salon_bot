"""
Обработчики админ-панели.
Просмотр записей, заказов, отзывов, рассылка.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID, ADMIN_BROADCAST_TEXT, ADMIN_BROADCAST_CONFIRM
from database import get_all_users, get_salon_appointments, get_flower_orders, get_reviews
from utils.helpers import format_price

logger = logging.getLogger(__name__)


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Главная админ-панель"""

    # Проверка прав
    if update.effective_user.id != ADMIN_ID:
        if update.message:
            await update.message.reply_text("❌ Нет доступа")
        return

    keyboard = [
        [InlineKeyboardButton("📋 Записи в салон", callback_data="admin_appointments")],
        [InlineKeyboardButton("💐 Заказы цветов", callback_data="admin_orders")],
        [InlineKeyboardButton("🎫 Сертификаты", callback_data="admin_certificates")],
        [InlineKeyboardButton("⭐ Отзывы", callback_data="admin_reviews")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
    ]

    text = "👨‍💼 АДМИН-ПАНЕЛЬ\n\nВыберите раздел:"

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_view_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Просмотр записей в салон"""

    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        appointments = get_salon_appointments()

        # Подсчитать статистику
        today_count = 0
        pending_count = 0

        for appt in appointments:
            if appt.get('status') == 'pending':
                pending_count += 1

        text = (
            "📋 ЗАПИСИ В САЛОН\n\n"
            f"Ожидают подтверждения: {pending_count}\n"
            f"Всего записей: {len(appointments)}\n\n"
        )

        # Показать последние 5 ожидающих
        pending = [a for a in appointments if a.get('status') == 'pending'][:5]

        if pending:
            text += "Ожидают подтверждения:\n━━━━━━━━━━━━━━━\n"
            for appt in pending:
                date_time = f"{appt.get('appointment_date')} {appt.get('time_slot')}"
                text += (
                    f"#{appt.get('id')} | {date_time}\n"
                    f"💅 {appt.get('service_name')}\n"
                    f"👤 {appt.get('user_name')} ({appt.get('phone')})\n\n"
                )

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Ошибка просмотра записей: {e}")
        await query.edit_message_text(
            "❌ Ошибка загрузки данных",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")
            ]])
        )


async def admin_view_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Просмотр заказов цветов"""

    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        orders = get_flower_orders()

        # Подсчитать статистику
        new_count = len([o for o in orders if o.get('status') == 'new'])
        processing_count = len([o for o in orders if o.get('status') == 'processing'])

        text = (
            "💐 ЗАКАЗЫ ЦВЕТОВ\n\n"
            f"Новые: {new_count}\n"
            f"В обработке: {processing_count}\n"
            f"Всего заказов: {len(orders)}\n\n"
        )

        # Показать последние 5 новых
        new_orders = [o for o in orders if o.get('status') == 'new'][:5]

        if new_orders:
            text += "Новые заказы:\n━━━━━━━━━━━━━━━\n"
            for order in new_orders:
                items_text = order.get('items', '')[:40]
                text += (
                    f"#{order.get('id')} | {order.get('created_at', '')[:10]}\n"
                    f"💐 {items_text}...\n"
                    f"💵 {format_price(order.get('total_amount', 0))}\n"
                    f"👤 {order.get('user_name')}\n\n"
                )

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Ошибка просмотра заказов: {e}")
        await query.edit_message_text(
            "❌ Ошибка загрузки данных",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")
            ]])
        )


async def admin_view_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Просмотр отзывов"""

    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        reviews = get_reviews()

        # Подсчитать статистику
        positive = [r for r in reviews if r.get('rating', 0) >= 4]
        negative = [r for r in reviews if r.get('rating', 0) <= 3]

        text = (
            "⭐ ОТЗЫВЫ\n\n"
            f"Положительные (4-5⭐): {len(positive)}\n"
            f"Негативные (1-3⭐): {len(negative)}\n"
            f"Всего отзывов: {len(reviews)}\n\n"
        )

        # Показать последние 3 отзыва
        recent = reviews[:3]

        if recent:
            text += "Последние отзывы:\n━━━━━━━━━━━━━━━\n"
            for review in recent:
                rating = review.get('rating', 0)
                text += (
                    f"{'⭐' * rating} | {review.get('created_at', '')[:10]}\n"
                    f"От: {review.get('user_name', 'Аноним')}\n"
                )
                if review.get('text'):
                    text += f"\"{review.get('text')[:50]}...\"\n"
                text += "\n"

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Ошибка просмотра отзывов: {e}")
        await query.edit_message_text(
            "❌ Ошибка загрузки данных",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")
            ]])
        )


async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало рассылки"""

    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ Нет доступа", show_alert=True)
        return ConversationHandler.END

    await query.edit_message_text(
        "📢 РАССЫЛКА\n\n"
        "⚠️ Сообщение будет отправлено ВСЕМ пользователям бота!\n\n"
        "Введите текст сообщения:"
    )

    return ADMIN_BROADCAST_TEXT


async def admin_broadcast_enter_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ввод текста рассылки"""

    text = update.message.text
    context.user_data['broadcast_text'] = text

    # Получить количество пользователей
    users = get_all_users()
    user_count = len(users)

    keyboard = [
        [InlineKeyboardButton("✅ Отправить", callback_data="confirm_broadcast")],
        [InlineKeyboardButton("❌ Отмена", callback_data="admin_panel")]
    ]

    await update.message.reply_text(
        f"📢 Предпросмотр:\n\n{text}\n\n"
        f"Отправить: {user_count} пользователям",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return ADMIN_BROADCAST_CONFIRM


async def admin_broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Подтверждение и отправка рассылки"""

    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ Нет доступа", show_alert=True)
        return ConversationHandler.END

    broadcast_text = context.user_data.get('broadcast_text')
    users = get_all_users()

    await query.edit_message_text("📤 Отправка...")

    sent = 0
    failed = 0

    for user_id in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=broadcast_text
            )
            sent += 1
        except Exception as e:
            logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
            failed += 1

    await query.edit_message_text(
        f"✅ Рассылка завершена!\n\n"
        f"Отправлено: {sent}\n"
        f"Ошибок: {failed}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 В админ-панель", callback_data="admin_panel")
        ]])
    )

    context.user_data.clear()
    logger.info(f"Рассылка завершена: {sent} отправлено, {failed} ошибок")

    return ConversationHandler.END
