"""
Планировщик автоматических запросов отзывов.
Отправляет запросы на отзывы клиентам через заданное время после заказа.
"""

import asyncio
import logging
from datetime import datetime
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton

from config import TELEGRAM_BOT_TOKEN
from database import (
    get_pending_feedback_requests, mark_feedback_request_sent,
    get_feedback_settings
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def send_feedback_requests():
    """
    Отправить запросы на отзывы всем пользователям, у которых подошло время.
    """
    try:
        settings = get_feedback_settings()

        if not settings['enabled']:
            logger.info("Система запросов отзывов отключена")
            return

        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        pending_requests = get_pending_feedback_requests()

        if not pending_requests:
            logger.info("Нет запланированных запросов отзывов на сегодня")
            return

        logger.info(f"Найдено {len(pending_requests)} запросов на отправку")

        for request in pending_requests:
            try:
                user_id = request['user_id']
                order_type = request['order_type']
                order_id = request['order_id']
                user_name = request['user_name']

                # Формируем текст сообщения
                if order_type == 'appointment':
                    message_text = (
                        f"Здравствуйте, {user_name}! 👋\n\n"
                        f"Как вам понравилась услуга в нашем салоне?\n\n"
                        f"{settings['message_template']}\n\n"
                        f"Ваше мнение очень важно для нас! 💖"
                    )
                else:  # flower_order
                    message_text = (
                        f"Здравствуйте, {user_name}! 👋\n\n"
                        f"Как вам понравились наши цветы?\n\n"
                        f"{settings['message_template']}\n\n"
                        f"Ваше мнение очень важно для нас! 💖"
                    )

                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✍️ Оставить отзыв", callback_data="write_review")],
                    [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
                ])

                # Отправляем сообщение
                await bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    reply_markup=keyboard
                )

                # Отмечаем как отправленный
                mark_feedback_request_sent(request['id'])

                logger.info(f"Запрос отзыва отправлен пользователю {user_id} (заказ {order_type}:{order_id})")

                # Небольшая задержка между отправками
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Ошибка отправки запроса отзыва {request['id']}: {e}")
                continue

        logger.info(f"Обработано {len(pending_requests)} запросов отзывов")

    except Exception as e:
        logger.error(f"Ошибка в send_feedback_requests: {e}")


async def run_scheduler():
    """
    Запустить планировщик (проверка каждый час).
    """
    logger.info("Планировщик запросов отзывов запущен")

    while True:
        try:
            current_hour = datetime.now().hour

            # Отправляем запросы в 10:00 каждый день
            if current_hour == 10:
                await send_feedback_requests()
                # Ждем час, чтобы не отправить повторно
                await asyncio.sleep(3600)
            else:
                # Проверяем каждый час
                await asyncio.sleep(3600)

        except Exception as e:
            logger.error(f"Ошибка в run_scheduler: {e}")
            await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(run_scheduler())
