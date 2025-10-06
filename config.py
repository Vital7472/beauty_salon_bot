"""
Конфигурация бота для салона красоты и цветочного магазина.
"""

import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env
load_dotenv()

# =================================================================
# ТОКЕНЫ И КЛЮЧИ
# =================================================================

# Получение переменных из .env с проверкой
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    raise ValueError(
        "❌ TELEGRAM_BOT_TOKEN не установлен!\n"
        "Создайте файл .env и добавьте: TELEGRAM_BOT_TOKEN=ваш_токен\n"
        "Получить токен: https://t.me/BotFather"
    )

ADMIN_ID = os.getenv('ADMIN_ID')
if not ADMIN_ID:
    raise ValueError(
        "❌ ADMIN_ID не установлен!\n"
        "Создайте файл .env и добавьте: ADMIN_ID=ваш_telegram_id\n"
        "Узнать свой ID: https://t.me/userinfobot"
    )
try:
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    raise ValueError(f"❌ ADMIN_ID должен быть числом, получено: {ADMIN_ID}")

GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
if not GOOGLE_SHEET_ID:
    raise ValueError(
        "❌ GOOGLE_SHEET_ID не установлен!\n"
        "Создайте файл .env и добавьте: GOOGLE_SHEET_ID=id_вашей_таблицы"
    )

# ADMIN_GROUP_ID опциональный, можно не указывать
ADMIN_GROUP_ID = os.getenv('ADMIN_GROUP_ID')
if ADMIN_GROUP_ID:
    try:
        ADMIN_GROUP_ID = int(ADMIN_GROUP_ID)
    except ValueError:
        raise ValueError(f"❌ ADMIN_GROUP_ID должен быть числом, получено: {ADMIN_GROUP_ID}")

# =================================================================
# ОСНОВНЫЕ НАСТРОЙКИ
# =================================================================

TIMEZONE = "Asia/Yekaterinburg"  # UTC+5
CITY = "Челябинск"
CURRENCY = "₽"

# =================================================================
# РАБОЧЕЕ ВРЕМЯ САЛОНА
# =================================================================

SALON_WORK_HOURS = {
    "start": 9,           # Начало работы (часы)
    "end": 21,            # Конец работы (часы)
    "interval_minutes": 60  # Интервал записи (минуты)
}

# =================================================================
# ДОСТАВКА ЦВЕТОВ
# =================================================================

FREE_DELIVERY_THRESHOLD = 3000  # Бесплатная доставка от 3000₽
DELIVERY_COST = 300             # Стоимость доставки

# =================================================================
# СИСТЕМА БОНУСОВ
# =================================================================

BONUS_PERCENT = 5                # 5% от суммы заказа
BONUS_THRESHOLD = 3000           # Минимальная сумма для начисления бонусов
MAX_BONUS_PAYMENT_PERCENT = 50   # Максимум 50% оплаты бонусами
REFERRAL_BONUS = 500            # Бонусы за реферальную программу

# =================================================================
# ССЫЛКИ НА ОТЗЫВЫ
# =================================================================

REVIEW_LINKS = {
    "yandex": "https://yandex.ru/maps/org/example",
    "2gis": "https://2gis.ru/example",
    "google": "https://maps.google.com/example"
}

# =================================================================
# СОСТОЯНИЯ ДЛЯ CONVERSATION HANDLERS
# =================================================================

# Салон красоты
SALON_CATEGORY = 1
SALON_SERVICE = 2
SALON_DATE = 3
SALON_TIME = 4
SALON_PHONE = 5
SALON_COMMENT = 6
SALON_PAYMENT = 7
SALON_CONFIRM = 8

# Цветочный магазин
FLOWERS_CATEGORY = 10
FLOWERS_ITEM = 11
FLOWERS_CART = 12
FLOWERS_DELIVERY_TYPE = 13
FLOWERS_ADDRESS = 14
FLOWERS_TIME = 15
FLOWERS_ANONYMOUS = 16
FLOWERS_CARD = 17
FLOWERS_RECIPIENT = 18
FLOWERS_PAYMENT = 19
FLOWERS_CONFIRM = 20

# Индивидуальный заказ цветов
CUSTOM_ORDER_DESCRIPTION = 30

# Сертификаты
CERT_AMOUNT = 40
CERT_RECIPIENT = 41
CERT_CONFIRM = 42

# Отзывы
REVIEW_RATING = 50
REVIEW_TEXT = 51

# Поддержка
SUPPORT_MESSAGE = 60
SUPPORT_CONVERSATION = 61

# Админ рассылка
ADMIN_BROADCAST_TEXT = 70
ADMIN_BROADCAST_CONFIRM = 71

# =================================================================
# ТИПЫ УВЕДОМЛЕНИЙ
# =================================================================

NOTIFICATION_TYPES = {
    "appointment_reminder": "Напоминание о записи",
    "review_request": "Запрос отзыва",
    "bonus_earned": "Начисление бонусов",
    "promo": "Промо-акция",
    "loyalty_offer": "Предложение лояльности"
}

# =================================================================
# НАСТРОЙКИ УВЕДОМЛЕНИЙ
# =================================================================

# Время перед записью для отправки напоминания (в часах)
REMINDER_HOURS_BEFORE = 2

# Время после записи без подтверждения (в минутах)
UNCONFIRMED_WARNING_MINUTES = 90  # 2 часа - 30 минут = 90 минут

# Время после услуги для запроса отзыва (в часах)
REVIEW_REQUEST_HOURS_AFTER = 24

# =================================================================
# ПУТИ К ФАЙЛАМ
# =================================================================

DB_PATH = "data/beauty_salon.db"
BOT_DATA_PATH = "data/bot_data.pickle"
CREDENTIALS_PATH = "credentials.json"

# =================================================================
# НАСТРОЙКИ КЭШИРОВАНИЯ
# =================================================================

CACHE_TTL_SECONDS = 300  # 5 минут кэш для Google Sheets
# =================================================================
# PAYMENT CONFIGURATION
# =================================================================

# Выбор провайдера по умолчанию
DEFAULT_PAYMENT_PROVIDER = 'cash'  # cash, telegram, yookassa, stripe

# Конфигурация платежных систем
PAYMENT_CONFIG = {
    # Telegram Payments (использует Stripe или ЮКassa через Telegram)
    'telegram': {
        'enabled': False,
        'provider_token': '',  # Токен от @BotFather -> /mybots -> Bot Settings -> Payments
    },
    
    # Прямая интеграция с ЮКassa
    'yookassa': {
        'enabled': False,
        'shop_id': '',  # ID магазина из личного кабинета ЮКassa
        'secret_key': '',  # Секретный ключ из личного кабинета
        'return_url': 'https://your-domain.com/payment/return',  # URL возврата после оплаты
    },
    
    # Прямая интеграция со Stripe
    'stripe': {
        'enabled': False,
        'secret_key': '',  # Secret Key из Stripe Dashboard
        'publishable_key': '',  # Publishable Key из Stripe Dashboard
        'webhook_secret': '',  # Webhook Secret для проверки подписи
    },
}

