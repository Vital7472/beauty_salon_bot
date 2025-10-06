"""
Вспомогательные функции для бота.
Форматирование, работа с датами, отправка сообщений.
"""

import logging
from datetime import datetime
from typing import Optional
import pytz

from config import TIMEZONE, FREE_DELIVERY_THRESHOLD, DELIVERY_COST, ADMIN_GROUP_ID

# Настройка логирования
logger = logging.getLogger(__name__)

# Словарь месяцев на русском
MONTHS = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}


def format_price(amount: int) -> str:
    """
    Форматирование цены с разделителями тысяч и знаком валюты.

    Args:
        amount: Сумма в рублях

    Returns:
        str: Отформатированная цена (например: "3 500 ₽")
    """
    return f"{amount:,} ₽".replace(',', ' ')


def get_current_datetime() -> datetime:
    """
    Получить текущие дату и время в часовом поясе Челябинска.

    Returns:
        datetime: Текущее время в UTC+5
    """
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz)


def format_datetime(dt_string: str) -> str:
    """
    Форматирование даты-времени для отображения пользователю.

    Args:
        dt_string: Строка даты в формате "YYYY-MM-DD HH:MM"

    Returns:
        str: Отформатированная дата (например: "15 октября 2024, 14:00")
    """
    try:
        # Парсинг строки даты
        dt = datetime.strptime(dt_string, "%Y-%m-%d %H:%M")

        # Форматирование
        day = dt.day
        month = MONTHS[dt.month]
        year = dt.year
        time = dt.strftime("%H:%M")

        return f"{day} {month} {year}, {time}"

    except Exception as e:
        logger.error(f"Ошибка форматирования даты '{dt_string}': {e}")
        return dt_string


def escape_markdown(text: str) -> str:
    """
    Экранирование специальных символов для Markdown.

    Args:
        text: Исходный текст

    Returns:
        str: Текст с экранированными спецсимволами
    """
    chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']

    for char in chars:
        text = text.replace(char, f'\\{char}')

    return text


async def get_or_create_user_topic(context, user_id: int, user_name: str):
    """
    Получить существующий топик пользователя или создать новый.

    Args:
        context: Контекст бота
        user_id: ID пользователя
        user_name: Имя пользователя

    Returns:
        dict: {'thread_id': int, 'is_new': bool} или None при ошибке
    """
    if not ADMIN_GROUP_ID:
        logger.error("ADMIN_GROUP_ID не установлен в config.py")
        return None

    # Проверить, есть ли уже топик для этого пользователя
    if 'user_topics' not in context.bot_data:
        context.bot_data['user_topics'] = {}

    user_topics = context.bot_data['user_topics']

    # Если топик уже существует
    if user_id in user_topics and isinstance(user_topics[user_id], dict):
        thread_id = user_topics[user_id].get('thread_id')
        if thread_id:
            logger.info(f"✅ Используется существующий топик {thread_id} для пользователя {user_id}")
            return {
                'thread_id': thread_id,
                'is_new': False
            }

    # Создать новый топик
    try:
        topic_name = f"❗ {user_name}"
        forum_topic = await context.bot.create_forum_topic(
            chat_id=ADMIN_GROUP_ID,
            name=topic_name[:128]
        )
        thread_id = forum_topic.message_thread_id

        # Сохранить топик
        from datetime import datetime
        user_topics[user_id] = {
            'thread_id': thread_id,
            'user_name': user_name,
            'created_at': datetime.now().isoformat(),
            'status': 'new',
            'responded': False
        }

        logger.info(f"✅ Создан новый топик '{topic_name}' с ID {thread_id} для пользователя {user_id}")

        return {
            'thread_id': thread_id,
            'is_new': True
        }

    except Exception as e:
        error_msg = str(e).lower()

        if "chat not found" in error_msg or "chat_not_found" in error_msg:
            logger.error(f"❌ Группа {ADMIN_GROUP_ID} не найдена. Проверьте ADMIN_GROUP_ID в .env")
        elif "not enough rights" in error_msg or "forbidden" in error_msg:
            logger.error(f"❌ Бот не имеет прав на создание топиков. Сделайте бота администратором группы с правами 'Manage Topics'")
        elif "method is available only for forum" in error_msg or "forum" in error_msg:
            logger.error(f"⚠️ Группа не является форумом. Включите 'Topics' в настройках группы")
        else:
            logger.error(f"❌ Ошибка создания топика: {e}")

        return None


async def send_to_user_topic(context, user_id: int, user_name: str, message: str, keyboard=None):
    """
    Отправить сообщение в топик пользователя (создать топик если не существует).

    Args:
        context: Контекст бота
        user_id: ID пользователя
        user_name: Имя пользователя
        message: Текст сообщения
        keyboard: Inline клавиатура (опционально)

    Returns:
        dict: {'message_id': int, 'thread_id': int, 'is_new_topic': bool} или None
    """
    if not ADMIN_GROUP_ID:
        logger.error("ADMIN_GROUP_ID не установлен в config.py")
        return None

    try:
        # Получить или создать топик для пользователя
        topic_result = await get_or_create_user_topic(context, user_id, user_name)

        if not topic_result:
            logger.error(f"❌ Не удалось получить/создать топик для пользователя {user_id}")
            return None

        thread_id = topic_result['thread_id']
        is_new_topic = topic_result['is_new']

        # Отправить сообщение в топик
        msg = await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            message_thread_id=thread_id,
            text=message,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

        logger.info(f"✉️ Сообщение отправлено в топик {thread_id} пользователя {user_id}")

        return {
            'message_id': msg.message_id,
            'thread_id': thread_id,
            'is_new_topic': is_new_topic
        }

    except Exception as e:
        logger.error(f"❌ Ошибка отправки сообщения в топик пользователя {user_id}: {e}")
        return None


async def send_to_admin_group(context, message: str, keyboard=None, topic_name: str = None):
    """
    Отправка сообщения в админ-группу с возможностью создания топика.

    Args:
        context: Контекст бота
        message: Текст сообщения
        keyboard: Inline клавиатура (опционально)
        topic_name: Название топика для создания (опционально)

    Returns:
        dict: {'message_id': int, 'thread_id': int} если топик создан,
        int: message_id если топик не создан,
        None: в случае ошибки
    """
    if not ADMIN_GROUP_ID:
        logger.error("ADMIN_GROUP_ID не установлен в config.py")
        return None

    try:
        message_thread_id = None

        # Если указано название топика - создаем новый топик
        if topic_name:
            try:
                # Создание топика (форум-темы) в группе
                forum_topic = await context.bot.create_forum_topic(
                    chat_id=ADMIN_GROUP_ID,
                    name=topic_name[:128]  # Максимум 128 символов для названия топика
                )
                message_thread_id = forum_topic.message_thread_id
                logger.info(f"✅ Создан топик '{topic_name}' с ID {message_thread_id}")
            except Exception as e:
                error_msg = str(e).lower()

                if "chat not found" in error_msg or "chat_not_found" in error_msg:
                    logger.error(f"❌ Группа {ADMIN_GROUP_ID} не найдена. Проверьте ADMIN_GROUP_ID в .env")
                elif "not enough rights" in error_msg or "forbidden" in error_msg:
                    logger.error(f"❌ Бот не имеет прав на создание топиков. Сделайте бота администратором группы с правами 'Manage Topics'")
                elif "method is available only for forum" in error_msg or "forum" in error_msg:
                    logger.error(f"⚠️ Группа не является форумом. Включите 'Topics' в настройках группы:")
                    logger.error(f"   1. Откройте группу в Telegram")
                    logger.error(f"   2. Нажмите на название группы")
                    logger.error(f"   3. Выберите 'Edit' → 'Group Type'")
                    logger.error(f"   4. Включите 'Topics' (форум)")
                    logger.error(f"   Отправка сообщения без топика...")
                else:
                    logger.warning(f"⚠️ Не удалось создать топик: {e}")
                    logger.warning(f"   Отправка сообщения в общий чат...")

        # Отправка сообщения в топик или в общий чат
        msg = await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            message_thread_id=message_thread_id,
            text=message,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

        logger.info(f"✉️ Сообщение отправлено в админ-группу: message_id={msg.message_id}, topic_id={message_thread_id}")

        # Вернуть dict если топик создан, иначе только message_id
        if message_thread_id:
            return {
                'message_id': msg.message_id,
                'thread_id': message_thread_id
            }
        else:
            return msg.message_id

    except Exception as e:
        logger.error(f"❌ Ошибка отправки сообщения в админ-группу: {e}")
        return None


async def close_admin_topic(context, message_thread_id: int) -> bool:
    """
    Закрытие топика в админ-группе.

    Args:
        context: Контекст бота
        message_thread_id: ID топика для закрытия

    Returns:
        bool: True если топик закрыт успешно, False в случае ошибки
    """
    if not ADMIN_GROUP_ID:
        logger.error("ADMIN_GROUP_ID не установлен в config.py")
        return False

    try:
        await context.bot.close_forum_topic(
            chat_id=ADMIN_GROUP_ID,
            message_thread_id=message_thread_id
        )
        logger.info(f"Топик {message_thread_id} закрыт")
        return True

    except Exception as e:
        logger.error(f"Ошибка закрытия топика {message_thread_id}: {e}")
        return False


def generate_order_number() -> str:
    """
    Генерация уникального номера заказа на основе timestamp.

    Returns:
        str: Номер заказа (например: "ORD1696512345")
    """
    timestamp = int(datetime.now().timestamp())
    return f"ORD{timestamp}"


def calculate_delivery_cost(total_amount: int) -> int:
    """
    Расчет стоимости доставки.

    Args:
        total_amount: Общая сумма заказа

    Returns:
        int: Стоимость доставки (0 если бесплатная)
    """
    if total_amount >= FREE_DELIVERY_THRESHOLD:
        return 0

    return DELIVERY_COST




def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Обрезать текст до максимальной длины с добавлением многоточия.

    Args:
        text: Исходный текст
        max_length: Максимальная длина

    Returns:
        str: Обрезанный текст
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - 3] + "..."
