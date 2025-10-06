"""
Модуль для расчета цен с учетом привилегий пользователя
"""

from database import get_user_active_subscription
from utils.helpers import format_price


def calculate_final_price(user_id: int, base_price: int, item_type: str = 'service') -> dict:
    """
    Рассчитать финальную цену с учетом статуса пользователя.

    Args:
        user_id: ID пользователя
        base_price: Базовая цена
        item_type: Тип товара ('service' или 'flower')

    Returns:
        dict: {
            'base_price': int,
            'final_price': int,
            'discount_percent': int,
            'discount_amount': int,
            'subscription_name': str or None,
            'saved': int
        }
    """
    result = {
        'base_price': base_price,
        'final_price': base_price,
        'discount_percent': 0,
        'discount_amount': 0,
        'subscription_name': None,
        'saved': 0
    }

    # Получить активную подписку
    subscription = get_user_active_subscription(user_id)

    if not subscription:
        return result

    # Определить процент скидки
    discount_percent = 0
    if item_type == 'service':
        discount_percent = subscription.get('service_discount_percent', 0)
    elif item_type == 'flower':
        discount_percent = subscription.get('flower_discount_percent', 0)

    if discount_percent > 0:
        discount_amount = int(base_price * discount_percent / 100)
        final_price = base_price - discount_amount

        result.update({
            'final_price': final_price,
            'discount_percent': discount_percent,
            'discount_amount': discount_amount,
            'subscription_name': subscription.get('plan_name'),
            'saved': discount_amount
        })

    return result


def calculate_cart_total(user_id: int, cart_items: list, delivery_cost: int = 0) -> dict:
    """
    Рассчитать итоговую стоимость корзины с учетом привилегий.

    Args:
        user_id: ID пользователя
        cart_items: Список товаров [{'price': int, 'quantity': int, 'type': 'flower/service'}]
        delivery_cost: Стоимость доставки

    Returns:
        dict: {
            'subtotal': int,
            'total_discount': int,
            'delivery_cost': int,
            'final_total': int,
            'items_with_discount': list,
            'subscription_name': str or None,
            'total_saved': int
        }
    """
    subscription = get_user_active_subscription(user_id)

    subtotal = 0
    total_discount = 0
    items_with_discount = []

    for item in cart_items:
        item_base = item['price'] * item['quantity']
        item_type = item.get('type', 'flower')

        price_info = calculate_final_price(user_id, item['price'], item_type)

        items_with_discount.append({
            **item,
            'base_price': item['price'],
            'final_price': price_info['final_price'],
            'discount_percent': price_info['discount_percent'],
            'item_discount': price_info['discount_amount'] * item['quantity']
        })

        subtotal += item_base
        total_discount += price_info['discount_amount'] * item['quantity']

    final_total = subtotal - total_discount + delivery_cost

    return {
        'subtotal': subtotal,
        'total_discount': total_discount,
        'delivery_cost': delivery_cost,
        'final_total': final_total,
        'items_with_discount': items_with_discount,
        'subscription_name': subscription.get('plan_name') if subscription else None,
        'total_saved': total_discount
    }


def format_price_summary(pricing_info: dict, show_delivery: bool = True) -> str:
    """
    Форматировать сводку цен для отображения пользователю.

    Args:
        pricing_info: Результат calculate_cart_total()
        show_delivery: Показывать ли строку доставки

    Returns:
        str: Форматированный текст
    """
    text = f"💰 Сумма: {format_price(pricing_info['subtotal'])}\n"

    if pricing_info['total_discount'] > 0:
        text += f"🎉 Скидка ({pricing_info['subscription_name']}): -{format_price(pricing_info['total_discount'])}\n"

    if show_delivery:
        if pricing_info['delivery_cost'] > 0:
            text += f"🚚 Доставка: {format_price(pricing_info['delivery_cost'])}\n"
        else:
            text += "🚚 Доставка: БЕСПЛАТНО ✅\n"

    text += "━━━━━━━━━━━━━━━\n"
    text += f"💵 Итого: {format_price(pricing_info['final_total'])}\n"

    if pricing_info['total_saved'] > 0:
        text += f"\n🎁 Вы сэкономили: {format_price(pricing_info['total_saved'])} благодаря подписке!\n"

    return text


def get_subscription_benefits_summary(user_id: int) -> str:
    """
    Получить краткую сводку привилегий пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        str: Текст с привилегиями
    """
    subscription = get_user_active_subscription(user_id)

    if not subscription:
        return "У вас нет активной подписки."

    text = f"✨ Ваша подписка: {subscription['plan_name']}\n\n"
    text += "🎁 Ваши привилегии:\n"

    if subscription.get('service_discount_percent', 0) > 0:
        text += f"• {subscription['service_discount_percent']}% скидка на услуги салона\n"

    if subscription.get('flower_discount_percent', 0) > 0:
        text += f"• {subscription['flower_discount_percent']}% скидка на цветы\n"

    if subscription.get('monthly_flowers_included', 0) > 0:
        used = subscription.get('flowers_used_this_month', 0)
        total = subscription['monthly_flowers_included']
        text += f"• Букетов в месяц: {used}/{total}\n"

    if subscription.get('monthly_service_included'):
        used = "✅" if subscription.get('service_used_this_month') else "❌"
        text += f"• Услуга салона в месяц: {used}\n"

    text += f"\n📅 Действует до: {subscription['end_date']}"

    return text


def can_use_subscription_benefit(user_id: int, benefit_type: str) -> dict:
    """
    Проверить, может ли пользователь использовать преимущество подписки.

    Args:
        user_id: ID пользователя
        benefit_type: Тип преимущества ('flower' или 'service')

    Returns:
        dict: {
            'can_use': bool,
            'reason': str or None,
            'subscription': dict or None
        }
    """
    subscription = get_user_active_subscription(user_id)

    if not subscription:
        return {
            'can_use': False,
            'reason': 'Нет активной подписки',
            'subscription': None
        }

    if benefit_type == 'flower':
        total = subscription.get('monthly_flowers_included', 0)
        used = subscription.get('flowers_used_this_month', 0)

        if total == 0:
            return {
                'can_use': False,
                'reason': 'Ваша подписка не включает бесплатные букеты',
                'subscription': subscription
            }

        if used >= total:
            return {
                'can_use': False,
                'reason': f'Вы уже использовали все букеты в этом месяце ({used}/{total})',
                'subscription': subscription
            }

        return {
            'can_use': True,
            'reason': None,
            'subscription': subscription
        }

    elif benefit_type == 'service':
        if not subscription.get('monthly_service_included'):
            return {
                'can_use': False,
                'reason': 'Ваша подписка не включает бесплатные услуги',
                'subscription': subscription
            }

        if subscription.get('service_used_this_month'):
            return {
                'can_use': False,
                'reason': 'Вы уже использовали бесплатную услугу в этом месяце',
                'subscription': subscription
            }

        return {
            'can_use': True,
            'reason': None,
            'subscription': subscription
        }

    return {
        'can_use': False,
        'reason': 'Неизвестный тип преимущества',
        'subscription': None
    }
