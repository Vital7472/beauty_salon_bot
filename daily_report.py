"""
📊 ЕЖЕДНЕВНЫЙ ОТЧЕТ ДЛЯ СОБСТВЕННИКА
Автоматическая отправка комплексной аналитики в Telegram
"""

import asyncio
from datetime import datetime, timedelta
from telegram import Bot
from telegram.constants import ParseMode
from config import TELEGRAM_BOT_TOKEN, ADMIN_ID
from database import get_connection

def get_daily_statistics():
    """Получить полную статистику за день"""

    conn = get_connection()
    cursor = conn.cursor()

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    stats = {
        'date': today.strftime('%d.%m.%Y'),
        'users': {},
        'revenue': {},
        'orders': {},
        'salon': {},
        'marketing': {},
        'subscriptions': {},
        'bonuses': {},
        'top_performers': {}
    }

    # =====================================================
    # 1. ПОЛЬЗОВАТЕЛИ
    # =====================================================

    # Новые регистрации за день
    cursor.execute("""
        SELECT COUNT(*) FROM users
        WHERE DATE(registration_date) = ?
    """, (today,))
    stats['users']['new_today'] = cursor.fetchone()[0]

    # Новые за вчера (для сравнения)
    cursor.execute("""
        SELECT COUNT(*) FROM users
        WHERE DATE(registration_date) = ?
    """, (yesterday,))
    stats['users']['new_yesterday'] = cursor.fetchone()[0]

    # Всего пользователей
    cursor.execute("SELECT COUNT(*) FROM users")
    stats['users']['total'] = cursor.fetchone()[0]

    # Активные пользователи (совершили действие за день)
    cursor.execute("""
        SELECT COUNT(DISTINCT user_id) FROM (
            SELECT user_id FROM salon_appointments WHERE DATE(created_at) = ?
            UNION
            SELECT user_id FROM flower_orders WHERE DATE(created_at) = ?
            UNION
            SELECT user_id FROM loyalty_transactions WHERE DATE(created_at) = ?
        )
    """, (today, today, today))
    stats['users']['active_today'] = cursor.fetchone()[0]

    # =====================================================
    # 2. ВЫРУЧКА
    # =====================================================

    # Выручка салона за день
    cursor.execute("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM salon_appointments
        WHERE DATE(appointment_date) = ? AND status IN ('completed', 'confirmed')
    """, (today,))
    stats['revenue']['salon_today'] = cursor.fetchone()[0]

    # Выручка салона вчера
    cursor.execute("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM salon_appointments
        WHERE DATE(appointment_date) = ? AND status IN ('completed', 'confirmed')
    """, (yesterday,))
    stats['revenue']['salon_yesterday'] = cursor.fetchone()[0]

    # Выручка цветов за день
    cursor.execute("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM flower_orders
        WHERE DATE(created_at) = ? AND status IN ('completed', 'paid')
    """, (today,))
    stats['revenue']['flowers_today'] = cursor.fetchone()[0]

    # Выручка цветов вчера
    cursor.execute("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM flower_orders
        WHERE DATE(created_at) = ? AND status IN ('completed', 'paid')
    """, (yesterday,))
    stats['revenue']['flowers_yesterday'] = cursor.fetchone()[0]

    # Выручка сертификатов за день
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM certificates
        WHERE DATE(created_at) = ? AND status = 'active'
    """, (today,))
    stats['revenue']['certificates_today'] = cursor.fetchone()[0]

    # Выручка подписок за день
    cursor.execute("""
        SELECT COALESCE(SUM(payment_amount), 0)
        FROM user_subscriptions
        WHERE DATE(created_at) = ?
    """, (today,))
    stats['revenue']['subscriptions_today'] = cursor.fetchone()[0]

    # Общая выручка
    stats['revenue']['total_today'] = (
        stats['revenue']['salon_today'] +
        stats['revenue']['flowers_today'] +
        stats['revenue']['certificates_today'] +
        stats['revenue']['subscriptions_today']
    )

    stats['revenue']['total_yesterday'] = (
        stats['revenue']['salon_yesterday'] +
        stats['revenue']['flowers_yesterday']
    )

    # =====================================================
    # 3. ЗАКАЗЫ
    # =====================================================

    # Заказы цветов
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled
        FROM flower_orders
        WHERE DATE(created_at) = ?
    """, (today,))
    row = cursor.fetchone()
    stats['orders']['flowers'] = {
        'total': row[0],
        'pending': row[1] or 0,
        'completed': row[2] or 0,
        'cancelled': row[3] or 0
    }

    # Средний чек цветов
    cursor.execute("""
        SELECT AVG(total_amount)
        FROM flower_orders
        WHERE DATE(created_at) = ? AND status = 'completed'
    """, (today,))
    stats['orders']['avg_flower_order'] = cursor.fetchone()[0] or 0

    # =====================================================
    # 4. САЛОН КРАСОТЫ
    # =====================================================

    # Записи в салон
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled
        FROM salon_appointments
        WHERE DATE(appointment_date) = ?
    """, (today,))
    row = cursor.fetchone()
    stats['salon']['appointments'] = {
        'total': row[0],
        'pending': row[1] or 0,
        'confirmed': row[2] or 0,
        'completed': row[3] or 0,
        'cancelled': row[4] or 0
    }

    # Средний чек салона
    cursor.execute("""
        SELECT AVG(total_amount)
        FROM salon_appointments
        WHERE DATE(appointment_date) = ? AND status = 'completed'
    """, (today,))
    stats['salon']['avg_check'] = cursor.fetchone()[0] or 0

    # Топ услуги дня
    cursor.execute("""
        SELECT s.name, COUNT(*) as cnt
        FROM salon_appointments sa
        JOIN services s ON sa.service_id = s.id
        WHERE DATE(sa.appointment_date) = ?
        GROUP BY s.name
        ORDER BY cnt DESC
        LIMIT 3
    """, (today,))
    stats['salon']['top_services'] = cursor.fetchall()

    # Загруженность (% занятых слотов)
    cursor.execute("""
        SELECT COUNT(*) FROM salon_appointments
        WHERE DATE(appointment_date) = ? AND status != 'cancelled'
    """, (today,))
    booked_slots = cursor.fetchone()[0]
    total_slots = 12 * 8  # 12 часов работы * 8 слотов в час (примерно)
    stats['salon']['occupancy'] = (booked_slots / total_slots * 100) if total_slots > 0 else 0

    # =====================================================
    # 5. МАРКЕТИНГ
    # =====================================================

    # UTM-кампании
    cursor.execute("""
        SELECT
            utm_source,
            COUNT(DISTINCT user_id) as registrations,
            SUM(conversions) as conversions,
            SUM(conversion_amount) as revenue
        FROM user_utm_tracking
        WHERE DATE(first_visit) = ?
        GROUP BY utm_source
        ORDER BY conversions DESC
        LIMIT 5
    """, (today,))
    stats['marketing']['utm_sources'] = cursor.fetchall()

    # Реферальная программа за день
    cursor.execute("""
        SELECT COUNT(*) FROM users
        WHERE DATE(registration_date) = ? AND referred_by IS NOT NULL
    """, (today,))
    stats['marketing']['referral_signups'] = cursor.fetchone()[0]

    # Начислено реферальных бонусов
    cursor.execute("""
        SELECT COALESCE(SUM(points), 0)
        FROM loyalty_transactions
        WHERE DATE(created_at) = ?
        AND description LIKE '%Реферальная%'
    """, (today,))
    stats['marketing']['referral_bonuses'] = cursor.fetchone()[0]

    # =====================================================
    # 6. ПОДПИСКИ
    # =====================================================

    # Новые подписки за день
    cursor.execute("""
        SELECT sp.name, COUNT(*) as cnt
        FROM user_subscriptions us
        JOIN subscription_plans sp ON us.plan_id = sp.id
        WHERE DATE(us.created_at) = ?
        GROUP BY sp.name
    """, (today,))
    stats['subscriptions']['new_today'] = cursor.fetchall()

    # Всего активных подписок
    cursor.execute("""
        SELECT COUNT(*) FROM user_subscriptions
        WHERE status = 'active' AND end_date >= ?
    """, (today,))
    stats['subscriptions']['active_total'] = cursor.fetchone()[0]

    # Использование подписок сегодня
    cursor.execute("""
        SELECT
            SUM(CASE WHEN type = 'flower' THEN 1 ELSE 0 END) as flowers_used,
            SUM(CASE WHEN type = 'service' THEN 1 ELSE 0 END) as services_used
        FROM subscription_usage
        WHERE DATE(used_at) = ?
    """, (today,))
    row = cursor.fetchone()
    stats['subscriptions']['usage_today'] = {
        'flowers': row[0] or 0,
        'services': row[1] or 0
    }

    # =====================================================
    # 7. БОНУСНАЯ СИСТЕМА
    # =====================================================

    # Начислено бонусов
    cursor.execute("""
        SELECT COALESCE(SUM(points), 0)
        FROM loyalty_transactions
        WHERE DATE(created_at) = ? AND points > 0
    """, (today,))
    stats['bonuses']['earned_today'] = cursor.fetchone()[0]

    # Потрачено бонусов
    cursor.execute("""
        SELECT COALESCE(SUM(ABS(points)), 0)
        FROM loyalty_transactions
        WHERE DATE(created_at) = ? AND points < 0
    """, (today,))
    stats['bonuses']['spent_today'] = cursor.fetchone()[0]

    # Сумма оплаченная бонусами
    cursor.execute("""
        SELECT COALESCE(SUM(bonus_used), 0)
        FROM (
            SELECT bonus_used FROM salon_appointments WHERE DATE(appointment_date) = ?
            UNION ALL
            SELECT bonus_used FROM flower_orders WHERE DATE(created_at) = ?
        )
    """, (today, today))
    stats['bonuses']['paid_with_bonuses'] = cursor.fetchone()[0]

    # =====================================================
    # 8. ТОП ИСПОЛНИТЕЛИ
    # =====================================================

    # Топ клиенты по выручке за день
    cursor.execute("""
        SELECT
            u.first_name,
            u.user_id,
            SUM(total) as revenue
        FROM (
            SELECT user_id, total_amount as total
            FROM salon_appointments
            WHERE DATE(appointment_date) = ? AND status = 'completed'
            UNION ALL
            SELECT user_id, total_amount as total
            FROM flower_orders
            WHERE DATE(created_at) = ? AND status = 'completed'
        ) as orders
        JOIN users u ON orders.user_id = u.user_id
        GROUP BY u.user_id, u.first_name
        ORDER BY revenue DESC
        LIMIT 5
    """, (today, today))
    stats['top_performers']['clients'] = cursor.fetchall()

    # Топ товары за день
    cursor.execute("""
        SELECT
            p.name,
            COUNT(*) as quantity,
            SUM(p.price * quantity) as revenue
        FROM flower_orders fo
        CROSS JOIN json_each(fo.items_json) as item
        JOIN products p ON json_extract(item.value, '$.id') = p.id
        WHERE DATE(fo.created_at) = ?
        GROUP BY p.name
        ORDER BY revenue DESC
        LIMIT 5
    """, (today,))
    stats['top_performers']['products'] = cursor.fetchall()

    conn.close()
    return stats


def format_daily_report(stats):
    """Форматировать отчет в красивое сообщение"""

    # Рассчитать изменения
    user_change = stats['users']['new_today'] - stats['users']['new_yesterday']
    user_emoji = "📈" if user_change > 0 else "📉" if user_change < 0 else "➡️"

    revenue_change = stats['revenue']['total_today'] - stats['revenue']['total_yesterday']
    revenue_emoji = "📈" if revenue_change > 0 else "📉" if revenue_change < 0 else "➡️"
    revenue_percent = (revenue_change / stats['revenue']['total_yesterday'] * 100) if stats['revenue']['total_yesterday'] > 0 else 0

    report = f"""
📊 <b>ЕЖЕДНЕВНЫЙ ОТЧЕТ</b>
📅 {stats['date']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 <b>ВЫРУЧКА ЗА ДЕНЬ</b>
┣ Общая: <b>{stats['revenue']['total_today']:,}₽</b> {revenue_emoji} {revenue_change:+,}₽ ({revenue_percent:+.1f}%)
┣ Салон: {stats['revenue']['salon_today']:,}₽
┣ Цветы: {stats['revenue']['flowers_today']:,}₽
┣ Сертификаты: {stats['revenue']['certificates_today']:,}₽
┗ Подписки: {stats['revenue']['subscriptions_today']:,}₽

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👥 <b>ПОЛЬЗОВАТЕЛИ</b>
┣ Новых за день: <b>{stats['users']['new_today']}</b> {user_emoji} {user_change:+d}
┣ Активных: {stats['users']['active_today']}
┗ Всего: {stats['users']['total']:,}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💇‍♀️ <b>САЛОН КРАСОТЫ</b>
┣ Записей: {stats['salon']['appointments']['total']}
   ├ ✅ Завершено: {stats['salon']['appointments']['completed']}
   ├ ⏳ Подтверждено: {stats['salon']['appointments']['confirmed']}
   ├ 🕐 В ожидании: {stats['salon']['appointments']['pending']}
   └ ❌ Отменено: {stats['salon']['appointments']['cancelled']}
┣ Средний чек: {stats['salon']['avg_check']:,.0f}₽
┗ Загруженность: {stats['salon']['occupancy']:.1f}%

<b>Топ услуги:</b>
"""

    for idx, (service, count) in enumerate(stats['salon']['top_services'], 1):
        report += f"   {idx}. {service} — {count} раз\n"

    report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💐 <b>ЦВЕТОЧНЫЙ МАГАЗИН</b>
┣ Заказов: {stats['orders']['flowers']['total']}
   ├ ✅ Завершено: {stats['orders']['flowers']['completed']}
   ├ 🕐 В обработке: {stats['orders']['flowers']['pending']}
   └ ❌ Отменено: {stats['orders']['flowers']['cancelled']}
┗ Средний чек: {stats['orders']['avg_flower_order']:,.0f}₽

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💎 <b>ПОДПИСКИ</b>
┣ Активных: {stats['subscriptions']['active_total']}
┣ Новых за день: {len(stats['subscriptions']['new_today'])}
┗ Использовано сегодня:
   ├ 🌹 Букетов: {stats['subscriptions']['usage_today']['flowers']}
   └ 💅 Услуг: {stats['subscriptions']['usage_today']['services']}

"""

    if stats['subscriptions']['new_today']:
        report += "<b>Купленные подписки:</b>\n"
        for plan, count in stats['subscriptions']['new_today']:
            report += f"   • {plan} — {count} шт\n"
        report += "\n"

    report += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎁 <b>БОНУСНАЯ СИСТЕМА</b>
┣ Начислено: +{stats['bonuses']['earned_today']:,} баллов
┣ Потрачено: -{stats['bonuses']['spent_today']:,} баллов
┗ Оплачено бонусами: {stats['bonuses']['paid_with_bonuses']:,}₽

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📢 <b>МАРКЕТИНГ</b>
┣ Регистраций по реферальной программе: {stats['marketing']['referral_signups']}
┗ Реферальных бонусов выдано: {stats['marketing']['referral_bonuses']:,}

"""

    if stats['marketing']['utm_sources']:
        report += "<b>Топ источники трафика:</b>\n"
        for source, regs, convs, rev in stats['marketing']['utm_sources']:
            report += f"   • {source}: {regs} регистраций, {convs} конверсий, {rev:,}₽\n"
        report += "\n"

    report += """━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏆 <b>ТОП КЛИЕНТЫ ДНЯ</b>
"""

    if stats['top_performers']['clients']:
        for idx, (name, user_id, revenue) in enumerate(stats['top_performers']['clients'], 1):
            report += f"   {idx}. {name} — {revenue:,}₽\n"
    else:
        report += "   Нет данных\n"

    report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 <b>ТОП ТОВАРЫ ДНЯ</b>
"""

    if stats['top_performers']['products']:
        for idx, (product, qty, revenue) in enumerate(stats['top_performers']['products'], 1):
            report += f"   {idx}. {product} — {qty} шт, {revenue:,}₽\n"
    else:
        report += "   Нет данных\n"

    report += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 <b>РЕКОМЕНДАЦИИ:</b>
"""

    # Автоматические рекомендации
    recommendations = []

    if stats['salon']['occupancy'] < 50:
        recommendations.append("⚠️ Низкая загруженность салона (<50%). Рассмотрите промо-акцию.")

    if stats['orders']['flowers']['cancelled'] > stats['orders']['flowers']['completed']:
        recommendations.append("⚠️ Много отмененных заказов цветов. Проверьте качество обслуживания.")

    if revenue_change < 0 and abs(revenue_percent) > 20:
        recommendations.append(f"📉 Выручка упала на {abs(revenue_percent):.0f}%. Активируйте маркетинг.")

    if stats['users']['new_today'] == 0:
        recommendations.append("⚠️ Сегодня не было новых регистраций. Проверьте рекламу.")

    if stats['bonuses']['spent_today'] > stats['bonuses']['earned_today']:
        recommendations.append("💸 Больше тратят бонусов, чем зарабатывают. Ускорьте начисления.")

    if stats['subscriptions']['active_total'] < 10:
        recommendations.append("💎 Мало активных подписок. Предложите специальные условия.")

    if not recommendations:
        recommendations.append("✅ Все показатели в норме! Продолжайте в том же духе.")

    for rec in recommendations:
        report += f"   {rec}\n"

    report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🕐 Отчет сформирован: {datetime.now().strftime('%H:%M')}
"""

    return report


async def send_daily_report():
    """Отправить ежедневный отчет собственнику"""

    try:
        # Получить статистику
        stats = get_daily_statistics()

        # Форматировать отчет
        report = format_daily_report(stats)

        # Отправить в Telegram
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=report,
            parse_mode=ParseMode.HTML
        )

        print(f"✅ Ежедневный отчет отправлен успешно в {datetime.now().strftime('%H:%M')}")

    except Exception as e:
        print(f"❌ Ошибка отправки отчета: {e}")


def main():
    """Главная функция для запуска"""
    asyncio.run(send_daily_report())


if __name__ == "__main__":
    main()
