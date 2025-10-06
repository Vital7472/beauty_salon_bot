"""
Utils package.
Вспомогательные функции и утилиты.
"""

from .helpers import (
    format_price,
    get_current_datetime,
    format_datetime,
    escape_markdown,
    send_to_admin_group,
    generate_order_number,
    calculate_delivery_cost,
    truncate_text
)
from .validators import (
    validate_phone,
    format_phone,
    validate_email,
    sanitize_text,
    validate_amount,
    format_certificate_code
)
from .calendar import (
    create_calendar,
    handle_calendar_navigation,
    parse_calendar_date,
    is_date_available
)

__all__ = [
    'format_price',
    'get_current_datetime',
    'format_datetime',
    'escape_markdown',
    'send_to_admin_group',
    'generate_order_number',
    'calculate_delivery_cost',
    'truncate_text',
    'validate_phone',
    'format_phone',
    'validate_email',
    'sanitize_text',
    'validate_amount',
    'format_certificate_code',
    'create_calendar',
    'handle_calendar_navigation',
    'parse_calendar_date',
    'is_date_available'
]
