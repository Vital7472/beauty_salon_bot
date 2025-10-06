"""
Handlers package.
Обработчики команд и взаимодействий бота.
"""

from .start_handler import start, menu, help_command, coming_soon
from .salon_handlers import (
    salon_start, salon_select_category, salon_select_service,
    salon_select_date, salon_select_time, salon_enter_phone,
    salon_contact_shared, salon_enter_comment, salon_skip_comment,
    salon_select_payment, salon_confirm_booking
)
from .flowers_handlers import (
    flowers_start, flowers_select_category, flowers_view_item,
    flowers_add_to_cart, flowers_view_cart, flowers_update_quantity,
    flowers_remove_item, flowers_clear_cart, flowers_checkout,
    flowers_select_delivery_type, flowers_handle_address_selection,
    flowers_enter_new_address, flowers_handle_delivery_time,
    flowers_enter_delivery_time, flowers_handle_anonymous,
    flowers_handle_card_text, flowers_handle_recipient_data,
    flowers_handle_payment_selection, flowers_enter_bonus_amount,
    flowers_show_full_confirmation, flowers_create_full_order,
    custom_order_start, custom_order_process
)
from .profile_handlers import (
    profile_view, profile_view_appointments, profile_view_orders,
    profile_view_addresses, profile_set_default_address, profile_delete_address,
    profile_view_bonuses, profile_view_referral
)
from .certificate_handlers import (
    certificate_start, certificate_select_amount, certificate_enter_custom_amount,
    certificate_handle_recipient, certificate_enter_recipient_data,
    certificate_confirm_purchase
)
from .gallery_handlers import gallery_view, gallery_show_category
from .reviews_handlers import (
    review_start, review_select_rating, review_enter_text, review_skip_text
)
from .support_handlers import support_start, support_send_message
from .admin_handlers import (
    admin_panel, admin_view_appointments, admin_view_orders,
    admin_view_reviews, admin_broadcast_start, admin_broadcast_enter_text,
    admin_broadcast_confirm
)

__all__ = [
    'start', 'menu', 'help_command', 'coming_soon',
    'salon_start', 'salon_select_category', 'salon_select_service',
    'salon_select_date', 'salon_select_time', 'salon_enter_phone',
    'salon_contact_shared', 'salon_enter_comment', 'salon_skip_comment',
    'salon_select_payment', 'salon_confirm_booking',
    'flowers_start', 'flowers_select_category', 'flowers_view_item',
    'flowers_add_to_cart', 'flowers_view_cart', 'flowers_update_quantity',
    'flowers_remove_item', 'flowers_clear_cart', 'flowers_checkout',
    'flowers_select_delivery_type', 'flowers_handle_address_selection',
    'flowers_enter_new_address', 'flowers_handle_delivery_time',
    'flowers_enter_delivery_time', 'flowers_handle_anonymous',
    'flowers_handle_card_text', 'flowers_handle_recipient_data',
    'flowers_handle_payment_selection', 'flowers_enter_bonus_amount',
    'flowers_show_full_confirmation', 'flowers_create_full_order',
    'custom_order_start', 'custom_order_process',
    'profile_view', 'profile_view_appointments', 'profile_view_orders',
    'profile_view_addresses', 'profile_set_default_address', 'profile_delete_address',
    'profile_view_bonuses', 'profile_view_referral',
    'certificate_start', 'certificate_select_amount', 'certificate_enter_custom_amount',
    'certificate_handle_recipient', 'certificate_enter_recipient_data',
    'certificate_confirm_purchase',
    'gallery_view', 'gallery_show_category',
    'review_start', 'review_select_rating', 'review_enter_text', 'review_skip_text',
    'support_start', 'support_send_message',
    'admin_panel', 'admin_view_appointments', 'admin_view_orders',
    'admin_view_reviews', 'admin_broadcast_start', 'admin_broadcast_enter_text',
    'admin_broadcast_confirm'
]
