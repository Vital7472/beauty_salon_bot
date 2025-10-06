"""
Модуль для создания inline календаря.
Генерация интерактивного календаря для выбора даты.
"""

import calendar
import logging
from datetime import datetime, timedelta
from typing import Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from utils.helpers import get_current_datetime

logger = logging.getLogger(__name__)

# Месяцы на русском
MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}

# Дни недели (сокращенно)
WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def create_calendar(year: int = None, month: int = None) -> InlineKeyboardMarkup:
    """
    Создание inline календаря для выбора даты.

    Args:
        year: Год (если не указан - текущий)
        month: Месяц (если не указан - текущий)

    Returns:
        InlineKeyboardMarkup: Клавиатура с календарем
    """
    try:
        # Получить текущую дату
        now = get_current_datetime()

        # Использовать переданные или текущие год/месяц
        if year is None:
            year = now.year
        if month is None:
            month = now.month

        # Создать календарь
        keyboard = []

        # Первая строка - название месяца и год
        keyboard.append([
            InlineKeyboardButton(
                f"📅 {MONTHS_RU[month]} {year}",
                callback_data="ignore"
            )
        ])

        # Вторая строка - дни недели
        weekday_row = [
            InlineKeyboardButton(day, callback_data="ignore")
            for day in WEEKDAYS_RU
        ]
        keyboard.append(weekday_row)

        # Получить календарь месяца
        month_calendar = calendar.monthcalendar(year, month)

        # Заполнить даты
        for week in month_calendar:
            row = []
            for day in week:
                if day == 0:
                    # Пустая ячейка
                    row.append(InlineKeyboardButton(" ", callback_data="ignore"))
                else:
                    # Создать дату
                    date = datetime(year, month, day)

                    # Проверить, не прошла ли дата
                    if date.date() < now.date():
                        # Прошедшая дата - неактивная
                        row.append(InlineKeyboardButton(
                            f"✖️{day}",
                            callback_data="ignore"
                        ))
                    else:
                        # Будущая дата - активная
                        callback_data = f"calendar_{year}-{month:02d}-{day:02d}"
                        row.append(InlineKeyboardButton(
                            str(day),
                            callback_data=callback_data
                        ))

            keyboard.append(row)

        # Кнопки навигации
        nav_row = [
            InlineKeyboardButton(
                "◀️ Пред",
                callback_data=f"calendar_prev_{year}_{month}"
            ),
            InlineKeyboardButton(
                "След ▶️",
                callback_data=f"calendar_next_{year}_{month}"
            )
        ]
        keyboard.append(nav_row)

        # Кнопка "Назад"
        keyboard.append([
            InlineKeyboardButton("🔙 Назад", callback_data="back_to_services")
        ])

        return InlineKeyboardMarkup(keyboard)

    except Exception as e:
        logger.error(f"Ошибка создания календаря: {e}")
        # Вернуть пустую клавиатуру с кнопкой назад
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад", callback_data="salon_booking")
        ]])


def handle_calendar_navigation(callback_data: str, current_year: int, current_month: int) -> Tuple[int, int]:
    """
    Обработка нажатий на кнопки навигации календаря.

    Args:
        callback_data: Данные callback
        current_year: Текущий год
        current_month: Текущий месяц

    Returns:
        tuple: (новый_год, новый_месяц)
    """
    try:
        if callback_data.startswith("calendar_prev"):
            # Месяц назад
            if current_month == 1:
                return current_year - 1, 12
            else:
                return current_year, current_month - 1

        elif callback_data.startswith("calendar_next"):
            # Месяц вперед
            if current_month == 12:
                return current_year + 1, 1
            else:
                return current_year, current_month + 1

        # Если не распознано - вернуть текущие
        return current_year, current_month

    except Exception as e:
        logger.error(f"Ошибка навигации календаря: {e}")
        return current_year, current_month


def parse_calendar_date(callback_data: str) -> str:
    """
    Извлечь дату из callback_data календаря.

    Args:
        callback_data: Данные вида "calendar_YYYY-MM-DD"

    Returns:
        str: Дата в формате YYYY-MM-DD
    """
    try:
        if callback_data.startswith("calendar_"):
            return callback_data.replace("calendar_", "")
        return None
    except Exception as e:
        logger.error(f"Ошибка парсинга даты: {e}")
        return None


def is_date_available(date_str: str) -> bool:
    """
    Проверить, доступна ли дата для записи.

    Args:
        date_str: Дата в формате YYYY-MM-DD

    Returns:
        bool: True если дата доступна
    """
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        now = get_current_datetime()

        # Дата должна быть в будущем
        return date.date() >= now.date()

    except Exception as e:
        logger.error(f"Ошибка проверки даты: {e}")
        return False
