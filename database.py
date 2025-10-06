"""
Модуль для работы с SQLite базой данных.
Управление пользователями, адресами, бонусами и уведомлениями.
"""

import sqlite3
import logging
import os
import random
import string
import json
from datetime import datetime
from typing import Optional, List, Tuple

from config import DB_PATH

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def get_connection():
    """
    Получить соединение с базой данных.

    Returns:
        sqlite3.Connection: Объект соединения с БД
    """
    # Создать папку data/ если её нет
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    """
    Инициализация базы данных.
    Создание всех необходимых таблиц.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                phone TEXT,
                registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                bonus_points INTEGER DEFAULT 0,
                referral_code TEXT UNIQUE,
                referred_by INTEGER
            )
        ''')

        # Таблица адресов доставки
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                address TEXT,
                is_default BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица транзакций лояльности
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS loyalty_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                points INTEGER,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица журнала уведомлений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                notification_type TEXT,
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица услуг салона
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT,
                duration_minutes INTEGER NOT NULL,
                active BOOLEAN DEFAULT TRUE
            )
        ''')

        # Таблица товаров (цветы)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                photo_url TEXT,
                description TEXT,
                in_stock BOOLEAN DEFAULT TRUE,
                active BOOLEAN DEFAULT TRUE
            )
        ''')

        # Таблица записей в салон
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS salon_appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                service_id INTEGER NOT NULL,
                service_name TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                prepaid BOOLEAN DEFAULT FALSE,
                comment TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (service_id) REFERENCES services(id)
            )
        ''')

        # Таблица заказов цветов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flower_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                items TEXT NOT NULL,
                total_amount INTEGER NOT NULL,
                delivery_type TEXT NOT NULL,
                delivery_address TEXT,
                delivery_time TEXT,
                anonymous BOOLEAN DEFAULT FALSE,
                card_text TEXT,
                recipient_name TEXT,
                recipient_phone TEXT,
                status TEXT DEFAULT 'new',
                paid BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица сертификатов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS certificates (
                code TEXT PRIMARY KEY,
                amount INTEGER NOT NULL,
                buyer_user_id INTEGER NOT NULL,
                purchase_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                used BOOLEAN DEFAULT FALSE,
                used_by_user_id INTEGER,
                used_date DATETIME,
                FOREIGN KEY (buyer_user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица галереи
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gallery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                description TEXT,
                photo_url TEXT NOT NULL,
                price INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Миграция: добавить created_at если его нет
        try:
            cursor.execute("SELECT created_at FROM gallery LIMIT 1")
        except:
            # SQLite не позволяет DEFAULT CURRENT_TIMESTAMP при ALTER TABLE
            # Используем NULL как значение по умолчанию, а затем обновим существующие записи
            cursor.execute("ALTER TABLE gallery ADD COLUMN created_at DATETIME")
            cursor.execute("UPDATE gallery SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
            logger.info("Добавлен столбец created_at в таблицу gallery")

        # Миграция: добавить price если его нет
        try:
            cursor.execute("SELECT price FROM gallery LIMIT 1")
        except:
            cursor.execute("ALTER TABLE gallery ADD COLUMN price INTEGER DEFAULT 0")
            logger.info("Добавлен столбец price в таблицу gallery")

        # Миграция: добавить price и duration_minutes в salon_appointments
        try:
            cursor.execute("SELECT price FROM salon_appointments LIMIT 1")
        except:
            cursor.execute("ALTER TABLE salon_appointments ADD COLUMN price INTEGER DEFAULT 0")
            # Обновить цены из услуг
            cursor.execute("""
                UPDATE salon_appointments
                SET price = (SELECT price FROM services WHERE services.id = salon_appointments.service_id)
                WHERE price = 0 OR price IS NULL
            """)
            logger.info("Добавлен столбец price в таблицу salon_appointments")

        try:
            cursor.execute("SELECT duration_minutes FROM salon_appointments LIMIT 1")
        except:
            cursor.execute("ALTER TABLE salon_appointments ADD COLUMN duration_minutes INTEGER DEFAULT 60")
            # Обновить длительность из услуг
            cursor.execute("""
                UPDATE salon_appointments
                SET duration_minutes = (SELECT duration_minutes FROM services WHERE services.id = salon_appointments.service_id)
                WHERE duration_minutes = 60 OR duration_minutes IS NULL
            """)
            logger.info("Добавлен столбец duration_minutes в таблицу salon_appointments")

        # Миграция: добавить поля источников привлечения в users
        try:
            cursor.execute("SELECT utm_source FROM users LIMIT 1")
        except:
            cursor.execute("ALTER TABLE users ADD COLUMN utm_source TEXT")
            cursor.execute("ALTER TABLE users ADD COLUMN utm_medium TEXT")
            cursor.execute("ALTER TABLE users ADD COLUMN utm_campaign TEXT")
            cursor.execute("ALTER TABLE users ADD COLUMN utm_content TEXT")
            cursor.execute("ALTER TABLE users ADD COLUMN utm_term TEXT")
            cursor.execute("ALTER TABLE users ADD COLUMN source_type TEXT DEFAULT 'organic'")
            logger.info("Добавлены столбцы UTM-меток в таблицу users")

        # Миграция: добавить поле дня рождения и флаг заполнения профиля
        try:
            cursor.execute("SELECT birthday FROM users LIMIT 1")
        except:
            cursor.execute("ALTER TABLE users ADD COLUMN birthday DATE")
            cursor.execute("ALTER TABLE users ADD COLUMN profile_filled BOOLEAN DEFAULT FALSE")
            logger.info("Добавлены поля birthday и profile_filled в таблицу users")

        # Таблица реферальных наград
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referral_rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_user_id INTEGER NOT NULL,
                referred_user_id INTEGER NOT NULL,
                reward_type TEXT NOT NULL,
                reward_amount INTEGER NOT NULL,
                trigger_order_id INTEGER,
                trigger_order_amount INTEGER,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                paid_at DATETIME,
                FOREIGN KEY (referrer_user_id) REFERENCES users(user_id),
                FOREIGN KEY (referred_user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица UTM-кампаний (для генерации ссылок)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS utm_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                utm_source TEXT NOT NULL,
                utm_medium TEXT,
                utm_campaign TEXT,
                utm_content TEXT,
                utm_term TEXT,
                generated_link TEXT,
                clicks INTEGER DEFAULT 0,
                registrations INTEGER DEFAULT 0,
                conversions INTEGER DEFAULT 0,
                revenue INTEGER DEFAULT 0,
                active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица платежей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                order_type TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT DEFAULT 'RUB',
                provider TEXT NOT NULL,
                payment_method TEXT,
                payment_id TEXT UNIQUE,
                payment_url TEXT,
                status TEXT DEFAULT 'pending',
                paid_at DATETIME,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Индексы для платежей
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_payments_order
            ON payments(order_id, order_type)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_payments_status
            ON payments(status)
        ''')

        # Таблица настроек реферальной программы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referral_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled BOOLEAN DEFAULT TRUE,
                reward_type TEXT DEFAULT 'fixed',
                reward_amount INTEGER DEFAULT 500,
                reward_percent INTEGER DEFAULT 10,
                min_order_amount INTEGER DEFAULT 1000,
                max_reward_amount INTEGER DEFAULT 5000,
                reward_on_first_order_only BOOLEAN DEFAULT TRUE,
                auto_approve BOOLEAN DEFAULT FALSE,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Вставить настройки реферальной программы по умолчанию
        cursor.execute('''
            INSERT OR IGNORE INTO referral_settings
            (id, enabled, reward_type, reward_amount, min_order_amount, reward_on_first_order_only, auto_approve)
            VALUES (1, 1, 'fixed', 500, 1000, 1, 0)
        ''')

        # Таблица отзывов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                rating INTEGER NOT NULL,
                text TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица логов согласия на обработку данных
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS consent_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                consent_type TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                consent_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица настроек бонусной программы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bonus_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                bonus_percent INTEGER DEFAULT 5,
                bonus_threshold INTEGER DEFAULT 3000,
                max_bonus_payment_percent INTEGER DEFAULT 50,
                referral_bonus INTEGER DEFAULT 500,
                bonus_expiry_days INTEGER DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Вставить настройки по умолчанию если их нет
        cursor.execute('''
            INSERT OR IGNORE INTO bonus_settings (id, bonus_percent, bonus_threshold, max_bonus_payment_percent, referral_bonus, bonus_expiry_days)
            VALUES (1, 5, 3000, 50, 500, 0)
        ''')

        # Таблица запросов отзывов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                order_type TEXT NOT NULL,
                order_id INTEGER NOT NULL,
                scheduled_date DATE NOT NULL,
                sent_at DATETIME,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица настроек рекомендательной системы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled BOOLEAN DEFAULT TRUE,
                delay_days INTEGER DEFAULT 1,
                message_template TEXT DEFAULT 'Здравствуйте! Как вам наши услуги/товары? Будем рады вашему отзыву! 💐',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Вставить настройки по умолчанию если их нет
        cursor.execute('''
            INSERT OR IGNORE INTO feedback_settings (id, enabled, delay_days, message_template)
            VALUES (1, 1, 1, 'Здравствуйте! Как вам наши услуги/товары? Будем рады вашему отзыву! 💐')
        ''')

        # Таблица тарифных планов подписок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscription_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                type TEXT NOT NULL,
                price INTEGER NOT NULL,
                duration_months INTEGER NOT NULL,
                benefits TEXT,
                monthly_flowers_included INTEGER DEFAULT 0,
                monthly_service_included BOOLEAN DEFAULT FALSE,
                service_discount_percent INTEGER DEFAULT 0,
                flower_discount_percent INTEGER DEFAULT 0,
                active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица активных подписок пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan_id INTEGER NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                status TEXT DEFAULT 'active',
                flowers_used_this_month INTEGER DEFAULT 0,
                service_used_this_month BOOLEAN DEFAULT FALSE,
                last_benefit_reset DATE,
                payment_amount INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (plan_id) REFERENCES subscription_plans(id)
            )
        ''')

        # Таблица истории использования подписок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscription_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscription_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                usage_type TEXT NOT NULL,
                order_id INTEGER,
                used_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subscription_id) REFERENCES user_subscriptions(id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Добавить дефолтные планы подписок
        cursor.execute('''
            INSERT OR IGNORE INTO subscription_plans
            (id, name, description, type, price, duration_months, benefits, monthly_flowers_included, monthly_service_included, service_discount_percent, flower_discount_percent)
            VALUES
            (1, 'Красота + Цветы', 'Годовая карта с букетом каждый месяц и скидками на услуги', 'premium', 5000, 12,
             '✅ 1 букет в месяц (до 1500₽)\n✅ 15% скидка на все услуги салона\n✅ Приоритетная запись',
             1, 0, 15, 0),
            (2, 'Карта привилегий', 'Накопительные скидки и бонусы', 'privilege', 2000, 12,
             '✅ 10% скидка на все услуги\n✅ 20% скидка на цветы\n✅ Двойные бонусы\n✅ Приоритетная поддержка',
             0, 0, 10, 20),
            (3, 'Цветочная VIP подписка', 'Премиум подписка с максимальными привилегиями', 'vip', 10000, 1,
             '✅ 4 букета премиум класса в месяц\n✅ 1 услуга салона включена\n✅ Персональный менеджер\n✅ VIP обслуживание',
             4, 1, 0, 0),
            (4, 'Пакет для мужчин', 'Готовое решение: букет + услуга', 'gift_package', 4500, 0,
             '✅ Премиум букет (до 2000₽)\n✅ Услуга на выбор (маникюр/педикюр)\n✅ Красивая упаковка',
             1, 1, 0, 0)
        ''')

        # ====================================================================
        # ТАБЛИЦЫ МАСТЕРОВ И ГРАФИКОВ
        # ====================================================================

        # Таблица мастеров
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS masters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                specialization TEXT,
                photo_url TEXT,
                description TEXT,
                color TEXT DEFAULT '#3498db',
                active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица графиков работы мастеров
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS master_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                master_id INTEGER NOT NULL,
                work_date DATE NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                is_day_off BOOLEAN DEFAULT FALSE,
                note TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (master_id) REFERENCES masters(id),
                UNIQUE(master_id, work_date)
            )
        ''')

        # Миграция: добавить master_id в salon_appointments
        try:
            cursor.execute("SELECT master_id FROM salon_appointments LIMIT 1")
        except:
            cursor.execute("ALTER TABLE salon_appointments ADD COLUMN master_id INTEGER")
            cursor.execute("ALTER TABLE salon_appointments ADD COLUMN master_name TEXT")
            logger.info("Добавлены поля master_id и master_name в salon_appointments")

        # Добавить примерных мастеров
        cursor.execute('''
            INSERT OR IGNORE INTO masters
            (id, name, phone, specialization, color, active)
            VALUES
            (1, 'Анна Иванова', '+79001234567', 'Маникюр, педикюр', '#e74c3c', TRUE),
            (2, 'Мария Петрова', '+79001234568', 'Стрижки, окрашивание', '#3498db', TRUE),
            (3, 'Елена Сидорова', '+79001234569', 'Визаж, брови', '#2ecc71', TRUE),
            (4, 'Ольга Козлова', '+79001234570', 'Универсал', '#f39c12', TRUE)
        ''')

        conn.commit()
        conn.close()
        logger.info("База данных инициализирована успешно")

    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")
        raise


# =================================================================
# РАБОТА С ПОЛЬЗОВАТЕЛЯМИ
# =================================================================

def generate_referral_code(user_id: int) -> str:
    """
    Генерация уникального реферального кода.

    Args:
        user_id: ID пользователя

    Returns:
        str: Реферальный код формата REF + 6 случайных символов
    """
    while True:
        code = 'REF' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        # Проверить уникальность
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (code,))
        exists = cursor.fetchone()
        conn.close()

        if not exists:
            return code


def add_user(user_id: int, username: Optional[str], first_name: Optional[str],
             referred_by: Optional[int] = None) -> bool:
    """
    Добавить нового пользователя в базу данных.

    Args:
        user_id: Telegram ID пользователя
        username: Username пользователя
        first_name: Имя пользователя
        referred_by: ID пользователя, который пригласил

    Returns:
        bool: True если пользователь добавлен, False если уже существует
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Проверить существование пользователя
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            conn.close()
            return False

        # Генерировать реферальный код
        referral_code = generate_referral_code(user_id)

        # Добавить пользователя
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, referral_code, referred_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, referral_code, referred_by))

        conn.commit()
        conn.close()

        logger.info(f"Пользователь {user_id} ({first_name}) добавлен в БД")
        return True

    except Exception as e:
        logger.error(f"Ошибка добавления пользователя: {e}")
        return False


def get_user(user_id: int) -> Optional[Tuple]:
    """
    Получить данные пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        tuple: Кортеж с данными пользователя или None
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()

        conn.close()
        return user

    except Exception as e:
        logger.error(f"Ошибка получения пользователя: {e}")
        return None


def update_user_phone(user_id: int, phone: str):
    """
    Обновить номер телефона пользователя.

    Args:
        user_id: ID пользователя
        phone: Номер телефона
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('UPDATE users SET phone = ? WHERE user_id = ?', (phone, user_id))

        conn.commit()
        conn.close()

        logger.info(f"Телефон пользователя {user_id} обновлен")

    except Exception as e:
        logger.error(f"Ошибка обновления телефона: {e}")


def update_user_profile(user_id: int, first_name: str = None, phone: str = None, birthday: str = None):
    """
    Обновить профиль пользователя (только если он еще не был заполнен).

    Args:
        user_id: ID пользователя
        first_name: Имя
        phone: Номер телефона
        birthday: День рождения (формат YYYY-MM-DD)

    Returns:
        bool: True если обновление успешно, False если профиль уже был заполнен
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Проверить, был ли уже заполнен профиль
        cursor.execute('SELECT profile_filled FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if result and result[0]:
            conn.close()
            logger.info(f"Профиль пользователя {user_id} уже был заполнен ранее")
            return False

        # Обновить данные
        updates = []
        params = []

        if first_name:
            updates.append("first_name = ?")
            params.append(first_name)

        if phone:
            updates.append("phone = ?")
            params.append(phone)

        if birthday:
            updates.append("birthday = ?")
            params.append(birthday)

        # Установить флаг, что профиль заполнен
        updates.append("profile_filled = ?")
        params.append(True)

        params.append(user_id)

        query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
        cursor.execute(query, params)

        conn.commit()
        conn.close()

        logger.info(f"Профиль пользователя {user_id} успешно обновлен")
        return True

    except Exception as e:
        logger.error(f"Ошибка обновления профиля: {e}")
        return False


def admin_update_user_profile(user_id: int, first_name: str = None, phone: str = None, birthday: str = None):
    """
    Обновить профиль пользователя администратором (без ограничений).

    Args:
        user_id: ID пользователя
        first_name: Имя
        phone: Номер телефона
        birthday: День рождения (формат YYYY-MM-DD)

    Returns:
        bool: True если обновление успешно
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Обновить данные
        updates = []
        params = []

        if first_name is not None:
            updates.append("first_name = ?")
            params.append(first_name)

        if phone is not None:
            updates.append("phone = ?")
            params.append(phone)

        if birthday is not None:
            updates.append("birthday = ?")
            params.append(birthday)

        if not updates:
            conn.close()
            return False

        params.append(user_id)

        query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
        cursor.execute(query, params)

        conn.commit()
        conn.close()

        logger.info(f"Администратор обновил профиль пользователя {user_id}")
        return True

    except Exception as e:
        logger.error(f"Ошибка обновления профиля администратором: {e}")
        return False


def is_profile_filled(user_id: int) -> bool:
    """
    Проверить, был ли заполнен профиль пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        bool: True если профиль был заполнен
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT profile_filled FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        conn.close()

        return result[0] if result else False

    except Exception as e:
        logger.error(f"Ошибка проверки заполнения профиля: {e}")
        return False


def get_user_by_referral_code(code: str) -> Optional[int]:
    """
    Получить ID пользователя по реферальному коду.

    Args:
        code: Реферальный код

    Returns:
        int: ID пользователя или None
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (code,))
        result = cursor.fetchone()

        conn.close()

        if result:
            return result[0]
        return None

    except Exception as e:
        logger.error(f"Ошибка поиска пользователя по коду: {e}")
        return None


# =================================================================
# РАБОТА С БОНУСАМИ
# =================================================================

def add_bonus_points(user_id: int, points: int, description: str):
    """
    Начислить бонусные баллы пользователю.

    Args:
        user_id: ID пользователя
        points: Количество баллов
        description: Описание транзакции
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Обновить баланс
        cursor.execute('''
            UPDATE users
            SET bonus_points = bonus_points + ?
            WHERE user_id = ?
        ''', (points, user_id))

        # Записать транзакцию
        cursor.execute('''
            INSERT INTO loyalty_transactions (user_id, points, description)
            VALUES (?, ?, ?)
        ''', (user_id, points, description))

        conn.commit()
        conn.close()

        logger.info(f"Пользователю {user_id} начислено {points} бонусов: {description}")

    except Exception as e:
        logger.error(f"Ошибка начисления бонусов: {e}")


def subtract_bonus_points(user_id: int, points: int, description: str) -> bool:
    """
    Списать бонусные баллы у пользователя.

    Args:
        user_id: ID пользователя
        points: Количество баллов
        description: Описание транзакции

    Returns:
        bool: True если списание успешно, False если недостаточно баллов
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Проверить баланс
        cursor.execute('SELECT bonus_points FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if not result or result[0] < points:
            conn.close()
            return False

        # Списать баллы
        cursor.execute('''
            UPDATE users
            SET bonus_points = bonus_points - ?
            WHERE user_id = ?
        ''', (points, user_id))

        # Записать транзакцию
        cursor.execute('''
            INSERT INTO loyalty_transactions (user_id, points, description)
            VALUES (?, ?, ?)
        ''', (user_id, -points, description))

        conn.commit()
        conn.close()

        logger.info(f"У пользователя {user_id} списано {points} бонусов: {description}")
        return True

    except Exception as e:
        logger.error(f"Ошибка списания бонусов: {e}")
        return False


def get_bonus_balance(user_id: int) -> int:
    """
    Получить баланс бонусов пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        int: Количество бонусных баллов
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT bonus_points FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        conn.close()

        if result:
            return result[0]
        return 0

    except Exception as e:
        logger.error(f"Ошибка получения баланса бонусов: {e}")
        return 0


def get_loyalty_transactions(user_id: int, limit: int = 10) -> List[Tuple]:
    """
    Получить историю транзакций лояльности.

    Args:
        user_id: ID пользователя
        limit: Количество записей

    Returns:
        list: Список транзакций
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT points, description, created_at
            FROM loyalty_transactions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (user_id, limit))

        transactions = cursor.fetchall()
        conn.close()

        return transactions

    except Exception as e:
        logger.error(f"Ошибка получения транзакций: {e}")
        return []


# =================================================================
# РАБОТА С АДРЕСАМИ
# =================================================================

def add_address(user_id: int, address: str, is_default: bool = False):
    """
    Добавить адрес доставки.

    Args:
        user_id: ID пользователя
        address: Адрес доставки
        is_default: Установить как адрес по умолчанию
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Если адрес по умолчанию, снять флаг с других
        if is_default:
            cursor.execute('''
                UPDATE addresses
                SET is_default = FALSE
                WHERE user_id = ?
            ''', (user_id,))

        # Добавить новый адрес
        cursor.execute('''
            INSERT INTO addresses (user_id, address, is_default)
            VALUES (?, ?, ?)
        ''', (user_id, address, is_default))

        conn.commit()
        conn.close()

        logger.info(f"Адрес добавлен для пользователя {user_id}")

    except Exception as e:
        logger.error(f"Ошибка добавления адреса: {e}")


def get_addresses(user_id: int) -> List[Tuple]:
    """
    Получить все адреса пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        list: Список адресов
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, address, is_default
            FROM addresses
            WHERE user_id = ?
            ORDER BY is_default DESC, id DESC
        ''', (user_id,))

        addresses = cursor.fetchall()
        conn.close()

        return addresses

    except Exception as e:
        logger.error(f"Ошибка получения адресов: {e}")
        return []


def set_default_address(user_id: int, address_id: int):
    """
    Установить адрес по умолчанию.

    Args:
        user_id: ID пользователя
        address_id: ID адреса
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Снять флаг со всех адресов
        cursor.execute('''
            UPDATE addresses
            SET is_default = FALSE
            WHERE user_id = ?
        ''', (user_id,))

        # Установить флаг для выбранного адреса
        cursor.execute('''
            UPDATE addresses
            SET is_default = TRUE
            WHERE id = ? AND user_id = ?
        ''', (address_id, user_id))

        conn.commit()
        conn.close()

        logger.info(f"Адрес {address_id} установлен по умолчанию для пользователя {user_id}")

    except Exception as e:
        logger.error(f"Ошибка установки адреса по умолчанию: {e}")


def delete_address(address_id: int):
    """
    Удалить адрес доставки.

    Args:
        address_id: ID адреса
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM addresses WHERE id = ?', (address_id,))

        conn.commit()
        conn.close()

        logger.info(f"Адрес {address_id} удален")

    except Exception as e:
        logger.error(f"Ошибка удаления адреса: {e}")


# =================================================================
# РАБОТА С УСЛУГАМИ
# =================================================================

def add_service(category: str, name: str, price: int, description: str = "", duration_minutes: int = 60) -> int:
    """
    Добавить новую услугу салона.

    Args:
        category: Категория услуги
        name: Название услуги
        price: Цена в рублях
        description: Описание услуги
        duration_minutes: Длительность в минутах

    Returns:
        int: ID добавленной услуги
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO services (category, name, price, description, duration_minutes, active)
            VALUES (?, ?, ?, ?, ?, TRUE)
        ''', (category, name, price, description, duration_minutes))

        service_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Услуга '{name}' добавлена с ID {service_id}")
        return service_id

    except Exception as e:
        logger.error(f"Ошибка добавления услуги: {e}")
        return 0


def get_services(category: Optional[str] = None, active_only: bool = True) -> List[dict]:
    """
    Получить список услуг.

    Args:
        category: Фильтр по категории (если None - все категории)
        active_only: Только активные услуги

    Returns:
        list: Список словарей с данными услуг
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = 'SELECT id, category, name, price, description, duration_minutes, active FROM services WHERE 1=1'
        params = []

        if category:
            query += ' AND category = ?'
            params.append(category)

        if active_only:
            query += ' AND active = TRUE'

        query += ' ORDER BY category, name'

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        services = []
        for row in rows:
            services.append({
                'id': row[0],
                'category': row[1],
                'name': row[2],
                'price': row[3],
                'description': row[4],
                'duration_minutes': row[5],
                'active': row[6]
            })

        return services

    except Exception as e:
        logger.error(f"Ошибка получения услуг: {e}")
        return []


def get_service_by_id(service_id: int) -> Optional[dict]:
    """
    Получить услугу по ID.

    Args:
        service_id: ID услуги

    Returns:
        dict: Данные услуги или None
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, category, name, price, description, duration_minutes, active FROM services WHERE id = ?', (service_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'category': row[1],
                'name': row[2],
                'price': row[3],
                'description': row[4],
                'duration_minutes': row[5],
                'active': row[6]
            }
        return None

    except Exception as e:
        logger.error(f"Ошибка получения услуги: {e}")
        return None


def update_service(service_id: int, **kwargs):
    """
    Обновить данные услуги.

    Args:
        service_id: ID услуги
        **kwargs: Поля для обновления (category, name, price, description, duration_minutes, active)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        fields = []
        values = []

        for key, value in kwargs.items():
            if key in ['category', 'name', 'price', 'description', 'duration_minutes', 'active']:
                fields.append(f"{key} = ?")
                values.append(value)

        if not fields:
            return

        values.append(service_id)
        query = f"UPDATE services SET {', '.join(fields)} WHERE id = ?"

        cursor.execute(query, values)
        conn.commit()
        conn.close()

        logger.info(f"Услуга {service_id} обновлена")

    except Exception as e:
        logger.error(f"Ошибка обновления услуги: {e}")


def delete_service(service_id: int):
    """
    Деактивировать услугу (мягкое удаление).

    Args:
        service_id: ID услуги
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('UPDATE services SET active = FALSE WHERE id = ?', (service_id,))

        conn.commit()
        conn.close()

        logger.info(f"Услуга {service_id} деактивирована")

    except Exception as e:
        logger.error(f"Ошибка деактивации услуги: {e}")


def get_service_categories() -> List[str]:
    """
    Получить список всех категорий услуг.

    Returns:
        list: Список категорий
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT DISTINCT category FROM services WHERE active = TRUE ORDER BY category')
        categories = [row[0] for row in cursor.fetchall()]

        conn.close()
        return categories

    except Exception as e:
        logger.error(f"Ошибка получения категорий услуг: {e}")
        return []


# =================================================================
# РАБОТА С ТОВАРАМИ
# =================================================================

def add_product(category: str, name: str, price: int, photo_url: str = "", description: str = "") -> int:
    """
    Добавить новый товар.

    Args:
        category: Категория товара
        name: Название товара
        price: Цена в рублях
        photo_url: URL фотографии
        description: Описание товара

    Returns:
        int: ID добавленного товара
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO products (category, name, price, photo_url, description, in_stock, active)
            VALUES (?, ?, ?, ?, ?, TRUE, TRUE)
        ''', (category, name, price, photo_url, description))

        product_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Товар '{name}' добавлен с ID {product_id}")
        return product_id

    except Exception as e:
        logger.error(f"Ошибка добавления товара: {e}")
        return 0


def get_products(category: Optional[str] = None, active_only: bool = True, in_stock_only: bool = True) -> List[dict]:
    """
    Получить список товаров.

    Args:
        category: Фильтр по категории
        active_only: Только активные товары
        in_stock_only: Только товары в наличии

    Returns:
        list: Список словарей с данными товаров
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = 'SELECT id, category, name, price, photo_url, description, in_stock, active FROM products WHERE 1=1'
        params = []

        if category:
            query += ' AND category = ?'
            params.append(category)

        if active_only:
            query += ' AND active = TRUE'

        if in_stock_only:
            query += ' AND in_stock = TRUE'

        query += ' ORDER BY category, name'

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        products = []
        for row in rows:
            products.append({
                'id': row[0],
                'category': row[1],
                'name': row[2],
                'price': row[3],
                'photo_url': row[4],
                'description': row[5],
                'in_stock': row[6],
                'active': row[7]
            })

        return products

    except Exception as e:
        logger.error(f"Ошибка получения товаров: {e}")
        return []


def get_product_by_id(product_id: int) -> Optional[dict]:
    """
    Получить товар по ID.

    Args:
        product_id: ID товара

    Returns:
        dict: Данные товара или None
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, category, name, price, photo_url, description, in_stock, active FROM products WHERE id = ?', (product_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'category': row[1],
                'name': row[2],
                'price': row[3],
                'photo_url': row[4],
                'description': row[5],
                'in_stock': row[6],
                'active': row[7]
            }
        return None

    except Exception as e:
        logger.error(f"Ошибка получения товара: {e}")
        return None


def update_product(product_id: int, **kwargs):
    """
    Обновить данные товара.

    Args:
        product_id: ID товара
        **kwargs: Поля для обновления (category, name, price, photo_url, description, in_stock, active)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        fields = []
        values = []

        for key, value in kwargs.items():
            if key in ['category', 'name', 'price', 'photo_url', 'description', 'in_stock', 'active']:
                fields.append(f"{key} = ?")
                values.append(value)

        if not fields:
            return

        values.append(product_id)
        query = f"UPDATE products SET {', '.join(fields)} WHERE id = ?"

        cursor.execute(query, values)
        conn.commit()
        conn.close()

        logger.info(f"Товар {product_id} обновлен")

    except Exception as e:
        logger.error(f"Ошибка обновления товара: {e}")


def delete_product(product_id: int):
    """
    Деактивировать товар (мягкое удаление).

    Args:
        product_id: ID товара
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('UPDATE products SET active = FALSE WHERE id = ?', (product_id,))

        conn.commit()
        conn.close()

        logger.info(f"Товар {product_id} деактивирован")

    except Exception as e:
        logger.error(f"Ошибка деактивации товара: {e}")


def get_product_categories() -> List[str]:
    """
    Получить список всех категорий товаров.

    Returns:
        list: Список категорий
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT DISTINCT category FROM products WHERE active = TRUE ORDER BY category')
        categories = [row[0] for row in cursor.fetchall()]

        conn.close()
        return categories

    except Exception as e:
        logger.error(f"Ошибка получения категорий товаров: {e}")
        return []


# =================================================================
# РАБОТА С ЗАПИСЯМИ В САЛОН
# =================================================================

def add_salon_appointment(user_id: int, user_name: str, phone: str, service_id: int,
                          service_name: str, appointment_date: str, time_slot: str,
                          prepaid: bool = False, comment: str = "") -> int:
    """
    Добавить запись в салон.

    Args:
        user_id: ID пользователя
        user_name: Имя пользователя
        phone: Телефон
        service_id: ID услуги
        service_name: Название услуги
        appointment_date: Дата записи
        time_slot: Временной слот
        prepaid: Предоплата внесена
        comment: Комментарий

    Returns:
        int: ID записи
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO salon_appointments
            (user_id, user_name, phone, service_id, service_name, appointment_date, time_slot, status, prepaid, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        ''', (user_id, user_name, phone, service_id, service_name, appointment_date, time_slot, prepaid, comment))

        appointment_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Запись #{appointment_id} создана для пользователя {user_id}")
        return appointment_id

    except Exception as e:
        logger.error(f"Ошибка создания записи: {e}")
        return 0


def get_salon_appointments(user_id: Optional[int] = None, status: Optional[str] = None) -> List[dict]:
    """
    Получить список записей.

    Args:
        user_id: Фильтр по пользователю
        status: Фильтр по статусу (pending, confirmed, completed, cancelled)

    Returns:
        list: Список записей
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = '''SELECT id, user_id, user_name, phone, service_id, service_name,
                   appointment_date, time_slot, status, prepaid, comment, created_at, price, duration_minutes
                   FROM salon_appointments WHERE 1=1'''
        params = []

        if user_id:
            query += ' AND user_id = ?'
            params.append(user_id)

        if status:
            query += ' AND status = ?'
            params.append(status)

        query += ' ORDER BY appointment_date DESC, time_slot DESC'

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        appointments = []
        for row in rows:
            appointments.append({
                'id': row[0],
                'user_id': row[1],
                'user_name': row[2],
                'phone': row[3],
                'service_id': row[4],
                'service_name': row[5],
                'appointment_date': row[6],
                'time_slot': row[7],
                'status': row[8],
                'prepaid': row[9],
                'comment': row[10],
                'created_at': row[11],
                'price': row[12] if len(row) > 12 else 0,
                'duration_minutes': row[13] if len(row) > 13 else 60
            })

        return appointments

    except Exception as e:
        logger.error(f"Ошибка получения записей: {e}")
        return []


def get_salon_appointment_by_id(appointment_id: int) -> Optional[dict]:
    """
    Получить запись по ID.

    Args:
        appointment_id: ID записи

    Returns:
        dict: Данные записи или None
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, user_id, user_name, phone, service_id, service_name,
                   appointment_date, time_slot, status, prepaid, comment, created_at, price, duration_minutes
            FROM salon_appointments
            WHERE id = ?
        ''', (appointment_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'user_id': row[1],
                'user_name': row[2],
                'phone': row[3],
                'service_id': row[4],
                'service_name': row[5],
                'appointment_date': row[6],
                'time_slot': row[7],
                'status': row[8],
                'prepaid': row[9],
                'comment': row[10],
                'created_at': row[11],
                'price': row[12] if len(row) > 12 else 0,
                'duration_minutes': row[13] if len(row) > 13 else 60
            }
        return None

    except Exception as e:
        logger.error(f"Ошибка получения записи по ID: {e}")
        return None


def update_salon_appointment_status(appointment_id: int, status: str):
    """
    Обновить статус записи.

    Args:
        appointment_id: ID записи
        status: Новый статус (pending, confirmed, completed, cancelled)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('UPDATE salon_appointments SET status = ? WHERE id = ?', (status, appointment_id))

        conn.commit()
        conn.close()

        logger.info(f"Запись #{appointment_id} обновлена на статус {status}")

    except Exception as e:
        logger.error(f"Ошибка обновления статуса записи: {e}")


# =================================================================
# РАБОТА С ЗАКАЗАМИ ЦВЕТОВ
# =================================================================

def add_flower_order(user_id: int, user_name: str, phone: str, items: str, total_amount: int,
                     delivery_type: str, delivery_address: str = "", delivery_time: str = "",
                     anonymous: bool = False, card_text: str = "",
                     recipient_name: str = "", recipient_phone: str = "") -> int:
    """
    Добавить заказ цветов.

    Args:
        user_id: ID пользователя
        user_name: Имя пользователя
        phone: Телефон
        items: JSON строка с товарами
        total_amount: Общая сумма
        delivery_type: Тип доставки (delivery/pickup)
        delivery_address: Адрес доставки
        delivery_time: Время доставки
        anonymous: Анонимная доставка
        card_text: Текст открытки
        recipient_name: Имя получателя
        recipient_phone: Телефон получателя

    Returns:
        int: ID заказа
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO flower_orders
            (user_id, user_name, phone, items, total_amount, delivery_type, delivery_address,
             delivery_time, anonymous, card_text, recipient_name, recipient_phone, status, paid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', FALSE)
        ''', (user_id, user_name, phone, items, total_amount, delivery_type, delivery_address,
              delivery_time, anonymous, card_text, recipient_name, recipient_phone))

        order_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Заказ цветов #{order_id} создан для пользователя {user_id}")
        return order_id

    except Exception as e:
        logger.error(f"Ошибка создания заказа цветов: {e}")
        return 0


def get_flower_orders(user_id: Optional[int] = None, status: Optional[str] = None) -> List[dict]:
    """
    Получить список заказов цветов.

    Args:
        user_id: Фильтр по пользователю
        status: Фильтр по статусу (new, confirmed, in_delivery, completed, cancelled)

    Returns:
        list: Список заказов
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = '''SELECT id, user_id, user_name, phone, items, total_amount, delivery_type,
                   delivery_address, delivery_time, anonymous, card_text, recipient_name,
                   recipient_phone, status, paid, created_at
                   FROM flower_orders WHERE 1=1'''
        params = []

        if user_id:
            query += ' AND user_id = ?'
            params.append(user_id)

        if status:
            query += ' AND status = ?'
            params.append(status)

        query += ' ORDER BY created_at DESC'

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        orders = []
        for row in rows:
            orders.append({
                'id': row[0],
                'user_id': row[1],
                'user_name': row[2],
                'phone': row[3],
                'items': row[4],
                'total_amount': row[5],
                'delivery_type': row[6],
                'delivery_address': row[7],
                'delivery_time': row[8],
                'anonymous': row[9],
                'card_text': row[10],
                'recipient_name': row[11],
                'recipient_phone': row[12],
                'status': row[13],
                'paid': row[14],
                'created_at': row[15]
            })

        return orders

    except Exception as e:
        logger.error(f"Ошибка получения заказов цветов: {e}")
        return []


def get_flower_order_by_id(order_id: int) -> Optional[dict]:
    """
    Получить заказ по ID.

    Args:
        order_id: ID заказа

    Returns:
        dict: Данные заказа или None
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, user_id, user_name, phone, items, total_amount, delivery_type,
                   delivery_address, delivery_time, anonymous, card_text, recipient_name,
                   recipient_phone, status, paid, created_at
            FROM flower_orders
            WHERE id = ?
        ''', (order_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'user_id': row[1],
                'user_name': row[2],
                'phone': row[3],
                'items': row[4],
                'total_amount': row[5],
                'delivery_type': row[6],
                'delivery_address': row[7],
                'delivery_time': row[8],
                'anonymous': row[9],
                'card_text': row[10],
                'recipient_name': row[11],
                'recipient_phone': row[12],
                'status': row[13],
                'paid': row[14],
                'created_at': row[15]
            }
        return None

    except Exception as e:
        logger.error(f"Ошибка получения заказа по ID: {e}")
        return None


def update_flower_order_status(order_id: int, status: str, paid: Optional[bool] = None, send_notification: bool = False):
    """
    Обновить статус заказа цветов.

    Args:
        order_id: ID заказа
        status: Новый статус (new, accepted, delivering, delivered, cancelled)
        paid: Оплачен ли заказ
        send_notification: Отправлять уведомление клиенту
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Получить информацию о заказе для уведомления
        cursor.execute('SELECT user_id, user_name, total_amount FROM flower_orders WHERE id = ?', (order_id,))
        order_data = cursor.fetchone()

        if paid is not None:
            cursor.execute('UPDATE flower_orders SET status = ?, paid = ? WHERE id = ?',
                         (status, paid, order_id))
        else:
            cursor.execute('UPDATE flower_orders SET status = ? WHERE id = ?',
                         (status, order_id))

        conn.commit()
        conn.close()

        logger.info(f"Заказ цветов #{order_id} обновлен на статус {status}")

        # Отправить уведомление клиенту
        if send_notification and order_data:
            user_id, user_name, total_amount = order_data

            status_messages = {
                'accepted': '✅ <b>Заказ принят!</b>\n\n📦 Ваш заказ цветов принят в обработку.\nСкоро мы с вами свяжемся для уточнения деталей доставки.',
                'delivering': '🚗 <b>Заказ в пути!</b>\n\n📦 Ваш заказ цветов передан курьеру.\nОжидайте доставку в ближайшее время!',
                'delivered': '🎉 <b>Заказ доставлен!</b>\n\n✅ Ваш заказ цветов успешно доставлен.\nСпасибо за покупку! Будем рады видеть вас снова!',
                'cancelled': '❌ <b>Заказ отменен</b>\n\n📦 К сожалению, ваш заказ был отменен.\nЕсли у вас есть вопросы, свяжитесь с нами через поддержку.'
            }

            message = status_messages.get(status)

            if message:
                try:
                    from config import TELEGRAM_BOT_TOKEN
                    from telegram import Bot
                    import asyncio

                    message += f"\n\n💰 Сумма заказа: {total_amount}₽\n📝 Номер заказа: #{order_id}"

                    bot = Bot(token=TELEGRAM_BOT_TOKEN)
                    asyncio.run(bot.send_message(chat_id=user_id, text=message, parse_mode='HTML'))
                    logger.info(f"Уведомление о статусе заказа отправлено пользователю {user_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления о статусе заказа: {e}")

    except Exception as e:
        logger.error(f"Ошибка обновления статуса заказа: {e}")


# =================================================================
# РАБОТА С СЕРТИФИКАТАМИ
# =================================================================

def generate_certificate_code() -> str:
    """
    Генерация уникального кода сертификата.

    Returns:
        str: Код формата CERT-XXXX
    """
    while True:
        code = 'CERT-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT code FROM certificates WHERE code = ?', (code,))
        exists = cursor.fetchone()
        conn.close()

        if not exists:
            return code


def add_certificate(amount: int, buyer_user_id: int) -> str:
    """
    Добавить новый сертификат.

    Args:
        amount: Номинал сертификата
        buyer_user_id: ID покупателя

    Returns:
        str: Код сертификата
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        code = generate_certificate_code()

        cursor.execute('''
            INSERT INTO certificates (code, amount, buyer_user_id, used)
            VALUES (?, ?, ?, FALSE)
        ''', (code, amount, buyer_user_id))

        conn.commit()
        conn.close()

        logger.info(f"Сертификат {code} создан на сумму {amount} руб.")
        return code

    except Exception as e:
        logger.error(f"Ошибка создания сертификата: {e}")
        return ""


def get_certificate(code: str) -> Optional[dict]:
    """
    Получить данные сертификата.

    Args:
        code: Код сертификата

    Returns:
        dict: Данные сертификата или None
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT code, amount, buyer_user_id, purchase_date, used, used_by_user_id, used_date
            FROM certificates WHERE code = ?
        ''', (code,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'code': row[0],
                'amount': row[1],
                'buyer_user_id': row[2],
                'purchase_date': row[3],
                'used': row[4],
                'used_by_user_id': row[5],
                'used_date': row[6]
            }
        return None

    except Exception as e:
        logger.error(f"Ошибка получения сертификата: {e}")
        return None


def use_certificate(code: str, user_id: int) -> bool:
    """
    Использовать сертификат.

    Args:
        code: Код сертификата
        user_id: ID пользователя, который использует

    Returns:
        bool: True если успешно, False если сертификат уже использован или не найден
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Проверить существование и статус
        cursor.execute('SELECT used FROM certificates WHERE code = ?', (code,))
        result = cursor.fetchone()

        if not result or result[0]:
            conn.close()
            return False

        # Отметить как использованный
        cursor.execute('''
            UPDATE certificates
            SET used = TRUE, used_by_user_id = ?, used_date = CURRENT_TIMESTAMP
            WHERE code = ?
        ''', (user_id, code))

        conn.commit()
        conn.close()

        logger.info(f"Сертификат {code} использован пользователем {user_id}")
        return True

    except Exception as e:
        logger.error(f"Ошибка использования сертификата: {e}")
        return False


# =================================================================
# РАБОТА С ГАЛЕРЕЕЙ
# =================================================================

def add_gallery_item(category: str, photo_url: str, description: str = "", price: int = 0) -> int:
    """
    Добавить фото в галерею.

    Args:
        category: Категория (salon/flowers)
        photo_url: URL фотографии
        description: Описание
        price: Стоимость

    Returns:
        int: ID записи
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO gallery (category, description, photo_url, price)
            VALUES (?, ?, ?, ?)
        ''', (category, description, photo_url, price))

        item_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Фото добавлено в галерею с ID {item_id}")
        return item_id

    except Exception as e:
        logger.error(f"Ошибка добавления фото в галерею: {e}")
        return 0


def get_gallery_items(category: Optional[str] = None) -> List[dict]:
    """
    Получить фото из галереи.

    Args:
        category: Фильтр по категории

    Returns:
        list: Список фото
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if category:
            cursor.execute('''
                SELECT id, category, description, photo_url, price, created_at
                FROM gallery WHERE category = ?
                ORDER BY id DESC
            ''', (category,))
        else:
            cursor.execute('''
                SELECT id, category, description, photo_url, price, created_at
                FROM gallery
                ORDER BY id DESC
            ''')

        rows = cursor.fetchall()
        conn.close()

        items = []
        for row in rows:
            items.append({
                'id': row[0],
                'category': row[1],
                'description': row[2],
                'photo_url': row[3],
                'price': row[4] if row[4] else 0,
                'created_at': row[5] if row[5] else ''
            })

        return items

    except Exception as e:
        logger.error(f"Ошибка получения галереи: {e}")
        return []


def get_gallery_item_by_id(item_id: int) -> Optional[dict]:
    """
    Получить фото из галереи по ID.

    Args:
        item_id: ID записи

    Returns:
        dict: Данные фото или None
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, category, description, photo_url, price, created_at
            FROM gallery WHERE id = ?
        ''', (item_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'category': row[1],
                'description': row[2],
                'photo_url': row[3],
                'price': row[4] if row[4] else 0,
                'created_at': row[5] if row[5] else ''
            }
        return None

    except Exception as e:
        logger.error(f"Ошибка получения фото по ID: {e}")
        return None


def update_gallery_item(item_id: int, category: str, description: str = "", price: int = 0):
    """
    Обновить информацию о фото в галерее.

    Args:
        item_id: ID записи
        category: Категория
        description: Описание
        price: Стоимость
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE gallery
            SET category = ?, description = ?, price = ?
            WHERE id = ?
        ''', (category, description, price, item_id))

        conn.commit()
        conn.close()

        logger.info(f"Фото {item_id} обновлено в галерее")

    except Exception as e:
        logger.error(f"Ошибка обновления фото: {e}")


def delete_gallery_item(item_id: int):
    """
    Удалить фото из галереи.

    Args:
        item_id: ID записи
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM gallery WHERE id = ?', (item_id,))

        conn.commit()
        conn.close()

        logger.info(f"Фото {item_id} удалено из галереи")

    except Exception as e:
        logger.error(f"Ошибка удаления фото: {e}")


# =================================================================
# РАБОТА С ОТЗЫВАМИ
# =================================================================

def add_review(user_id: int, user_name: str, rating: int, text: str = "") -> int:
    """
    Добавить отзыв.

    Args:
        user_id: ID пользователя
        user_name: Имя пользователя
        rating: Оценка (1-5)
        text: Текст отзыва

    Returns:
        int: ID отзыва
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO reviews (user_id, user_name, rating, text)
            VALUES (?, ?, ?, ?)
        ''', (user_id, user_name, rating, text))

        review_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Отзыв #{review_id} от пользователя {user_id} добавлен")
        return review_id

    except Exception as e:
        logger.error(f"Ошибка добавления отзыва: {e}")
        return 0


def get_reviews(min_rating: Optional[int] = None) -> List[dict]:
    """
    Получить отзывы.

    Args:
        min_rating: Минимальный рейтинг для фильтра

    Returns:
        list: Список отзывов
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if min_rating:
            cursor.execute('''
                SELECT id, user_id, user_name, rating, text, created_at
                FROM reviews WHERE rating >= ?
                ORDER BY created_at DESC
            ''', (min_rating,))
        else:
            cursor.execute('''
                SELECT id, user_id, user_name, rating, text, created_at
                FROM reviews
                ORDER BY created_at DESC
            ''')

        rows = cursor.fetchall()
        conn.close()

        reviews = []
        for row in rows:
            reviews.append({
                'id': row[0],
                'user_id': row[1],
                'user_name': row[2],
                'rating': row[3],
                'text': row[4],
                'created_at': row[5]
            })

        return reviews

    except Exception as e:
        logger.error(f"Ошибка получения отзывов: {e}")
        return []


# =================================================================
# ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ
# =================================================================

def log_notification(user_id: int, notification_type: str):
    """
    Записать отправленное уведомление в журнал.

    Args:
        user_id: ID пользователя
        notification_type: Тип уведомления
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO notifications_log (user_id, notification_type)
            VALUES (?, ?)
        ''', (user_id, notification_type))

        conn.commit()
        conn.close()

        logger.info(f"Уведомление '{notification_type}' для пользователя {user_id} записано в журнал")

    except Exception as e:
        logger.error(f"Ошибка записи уведомления: {e}")


def get_all_users() -> List[int]:
    """
    Получить список всех пользователей (для рассылки).

    Returns:
        list: Список ID пользователей
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT user_id FROM users')
        users = [row[0] for row in cursor.fetchall()]

        conn.close()
        return users

    except Exception as e:
        logger.error(f"Ошибка получения списка пользователей: {e}")
        return []


def get_users_list(search: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[dict]:
    """
    Получить список пользователей с полной информацией.

    Args:
        search: Поисковый запрос (имя, телефон, username)
        limit: Количество записей
        offset: Смещение для пагинации

    Returns:
        list: Список пользователей
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = '''
            SELECT user_id, first_name, username, phone, bonus_points, registration_date
            FROM users
            WHERE 1=1
        '''
        params = []

        if search:
            query += ''' AND (
                first_name LIKE ? OR
                username LIKE ? OR
                phone LIKE ?
            )'''
            search_pattern = f'%{search}%'
            params.extend([search_pattern, search_pattern, search_pattern])

        query += ' ORDER BY registration_date DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        users = []
        for row in rows:
            users.append({
                'user_id': row[0],
                'user_name': row[1],  # first_name как user_name для совместимости с шаблонами
                'username': row[2],
                'phone': row[3],
                'bonus_points': row[4],
                'created_at': row[5]
            })

        conn.close()
        return users

    except Exception as e:
        logger.error(f"Ошибка получения списка пользователей: {e}")
        return []


def get_user_stats(user_id: int) -> dict:
    """
    Получить статистику пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        dict: Статистика (записи, заказы, отзывы)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Записи в салон
        cursor.execute('SELECT COUNT(*) FROM salon_appointments WHERE user_id = ?', (user_id,))
        appointments_count = cursor.fetchone()[0]

        # Заказы цветов
        cursor.execute('SELECT COUNT(*) FROM flower_orders WHERE user_id = ?', (user_id,))
        orders_count = cursor.fetchone()[0]

        # Отзывы
        cursor.execute('SELECT COUNT(*) FROM reviews WHERE user_id = ?', (user_id,))
        reviews_count = cursor.fetchone()[0]

        # Общая сумма заказов
        cursor.execute('SELECT SUM(total_amount) FROM flower_orders WHERE user_id = ? AND status != "cancelled"', (user_id,))
        total_spent = cursor.fetchone()[0] or 0

        conn.close()

        return {
            'appointments_count': appointments_count,
            'orders_count': orders_count,
            'reviews_count': reviews_count,
            'total_spent': total_spent
        }

    except Exception as e:
        logger.error(f"Ошибка получения статистики пользователя: {e}")
        return {
            'appointments_count': 0,
            'orders_count': 0,
            'reviews_count': 0,
            'total_spent': 0
        }


def count_referrals(user_id: int) -> int:
    """
    Подсчитать количество приглашенных пользователей.

    Args:
        user_id: ID пользователя

    Returns:
        int: Количество рефералов
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = ?', (user_id,))
        count = cursor.fetchone()[0]

        conn.close()
        return count

    except Exception as e:
        logger.error(f"Ошибка подсчета рефералов: {e}")
        return 0


# =================================================================
# ЛОГИРОВАНИЕ СОГЛАСИЙ НА ОБРАБОТКУ ДАННЫХ
# =================================================================

def log_consent(user_id: int, user_name: str, phone: str, consent_type: str = 'phone_share') -> bool:
    """
    Зафиксировать согласие пользователя на обработку персональных данных.

    Args:
        user_id: Telegram ID пользователя
        user_name: Имя пользователя
        phone: Номер телефона
        consent_type: Тип согласия (phone_share, data_processing и т.д.)

    Returns:
        bool: True если успешно, False при ошибке
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO consent_logs (user_id, user_name, phone, consent_type)
            VALUES (?, ?, ?, ?)
        ''', (user_id, user_name, phone, consent_type))

        conn.commit()
        conn.close()

        logger.info(f"Зафиксировано согласие пользователя {user_id} ({user_name}) на {consent_type}")
        return True

    except Exception as e:
        logger.error(f"Ошибка логирования согласия: {e}")
        return False


def get_consent_logs(user_id: Optional[int] = None, limit: int = 100) -> List[dict]:
    """
    Получить историю согласий на обработку данных.

    Args:
        user_id: ID пользователя (опционально, для фильтрации)
        limit: Максимальное количество записей

    Returns:
        list: Список словарей с данными согласий
    """
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if user_id:
            cursor.execute('''
                SELECT * FROM consent_logs
                WHERE user_id = ?
                ORDER BY consent_date DESC
                LIMIT ?
            ''', (user_id, limit))
        else:
            cursor.execute('''
                SELECT * FROM consent_logs
                ORDER BY consent_date DESC
                LIMIT ?
            ''', (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"Ошибка получения логов согласий: {e}")
        return []


# ============================================================================
# УПРАВЛЕНИЕ КАТЕГОРИЯМИ
# ============================================================================

def get_service_categories_with_counts() -> List[dict]:
    """
    Получить список всех категорий услуг с количеством элементов.

    Returns:
        list: Список словарей {'name': str, 'count': int}
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT category, COUNT(*) as count
            FROM services
            WHERE active = TRUE
            GROUP BY category
            ORDER BY category
        ''')

        categories = [{'name': row[0], 'count': row[1]} for row in cursor.fetchall()]
        conn.close()
        return categories

    except Exception as e:
        logger.error(f"Ошибка получения категорий услуг с подсчетом: {e}")
        return []


def get_product_categories_with_counts() -> List[dict]:
    """
    Получить список всех категорий товаров с количеством элементов.

    Returns:
        list: Список словарей {'name': str, 'count': int}
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT category, COUNT(*) as count
            FROM products
            WHERE active = TRUE
            GROUP BY category
            ORDER BY category
        ''')

        categories = [{'name': row[0], 'count': row[1]} for row in cursor.fetchall()]
        conn.close()
        return categories

    except Exception as e:
        logger.error(f"Ошибка получения категорий товаров с подсчетом: {e}")
        return []


def rename_service_category(old_name: str, new_name: str) -> bool:
    """
    Переименовать категорию услуг.

    Args:
        old_name: Старое название категории
        new_name: Новое название категории

    Returns:
        bool: True если успешно, False в случае ошибки
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE services
            SET category = ?
            WHERE category = ?
        ''', (new_name, old_name))

        conn.commit()
        conn.close()

        logger.info(f"Категория услуг переименована: '{old_name}' -> '{new_name}'")
        return True

    except Exception as e:
        logger.error(f"Ошибка переименования категории услуг: {e}")
        return False


def rename_product_category(old_name: str, new_name: str) -> bool:
    """
    Переименовать категорию товаров.

    Args:
        old_name: Старое название категории
        new_name: Новое название категории

    Returns:
        bool: True если успешно, False в случае ошибки
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE products
            SET category = ?
            WHERE category = ?
        ''', (new_name, old_name))

        conn.commit()
        conn.close()

        logger.info(f"Категория товаров переименована: '{old_name}' -> '{new_name}'")
        return True

    except Exception as e:
        logger.error(f"Ошибка переименования категории товаров: {e}")
        return False


def delete_service_category(category_name: str) -> bool:
    """
    Удалить категорию услуг (деактивировать все услуги в этой категории).

    Args:
        category_name: Название категории

    Returns:
        bool: True если успешно, False в случае ошибки
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Деактивировать все услуги этой категории
        cursor.execute('''
            UPDATE services
            SET active = FALSE
            WHERE category = ?
        ''', (category_name,))

        conn.commit()
        conn.close()

        logger.info(f"Категория услуг '{category_name}' удалена (услуги деактивированы)")
        return True

    except Exception as e:
        logger.error(f"Ошибка удаления категории услуг: {e}")
        return False


def delete_product_category(category_name: str) -> bool:
    """
    Удалить категорию товаров (деактивировать все товары в этой категории).

    Args:
        category_name: Название категории

    Returns:
        bool: True если успешно, False в случае ошибки
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Деактивировать все товары этой категории
        cursor.execute('''
            UPDATE products
            SET active = FALSE
            WHERE category = ?
        ''', (category_name,))

        conn.commit()
        conn.close()

        logger.info(f"Категория товаров '{category_name}' удалена (товары деактивированы)")
        return True

    except Exception as e:
        logger.error(f"Ошибка удаления категории товаров: {e}")
        return False


def add_service_category(category_name: str, placeholder_name: str = "Новая услуга", price: int = 0) -> bool:
    """
    Добавить новую категорию услуг (создает placeholder-услугу в этой категории).

    Args:
        category_name: Название новой категории
        placeholder_name: Название placeholder-услуги
        price: Цена placeholder-услуги

    Returns:
        bool: True если успешно, False в случае ошибки
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Проверить, существует ли уже такая категория
        cursor.execute('''
            SELECT COUNT(*) FROM services WHERE category = ? AND active = TRUE
        ''', (category_name,))

        if cursor.fetchone()[0] > 0:
            conn.close()
            logger.warning(f"Категория услуг '{category_name}' уже существует")
            return False

        # Создать placeholder-услугу в новой категории
        cursor.execute('''
            INSERT INTO services (category, name, price, description, duration_minutes, active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (category_name, placeholder_name, price, f"Услуга в категории {category_name}", 60, True))

        conn.commit()
        conn.close()

        logger.info(f"Категория услуг '{category_name}' создана")
        return True

    except Exception as e:
        logger.error(f"Ошибка создания категории услуг: {e}")
        return False


def add_product_category(category_name: str, placeholder_name: str = "Новый товар", price: int = 0) -> bool:
    """
    Добавить новую категорию товаров (создает placeholder-товар в этой категории).

    Args:
        category_name: Название новой категории
        placeholder_name: Название placeholder-товара
        price: Цена placeholder-товара

    Returns:
        bool: True если успешно, False в случае ошибки
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Проверить, существует ли уже такая категория
        cursor.execute('''
            SELECT COUNT(*) FROM products WHERE category = ? AND active = TRUE
        ''', (category_name,))

        if cursor.fetchone()[0] > 0:
            conn.close()
            logger.warning(f"Категория товаров '{category_name}' уже существует")
            return False

        # Создать placeholder-товар в новой категории
        cursor.execute('''
            INSERT INTO products (category, name, price, description, photo_url, in_stock, active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (category_name, placeholder_name, price, f"Товар в категории {category_name}", "", True, True))

        conn.commit()
        conn.close()

        logger.info(f"Категория товаров '{category_name}' создана")
        return True

    except Exception as e:
        logger.error(f"Ошибка создания категории товаров: {e}")
        return False


# ============================================================================
# УПРАВЛЕНИЕ БОНУСНОЙ ПРОГРАММОЙ
# ============================================================================

def get_bonus_settings() -> dict:
    """
    Получить текущие настройки бонусной программы.

    Returns:
        dict: Настройки бонусной программы
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM bonus_settings WHERE id = 1')
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'bonus_percent': row[1],
                'bonus_threshold': row[2],
                'max_bonus_payment_percent': row[3],
                'referral_bonus': row[4],
                'bonus_expiry_days': row[5],
                'updated_at': row[6]
            }
        return {
            'bonus_percent': 5,
            'bonus_threshold': 3000,
            'max_bonus_payment_percent': 50,
            'referral_bonus': 500,
            'bonus_expiry_days': 0
        }

    except Exception as e:
        logger.error(f"Ошибка получения настроек бонусов: {e}")
        return {
            'bonus_percent': 5,
            'bonus_threshold': 3000,
            'max_bonus_payment_percent': 50,
            'referral_bonus': 500,
            'bonus_expiry_days': 0
        }


def update_bonus_settings(bonus_percent: int, bonus_threshold: int,
                          max_bonus_payment_percent: int, referral_bonus: int,
                          bonus_expiry_days: int) -> bool:
    """
    Обновить настройки бонусной программы.

    Args:
        bonus_percent: Процент начисления бонусов от суммы заказа
        bonus_threshold: Минимальная сумма заказа для начисления бонусов
        max_bonus_payment_percent: Максимальный процент оплаты бонусами
        referral_bonus: Бонусы за приглашение друга
        bonus_expiry_days: Срок действия бонусов (дней), 0 = бессрочно

    Returns:
        bool: True если успешно, False в случае ошибки
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE bonus_settings
            SET bonus_percent = ?,
                bonus_threshold = ?,
                max_bonus_payment_percent = ?,
                referral_bonus = ?,
                bonus_expiry_days = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        ''', (bonus_percent, bonus_threshold, max_bonus_payment_percent,
              referral_bonus, bonus_expiry_days))

        conn.commit()
        conn.close()

        logger.info("Настройки бонусной программы обновлены")
        return True

    except Exception as e:
        logger.error(f"Ошибка обновления настроек бонусов: {e}")
        return False


def expire_old_bonuses() -> int:
    """
    Списать просроченные бонусы у всех пользователей.

    Returns:
        int: Количество пользователей, у которых списаны бонусы
    """
    try:
        settings = get_bonus_settings()
        expiry_days = settings.get('bonus_expiry_days', 0)

        if expiry_days <= 0:
            return 0  # Бонусы бессрочные

        conn = get_connection()
        cursor = conn.cursor()

        # Найти транзакции старше expiry_days
        cursor.execute('''
            SELECT user_id, SUM(points) as expired_points
            FROM loyalty_transactions
            WHERE points > 0
            AND datetime(created_at, '+' || ? || ' days') < datetime('now')
            GROUP BY user_id
            HAVING expired_points > 0
        ''', (expiry_days,))

        expired_users = cursor.fetchall()
        count = 0

        for user_id, expired_points in expired_users:
            # Списать просроченные бонусы
            cursor.execute('''
                UPDATE users
                SET bonus_points = MAX(0, bonus_points - ?)
                WHERE user_id = ?
            ''', (expired_points, user_id))

            # Записать транзакцию списания
            cursor.execute('''
                INSERT INTO loyalty_transactions (user_id, points, description)
                VALUES (?, ?, ?)
            ''', (user_id, -expired_points, f"Списание просроченных бонусов ({expiry_days} дней)"))

            count += 1

        conn.commit()
        conn.close()

        if count > 0:
            logger.info(f"Списаны просроченные бонусы у {count} пользователей")

        return count

    except Exception as e:
        logger.error(f"Ошибка списания просроченных бонусов: {e}")
        return 0


def manually_adjust_bonus_points(user_id: int, points: int, description: str) -> bool:
    """
    Вручную начислить или списать бонусы пользователю (для админов).

    Args:
        user_id: ID пользователя
        points: Количество баллов (положительное = начисление, отрицательное = списание)
        description: Описание операции

    Returns:
        bool: True если успешно, False в случае ошибки
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Проверить текущий баланс при списании
        if points < 0:
            cursor.execute('SELECT bonus_points FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            if not result or result[0] + points < 0:
                conn.close()
                logger.warning(f"Недостаточно бонусов для списания у пользователя {user_id}")
                return False

        # Обновить баланс
        cursor.execute('''
            UPDATE users
            SET bonus_points = bonus_points + ?
            WHERE user_id = ?
        ''', (points, user_id))

        # Записать транзакцию
        cursor.execute('''
            INSERT INTO loyalty_transactions (user_id, points, description)
            VALUES (?, ?, ?)
        ''', (user_id, points, description))

        conn.commit()
        conn.close()

        logger.info(f"Вручную изменены бонусы пользователя {user_id}: {points:+d} ({description})")
        return True

    except Exception as e:
        logger.error(f"Ошибка ручного изменения бонусов: {e}")
        return False


# ============================================================================
# РЕКОМЕНДАТЕЛЬНАЯ СИСТЕМА / ЗАПРОСЫ ОТЗЫВОВ
# ============================================================================

def get_feedback_settings() -> dict:
    """
    Получить настройки рекомендательной системы.

    Returns:
        dict: Настройки системы запросов отзывов
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM feedback_settings WHERE id = 1')
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'enabled': bool(row[1]),
                'delay_days': row[2],
                'message_template': row[3],
                'updated_at': row[4]
            }
        return {
            'enabled': True,
            'delay_days': 1,
            'message_template': 'Здравствуйте! Как вам наши услуги/товары? Будем рады вашему отзыву! 💐'
        }

    except Exception as e:
        logger.error(f"Ошибка получения настроек отзывов: {e}")
        return {
            'enabled': True,
            'delay_days': 1,
            'message_template': 'Здравствуйте! Как вам наши услуги/товары? Будем рады вашему отзыву! 💐'
        }


def update_feedback_settings(enabled: bool, delay_days: int, message_template: str) -> bool:
    """
    Обновить настройки рекомендательной системы.

    Args:
        enabled: Включена ли система автоматических запросов
        delay_days: Через сколько дней после заказа отправлять запрос
        message_template: Шаблон сообщения для запроса отзыва

    Returns:
        bool: True если успешно, False в случае ошибки
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE feedback_settings
            SET enabled = ?,
                delay_days = ?,
                message_template = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        ''', (enabled, delay_days, message_template))

        conn.commit()
        conn.close()

        logger.info("Настройки рекомендательной системы обновлены")
        return True

    except Exception as e:
        logger.error(f"Ошибка обновления настроек отзывов: {e}")
        return False


def schedule_feedback_request(user_id: int, order_type: str, order_id: int) -> bool:
    """
    Запланировать отправку запроса на отзыв.

    Args:
        user_id: ID пользователя
        order_type: Тип заказа ('appointment' или 'flower_order')
        order_id: ID заказа

    Returns:
        bool: True если успешно, False в случае ошибки
    """
    try:
        settings = get_feedback_settings()
        if not settings['enabled']:
            return False

        conn = get_connection()
        cursor = conn.cursor()

        # Вычислить дату отправки (через delay_days дней)
        delay_days = settings['delay_days']
        cursor.execute('''
            INSERT INTO feedback_requests (user_id, order_type, order_id, scheduled_date, status)
            VALUES (?, ?, ?, date('now', '+' || ? || ' days'), 'pending')
        ''', (user_id, order_type, order_id, delay_days))

        conn.commit()
        conn.close()

        logger.info(f"Запланирован запрос отзыва для пользователя {user_id} через {delay_days} дней")
        return True

    except Exception as e:
        logger.error(f"Ошибка планирования запроса отзыва: {e}")
        return False


def get_pending_feedback_requests() -> List[dict]:
    """
    Получить запросы отзывов, которые нужно отправить сегодня.

    Returns:
        list: Список запросов на отправку
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT fr.id, fr.user_id, fr.order_type, fr.order_id, u.first_name
            FROM feedback_requests fr
            JOIN users u ON fr.user_id = u.user_id
            WHERE fr.status = 'pending'
            AND fr.scheduled_date <= date('now')
            ORDER BY fr.scheduled_date ASC
        ''')

        requests = []
        for row in cursor.fetchall():
            requests.append({
                'id': row[0],
                'user_id': row[1],
                'order_type': row[2],
                'order_id': row[3],
                'user_name': row[4]
            })

        conn.close()
        return requests

    except Exception as e:
        logger.error(f"Ошибка получения запросов отзывов: {e}")
        return []


def mark_feedback_request_sent(request_id: int) -> bool:
    """
    Отметить запрос отзыва как отправленный.

    Args:
        request_id: ID запроса

    Returns:
        bool: True если успешно
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE feedback_requests
            SET status = 'sent',
                sent_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (request_id,))

        conn.commit()
        conn.close()

        return True

    except Exception as e:
        logger.error(f"Ошибка обновления статуса запроса отзыва: {e}")
        return False


def get_feedback_statistics() -> dict:
    """
    Получить статистику по запросам отзывов.

    Returns:
        dict: Статистика отправленных запросов
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM feedback_requests WHERE status = "pending"')
        pending = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM feedback_requests WHERE status = "sent"')
        sent = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM feedback_requests WHERE scheduled_date <= date("now") AND status = "pending"')
        ready_to_send = cursor.fetchone()[0]

        conn.close()

        return {
            'pending': pending,
            'sent': sent,
            'ready_to_send': ready_to_send
        }

    except Exception as e:
        logger.error(f"Ошибка получения статистики отзывов: {e}")
        return {'pending': 0, 'sent': 0, 'ready_to_send': 0}


# =================================================================
# РАБОТА С UTM-МЕТКАМИ И ИСТОЧНИКАМИ ПРИВЛЕЧЕНИЯ
# =================================================================

def save_user_utm(user_id: int, utm_params: dict):
    """
    Сохранить UTM-метки пользователя при регистрации.

    Args:
        user_id: ID пользователя
        utm_params: Словарь с UTM-параметрами
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE users
            SET utm_source = ?,
                utm_medium = ?,
                utm_campaign = ?,
                utm_content = ?,
                utm_term = ?,
                source_type = ?
            WHERE user_id = ?
        ''', (
            utm_params.get('utm_source'),
            utm_params.get('utm_medium'),
            utm_params.get('utm_campaign'),
            utm_params.get('utm_content'),
            utm_params.get('utm_term'),
            utm_params.get('source_type', 'utm'),
            user_id
        ))

        conn.commit()
        conn.close()
        logger.info(f"UTM-метки сохранены для пользователя {user_id}")

    except Exception as e:
        logger.error(f"Ошибка сохранения UTM-меток: {e}")


def create_utm_campaign(name: str, utm_source: str, utm_medium: str = None,
                       utm_campaign: str = None, utm_content: str = None,
                       utm_term: str = None) -> Optional[str]:
    """
    Создать UTM-кампанию и сгенерировать ссылку.

    Args:
        name: Название кампании
        utm_source: Источник (instagram, vk, google, etc.)
        utm_medium: Медиум (cpc, banner, email, etc.)
        utm_campaign: Название кампании
        utm_content: Контент/вариант объявления
        utm_term: Поисковый запрос

    Returns:
        str: Сгенерированная ссылка или None
    """
    try:
        from config import TELEGRAM_BOT_TOKEN
        import asyncio
        from telegram import Bot

        # Получить имя бота асинхронно
        async def get_bot_username():
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            bot_info = await bot.get_me()
            return bot_info.username

        try:
            loop = asyncio.get_event_loop()
            bot_username = loop.run_until_complete(get_bot_username())
        except RuntimeError:
            # Если event loop уже запущен, создаем новый
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            bot_username = loop.run_until_complete(get_bot_username())

        # Создать deep link с UTM-параметрами
        # Формат: utm_source__medium__campaign__content__term
        utm_code = f"{utm_source or ''}__{utm_medium or ''}__{utm_campaign or ''}__{utm_content or ''}__{utm_term or ''}".replace(' ', '_')

        generated_link = f"https://t.me/{bot_username}?start=utm_{utm_code}"

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO utm_campaigns
            (name, utm_source, utm_medium, utm_campaign, utm_content, utm_term, generated_link)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, utm_source, utm_medium, utm_campaign, utm_content, utm_term, generated_link))

        conn.commit()
        conn.close()

        logger.info(f"UTM-кампания '{name}' создана: {generated_link}")
        return generated_link

    except Exception as e:
        logger.error(f"Ошибка создания UTM-кампании: {e}")
        return None


def parse_utm_from_start_param(start_param: str) -> dict:
    """
    Распарсить UTM-параметры из /start параметра.

    Args:
        start_param: Параметр команды /start

    Returns:
        dict: Словарь с UTM-параметрами
    """
    utm_params = {
        'source_type': 'organic',
        'utm_source': None,
        'utm_medium': None,
        'utm_campaign': None,
        'utm_content': None,
        'utm_term': None
    }

    try:
        if not start_param:
            return utm_params

        # Реферальная ссылка (формат: REF123456)
        if start_param.startswith('REF'):
            utm_params['source_type'] = 'referral'
            utm_params['utm_source'] = 'referral'
            utm_params['utm_content'] = start_param
            return utm_params

        # UTM-метки (формат: utm_source__medium__campaign__content__term)
        if start_param.startswith('utm_'):
            utm_params['source_type'] = 'utm'
            parts = start_param.replace('utm_', '').split('__')

            if len(parts) >= 1 and parts[0]:
                utm_params['utm_source'] = parts[0]
            if len(parts) >= 2 and parts[1]:
                utm_params['utm_medium'] = parts[1]
            if len(parts) >= 3 and parts[2]:
                utm_params['utm_campaign'] = parts[2]
            if len(parts) >= 4 and parts[3]:
                utm_params['utm_content'] = parts[3]
            if len(parts) >= 5 and parts[4]:
                utm_params['utm_term'] = parts[4]

            # Обновить статистику кампании
            update_utm_campaign_stats(start_param, 'click')

        return utm_params

    except Exception as e:
        logger.error(f"Ошибка парсинга UTM: {e}")
        return utm_params


def update_utm_campaign_stats(utm_code: str, stat_type: str, amount: int = 1):
    """
    Обновить статистику UTM-кампании.

    Args:
        utm_code: Код UTM-кампании
        stat_type: Тип статистики (click, registration, conversion)
        amount: Значение для revenue
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Восстановить полный код
        if not utm_code.startswith('utm_'):
            utm_code = f'utm_{utm_code}'

        generated_link_pattern = f'%{utm_code}'

        if stat_type == 'click':
            cursor.execute('''
                UPDATE utm_campaigns
                SET clicks = clicks + 1
                WHERE generated_link LIKE ?
            ''', (generated_link_pattern,))
        elif stat_type == 'registration':
            cursor.execute('''
                UPDATE utm_campaigns
                SET registrations = registrations + 1
                WHERE generated_link LIKE ?
            ''', (generated_link_pattern,))
        elif stat_type == 'conversion':
            cursor.execute('''
                UPDATE utm_campaigns
                SET conversions = conversions + 1,
                    revenue = revenue + ?
                WHERE generated_link LIKE ?
            ''', (amount, generated_link_pattern))

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"Ошибка обновления статистики UTM: {e}")


def get_utm_campaigns() -> List[dict]:
    """Получить список UTM-кампаний."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, name, utm_source, utm_medium, utm_campaign, utm_content, utm_term,
                   generated_link, clicks, registrations, conversions, revenue, active, created_at
            FROM utm_campaigns
            ORDER BY created_at DESC
        ''')

        rows = cursor.fetchall()
        conn.close()

        campaigns = []
        for row in rows:
            campaigns.append({
                'id': row[0],
                'name': row[1],
                'utm_source': row[2],
                'utm_medium': row[3],
                'utm_campaign': row[4],
                'utm_content': row[5],
                'utm_term': row[6],
                'generated_link': row[7],
                'clicks': row[8],
                'registrations': row[9],
                'conversions': row[10],
                'revenue': row[11],
                'active': row[12],
                'created_at': row[13]
            })

        return campaigns

    except Exception as e:
        logger.error(f"Ошибка получения UTM-кампаний: {e}")
        return []


def toggle_utm_campaign(campaign_id: int) -> bool:
    """
    Переключить активность UTM-кампании.

    Args:
        campaign_id: ID кампании

    Returns:
        bool: True если успешно
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE utm_campaigns
            SET active = NOT active
            WHERE id = ?
        ''', (campaign_id,))

        conn.commit()
        conn.close()

        logger.info(f"UTM-кампания {campaign_id} переключена")
        return True

    except Exception as e:
        logger.error(f"Ошибка переключения UTM-кампании: {e}")
        return False


# =================================================================
# РАБОТА С РЕФЕРАЛЬНОЙ ПРОГРАММОЙ
# =================================================================

def get_referral_settings() -> dict:
    """Получить настройки реферальной программы."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM referral_settings WHERE id = 1')
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'enabled': bool(row[1]),
                'reward_type': row[2],
                'reward_amount': row[3],
                'reward_percent': row[4],
                'min_order_amount': row[5],
                'max_reward_amount': row[6],
                'reward_on_first_order_only': bool(row[7]),
                'auto_approve': bool(row[8])
            }
        return {}

    except Exception as e:
        logger.error(f"Ошибка получения настроек реферальной программы: {e}")
        return {}


def update_referral_settings(**settings):
    """Обновить настройки реферальной программы."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Построить SQL динамически
        set_clause = ', '.join([f"{key} = ?" for key in settings.keys()])
        values = list(settings.values())

        cursor.execute(f'''
            UPDATE referral_settings
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        ''', values)

        conn.commit()
        conn.close()
        logger.info("Настройки реферальной программы обновлены")

    except Exception as e:
        logger.error(f"Ошибка обновления настроек реферальной программы: {e}")


def check_and_award_referral_bonus(order_id: int, user_id: int, order_amount: int):
    """
    Проверить и начислить реферальный бонус.

    Args:
        order_id: ID заказа
        user_id: ID пользователя, совершившего заказ
        order_amount: Сумма заказа
    """
    try:
        # Получить настройки
        settings = get_referral_settings()
        if not settings or not settings.get('enabled'):
            return

        # Проверить минимальную сумму
        if order_amount < settings['min_order_amount']:
            return

        conn = get_connection()
        cursor = conn.cursor()

        # Получить того, кто пригласил
        cursor.execute('SELECT referred_by FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if not result or not result[0]:
            conn.close()
            return

        referrer_id = result[0]

        # Проверить, был ли уже начислен бонус (если настроено только за первый заказ)
        if settings['reward_on_first_order_only']:
            cursor.execute('''
                SELECT COUNT(*) FROM referral_rewards
                WHERE referred_user_id = ? AND status IN ('pending', 'approved')
            ''', (user_id,))

            if cursor.fetchone()[0] > 0:
                conn.close()
                return

        # Рассчитать сумму награды
        if settings['reward_type'] == 'fixed':
            reward_amount = settings['reward_amount']
        else:  # percent
            reward_amount = int(order_amount * settings['reward_percent'] / 100)
            if reward_amount > settings['max_reward_amount']:
                reward_amount = settings['max_reward_amount']

        # Создать запись о награде
        cursor.execute('''
            INSERT INTO referral_rewards
            (referrer_user_id, referred_user_id, reward_type, reward_amount,
             trigger_order_id, trigger_order_amount, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            referrer_id, user_id, settings['reward_type'], reward_amount,
            order_id, order_amount,
            'approved' if settings['auto_approve'] else 'pending'
        ))

        # Если автоматическое одобрение - начислить бонусы сразу
        if settings['auto_approve']:
            add_bonus_points(
                referrer_id,
                reward_amount,
                f"Реферальный бонус за приглашение пользователя (заказ #{order_id})"
            )
            cursor.execute('''
                UPDATE referral_rewards
                SET paid_at = CURRENT_TIMESTAMP
                WHERE referrer_user_id = ? AND referred_user_id = ? AND trigger_order_id = ?
            ''', (referrer_id, user_id, order_id))

        conn.commit()
        conn.close()

        logger.info(f"Реферальный бонус {reward_amount} создан для пользователя {referrer_id}")

    except Exception as e:
        logger.error(f"Ошибка проверки реферального бонуса: {e}")


def get_referral_rewards(user_id: int = None, status: str = None) -> List[dict]:
    """
    Получить список реферальных наград.

    Args:
        user_id: Фильтр по рефереру
        status: Фильтр по статусу (pending, approved, rejected)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = '''
            SELECT r.id, r.referrer_user_id, r.referred_user_id, r.reward_type,
                   r.reward_amount, r.trigger_order_id, r.trigger_order_amount,
                   r.status, r.created_at, r.paid_at,
                   u1.first_name as referrer_name, u2.first_name as referred_name
            FROM referral_rewards r
            LEFT JOIN users u1 ON r.referrer_user_id = u1.user_id
            LEFT JOIN users u2 ON r.referred_user_id = u2.user_id
            WHERE 1=1
        '''
        params = []

        if user_id:
            query += ' AND r.referrer_user_id = ?'
            params.append(user_id)

        if status:
            query += ' AND r.status = ?'
            params.append(status)

        query += ' ORDER BY r.created_at DESC'

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        rewards = []
        for row in rows:
            rewards.append({
                'id': row[0],
                'referrer_user_id': row[1],
                'referred_user_id': row[2],
                'reward_type': row[3],
                'reward_amount': row[4],
                'trigger_order_id': row[5],
                'trigger_order_amount': row[6],
                'status': row[7],
                'created_at': row[8],
                'paid_at': row[9],
                'referrer_name': row[10],
                'referred_name': row[11]
            })

        return rewards

    except Exception as e:
        logger.error(f"Ошибка получения реферальных наград: {e}")
        return []


def approve_referral_reward(reward_id: int) -> bool:
    """Одобрить и выплатить реферальную награду."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Получить данные награды
        cursor.execute('SELECT referrer_user_id, reward_amount, status FROM referral_rewards WHERE id = ?', (reward_id,))
        result = cursor.fetchone()

        if not result or result[2] != 'pending':
            conn.close()
            return False

        referrer_id, amount, _ = result

        # Начислить бонусы
        add_bonus_points(referrer_id, amount, f"Реферальный бонус (награда #{reward_id})")

        # Обновить статус
        cursor.execute('''
            UPDATE referral_rewards
            SET status = 'approved', paid_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (reward_id,))

        conn.commit()
        conn.close()

        logger.info(f"Реферальная награда #{reward_id} одобрена и выплачена")
        return True

    except Exception as e:
        logger.error(f"Ошибка одобрения реферальной награды: {e}")
        return False


def reject_referral_reward(reward_id: int) -> bool:
    """Отклонить реферальную награду."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE referral_rewards
            SET status = 'rejected'
            WHERE id = ? AND status = 'pending'
        ''', (reward_id,))

        conn.commit()
        success = cursor.rowcount > 0
        conn.close()

        if success:
            logger.info(f"Реферальная награда #{reward_id} отклонена")
        return success

    except Exception as e:
        logger.error(f"Ошибка отклонения реферальной награды: {e}")
        return False


def get_user_acquisition_sources() -> dict:
    """Получить статистику по источникам привлечения."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Статистика по source_type
        cursor.execute('''
            SELECT source_type, COUNT(*) as count
            FROM users
            WHERE source_type IS NOT NULL
            GROUP BY source_type
            ORDER BY count DESC
        ''')

        source_types = {}
        for row in cursor.fetchall():
            source_types[row[0] or 'organic'] = row[1]

        # Статистика по utm_source
        cursor.execute('''
            SELECT utm_source, COUNT(*) as count
            FROM users
            WHERE utm_source IS NOT NULL
            GROUP BY utm_source
            ORDER BY count DESC
        ''')

        utm_sources = {}
        for row in cursor.fetchall():
            utm_sources[row[0]] = row[1]

        # Статистика по utm_campaign
        cursor.execute('''
            SELECT utm_campaign, COUNT(*) as count
            FROM users
            WHERE utm_campaign IS NOT NULL
            GROUP BY utm_campaign
            ORDER BY count DESC
        ''')

        campaigns = {}
        for row in cursor.fetchall():
            campaigns[row[0]] = row[1]

        # Реферальная статистика
        cursor.execute('''
            SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL
        ''')
        referrals_count = cursor.fetchone()[0]

        cursor.execute('''
            SELECT COUNT(DISTINCT referrer_user_id) FROM referral_rewards
        ''')
        active_referrers = cursor.fetchone()[0]

        conn.close()

        return {
            'source_types': source_types,
            'utm_sources': utm_sources,
            'campaigns': campaigns,
            'referrals_count': referrals_count,
            'active_referrers': active_referrers
        }

    except Exception as e:
        logger.error(f"Ошибка получения статистики источников: {e}")
        return {}


# ============================================================================
# ПОДПИСКИ И КАРТЫ
# ============================================================================

def get_subscription_plans(active_only=True):
    """Получить список тарифных планов"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if active_only:
            cursor.execute('SELECT * FROM subscription_plans WHERE active = 1 ORDER BY price')
        else:
            cursor.execute('SELECT * FROM subscription_plans ORDER BY price')

        plans = cursor.fetchall()
        conn.close()

        return [
            {
                'id': p[0],
                'name': p[1],
                'description': p[2],
                'type': p[3],
                'price': p[4],
                'duration_months': p[5],
                'benefits': p[6],
                'monthly_flowers_included': p[7],
                'monthly_service_included': p[8],
                'service_discount_percent': p[9],
                'flower_discount_percent': p[10],
                'active': p[11]
            }
            for p in plans
        ]

    except Exception as e:
        logger.error(f"Ошибка получения планов подписок: {e}")
        return []


def get_user_active_subscription(user_id: int):
    """Получить активную подписку пользователя"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT us.*, sp.name, sp.type, sp.monthly_flowers_included,
                   sp.monthly_service_included, sp.service_discount_percent, sp.flower_discount_percent
            FROM user_subscriptions us
            JOIN subscription_plans sp ON us.plan_id = sp.id
            WHERE us.user_id = ? AND us.status = 'active' AND us.end_date >= date('now')
            ORDER BY us.end_date DESC
            LIMIT 1
        ''', (user_id,))

        sub = cursor.fetchone()
        conn.close()

        if not sub:
            return None

        return {
            'id': sub[0],
            'user_id': sub[1],
            'plan_id': sub[2],
            'start_date': sub[3],
            'end_date': sub[4],
            'status': sub[5],
            'flowers_used_this_month': sub[6],
            'service_used_this_month': sub[7],
            'last_benefit_reset': sub[8],
            'payment_amount': sub[9],
            'plan_name': sub[11],
            'plan_type': sub[12],
            'monthly_flowers_included': sub[13],
            'monthly_service_included': sub[14],
            'service_discount_percent': sub[15],
            'flower_discount_percent': sub[16]
        }

    except Exception as e:
        logger.error(f"Ошибка получения подписки: {e}")
        return None


def create_user_subscription(user_id: int, plan_id: int, payment_amount: int):
    """Создать подписку для пользователя"""
    try:
        from datetime import datetime, timedelta

        conn = get_connection()
        cursor = conn.cursor()

        # Получить информацию о плане
        cursor.execute('SELECT duration_months FROM subscription_plans WHERE id = ?', (plan_id,))
        plan = cursor.fetchone()

        if not plan:
            conn.close()
            return None

        duration_months = plan[0]
        start_date = datetime.now().date()

        # Для одноразовых пакетов (duration_months=0) срок действия 1 день
        if duration_months == 0:
            end_date = start_date
        else:
            # Приблизительный расчёт (30 дней в месяце)
            end_date = start_date + timedelta(days=duration_months * 30)

        cursor.execute('''
            INSERT INTO user_subscriptions
            (user_id, plan_id, start_date, end_date, status, payment_amount, last_benefit_reset)
            VALUES (?, ?, ?, ?, 'active', ?, ?)
        ''', (user_id, plan_id, start_date, end_date, payment_amount, start_date))

        subscription_id = cursor.lastrowid

        conn.commit()
        conn.close()

        logger.info(f"Создана подписка {subscription_id} для пользователя {user_id}")
        return subscription_id

    except Exception as e:
        logger.error(f"Ошибка создания подписки: {e}")
        return None


def use_subscription_flower(user_id: int):
    """Использовать букет из подписки"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Получить активную подписку
        sub = get_user_active_subscription(user_id)

        if not sub:
            conn.close()
            return False

        # Проверить, есть ли доступные букеты
        if sub['flowers_used_this_month'] >= sub['monthly_flowers_included']:
            conn.close()
            return False

        # Увеличить счётчик использования
        cursor.execute('''
            UPDATE user_subscriptions
            SET flowers_used_this_month = flowers_used_this_month + 1
            WHERE id = ?
        ''', (sub['id'],))

        # Записать использование
        cursor.execute('''
            INSERT INTO subscription_usage (subscription_id, user_id, usage_type)
            VALUES (?, ?, 'flower')
        ''', (sub['id'], user_id))

        conn.commit()
        conn.close()

        logger.info(f"Пользователь {user_id} использовал букет из подписки {sub['id']}")
        return True

    except Exception as e:
        logger.error(f"Ошибка использования букета: {e}")
        return False


def use_subscription_service(user_id: int):
    """Использовать услугу из подписки"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Получить активную подписку
        sub = get_user_active_subscription(user_id)

        if not sub:
            conn.close()
            return False

        # Проверить, включена ли услуга и не использована ли уже
        if not sub['monthly_service_included'] or sub['service_used_this_month']:
            conn.close()
            return False

        # Отметить услугу как использованную
        cursor.execute('''
            UPDATE user_subscriptions
            SET service_used_this_month = TRUE
            WHERE id = ?
        ''', (sub['id'],))

        # Записать использование
        cursor.execute('''
            INSERT INTO subscription_usage (subscription_id, user_id, usage_type)
            VALUES (?, ?, 'service')
        ''', (sub['id'], user_id))

        conn.commit()
        conn.close()

        logger.info(f"Пользователь {user_id} использовал услугу из подписки {sub['id']}")
        return True

    except Exception as e:
        logger.error(f"Ошибка использования услуги: {e}")
        return False


def reset_monthly_benefits():
    """Сбросить месячные лимиты подписок (запускать каждый месяц)"""
    try:
        from datetime import datetime

        conn = get_connection()
        cursor = conn.cursor()

        today = datetime.now().date()

        cursor.execute('''
            UPDATE user_subscriptions
            SET flowers_used_this_month = 0,
                service_used_this_month = FALSE,
                last_benefit_reset = ?
            WHERE status = 'active'
              AND (last_benefit_reset IS NULL
                   OR (julianday(?) - julianday(last_benefit_reset)) >= 30)
        ''', (today, today))

        rows_affected = cursor.rowcount

        conn.commit()
        conn.close()

        logger.info(f"Сброшены лимиты для {rows_affected} подписок")
        return rows_affected

    except Exception as e:
        logger.error(f"Ошибка сброса лимитов: {e}")
        return 0


def get_subscription_stats():
    """Получить статистику по подпискам"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Общая статистика
        cursor.execute('''
            SELECT
                COUNT(*) as total_active,
                SUM(payment_amount) as total_revenue
            FROM user_subscriptions
            WHERE status = 'active'
        ''')
        total_stats = cursor.fetchone()

        # По типам планов
        cursor.execute('''
            SELECT
                sp.name,
                sp.type,
                COUNT(us.id) as count,
                SUM(us.payment_amount) as revenue
            FROM user_subscriptions us
            JOIN subscription_plans sp ON us.plan_id = sp.id
            WHERE us.status = 'active'
            GROUP BY sp.id
            ORDER BY revenue DESC
        ''')
        by_plan = cursor.fetchall()

        conn.close()

        return {
            'total_active': total_stats[0] or 0,
            'total_revenue': total_stats[1] or 0,
            'by_plan': [
                {
                    'name': p[0],
                    'type': p[1],
                    'count': p[2],
                    'revenue': p[3]
                }
                for p in by_plan
            ]
        }

    except Exception as e:
        logger.error(f"Ошибка получения статистики подписок: {e}")
        return {'total_active': 0, 'total_revenue': 0, 'by_plan': []}


# ====================================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С МАСТЕРАМИ
# ====================================================================

def get_all_masters(active_only=True):
    """Получить список всех мастеров"""
    conn = get_connection()
    cursor = conn.cursor()

    if active_only:
        cursor.execute('''
            SELECT id, name, phone, specialization, photo_url, description, color, active
            FROM masters
            WHERE active = TRUE
            ORDER BY name
        ''')
    else:
        cursor.execute('''
            SELECT id, name, phone, specialization, photo_url, description, color, active
            FROM masters
            ORDER BY name
        ''')

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            'id': row[0],
            'name': row[1],
            'phone': row[2],
            'specialization': row[3],
            'photo_url': row[4],
            'description': row[5],
            'color': row[6],
            'active': row[7]
        }
        for row in rows
    ]


def get_master_by_id(master_id: int):
    """Получить мастера по ID"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, name, phone, specialization, photo_url, description, color, active
        FROM masters
        WHERE id = ?
    ''', (master_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            'id': row[0],
            'name': row[1],
            'phone': row[2],
            'specialization': row[3],
            'photo_url': row[4],
            'description': row[5],
            'color': row[6],
            'active': row[7]
        }
    return None


def add_master(name: str, phone: str = None, specialization: str = None,
               photo_url: str = None, description: str = None, color: str = '#3498db'):
    """Добавить нового мастера"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO masters (name, phone, specialization, photo_url, description, color, active)
        VALUES (?, ?, ?, ?, ?, ?, TRUE)
    ''', (name, phone, specialization, photo_url, description, color))

    master_id = cursor.lastrowid
    conn.commit()
    conn.close()

    logger.info(f"Добавлен мастер: {name} (ID: {master_id})")
    return master_id


def update_master(master_id: int, name: str = None, phone: str = None,
                  specialization: str = None, photo_url: str = None,
                  description: str = None, color: str = None, active: bool = None):
    """Обновить данные мастера"""
    conn = get_connection()
    cursor = conn.cursor()

    fields = []
    values = []

    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if phone is not None:
        fields.append("phone = ?")
        values.append(phone)
    if specialization is not None:
        fields.append("specialization = ?")
        values.append(specialization)
    if photo_url is not None:
        fields.append("photo_url = ?")
        values.append(photo_url)
    if description is not None:
        fields.append("description = ?")
        values.append(description)
    if color is not None:
        fields.append("color = ?")
        values.append(color)
    if active is not None:
        fields.append("active = ?")
        values.append(active)

    if not fields:
        return False

    values.append(master_id)
    query = f"UPDATE masters SET {', '.join(fields)} WHERE id = ?"

    cursor.execute(query, values)
    conn.commit()
    conn.close()

    logger.info(f"Обновлен мастер ID: {master_id}")
    return True


def delete_master(master_id: int):
    """Деактивировать мастера"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('UPDATE masters SET active = FALSE WHERE id = ?', (master_id,))
    conn.commit()
    conn.close()

    logger.info(f"Деактивирован мастер ID: {master_id}")


def get_master_schedule(master_id: int, date_from: str = None, date_to: str = None):
    """Получить график работы мастера"""
    conn = get_connection()
    cursor = conn.cursor()

    if date_from and date_to:
        cursor.execute('''
            SELECT id, master_id, work_date, start_time, end_time, is_day_off, note
            FROM master_schedules
            WHERE master_id = ? AND work_date BETWEEN ? AND ?
            ORDER BY work_date
        ''', (master_id, date_from, date_to))
    elif date_from:
        cursor.execute('''
            SELECT id, master_id, work_date, start_time, end_time, is_day_off, note
            FROM master_schedules
            WHERE master_id = ? AND work_date >= ?
            ORDER BY work_date
        ''', (master_id, date_from))
    else:
        cursor.execute('''
            SELECT id, master_id, work_date, start_time, end_time, is_day_off, note
            FROM master_schedules
            WHERE master_id = ?
            ORDER BY work_date
        ''', (master_id,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            'id': row[0],
            'master_id': row[1],
            'work_date': row[2],
            'start_time': row[3],
            'end_time': row[4],
            'is_day_off': row[5],
            'note': row[6]
        }
        for row in rows
    ]


def set_master_schedule(master_id: int, work_date: str, start_time: str,
                        end_time: str, is_day_off: bool = False, note: str = None):
    """Установить график работы мастера на дату"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO master_schedules (master_id, work_date, start_time, end_time, is_day_off, note)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (master_id, work_date, start_time, end_time, is_day_off, note))
    except sqlite3.IntegrityError:
        # Если запись уже существует, обновляем
        cursor.execute('''
            UPDATE master_schedules
            SET start_time = ?, end_time = ?, is_day_off = ?, note = ?
            WHERE master_id = ? AND work_date = ?
        ''', (start_time, end_time, is_day_off, note, master_id, work_date))

    conn.commit()
    conn.close()

    logger.info(f"Установлен график для мастера {master_id} на {work_date}")
    return True


def get_master_appointments(master_id: int, date: str):
    """Получить записи мастера на дату"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            id, user_id, user_name, phone, service_id, service_name,
            appointment_date, time_slot, status, duration_minutes, price, comment
        FROM salon_appointments
        WHERE master_id = ? AND appointment_date = ?
        ORDER BY time_slot
    ''', (master_id, date))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            'id': row[0],
            'user_id': row[1],
            'user_name': row[2],
            'phone': row[3],
            'service_id': row[4],
            'service_name': row[5],
            'appointment_date': row[6],
            'time_slot': row[7],
            'status': row[8],
            'duration_minutes': row[9] or 60,
            'price': row[10] or 0,
            'comment': row[11]
        }
        for row in rows
    ]


def get_all_appointments_by_date(date: str):
    """Получить все записи на дату с информацией о мастерах"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            sa.id, sa.user_id, sa.user_name, sa.phone,
            sa.service_id, sa.service_name, sa.appointment_date, sa.time_slot,
            sa.status, sa.duration_minutes, sa.price, sa.comment,
            sa.master_id, sa.master_name,
            m.color as master_color
        FROM salon_appointments sa
        LEFT JOIN masters m ON sa.master_id = m.id
        WHERE sa.appointment_date = ?
        ORDER BY sa.time_slot, sa.master_id
    ''', (date,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            'id': row[0],
            'user_id': row[1],
            'user_name': row[2],
            'phone': row[3],
            'service_id': row[4],
            'service_name': row[5],
            'appointment_date': row[6],
            'time_slot': row[7],
            'status': row[8],
            'duration_minutes': row[9] or 60,
            'price': row[10] or 0,
            'comment': row[11],
            'master_id': row[12],
            'master_name': row[13],
            'master_color': row[14] or '#3498db'
        }
        for row in rows
    ]


def assign_master_to_appointment(appointment_id: int, master_id: int, send_notification: bool = False):
    """Назначить мастера на запись"""
    conn = get_connection()
    cursor = conn.cursor()

    # Получить старую запись для уведомления
    cursor.execute('''
        SELECT user_id, master_name, appointment_date, time_slot, service_name
        FROM salon_appointments
        WHERE id = ?
    ''', (appointment_id,))
    old_data = cursor.fetchone()

    # Получить имя нового мастера
    cursor.execute('SELECT name FROM masters WHERE id = ?', (master_id,))
    master = cursor.fetchone()

    if not master:
        conn.close()
        return False

    new_master_name = master[0]

    cursor.execute('''
        UPDATE salon_appointments
        SET master_id = ?, master_name = ?
        WHERE id = ?
    ''', (master_id, new_master_name, appointment_id))

    conn.commit()
    conn.close()

    logger.info(f"Мастер {new_master_name} назначен на запись {appointment_id}")

    # Отправить уведомление ПОСЛЕ закрытия соединения с БД
    if send_notification and old_data:
        user_id, old_master_name, appt_date, time_slot, service_name = old_data
        if old_master_name and old_master_name != new_master_name:
            try:
                from config import TELEGRAM_BOT_TOKEN
                from telegram import Bot
                import asyncio

                bot = Bot(token=TELEGRAM_BOT_TOKEN)
                message = (
                    f"⚠️ <b>Изменение в вашей записи</b>\n\n"
                    f"📅 Дата: {appt_date}\n"
                    f"⏰ Время: {time_slot}\n"
                    f"💅 Услуга: {service_name}\n\n"
                    f"Мастер изменен:\n"
                    f"❌ Было: {old_master_name}\n"
                    f"✅ Стало: {new_master_name}\n\n"
                    f"Приносим извинения за неудобства!"
                )
                asyncio.run(bot.send_message(chat_id=user_id, text=message, parse_mode='HTML'))
                logger.info(f"Уведомление о смене мастера отправлено пользователю {user_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления о смене мастера: {e}")

    return True


def get_master_future_appointments(master_id: int):
    """Получить все будущие записи мастера (начиная с сегодня)"""
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            id, user_id, user_name, phone, service_id, service_name,
            appointment_date, time_slot, status, duration_minutes, price, comment
        FROM salon_appointments
        WHERE master_id = ? AND appointment_date >= ? AND status IN ('pending', 'confirmed')
        ORDER BY appointment_date, time_slot
    ''', (master_id, today))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            'id': row[0],
            'user_id': row[1],
            'user_name': row[2],
            'phone': row[3],
            'service_id': row[4],
            'service_name': row[5],
            'appointment_date': row[6],
            'time_slot': row[7],
            'status': row[8],
            'duration_minutes': row[9] or 60,
            'price': row[10] or 0,
            'comment': row[11]
        }
        for row in rows
    ]


def reassign_master_appointments(old_master_id: int, new_master_id: int, appointment_ids: list = None):
    """
    Перераспределить записи с одного мастера на другого

    Args:
        old_master_id: ID старого мастера
        new_master_id: ID нового мастера
        appointment_ids: Список ID записей для перераспределения (если None - все будущие)

    Returns:
        int: Количество перераспределенных записей
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Получить имя нового мастера
    cursor.execute('SELECT name FROM masters WHERE id = ?', (new_master_id,))
    master = cursor.fetchone()

    if not master:
        conn.close()
        return 0

    new_master_name = master[0]

    # Если указаны конкретные ID записей
    if appointment_ids:
        placeholders = ','.join('?' * len(appointment_ids))
        query = f'''
            SELECT id, user_id, master_name, appointment_date, time_slot, service_name
            FROM salon_appointments
            WHERE id IN ({placeholders}) AND master_id = ?
        '''
        cursor.execute(query, appointment_ids + [old_master_id])
    else:
        # Все будущие записи
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT id, user_id, master_name, appointment_date, time_slot, service_name
            FROM salon_appointments
            WHERE master_id = ? AND appointment_date >= ? AND status IN ('pending', 'confirmed')
        ''', (old_master_id, today))

    appointments = cursor.fetchall()

    if not appointments:
        conn.close()
        return 0

    # Сохранить данные для уведомлений
    notifications = []
    count = 0

    # Обновить записи в базе данных
    for appt in appointments:
        appt_id, user_id, old_master_name, appt_date, time_slot, service_name = appt

        cursor.execute('''
            UPDATE salon_appointments
            SET master_id = ?, master_name = ?
            WHERE id = ?
        ''', (new_master_id, new_master_name, appt_id))

        count += 1

        # Сохранить данные для уведомления
        notifications.append({
            'user_id': user_id,
            'old_master_name': old_master_name,
            'new_master_name': new_master_name,
            'appt_date': appt_date,
            'time_slot': time_slot,
            'service_name': service_name
        })

    conn.commit()
    conn.close()

    logger.info(f"Перераспределено {count} записей с мастера {old_master_id} на мастера {new_master_id}")

    # Отправить уведомления ПОСЛЕ закрытия соединения с БД
    for notif in notifications:
        try:
            from config import TELEGRAM_BOT_TOKEN
            from telegram import Bot
            import asyncio

            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            message = (
                f"⚠️ <b>Изменение в вашей записи</b>\n\n"
                f"📅 Дата: {notif['appt_date']}\n"
                f"⏰ Время: {notif['time_slot']}\n"
                f"💅 Услуга: {notif['service_name']}\n\n"
                f"Мастер изменен:\n"
                f"❌ Было: {notif['old_master_name']}\n"
                f"✅ Стало: {notif['new_master_name']}\n\n"
                f"Приносим извинения за неудобства!"
            )
            asyncio.run(bot.send_message(chat_id=notif['user_id'], text=message, parse_mode='HTML'))
            logger.info(f"Уведомление о смене мастера отправлено пользователю {notif['user_id']}")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о смене мастера: {e}")

    return count


# =================================================================
# РАБОТА С ПЛАТЕЖАМИ
# =================================================================

def create_payment_record(order_id: str, order_type: str, user_id: int,
                         amount: int, provider: str, payment_method: str = None,
                         payment_id: str = None, payment_url: str = None,
                         metadata: dict = None) -> int:
    """
    Создать запись о платеже

    Args:
        order_id: ID заказа
        order_type: Тип заказа (flower_order, salon_appointment, subscription)
        user_id: ID пользователя
        amount: Сумма в копейках
        provider: Платежный провайдер
        payment_method: Способ оплаты
        payment_id: ID платежа в системе провайдера
        payment_url: URL для оплаты
        metadata: Дополнительные данные (JSON)

    Returns:
        int: ID созданной записи
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        metadata_json = json.dumps(metadata) if metadata else None

        cursor.execute('''
            INSERT INTO payments
            (order_id, order_type, user_id, amount, provider, payment_method,
             payment_id, payment_url, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (order_id, order_type, user_id, amount, provider, payment_method,
              payment_id, payment_url, metadata_json))

        payment_record_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Payment record created: #{payment_record_id} for {order_type} {order_id}")
        return payment_record_id

    except Exception as e:
        logger.error(f"Error creating payment record: {e}")
        return 0


def update_payment_status(payment_record_id: int, status: str,
                         payment_id: str = None) -> bool:
    """
    Обновить статус платежа

    Args:
        payment_record_id: ID записи платежа
        status: Новый статус
        payment_id: ID платежа в системе провайдера

    Returns:
        bool: True если успешно
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if status == 'succeeded':
            cursor.execute('''
                UPDATE payments
                SET status = ?, payment_id = ?, paid_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, payment_id, payment_record_id))
        else:
            cursor.execute('''
                UPDATE payments
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, payment_record_id))

        conn.commit()
        conn.close()

        logger.info(f"Payment #{payment_record_id} status updated to {status}")
        return True

    except Exception as e:
        logger.error(f"Error updating payment status: {e}")
        return False


def get_payment_by_order(order_id: str, order_type: str) -> Optional[dict]:
    """
    Получить платеж по заказу

    Args:
        order_id: ID заказа
        order_type: Тип заказа

    Returns:
        dict or None: Данные платежа
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, order_id, order_type, user_id, amount, currency,
                   provider, payment_method, payment_id, payment_url,
                   status, paid_at, metadata, created_at
            FROM payments
            WHERE order_id = ? AND order_type = ?
            ORDER BY created_at DESC
            LIMIT 1
        ''', (order_id, order_type))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        metadata = json.loads(row[12]) if row[12] else None

        return {
            'id': row[0],
            'order_id': row[1],
            'order_type': row[2],
            'user_id': row[3],
            'amount': row[4],
            'currency': row[5],
            'provider': row[6],
            'payment_method': row[7],
            'payment_id': row[8],
            'payment_url': row[9],
            'status': row[10],
            'paid_at': row[11],
            'metadata': metadata,
            'created_at': row[13]
        }

    except Exception as e:
        logger.error(f"Error getting payment by order: {e}")
        return None


def get_payment_by_payment_id(payment_id: str) -> Optional[dict]:
    """
    Получить платеж по payment_id провайдера

    Args:
        payment_id: ID платежа в системе провайдера

    Returns:
        dict or None: Данные платежа
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, order_id, order_type, user_id, amount, currency,
                   provider, payment_method, payment_id, payment_url,
                   status, paid_at, metadata, created_at
            FROM payments
            WHERE payment_id = ?
        ''', (payment_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        metadata = json.loads(row[12]) if row[12] else None

        return {
            'id': row[0],
            'order_id': row[1],
            'order_type': row[2],
            'user_id': row[3],
            'amount': row[4],
            'currency': row[5],
            'provider': row[6],
            'payment_method': row[7],
            'payment_id': row[8],
            'payment_url': row[9],
            'status': row[10],
            'paid_at': row[11],
            'metadata': metadata,
            'created_at': row[13]
        }

    except Exception as e:
        logger.error(f"Error getting payment by payment_id: {e}")
        return None


def get_user_payments(user_id: int, limit: int = 50) -> List[dict]:
    """
    Получить платежи пользователя

    Args:
        user_id: ID пользователя
        limit: Лимит записей

    Returns:
        list: Список платежей
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, order_id, order_type, amount, currency,
                   provider, payment_method, status, paid_at, created_at
            FROM payments
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (user_id, limit))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                'id': row[0],
                'order_id': row[1],
                'order_type': row[2],
                'amount': row[3],
                'currency': row[4],
                'provider': row[5],
                'payment_method': row[6],
                'status': row[7],
                'paid_at': row[8],
                'created_at': row[9]
            }
            for row in rows
        ]

    except Exception as e:
        logger.error(f"Error getting user payments: {e}")
        return []


# Инициализировать БД при импорте модуля
if __name__ != "__main__":
    init_db()
