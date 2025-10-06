"""
Модуль валидации данных.
Проверка и форматирование телефонов, email и других данных.
"""

import re
import logging

logger = logging.getLogger(__name__)


def validate_phone(phone: str) -> bool:
    """
    Валидация номера телефона.

    Args:
        phone: Номер телефона для проверки

    Returns:
        bool: True если телефон валиден
    """
    # Паттерн для российских номеров
    # Форматы: +79991234567, 89991234567, +7 999 123 45 67, +7 (999) 123-45-67
    pattern = r'^\+?[78][\s\-]?\(?[0-9]{3}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$'

    return re.match(pattern, phone) is not None


def format_phone(phone: str) -> str:
    """
    Форматирование телефона в стандартный вид: +7 (XXX) XXX-XX-XX

    Args:
        phone: Номер телефона (любой формат)

    Returns:
        str: Отформатированный номер телефона
    """
    try:
        # Убрать все кроме цифр
        digits = re.sub(r'\D', '', phone)

        # Если начинается с 8, заменить на 7
        if digits.startswith('8'):
            digits = '7' + digits[1:]

        # Если начинается не с 7, добавить 7
        if not digits.startswith('7'):
            digits = '7' + digits

        # Форматировать
        if len(digits) == 11:
            return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"

        # Если не удалось отформатировать, вернуть как есть
        logger.warning(f"Не удалось отформатировать телефон: {phone}")
        return phone

    except Exception as e:
        logger.error(f"Ошибка форматирования телефона: {e}")
        return phone


def validate_email(email: str) -> bool:
    """
    Валидация email адреса.

    Args:
        email: Email для проверки

    Returns:
        bool: True если email валиден
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def sanitize_text(text: str, max_length: int = 500) -> str:
    """
    Очистка текста от потенциально опасных символов.

    Args:
        text: Исходный текст
        max_length: Максимальная длина

    Returns:
        str: Очищенный текст
    """
    # Обрезать до максимальной длины
    text = text[:max_length]

    # Убрать HTML теги
    text = re.sub(r'<[^>]+>', '', text)

    # Убрать множественные пробелы
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def validate_amount(amount: str) -> bool:
    """
    Валидация суммы (только числа).

    Args:
        amount: Сумма для проверки

    Returns:
        bool: True если сумма валидна
    """
    try:
        value = int(amount)
        return value > 0
    except ValueError:
        return False


def format_certificate_code(code: str) -> str:
    """
    Форматирование кода сертификата: CERT-XXXX-XXXX

    Args:
        code: Код сертификата

    Returns:
        str: Отформатированный код
    """
    # Убрать все кроме букв и цифр
    clean_code = re.sub(r'[^A-Z0-9]', '', code.upper())

    # Форматировать
    if len(clean_code) >= 8:
        return f"CERT-{clean_code[:4]}-{clean_code[4:8]}"

    return code
