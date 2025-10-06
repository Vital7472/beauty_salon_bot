"""
🚨 СИСТЕМА АЛЕРТОВ И УВЕДОМЛЕНИЙ
Критические уведомления собственнику в режиме реального времени
"""

import asyncio
from datetime import datetime, timedelta
from telegram import Bot
from telegram.constants import ParseMode
from config import TELEGRAM_BOT_TOKEN, ADMIN_ID
from database import get_connection

async def send_alert(message: str, emoji: str = "⚠️"):
    """Отправить срочное уведомление собственнику"""
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        alert_text = f"{emoji} <b>СРОЧНО!</b>\n\n{message}"
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=alert_text,
            parse_mode=ParseMode.HTML
        )
        print(f"✅ Алерт отправлен: {message[:50]}...")
    except Exception as e:
        print(f"❌ Ошибка отправки алерта: {e}")


async def check_critical_alerts():
    """Проверить критические ситуации и отправить алерты"""

    conn = get_connection()
    cursor = conn.cursor()
    today = datetime.now().date()

    alerts = []

    # ========================================
    # 1. ФИНАНСОВЫЕ АЛЕРТЫ
    # ========================================

    # Выручка упала более чем на 50% по сравнению со вчера
    cursor.execute("""
        SELECT
            (SELECT COALESCE(SUM(total_amount), 0)
             FROM flower_orders
             WHERE DATE(created_at) = DATE('now', '-1 day') AND status = 'completed') as yesterday,
            (SELECT COALESCE(SUM(total_amount), 0)
             FROM flower_orders
             WHERE DATE(created_at) = DATE('now') AND status = 'completed') as today
    """)
    row = cursor.fetchone()
    if row[0] > 0 and row[1] < row[0] * 0.5:
        alerts.append({
            'emoji': '📉',
            'message': f"<b>Падение выручки!</b>\n\nВчера: {row[0]:,}₽\nСегодня: {row[1]:,}₽\nПадение: {(1 - row[1]/row[0])*100:.0f}%"
        })

    # Много неоплаченных заказов (>10 за день)
    cursor.execute("""
        SELECT COUNT(*) FROM flower_orders
        WHERE DATE(created_at) = ? AND status = 'pending'
    """, (today,))
    pending = cursor.fetchone()[0]
    if pending > 10:
        alerts.append({
            'emoji': '💸',
            'message': f"<b>Много неоплаченных заказов!</b>\n\n{pending} заказов в статусе 'ожидание'\n\nПроверьте обработку платежей."
        })

    # ========================================
    # 2. ОПЕРАЦИОННЫЕ АЛЕРТЫ
    # ========================================

    # Нет новых регистраций уже 2 дня
    cursor.execute("""
        SELECT COUNT(*) FROM users
        WHERE DATE(registration_date) >= DATE('now', '-2 days')
    """)
    if cursor.fetchone()[0] == 0:
        alerts.append({
            'emoji': '🚫',
            'message': "<b>Нет новых пользователей!</b>\n\nУже 2 дня нет регистраций.\n\nПроверьте рекламу и каналы привлечения."
        })

    # Много отмененных записей (>30% от общего числа за день)
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled
        FROM salon_appointments
        WHERE DATE(appointment_date) = ?
    """, (today,))
    row = cursor.fetchone()
    if row[0] > 0 and row[1] / row[0] > 0.3:
        alerts.append({
            'emoji': '❌',
            'message': f"<b>Высокий процент отмен!</b>\n\nОтменено: {row[1]}/{row[0]} ({row[1]/row[0]*100:.0f}%)\n\nПроверьте качество обслуживания."
        })

    # ========================================
    # 3. МАРКЕТИНГОВЫЕ АЛЕРТЫ
    # ========================================

    # Реферальная программа не работает (0 рефералов за неделю)
    cursor.execute("""
        SELECT COUNT(*) FROM users
        WHERE DATE(registration_date) >= DATE('now', '-7 days')
        AND referred_by IS NOT NULL
    """)
    if cursor.fetchone()[0] == 0:
        alerts.append({
            'emoji': '👥',
            'message': "<b>Реферальная программа не работает!</b>\n\nЗа неделю 0 регистраций по реферальным ссылкам.\n\nНапомните клиентам о программе."
        })

    # UTM-кампании не дают конверсий
    cursor.execute("""
        SELECT name FROM utm_campaigns
        WHERE clicks > 100 AND conversions = 0
        AND created_at >= DATE('now', '-7 days')
    """)
    bad_campaigns = cursor.fetchall()
    if bad_campaigns:
        campaign_names = ", ".join([c[0] for c in bad_campaigns])
        alerts.append({
            'emoji': '📢',
            'message': f"<b>Кампании без конверсий!</b>\n\n{campaign_names}\n\nЕсть клики, но нет продаж. Проверьте воронку."
        })

    # ========================================
    # 4. ПОДПИСКИ И ЛОЯЛЬНОСТЬ
    # ========================================

    # Истекающие подписки (завтра)
    cursor.execute("""
        SELECT COUNT(*) FROM user_subscriptions
        WHERE DATE(end_date) = DATE('now', '+1 day')
        AND status = 'active'
    """)
    expiring = cursor.fetchone()[0]
    if expiring > 0:
        alerts.append({
            'emoji': '💎',
            'message': f"<b>Истекают подписки!</b>\n\n{expiring} подписок истекают завтра.\n\nПредложите продление с бонусом."
        })

    # Низкий баланс бонусов у VIP-клиентов
    cursor.execute("""
        SELECT first_name, bonus_points FROM users
        WHERE user_id IN (
            SELECT user_id FROM user_subscriptions
            WHERE status = 'active'
        )
        AND bonus_points < 100
        LIMIT 5
    """)
    low_bonus_vips = cursor.fetchall()
    if low_bonus_vips:
        names = ", ".join([n[0] for n in low_bonus_vips])
        alerts.append({
            'emoji': '🎁',
            'message': f"<b>VIP без бонусов!</b>\n\n{names}\n\nПодарите бонусы для удержания."
        })

    # ========================================
    # 5. ТЕХНИЧЕСКИЕ АЛЕРТЫ
    # ========================================

    # Проверить неотправленные уведомления
    cursor.execute("""
        SELECT COUNT(*) FROM notifications_log
        WHERE status = 'failed'
        AND sent_at >= DATE('now', '-1 day')
    """)
    failed_notif = cursor.fetchone()[0]
    if failed_notif > 10:
        alerts.append({
            'emoji': '🔔',
            'message': f"<b>Проблемы с уведомлениями!</b>\n\n{failed_notif} неотправленных за день.\n\nПроверьте Telegram Bot."
        })

    conn.close()

    # Отправить все алерты
    if alerts:
        for alert in alerts:
            await send_alert(alert['message'], alert['emoji'])
    else:
        print("✅ Критических ситуаций не обнаружено")

    return len(alerts)


async def send_hourly_summary():
    """Краткая сводка каждый час (опционально)"""

    conn = get_connection()
    cursor = conn.cursor()

    # Статистика за последний час
    cursor.execute("""
        SELECT
            (SELECT COUNT(*) FROM users WHERE registration_date >= datetime('now', '-1 hour')) as new_users,
            (SELECT COUNT(*) FROM flower_orders WHERE created_at >= datetime('now', '-1 hour')) as new_orders,
            (SELECT COALESCE(SUM(total_amount), 0) FROM flower_orders
             WHERE created_at >= datetime('now', '-1 hour') AND status = 'completed') as revenue
    """)
    row = cursor.fetchone()

    if any(row):  # Если есть какая-то активность
        message = f"""
📊 <b>Сводка за последний час</b>

👥 Новых пользователей: {row[0]}
🛒 Новых заказов: {row[1]}
💰 Выручка: {row[2]:,}₽
"""
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=message,
            parse_mode=ParseMode.HTML
        )

    conn.close()


async def check_business_opportunities():
    """Поиск возможностей для роста бизнеса"""

    conn = get_connection()
    cursor = conn.cursor()

    opportunities = []

    # Клиенты, которые давно не заказывали (>30 дней)
    cursor.execute("""
        SELECT COUNT(DISTINCT u.user_id)
        FROM users u
        WHERE u.user_id NOT IN (
            SELECT user_id FROM flower_orders
            WHERE created_at >= DATE('now', '-30 days')
        )
        AND u.registration_date < DATE('now', '-30 days')
    """)
    inactive = cursor.fetchone()[0]
    if inactive > 10:
        opportunities.append(
            f"💤 {inactive} клиентов не заказывали >30 дней\n"
            f"   Запустите win-back кампанию с промокодом"
        )

    # Популярные товары заканчиваются
    cursor.execute("""
        SELECT name FROM products
        WHERE stock_quantity < 5
        AND id IN (
            SELECT json_extract(value, '$.id')
            FROM flower_orders, json_each(items_json)
            WHERE created_at >= DATE('now', '-7 days')
            GROUP BY json_extract(value, '$.id')
            HAVING COUNT(*) > 5
        )
        LIMIT 3
    """)
    low_stock = cursor.fetchall()
    if low_stock:
        products = ", ".join([p[0] for p in low_stock])
        opportunities.append(
            f"📦 Популярные товары заканчиваются: {products}\n"
            f"   Срочно пополните запас!"
        )

    # Высокий спрос на определенную услугу
    cursor.execute("""
        SELECT s.name, COUNT(*) as cnt
        FROM salon_appointments sa
        JOIN services s ON sa.service_id = s.id
        WHERE sa.appointment_date >= DATE('now', '-7 days')
        GROUP BY s.name
        HAVING cnt > 20
        ORDER BY cnt DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        opportunities.append(
            f"🔥 Высокий спрос на '{row[0]}' ({row[1]} записей/неделю)\n"
            f"   Рассмотрите повышение цены на 10-15%"
        )

    # Хорошая конверсия UTM-кампании
    cursor.execute("""
        SELECT name, conversions, clicks
        FROM utm_campaigns
        WHERE clicks > 50
        AND (conversions * 1.0 / clicks) > 0.1
        ORDER BY (conversions * 1.0 / clicks) DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        conv_rate = row[1] / row[2] * 100
        opportunities.append(
            f"📈 Отличная конверсия у '{row[0]}': {conv_rate:.1f}%\n"
            f"   Увеличьте бюджет этой кампании"
        )

    conn.close()

    if opportunities:
        message = "💡 <b>ВОЗМОЖНОСТИ ДЛЯ РОСТА</b>\n\n" + "\n\n".join(opportunities)
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=message,
            parse_mode=ParseMode.HTML
        )


def main():
    """Главная функция"""
    asyncio.run(check_critical_alerts())


if __name__ == "__main__":
    main()
