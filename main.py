"""
Главный файл бота для салона красоты и цветочного магазина.
Точка входа, инициализация и запуск бота.
"""

import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    PicklePersistence,
    filters
)

# Импорт конфигурации
from config import (
    TELEGRAM_BOT_TOKEN,
    BOT_DATA_PATH,
    ADMIN_ID,
    ADMIN_GROUP_ID,
    # States для ConversationHandlers
    SALON_CATEGORY, SALON_SERVICE, SALON_DATE, SALON_TIME,
    SALON_PHONE, SALON_COMMENT, SALON_PAYMENT, SALON_CONFIRM,
    FLOWERS_CATEGORY, FLOWERS_ITEM, FLOWERS_CART, FLOWERS_DELIVERY_TYPE,
    FLOWERS_ADDRESS, FLOWERS_TIME, FLOWERS_ANONYMOUS, FLOWERS_CARD,
    FLOWERS_RECIPIENT, FLOWERS_PAYMENT, FLOWERS_CONFIRM,
    CUSTOM_ORDER_DESCRIPTION,
    CERT_AMOUNT, CERT_RECIPIENT, CERT_CONFIRM,
    REVIEW_RATING, REVIEW_TEXT,
    SUPPORT_MESSAGE, SUPPORT_CONVERSATION,
    ADMIN_BROADCAST_TEXT, ADMIN_BROADCAST_CONFIRM
)

# Импорт базы данных
from database import init_db

# Импорт обработчиков
from handlers import start, menu, help_command, coming_soon
from handlers.salon_handlers import (
    salon_start, salon_select_category, salon_select_service,
    salon_select_date, salon_select_time, salon_enter_phone,
    salon_contact_shared, salon_enter_comment, salon_skip_comment,
    salon_select_payment, salon_confirm_booking
)
from handlers.flowers_handlers import (
    flowers_start, flowers_select_category, flowers_view_item,
    flowers_add_to_cart, flowers_view_cart, flowers_update_quantity,
    flowers_remove_item, flowers_clear_cart, flowers_checkout,
    flowers_select_delivery_type, flowers_handle_address_selection,
    flowers_enter_new_address, flowers_handle_delivery_time,
    flowers_enter_delivery_time, flowers_handle_anonymous,
    flowers_handle_card_text, flowers_handle_recipient_data,
    flowers_handle_payment_selection, flowers_enter_bonus_amount,
    flowers_show_full_confirmation, flowers_create_full_order,
    flowers_confirm_order,
    custom_order_start, custom_order_process
)
from handlers.profile_handlers import (
    profile_view, profile_view_appointments, profile_view_orders,
    profile_view_addresses, profile_set_default_address, profile_delete_address,
    profile_view_bonuses, profile_view_referral,
    profile_edit_start, profile_edit_name, profile_edit_phone,
    profile_edit_birthday, profile_edit_cancel, EDIT_NAME, EDIT_PHONE, EDIT_BIRTHDAY
)
from handlers.certificate_handlers import (
    certificate_start, certificate_select_amount, certificate_enter_custom_amount,
    certificate_handle_recipient, certificate_enter_recipient_data,
    certificate_confirm_purchase
)
from handlers.gallery_handlers import gallery_view, gallery_show_category
from handlers.reviews_handlers import (
    review_start, review_select_rating, review_enter_text, review_skip_text
)
from handlers.support_handlers import support_start, support_send_message, handle_admin_reply
from handlers.admin_handlers import (
    admin_panel, admin_view_appointments, admin_view_orders,
    admin_view_reviews, admin_broadcast_start, admin_broadcast_enter_text,
    admin_broadcast_confirm
)
from handlers.subscription_handlers import (
    subscriptions_menu, subscription_view_plan, subscription_buy_confirm,
    subscription_payment_sent, subscription_claim_flower, subscription_claim_service,
    SUBSCRIPTION_CONFIRM
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def error_handler(update: Update, context):
    """
    Глобальный обработчик ошибок.

    Args:
        update: Объект Update
        context: Контекст бота
    """
    logger.error(f"Update {update} caused error: {context.error}", exc_info=context.error)

    # Попытаться уведомить пользователя
    try:
        if update and update.effective_user:
            error_message = (
                "Произошла ошибка при обработке вашего запроса. "
                "Попробуйте позже или обратитесь к администратору."
            )

            if update.message:
                await update.message.reply_text(error_message)
            elif update.callback_query:
                await update.callback_query.answer(error_message, show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения об ошибке: {e}")


def main():
    """
    Главная функция для инициализации и запуска бота.
    """
    try:
        logger.info("Инициализация бота...")

        # Инициализация базы данных
        init_db()
        logger.info("База данных инициализирована")

        # Создание Persistence
        persistence = PicklePersistence(filepath=BOT_DATA_PATH)

        # Создание Application
        application = Application.builder() \
            .token(TELEGRAM_BOT_TOKEN) \
            .persistence(persistence) \
            .build()

        # =================================================================
        # БАЗОВЫЕ КОМАНДЫ
        # =================================================================

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("menu", menu))
        application.add_handler(CommandHandler("help", help_command))

        # =================================================================
        # CONVERSATION HANDLERS
        # =================================================================

        # Запись в салон
        salon_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(salon_start, pattern='^salon_booking$')],
            states={
                SALON_CATEGORY: [
                    CallbackQueryHandler(salon_select_category, pattern='^salon_cat_')
                ],
                SALON_SERVICE: [
                    CallbackQueryHandler(salon_start, pattern='^salon_booking$'),  # Кнопка "Назад"
                    CallbackQueryHandler(salon_select_service, pattern='^salon_srv_')
                ],
                SALON_DATE: [
                    CallbackQueryHandler(salon_select_category, pattern='^back_to_services$'),  # Назад к услугам
                    CallbackQueryHandler(salon_select_date)
                ],
                SALON_TIME: [
                    CallbackQueryHandler(salon_select_date, pattern='^back_to_calendar$'),  # Назад к календарю
                    CallbackQueryHandler(salon_select_time)
                ],
                SALON_PHONE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, salon_enter_phone),
                    MessageHandler(filters.CONTACT, salon_contact_shared)
                ],
                SALON_COMMENT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, salon_enter_comment),
                    CallbackQueryHandler(salon_skip_comment, pattern='^skip_comment$')
                ],
                SALON_PAYMENT: [
                    CallbackQueryHandler(salon_select_payment, pattern='^payment_')
                ],
                SALON_CONFIRM: [
                    CallbackQueryHandler(salon_confirm_booking, pattern='^confirm_salon_booking$')
                ]
            },
            fallbacks=[
                CallbackQueryHandler(menu, pattern='^main_menu$'),
                CommandHandler('menu', menu)
            ],
            name='salon_booking',
            persistent=True
        )
        application.add_handler(salon_conv_handler)

        # Заказ цветов (полный)
        flowers_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(flowers_start, pattern='^flowers_shop$')],
            states={
                FLOWERS_CATEGORY: [
                    CallbackQueryHandler(flowers_select_category, pattern='^flowers_cat_'),
                    CallbackQueryHandler(flowers_view_cart, pattern='^view_cart$'),
                    CallbackQueryHandler(flowers_start, pattern='^flowers_shop$')
                ],
                FLOWERS_ITEM: [
                    CallbackQueryHandler(flowers_view_item, pattern='^view_flower_'),
                    CallbackQueryHandler(flowers_add_to_cart, pattern='^add_flower_'),
                    CallbackQueryHandler(flowers_view_cart, pattern='^view_cart$'),
                    CallbackQueryHandler(flowers_start, pattern='^flowers_shop$')
                ],
                FLOWERS_CART: [
                    CallbackQueryHandler(flowers_update_quantity, pattern='^qty_(increase|decrease)_'),
                    CallbackQueryHandler(flowers_remove_item, pattern='^remove_item_'),
                    CallbackQueryHandler(flowers_clear_cart, pattern='^clear_cart$'),
                    CallbackQueryHandler(flowers_checkout, pattern='^checkout$'),
                    CallbackQueryHandler(flowers_view_cart, pattern='^view_cart$'),
                    CallbackQueryHandler(flowers_start, pattern='^flowers_shop$')
                ],
                FLOWERS_DELIVERY_TYPE: [
                    CallbackQueryHandler(flowers_select_delivery_type, pattern='^delivery_')
                ],
                FLOWERS_ADDRESS: [
                    CallbackQueryHandler(flowers_handle_address_selection),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, flowers_enter_new_address)
                ],
                FLOWERS_TIME: [
                    CallbackQueryHandler(flowers_handle_delivery_time),
                    CallbackQueryHandler(flowers_enter_delivery_time),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, flowers_enter_delivery_time)
                ],
                FLOWERS_ANONYMOUS: [
                    CallbackQueryHandler(flowers_handle_anonymous, pattern='^anonymous_')
                ],
                FLOWERS_CARD: [
                    CallbackQueryHandler(flowers_handle_card_text, pattern='^skip_card$'),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, flowers_handle_card_text)
                ],
                FLOWERS_RECIPIENT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, flowers_handle_recipient_data)
                ],
                FLOWERS_PAYMENT: [
                    CallbackQueryHandler(flowers_handle_payment_selection, pattern='^payment_'),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, flowers_enter_bonus_amount)
                ],
                FLOWERS_CONFIRM: [
                    CallbackQueryHandler(flowers_create_full_order, pattern='^confirm_full_order$'),
                    CallbackQueryHandler(flowers_confirm_order, pattern='^confirm_flowers_order$'),
                    CallbackQueryHandler(flowers_show_full_confirmation, pattern='^show_confirmation$'),
                    CallbackQueryHandler(flowers_view_cart, pattern='^view_cart$')
                ]
            },
            fallbacks=[
                CallbackQueryHandler(menu, pattern='^main_menu$'),
                CommandHandler('menu', menu)
            ],
            name='flowers_shop',
            persistent=True
        )
        application.add_handler(flowers_conv_handler)

        # Индивидуальный заказ цветов
        custom_order_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(custom_order_start, pattern='^custom_flower_order$')],
            states={
                0: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_order_process)]
            },
            fallbacks=[
                CallbackQueryHandler(menu, pattern='^main_menu$'),
                CommandHandler('menu', menu)
            ],
            name='custom_flower_order',
            persistent=True
        )
        application.add_handler(custom_order_conv_handler)

        # Покупка сертификата
        certificate_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(certificate_start, pattern='^buy_certificate$')],
            states={
                CERT_AMOUNT: [
                    CallbackQueryHandler(certificate_select_amount, pattern='^cert_amt_'),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, certificate_enter_custom_amount)
                ],
                CERT_RECIPIENT: [
                    CallbackQueryHandler(certificate_handle_recipient),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, certificate_enter_recipient_data)
                ],
                CERT_CONFIRM: [
                    CallbackQueryHandler(certificate_confirm_purchase, pattern='^confirm_certificate$')
                ]
            },
            fallbacks=[
                CallbackQueryHandler(menu, pattern='^main_menu$'),
                CommandHandler('menu', menu)
            ],
            name='buy_certificate',
            persistent=True
        )
        application.add_handler(certificate_conv_handler)

        # Подписки
        subscription_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(subscription_buy_confirm, pattern='^subscription_buy_')],
            states={
                SUBSCRIPTION_CONFIRM: [
                    CallbackQueryHandler(subscription_payment_sent, pattern='^subscription_paid_')
                ]
            },
            fallbacks=[
                CallbackQueryHandler(subscriptions_menu, pattern='^subscriptions$'),
                CallbackQueryHandler(menu, pattern='^main_menu$')
            ],
            name='subscription_purchase',
            persistent=True
        )
        application.add_handler(subscription_conv_handler)

        # Отзывы
        review_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(review_start, pattern='^leave_review$')],
            states={
                REVIEW_RATING: [
                    CallbackQueryHandler(review_select_rating, pattern='^rating_')
                ],
                REVIEW_TEXT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, review_enter_text),
                    CallbackQueryHandler(review_skip_text, pattern='^skip_review_text$')
                ]
            },
            fallbacks=[
                CallbackQueryHandler(menu, pattern='^main_menu$'),
                CommandHandler('menu', menu)
            ],
            name='leave_review',
            persistent=True
        )
        application.add_handler(review_conv_handler)

        # Чат с поддержкой
        support_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(support_start, pattern='^contact_support$')],
            states={
                SUPPORT_MESSAGE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, support_send_message)
                ]
            },
            fallbacks=[
                CallbackQueryHandler(menu, pattern='^main_menu$'),
                CommandHandler('menu', menu)
            ],
            name='contact_support',
            persistent=True
        )
        application.add_handler(support_conv_handler)

        # Админ рассылка
        broadcast_conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("broadcast", admin_broadcast_start),
                CallbackQueryHandler(admin_broadcast_start, pattern='^admin_broadcast$')
            ],
            states={
                ADMIN_BROADCAST_TEXT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_enter_text)
                ],
                ADMIN_BROADCAST_CONFIRM: [
                    CallbackQueryHandler(admin_broadcast_confirm, pattern='^confirm_broadcast$')
                ]
            },
            fallbacks=[
                CallbackQueryHandler(menu, pattern='^main_menu$'),
                CallbackQueryHandler(admin_panel, pattern='^admin_panel$'),
                CommandHandler("cancel", menu)
            ],
            name='admin_broadcast',
            persistent=True
        )
        application.add_handler(broadcast_conv_handler)

        # =================================================================
        # CALLBACK HANDLERS
        # =================================================================

        # Профиль пользователя - редактирование (ConversationHandler)
        profile_edit_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(profile_edit_start, pattern='^profile_edit$')],
            states={
                EDIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_edit_name)],
                EDIT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_edit_phone)],
                EDIT_BIRTHDAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_edit_birthday)],
            },
            fallbacks=[
                CallbackQueryHandler(profile_edit_cancel, pattern='^profile_edit_cancel$')
            ],
            allow_reentry=True
        )
        application.add_handler(profile_edit_conv_handler)

        # Профиль пользователя - просмотр
        application.add_handler(CallbackQueryHandler(profile_view, pattern='^profile$'))
        application.add_handler(CallbackQueryHandler(profile_view_appointments, pattern='^profile_appointments$'))
        application.add_handler(CallbackQueryHandler(profile_view_orders, pattern='^profile_orders$'))
        application.add_handler(CallbackQueryHandler(profile_view_addresses, pattern='^profile_addresses$'))
        application.add_handler(CallbackQueryHandler(profile_set_default_address, pattern='^set_default_addr_'))
        application.add_handler(CallbackQueryHandler(profile_delete_address, pattern='^delete_addr_'))
        application.add_handler(CallbackQueryHandler(profile_view_bonuses, pattern='^profile_bonuses$'))
        application.add_handler(CallbackQueryHandler(profile_view_referral, pattern='^profile_referral$'))

        # Подписки
        application.add_handler(CallbackQueryHandler(subscriptions_menu, pattern='^subscriptions$'))
        application.add_handler(CallbackQueryHandler(subscription_view_plan, pattern='^subscription_view_'))
        application.add_handler(CallbackQueryHandler(subscription_claim_flower, pattern='^subscription_claim_flower$'))
        application.add_handler(CallbackQueryHandler(subscription_claim_service, pattern='^subscription_claim_service$'))

        # Галерея работ
        application.add_handler(CallbackQueryHandler(gallery_view, pattern='^gallery$'))
        application.add_handler(CallbackQueryHandler(gallery_show_category, pattern='^gallery_(salon|flowers|all)$'))

        # Админ-панель
        application.add_handler(CommandHandler("admin", admin_panel))
        application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
        application.add_handler(CallbackQueryHandler(admin_view_appointments, pattern='^admin_appointments$'))
        application.add_handler(CallbackQueryHandler(admin_view_orders, pattern='^admin_orders$'))
        application.add_handler(CallbackQueryHandler(admin_view_reviews, pattern='^admin_reviews$'))

        # Возврат в главное меню
        application.add_handler(CallbackQueryHandler(menu, pattern='^main_menu$'))

        # TODO: Подтверждение и отмена записи
        application.add_handler(CallbackQueryHandler(coming_soon, pattern='^confirm_appointment_'))
        application.add_handler(CallbackQueryHandler(coming_soon, pattern='^cancel_appointment_'))

        # =================================================================
        # ОБРАБОТЧИК ОТВЕТОВ АДМИНИСТРАТОРА
        # =================================================================

        # Обработчик сообщений из админ-группы (для поддержки)
        if ADMIN_GROUP_ID:
            application.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.Chat(chat_id=ADMIN_GROUP_ID),
                handle_admin_reply
            ))

        # =================================================================
        # ОБРАБОТЧИК ОШИБОК
        # =================================================================

        application.add_error_handler(error_handler)

        # =================================================================
        # ЗАПУСК БОТА
        # =================================================================

        # TODO: Запуск планировщика уведомлений (APScheduler)
        # from utils.notifications import start_scheduler
        # start_scheduler(application)

        logger.info("🚀 Бот запущен!")
        logger.info(f"ID администратора: {ADMIN_ID}")

        # Запуск polling
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
