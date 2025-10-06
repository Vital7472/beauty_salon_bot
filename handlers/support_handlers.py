"""
Обработчики чата с поддержкой.
Создание топиков в админ-группе для общения с клиентами.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import SUPPORT_MESSAGE, SUPPORT_CONVERSATION, ADMIN_GROUP_ID

logger = logging.getLogger(__name__)


async def send_reminder_if_not_responded(context: ContextTypes.DEFAULT_TYPE):
    """
    Отправка напоминания в топик если на обращение не ответили в течение 3 минут.
    """
    job = context.job
    data = job.data

    user_id = data['user_id']
    thread_id = data['thread_id']
    user_name = data['user_name']

    # Проверить, ответили ли уже на обращение
    user_topics = context.bot_data.get('user_topics', {})
    topic_data = user_topics.get(user_id)

    if not topic_data or not isinstance(topic_data, dict):
        return

    # Если уже ответили - не отправлять напоминание
    if topic_data.get('responded'):
        logger.info(f"⏰ Напоминание отменено - уже ответили пользователю {user_id}")
        return

    try:
        # Отправить напоминание в топик
        reminder_text = (
            "⚠️ <b>НАПОМИНАНИЕ</b>\n\n"
            f"Обращение от пользователя <b>{user_name}</b> ожидает ответа уже 3 минуты!\n\n"
            "Пожалуйста, ответьте клиенту как можно скорее."
        )

        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            message_thread_id=thread_id,
            text=reminder_text,
            parse_mode='HTML'
        )

        logger.info(f"⚠️ Отправлено напоминание в топик {thread_id} для пользователя {user_id}")

    except Exception as e:
        logger.error(f"Ошибка отправки напоминания: {e}")


async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка ответа администратора из топика в админ-группе.
    Пересылает сообщение пользователю.
    """
    # Проверить, что сообщение из админ-группы
    if not update.message or update.message.chat.id != ADMIN_GROUP_ID:
        return

    # Проверить, что это сообщение в топике
    if not update.message.message_thread_id:
        return

    try:
        # Найти пользователя по топику
        user_topics = context.bot_data.get('user_topics', {})

        # Найти user_id по message_thread_id
        user_id = None
        for uid, topic_data in user_topics.items():
            if isinstance(topic_data, dict):
                if topic_data.get('thread_id') == update.message.message_thread_id:
                    user_id = uid
                    break

        if not user_id:
            logger.warning(f"Не найден пользователь для топика {update.message.message_thread_id}")
            return

        # Если это первый ответ - переименовать топик и обновить статус
        topic_data = user_topics.get(user_id)
        if isinstance(topic_data, dict) and not topic_data.get('responded'):
            try:
                # Переименовать топик в "✅ Имя"
                new_topic_name = f"✅ {topic_data.get('user_name', 'Клиент')}"
                await context.bot.edit_forum_topic(
                    chat_id=ADMIN_GROUP_ID,
                    message_thread_id=update.message.message_thread_id,
                    name=new_topic_name
                )

                # Обновить статус
                topic_data['responded'] = True
                topic_data['status'] = 'in_progress'
                user_topics[user_id] = topic_data

                logger.info(f"✅ Топик переименован в '{new_topic_name}'")
            except Exception as e:
                logger.error(f"Ошибка переименования топика: {e}")

        # Переслать сообщение пользователю
        admin_text = update.message.text or update.message.caption or ""

        if admin_text:
            message_text = f"💬 <b>Ответ от поддержки:</b>\n\n{admin_text}"

            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode='HTML'
            )

            logger.info(f"✅ Ответ от админа переслан пользователю {user_id}")

        # Если есть фото, переслать его
        if update.message.photo:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=update.message.photo[-1].file_id,
                caption=f"💬 <b>Ответ от поддержки:</b>\n\n{admin_text}" if admin_text else "💬 Ответ от поддержки",
                parse_mode='HTML'
            )
            logger.info(f"✅ Фото от админа переслано пользователю {user_id}")

    except Exception as e:
        logger.error(f"Ошибка обработки ответа администратора: {e}")


async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало обращения в поддержку"""

    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "💬 ЧАТ С ПОДДЕРЖКОЙ\n\n"
        "Напишите ваш вопрос, и администратор ответит в ближайшее время.\n\n"
        "Среднее время ответа: 15 минут\n\n"
        "Вы можете:\n"
        "• Задать вопрос о товарах/услугах\n"
        "• Уточнить детали заказа\n"
        "• Получить консультацию\n\n"
        "Напишите сообщение:"
    )

    return SUPPORT_MESSAGE


async def support_send_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отправка сообщения в поддержку"""

    user = update.effective_user
    message = update.message.text

    try:
        # Отправить в топик пользователя в админ-группе
        if ADMIN_GROUP_ID:
            from database import get_user
            from utils.helpers import send_to_user_topic

            user_data = get_user(user.id)
            phone = user_data[3] if user_data and user_data[3] else "Не указан"

            topic_text = (
                "💬 <b>ОБРАЩЕНИЕ В ПОДДЕРЖКУ</b>\n\n"
                f"👤 От: {user.first_name}"
            )

            if user.username:
                topic_text += f" (@{user.username})"

            topic_text += (
                f"\n📞 Телефон: {phone}\n"
                f"🆔 User ID: {user.id}\n\n"
                f"Сообщение:\n{message}"
            )

            # Отправить в топик пользователя (создать если не существует)
            result = await send_to_user_topic(
                context,
                user.id,
                user.first_name,
                topic_text,
                None
            )

            # Если это новый топик - запланировать напоминание
            if result and result.get('is_new_topic'):
                # Запланировать напоминание через 3 минуты
                context.job_queue.run_once(
                    send_reminder_if_not_responded,
                    when=180,  # 3 минуты = 180 секунд
                    data={
                        'user_id': user.id,
                        'thread_id': result['thread_id'],
                        'user_name': user.first_name
                    },
                    name=f"reminder_{user.id}"
                )
                logger.info(f"⏰ Запланировано напоминание через 3 минуты для user_id={user.id}")

        await update.message.reply_text(
            "✅ Сообщение отправлено!\n\n"
            "Администратор ответит в ближайшее время.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")
            ]])
        )

        logger.info(f"Обращение в поддержку от {user.id}")

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка отправки в поддержку: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 В меню", callback_data="main_menu")
            ]])
        )
        return ConversationHandler.END
