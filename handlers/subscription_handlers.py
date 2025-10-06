"""
Обработчики подписок и карт привилегий
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import (
    get_subscription_plans, get_user_active_subscription,
    create_user_subscription
)
from utils.helpers import format_price

logger = logging.getLogger(__name__)

# Состояния conversation handler
SUBSCRIPTION_CONFIRM = 1


async def subscriptions_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать меню подписок"""

    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    # Проверить активную подписку
    active_sub = get_user_active_subscription(user_id)

    if active_sub:
        text = (
            f"💎 ВАША ПОДПИСКА\n\n"
            f"📋 План: {active_sub['plan_name']}\n"
            f"📅 Действует до: {active_sub['end_date']}\n\n"
        )

        # Показать доступные преимущества
        if active_sub['monthly_flowers_included'] > 0:
            used = active_sub['flowers_used_this_month']
            total = active_sub['monthly_flowers_included']
            text += f"🌹 Букетов доступно: {total - used} из {total}\n"

        if active_sub['monthly_service_included']:
            status = "Использована" if active_sub['service_used_this_month'] else "Доступна"
            text += f"💅 Услуга салона: {status}\n"

        if active_sub['service_discount_percent'] > 0:
            text += f"✨ Скидка на услуги: {active_sub['service_discount_percent']}%\n"

        if active_sub['flower_discount_percent'] > 0:
            text += f"🌸 Скидка на цветы: {active_sub['flower_discount_percent']}%\n"

        keyboard = [
            [InlineKeyboardButton("🌹 Забрать букет", callback_data="subscription_claim_flower")],
            [InlineKeyboardButton("💅 Использовать услугу", callback_data="subscription_claim_service")],
            [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
        ]
    else:
        text = (
            "💎 ПОДПИСКИ И КАРТЫ\n\n"
            "Выберите подходящий тарифный план для максимальной выгоды!"
        )

        # Получить доступные планы
        plans = get_subscription_plans()

        keyboard = []
        for plan in plans:
            keyboard.append([InlineKeyboardButton(
                f"{plan['name']} - {format_price(plan['price'])}",
                callback_data=f"subscription_view_{plan['id']}"
            )])

        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_menu")])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def subscription_view_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать детали тарифного плана"""

    query = update.callback_query
    await query.answer()

    plan_id = int(query.data.replace("subscription_view_", ""))

    plans = get_subscription_plans(active_only=False)
    plan = next((p for p in plans if p['id'] == plan_id), None)

    if not plan:
        await query.edit_message_text(
            "❌ План не найден",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="subscriptions")
            ]])
        )
        return

    duration_text = ""
    if plan['duration_months'] > 0:
        if plan['duration_months'] == 1:
            duration_text = "1 месяц"
        elif plan['duration_months'] == 12:
            duration_text = "1 год"
        else:
            duration_text = f"{plan['duration_months']} мес."
    else:
        duration_text = "Одноразовый пакет"

    text = (
        f"💎 {plan['name'].upper()}\n\n"
        f"{plan['description']}\n\n"
        f"📋 Преимущества:\n"
        f"{plan['benefits']}\n\n"
        f"💰 Цена: {format_price(plan['price'])}\n"
        f"⏱ Срок: {duration_text}"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Купить подписку", callback_data=f"subscription_buy_{plan_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="subscriptions")]
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def subscription_buy_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Подтвердить покупку подписки"""

    query = update.callback_query
    await query.answer()

    plan_id = int(query.data.replace("subscription_buy_", ""))

    plans = get_subscription_plans(active_only=False)
    plan = next((p for p in plans if p['id'] == plan_id), None)

    if not plan:
        await query.edit_message_text("❌ План не найден")
        return ConversationHandler.END

    # Сохранить plan_id в контексте
    context.user_data['subscription_plan_id'] = plan_id
    context.user_data['subscription_price'] = plan['price']

    text = (
        f"💳 ОФОРМЛЕНИЕ ПОДПИСКИ\n\n"
        f"План: {plan['name']}\n"
        f"Сумма к оплате: {format_price(plan['price'])}\n\n"
        f"⚠️ ВАЖНО: После оплаты свяжитесь с администратором для активации подписки.\n\n"
        f"Реквизиты для оплаты:\n"
        f"💳 Карта: 1234 5678 9012 3456\n"
        f"👤 Получатель: ООО 'Салон красоты'\n\n"
        f"После оплаты нажмите кнопку 'Я оплатил' и отправьте скриншот чека администратору."
    )

    keyboard = [
        [InlineKeyboardButton("✅ Я оплатил", callback_data=f"subscription_paid_{plan_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data="subscriptions")]
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return SUBSCRIPTION_CONFIRM


async def subscription_payment_sent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пользователь сообщил об оплате"""

    query = update.callback_query
    await query.answer()

    plan_id = context.user_data.get('subscription_plan_id')

    await query.edit_message_text(
        "✅ ЗАЯВКА ПРИНЯТА\n\n"
        "Ваша заявка на подписку отправлена администратору.\n"
        "Подписка будет активирована после проверки оплаты.\n\n"
        "Обычно это занимает до 30 минут.\n"
        "Вы получите уведомление об активации.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("👌 Понятно", callback_data="main_menu")
        ]])
    )

    # Уведомить администратора (здесь можно добавить отправку сообщения админу)
    from config import ADMIN_ID
    user = update.effective_user
    try:
        plans = get_subscription_plans(active_only=False)
        plan = next((p for p in plans if p['id'] == plan_id), None)

        if plan and ADMIN_ID:
            admin_text = (
                f"🔔 НОВАЯ ЗАЯВКА НА ПОДПИСКУ\n\n"
                f"От: {user.first_name} (@{user.username or 'нет'})\n"
                f"ID: {user.id}\n"
                f"План: {plan['name']}\n"
                f"Сумма: {format_price(plan['price'])}\n\n"
                f"Проверьте оплату и активируйте подписку."
            )
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text
            )
    except Exception as e:
        logger.error(f"Ошибка уведомления админа о подписке: {e}")

    # Очистить данные
    context.user_data.pop('subscription_plan_id', None)
    context.user_data.pop('subscription_price', None)

    return ConversationHandler.END


async def subscription_claim_flower(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Забрать букет по подписке"""

    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    sub = get_user_active_subscription(user_id)

    if not sub:
        await query.answer("❌ У вас нет активной подписки", show_alert=True)
        return await subscriptions_menu(update, context)

    if sub['monthly_flowers_included'] == 0:
        await query.answer("❌ Ваша подписка не включает букеты", show_alert=True)
        return await subscriptions_menu(update, context)

    if sub['flowers_used_this_month'] >= sub['monthly_flowers_included']:
        await query.answer("❌ Вы уже использовали все букеты за этот месяц", show_alert=True)
        return await subscriptions_menu(update, context)

    # Перенаправить на оформление заказа цветов
    await query.edit_message_text(
        "🌹 БУКЕТ ПО ПОДПИСКЕ\n\n"
        "Для получения букета свяжитесь с администратором.\n"
        "Букет будет подготовлен в течение 1-2 часов.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("👌 Понятно", callback_data="subscriptions")
        ]])
    )


async def subscription_claim_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Использовать услугу по подписке"""

    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    sub = get_user_active_subscription(user_id)

    if not sub:
        await query.answer("❌ У вас нет активной подписки", show_alert=True)
        return await subscriptions_menu(update, context)

    if not sub['monthly_service_included']:
        await query.answer("❌ Ваша подписка не включает услуги", show_alert=True)
        return await subscriptions_menu(update, context)

    if sub['service_used_this_month']:
        await query.answer("❌ Вы уже использовали услугу за этот месяц", show_alert=True)
        return await subscriptions_menu(update, context)

    # Перенаправить на запись в салон
    await query.edit_message_text(
        "💅 УСЛУГА ПО ПОДПИСКЕ\n\n"
        "Для записи на услугу используйте раздел 'Записаться в салон'.\n"
        "При записи укажите, что у вас есть подписка.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 Записаться в салон", callback_data="salon_booking")],
            [InlineKeyboardButton("◀️ Назад", callback_data="subscriptions")]
        ])
    )
