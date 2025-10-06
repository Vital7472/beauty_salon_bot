"""
Обработчики отзывов.
Оставление отзывов с рейтингом и текстом.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import REVIEW_RATING, REVIEW_TEXT, REVIEW_LINKS
from database import add_review
from utils.helpers import send_to_user_topic

logger = logging.getLogger(__name__)


async def review_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало оставления отзыва"""

    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    keyboard = [
        [
            InlineKeyboardButton("⭐", callback_data="rating_1"),
            InlineKeyboardButton("⭐⭐", callback_data="rating_2"),
            InlineKeyboardButton("⭐⭐⭐", callback_data="rating_3")
        ],
        [
            InlineKeyboardButton("⭐⭐⭐⭐", callback_data="rating_4"),
            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="rating_5")
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
    ]

    await query.edit_message_text(
        "⭐ ОСТАВИТЬ ОТЗЫВ\n\nОцените нашу работу:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return REVIEW_RATING


async def review_select_rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора рейтинга"""

    query = update.callback_query
    await query.answer()

    rating = int(query.data.replace("rating_", ""))
    context.user_data['review_rating'] = rating

    keyboard = [[InlineKeyboardButton("Пропустить", callback_data="skip_review_text")]]

    await query.edit_message_text(
        "✍️ Расскажите подробнее о вашем опыте (необязательно):\n\n"
        "Что вам понравилось? Что можно улучшить?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return REVIEW_TEXT


async def review_enter_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение текста отзыва"""

    text = update.message.text.strip()
    context.user_data['review_text'] = text

    return await review_submit(update, context)


async def review_skip_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск текста отзыва"""

    query = update.callback_query
    await query.answer()

    context.user_data['review_text'] = ""

    return await review_submit(update, context)


async def review_submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отправка отзыва"""

    user = update.effective_user
    rating = context.user_data.get('review_rating')
    text = context.user_data.get('review_text', '')

    try:
        # Сохранить в БД
        add_review(user.id, user.first_name, rating, text)

        # Если 4-5 звезд - предложить оставить на площадках
        if rating >= 4:
            response_text = (
                "🙏 Спасибо за ваш отзыв!\n\n"
                "⭐ Рады, что вам понравилось!\n\n"
                "Будем благодарны, если вы оставите отзыв на площадках:"
            )

            keyboard = []
            if REVIEW_LINKS.get('yandex'):
                keyboard.append([InlineKeyboardButton("📝 Яндекс.Карты", url=REVIEW_LINKS['yandex'])])
            if REVIEW_LINKS.get('2gis'):
                keyboard.append([InlineKeyboardButton("📝 2ГИС", url=REVIEW_LINKS['2gis'])])
            if REVIEW_LINKS.get('google'):
                keyboard.append([InlineKeyboardButton("📝 Google Maps", url=REVIEW_LINKS['google'])])

            keyboard.append([InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")])

            # Уведомить админа (положительный отзыв)
            admin_text = (
                "✅ <b>ПОЛОЖИТЕЛЬНЫЙ ОТЗЫВ</b>\n\n"
                f"От: {user.first_name}"
            )
            if user.username:
                admin_text += f" (@{user.username})"
            admin_text += f"\nРейтинг: {'⭐' * rating}\n"
            if text:
                admin_text += f"Текст: {text}"

            # Отправить положительный отзыв в топик пользователя
            await send_to_user_topic(context, user.id, user.first_name, admin_text, None)

        else:
            # 1-3 звезды - негативный отзыв
            response_text = (
                "😔 Нам очень жаль, что вы остались недовольны\n\n"
                "Администратор свяжется с вами в ближайшее время "
                "для решения ситуации.\n\n"
                "Спасибо, что помогаете нам стать лучше!"
            )

            keyboard = [[InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]]

            # Уведомить админа (негативный отзыв)
            from database import get_user
            user_data = get_user(user.id)
            phone = user_data[3] if user_data and user_data[3] else "Не указан"

            admin_text = (
                "⚠️ <b>НЕГАТИВНЫЙ ОТЗЫВ</b>\n\n"
                f"От: {user.first_name}"
            )
            if user.username:
                admin_text += f" (@{user.username})"
            admin_text += (
                f"\nТелефон: {phone}\n"
                f"Рейтинг: {'⭐' * rating}\n"
            )
            if text:
                admin_text += f"Текст: {text}\n"
            admin_text += "\n⚠️ Требуется связаться с клиентом!"

            # Отправить негативный отзыв в топик пользователя (приоритетный)
            await send_to_user_topic(context, user.id, user.first_name, admin_text, None)

        if update.message:
            await update.message.reply_text(
                response_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        else:
            await update.callback_query.edit_message_text(
                response_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )

        context.user_data.clear()
        logger.info(f"Отзыв от пользователя {user.id}, рейтинг {rating}")

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка сохранения отзыва: {e}")
        text = "❌ Произошла ошибка. Попробуйте позже."
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В меню", callback_data="main_menu")]])

        if update.message:
            await update.message.reply_text(text, reply_markup=keyboard)
        else:
            await update.callback_query.edit_message_text(text, reply_markup=keyboard)

        return ConversationHandler.END
