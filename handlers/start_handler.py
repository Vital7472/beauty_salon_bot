"""
Обработчики базовых команд: /start, /menu, /help.
Регистрация пользователей и реферальная программа.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    add_user, get_user_by_referral_code, add_bonus_points, get_user,
    parse_utm_from_start_param, save_user_utm, update_utm_campaign_stats
)
from config import REFERRAL_BONUS

# Настройка логирования
logger = logging.getLogger(__name__)


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру главного меню.

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками меню
    """
    keyboard = [
        [InlineKeyboardButton("💇‍♀️ Записаться в салон", callback_data="salon_booking")],
        [InlineKeyboardButton("💐 Заказать цветы", callback_data="flowers_shop")],
        [InlineKeyboardButton("💎 Подписки и карты", callback_data="subscriptions")],
        [InlineKeyboardButton("🎁 Купить сертификат", callback_data="buy_certificate")],
        [InlineKeyboardButton("👤 Мой профиль", callback_data="profile")],
        [InlineKeyboardButton("📸 Наши работы", callback_data="gallery")],
        [InlineKeyboardButton("⭐ Оставить отзыв", callback_data="leave_review")],
        [InlineKeyboardButton("💬 Написать администратору", callback_data="contact_support")]
    ]

    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /start.
    Регистрация нового пользователя и обработка реферального кода.

    Args:
        update: Объект Update
        context: Контекст бота
    """
    try:
        user = update.effective_user
        user_id = user.id
        username = user.username
        first_name = user.first_name

        logger.info(f"Команда /start от пользователя {user_id} (@{username})")

        # Получить параметр из deep link
        start_param = context.args[0] if context.args and len(context.args) > 0 else None

        # Парсить UTM-метки из параметра
        utm_params = parse_utm_from_start_param(start_param)

        # Проверить реферальный код в аргументах
        referred_by = None
        if start_param:
            logger.info(f"Получен start параметр: {start_param}")

            # Если это реферальный код (формат REF...)
            if start_param.startswith('REF'):
                # Найти пользователя по реферальному коду
                referred_by = get_user_by_referral_code(start_param)

                if referred_by:
                    logger.info(f"Найден реферер: {referred_by}")
                else:
                    logger.warning(f"Реферальный код {start_param} не найден")

        # Попытаться зарегистрировать пользователя
        is_new_user = add_user(user_id, username, first_name, referred_by)

        # Если новый пользователь - сохранить UTM-метки и обновить статистику
        if is_new_user:
            try:
                # Сохранить UTM-метки пользователя
                save_user_utm(user_id, utm_params)
                logger.info(f"Сохранены UTM-метки для пользователя {user_id}: {utm_params['source_type']}")

                # Обновить статистику регистраций кампании
                if utm_params['source_type'] == 'utm' and start_param:
                    update_utm_campaign_stats(start_param, 'registration')
                    logger.info(f"Обновлена статистика регистраций для кампании: {start_param}")

            except Exception as e:
                logger.error(f"Ошибка сохранения UTM-меток: {e}")

        # Если новый пользователь и есть реферер
        if is_new_user and referred_by:
            try:
                # Начислить бонусы рефереру
                add_bonus_points(
                    referred_by,
                    REFERRAL_BONUS,
                    f"Реферальная программа: пригласил пользователя {first_name}"
                )

                # Начислить бонусы новому пользователю
                add_bonus_points(
                    user_id,
                    REFERRAL_BONUS,
                    "Регистрация по реферальной ссылке"
                )

                logger.info(f"Начислено {REFERRAL_BONUS} бонусов пользователю {user_id} и {referred_by}")

                # Отправить уведомление рефереру
                try:
                    referrer_data = get_user(referred_by)
                    if referrer_data:
                        await context.bot.send_message(
                            chat_id=referred_by,
                            text=f"🎉 Ваш друг {first_name} зарегистрировался по вашей ссылке!\n"
                                 f"+{REFERRAL_BONUS} бонусов на ваш счёт!"
                        )
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления рефереру: {e}")

            except Exception as e:
                logger.error(f"Ошибка начисления бонусов: {e}")

        # Приветственное сообщение
        welcome_text = (
            f"🌸 Добро пожаловать, {first_name}!\n\n"
            "Я помогу вам:\n"
            "• Записаться в салон красоты\n"
            "• Заказать букет с доставкой\n"
            "• Купить подарочный сертификат\n"
            "• И многое другое!\n\n"
            "Выберите действие:"
        )

        # Отправить сообщение с главным меню
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_main_menu_keyboard()
        )

        logger.info(f"Пользователь {user_id} получил приветствие")

    except Exception as e:
        logger.error(f"Ошибка в обработчике /start: {e}")
        await update.message.reply_text(
            "Произошла ошибка. Попробуйте позже или напишите администратору."
        )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /menu и возврата в главное меню.

    Args:
        update: Объект Update
        context: Контекст бота
    """
    try:
        menu_text = "🌸 Главное меню:"
        keyboard = get_main_menu_keyboard()

        # Если вызвано из callback query
        if update.callback_query:
            query = update.callback_query
            await query.answer()

            await query.edit_message_text(
                menu_text,
                reply_markup=keyboard
            )

            logger.info(f"Пользователь {update.effective_user.id} вернулся в главное меню (callback)")

        # Если вызвано из сообщения
        else:
            await update.message.reply_text(
                menu_text,
                reply_markup=keyboard
            )

            logger.info(f"Пользователь {update.effective_user.id} вызвал /menu")

    except Exception as e:
        logger.error(f"Ошибка в обработчике menu: {e}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /help.
    Справка по использованию бота.

    Args:
        update: Объект Update
        context: Контекст бота
    """
    try:
        help_text = (
            "📖 ПОМОЩЬ\n\n"
            "🔹 /start - Главное меню\n"
            "🔹 /menu - Вернуться в меню\n"
            "🔹 /help - Эта справка\n\n"
            "💇‍♀️ САЛОН КРАСОТЫ:\n"
            "Выберите услугу, дату и время.\n"
            "Администратор свяжется для уточнения.\n\n"
            "💐 ЦВЕТЫ:\n"
            "Выберите букет или закажите индивидуальный.\n"
            "Доставка БЕСПЛАТНО от 3000₽.\n\n"
            "🎁 БОНУСЫ:\n"
            "Получайте 5% бонусами от покупок.\n"
            "Оплачивайте до 50% бонусами.\n\n"
            "👥 РЕФЕРАЛЬНАЯ ПРОГРАММА:\n"
            "Пригласите друга - получите по 500 бонусов!\n\n"
            "❓ Вопросы? Напишите администратору!"
        )

        await update.message.reply_text(help_text)

        logger.info(f"Пользователь {update.effective_user.id} запросил справку")

    except Exception as e:
        logger.error(f"Ошибка в обработчике /help: {e}")


async def coming_soon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Временный обработчик для незавершенных функций.

    Args:
        update: Объект Update
        context: Контекст бота
    """
    query = update.callback_query
    await query.answer("Скоро будет реализовано! 🚧", show_alert=True)
    logger.info(f"Пользователь {update.effective_user.id} нажал на неготовую кнопку: {query.data}")
