"""
Обработчики для модуля заказа цветов.
Каталог, корзина, оформление заказа с доставкой.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from config import (
    FLOWERS_CATEGORY, FLOWERS_ITEM, FLOWERS_CART, FLOWERS_DELIVERY_TYPE,
    FLOWERS_ADDRESS, FLOWERS_TIME, FLOWERS_ANONYMOUS, FLOWERS_CARD,
    FLOWERS_RECIPIENT, FLOWERS_PAYMENT, FLOWERS_CONFIRM,
    FREE_DELIVERY_THRESHOLD, DELIVERY_COST, BONUS_PERCENT, MAX_BONUS_PAYMENT_PERCENT, BONUS_THRESHOLD
)
from database import (
    get_user, get_addresses, add_address, get_bonus_balance, subtract_bonus_points, add_bonus_points,
    get_products, get_product_by_id, get_product_categories, add_flower_order,
    schedule_feedback_request, check_and_award_referral_bonus, update_utm_campaign_stats
)
import json
from utils.helpers import format_price, get_current_datetime, calculate_delivery_cost, generate_order_number, send_to_user_topic
from utils.pricing import calculate_cart_total, format_price_summary, get_subscription_benefits_summary

logger = logging.getLogger(__name__)


# =================================================================
# ШАГ 1: ВЫБОР КАТЕГОРИИ ТОВАРОВ
# =================================================================

async def flowers_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало заказа цветов - выбор категории"""

    query = update.callback_query
    await query.answer()

    # Инициализировать корзину если её нет
    if 'cart' not in context.user_data:
        context.user_data['cart'] = []

    try:
        # Получить категории из БД
        categories = get_product_categories()

        if not categories:
            await query.edit_message_text(
                "❌ К сожалению, сейчас нет доступных товаров.\n"
                "Попробуйте позже или свяжитесь с администратором.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="main_menu")
                ]])
            )
            return ConversationHandler.END

        # Создать клавиатуру
        keyboard = []
        for category in categories:
            keyboard.append([InlineKeyboardButton(
                category,
                callback_data=f"flowers_cat_{category}"
            )])

        # Специальные кнопки
        keyboard.append([InlineKeyboardButton("🎨 Индивидуальный заказ", callback_data="custom_flower_order")])

        # Показать корзину если есть товары
        cart = context.user_data.get('cart', [])
        if cart:
            cart_count = sum(item['quantity'] for item in cart)
            keyboard.append([InlineKeyboardButton(f"🛒 Корзина ({cart_count})", callback_data="view_cart")])

        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_menu")])

        await query.edit_message_text(
            "💐 ЦВЕТОЧНЫЙ МАГАЗИН\n\n"
            "Работаем круглосуточно! 🌙\n\n"
            "Выберите категорию:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return FLOWERS_CATEGORY

    except Exception as e:
        logger.error(f"Ошибка в flowers_start: {e}")
        await query.edit_message_text(
            "❌ Произошла ошибка. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ В меню", callback_data="main_menu")
            ]])
        )
        return ConversationHandler.END


# =================================================================
# ШАГ 2: ПРОСМОТР ТОВАРОВ И ДОБАВЛЕНИЕ В КОРЗИНУ
# =================================================================

async def flowers_select_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать товары выбранной категории"""

    query = update.callback_query
    await query.answer()

    # Обработка просмотра корзины
    if query.data == "view_cart":
        return await flowers_view_cart(update, context)

    # Извлечь категорию
    category = query.data.replace("flowers_cat_", "")
    context.user_data['current_category'] = category

    try:
        # Получить товары категории из БД
        products = get_products(category=category, active_only=True, in_stock_only=True)

        if not products:
            await query.edit_message_text(
                f"❌ В категории '{category}' нет доступных товаров.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="flowers_shop")
                ]])
            )
            return FLOWERS_CATEGORY

        # Создать клавиатуру с товарами
        keyboard = []
        for product in products[:10]:  # Показываем первые 10
            keyboard.append([
                InlineKeyboardButton(f"{product['name']} - {format_price(product['price'])}", callback_data=f"view_flower_{product['id']}"),
                InlineKeyboardButton("➕", callback_data=f"add_flower_{product['id']}")
            ])

        # Показать корзину
        cart = context.user_data.get('cart', [])
        if cart:
            cart_count = sum(item['quantity'] for item in cart)
            keyboard.append([InlineKeyboardButton(f"🛒 Корзина ({cart_count})", callback_data="view_cart")])

        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="flowers_shop")])

        await query.edit_message_text(
            f"Категория: {category}\n\n"
            "Выберите товар:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return FLOWERS_ITEM

    except Exception as e:
        logger.error(f"Ошибка в flowers_select_category: {e}")
        await query.edit_message_text("❌ Произошла ошибка.")
        return ConversationHandler.END


async def flowers_view_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать детали товара"""

    query = update.callback_query
    await query.answer()

    product_id = int(query.data.replace("view_flower_", ""))

    try:
        product = get_product_by_id(product_id)

        if not product:
            await query.answer("❌ Товар не найден", show_alert=True)
            return FLOWERS_ITEM

        text = (
            f"🌹 {product['name']}\n\n"
            f"💰 Цена: {format_price(product['price'])}\n\n"
            f"📝 Описание:\n{product.get('description', 'Нет описания')}"
        )

        keyboard = [
            [InlineKeyboardButton("➕ Добавить в корзину", callback_data=f"add_flower_{product_id}")],
            [InlineKeyboardButton("◀️ Назад к каталогу", callback_data=f"flowers_cat_{product['category']}")]
        ]

        # Если есть фото, попробовать отправить
        if product.get('photo_url'):
            try:
                await query.message.reply_photo(
                    photo=product['photo_url'],
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                await query.message.delete()
            except:
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

        return FLOWERS_ITEM

    except Exception as e:
        logger.error(f"Ошибка в flowers_view_item: {e}")
        await query.answer("❌ Ошибка загрузки товара", show_alert=True)
        return FLOWERS_ITEM


async def flowers_add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Добавить товар в корзину"""

    query = update.callback_query

    product_id = int(query.data.replace("add_flower_", ""))

    try:
        product = get_product_by_id(product_id)

        if not product:
            await query.answer("❌ Товар не найден", show_alert=True)
            return FLOWERS_ITEM

        # Инициализировать корзину
        if 'cart' not in context.user_data:
            context.user_data['cart'] = []

        cart = context.user_data['cart']

        # Проверить, есть ли товар уже в корзине
        existing_item = next((item for item in cart if item['id'] == product_id), None)

        if existing_item:
            existing_item['quantity'] += 1
            await query.answer(f"✅ Добавлено! Теперь в корзине: {existing_item['quantity']} шт.")
        else:
            cart.append({
                'id': product_id,
                'name': product['name'],
                'price': product['price'],
                'quantity': 1,
                'photo_url': product.get('photo_url', ''),
                'category': product['category']
            })
            await query.answer("✅ Товар добавлен в корзину!")

        # Вернуться к каталогу с обновленной корзиной
        category = context.user_data.get('current_category')
        if category:
            return await flowers_select_category_update(update, context, category)
        else:
            return FLOWERS_ITEM

    except Exception as e:
        logger.error(f"Ошибка в flowers_add_to_cart: {e}")
        await query.answer("❌ Ошибка добавления в корзину", show_alert=True)
        return FLOWERS_ITEM


async def flowers_select_category_update(update, context, category):
    """Обновить каталог с обновленным счетчиком корзины"""

    query = update.callback_query

    try:
        products = get_products(category=category, active_only=True, in_stock_only=True)

        keyboard = []
        for product in products[:10]:
            keyboard.append([
                InlineKeyboardButton(f"{product['name']} - {format_price(product['price'])}", callback_data=f"view_flower_{product['id']}"),
                InlineKeyboardButton("➕", callback_data=f"add_flower_{product['id']}")
            ])

        cart = context.user_data.get('cart', [])
        cart_count = sum(item['quantity'] for item in cart)
        keyboard.append([InlineKeyboardButton(f"🛒 Корзина ({cart_count})", callback_data="view_cart")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="flowers_shop")])

        await query.edit_message_text(
            f"Категория: {category}\n\nВыберите товар:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return FLOWERS_ITEM

    except Exception as e:
        logger.error(f"Ошибка в flowers_select_category_update: {e}")
        return FLOWERS_ITEM


# =================================================================
# ШАГ 3: КОРЗИНА - УПРАВЛЕНИЕ ТОВАРАМИ
# =================================================================

async def flowers_view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать корзину с возможностью изменения"""

    query = update.callback_query
    await query.answer()

    cart = context.user_data.get('cart', [])

    if not cart:
        await query.edit_message_text(
            "🛒 Ваша корзина пуста\n\n"
            "Добавьте товары из каталога!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ К каталогу", callback_data="flowers_shop")
            ]])
        )
        return FLOWERS_CATEGORY

    # Подсчитать итоги с учетом подписки
    user_id = update.effective_user.id
    cart_items = [{'price': item['price'], 'quantity': item['quantity'], 'type': 'flower', 'name': item['name']} for item in cart]
    base_subtotal = sum(item['price'] * item['quantity'] for item in cart)
    delivery = calculate_delivery_cost(base_subtotal)
    pricing_info = calculate_cart_total(user_id, cart_items, delivery)

    # Создать текст корзины
    text = "🛒 ВАША КОРЗИНА:\n\n"

    keyboard = []
    for i, item_discount in enumerate(pricing_info['items_with_discount']):
        # Найти оригинальный элемент корзины для ID
        original_item = cart[i]

        item_total = item_discount['final_price'] * item_discount['quantity']
        text += f"{i+1}. {item_discount.get('name', 'Товар')}\n"
        text += f"   {format_price(item_discount['final_price'])} × {item_discount['quantity']} = {format_price(item_total)}"

        if item_discount.get('discount_percent', 0) > 0:
            text += f" 🎉 (-{item_discount['discount_percent']}%)"
        text += "\n\n"

        # Кнопки управления количеством
        keyboard.append([
            InlineKeyboardButton("➖", callback_data=f"qty_decrease_{original_item['id']}"),
            InlineKeyboardButton(f"{item_discount['quantity']} шт", callback_data="ignore"),
            InlineKeyboardButton("➕", callback_data=f"qty_increase_{original_item['id']}"),
            InlineKeyboardButton("🗑️", callback_data=f"remove_item_{original_item['id']}")
        ])

    text += "━━━━━━━━━━━━━━━\n"
    text += format_price_summary(pricing_info, show_delivery=True)

    # Кнопки действий
    keyboard.append([InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout")])
    keyboard.append([
        InlineKeyboardButton("🛍️ Продолжить покупки", callback_data="flowers_shop"),
        InlineKeyboardButton("🗑️ Очистить корзину", callback_data="clear_cart")
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return FLOWERS_CART


async def flowers_update_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Изменить количество товара"""

    query = update.callback_query
    await query.answer()

    callback_data = query.data
    cart = context.user_data.get('cart', [])

    if callback_data.startswith("qty_increase_"):
        product_id = int(callback_data.replace("qty_increase_", ""))
        item = next((i for i in cart if i['id'] == product_id), None)
        if item:
            item['quantity'] += 1
            await query.answer(f"✅ Количество увеличено до {item['quantity']}")

    elif callback_data.startswith("qty_decrease_"):
        product_id = int(callback_data.replace("qty_decrease_", ""))
        item = next((i for i in cart if i['id'] == product_id), None)
        if item:
            if item['quantity'] > 1:
                item['quantity'] -= 1
                await query.answer(f"✅ Количество уменьшено до {item['quantity']}")
            else:
                cart.remove(item)
                await query.answer("✅ Товар удален из корзины")

    # Обновить отображение корзины
    return await flowers_view_cart(update, context)


async def flowers_remove_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Удалить товар из корзины"""

    query = update.callback_query

    product_id = int(query.data.replace("remove_item_", ""))
    cart = context.user_data.get('cart', [])

    item = next((i for i in cart if i['id'] == product_id), None)
    if item:
        cart.remove(item)
        await query.answer(f"✅ {item['name']} удален из корзины")

    # Обновить корзину
    return await flowers_view_cart(update, context)


async def flowers_clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Очистить всю корзину"""

    query = update.callback_query
    await query.answer()

    context.user_data['cart'] = []

    await query.edit_message_text(
        "✅ Корзина очищена",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ К каталогу", callback_data="flowers_shop")
        ]])
    )

    return FLOWERS_CATEGORY


# =================================================================
# ШАГ 4-11: ОФОРМЛЕНИЕ ЗАКАЗА (продолжение)
# =================================================================


# Добавить недостающие функции для полного цикла оформления
# Эти функции будут вызываться из flowers_checkout()

async def flowers_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Упрощенное оформление заказа"""
    query = update.callback_query
    await query.answer()
    
    cart = context.user_data.get('cart', [])
    if not cart:
        await query.answer("❌ Корзина пуста", show_alert=True)
        return FLOWERS_CATEGORY
    
    # Установить значения по умолчанию для быстрого оформления
    context.user_data['delivery_type'] = "Самовывоз"
    context.user_data['delivery_address'] = "Самовывоз из салона"
    context.user_data['delivery_time'] = "По готовности"
    context.user_data['anonymous'] = False
    context.user_data['card_text'] = ""
    context.user_data['recipient'] = update.effective_user.first_name
    context.user_data['bonus_used'] = 0
    
    # Сразу показать подтверждение
    return await flowers_show_simple_confirmation(update, context)


async def flowers_show_simple_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Упрощенное подтверждение заказа"""
    query = update.callback_query
    
    cart = context.user_data.get('cart', [])
    subtotal = sum(item['price'] * item['quantity'] for item in cart)
    delivery = 0  # Самовывоз
    total = subtotal

    text = "✅ ПОДТВЕРЖДЕНИЕ ЗАКАЗА:\n\n🛒 Состав:\n"
    for item in cart:
        text += f"• {item['name']} × {item['quantity']} = {format_price(item['price'] * item['quantity'])}\n"

    text += f"\n💵 Итого: {format_price(total)}\n"
    text += f"📍 Самовывоз из салона\n\n"
    text += "Подтвердите заказ:"
    
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_flowers_order")],
        [InlineKeyboardButton("◀️ Назад к корзине", callback_data="view_cart")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return FLOWERS_CONFIRM


async def flowers_confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Создание заказа"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    cart = context.user_data.get('cart', [])
    
    try:
        subtotal = sum(item['price'] * item['quantity'] for item in cart)
        composition = ", ".join([f"{item['name']} x{item['quantity']}" for item in cart])
        
        # Создать заказ в БД
        items_json = json.dumps(cart, ensure_ascii=False)

        order_id = add_flower_order(
            user_id=user.id,
            user_name=user.first_name,
            phone='',
            items=items_json,
            total_amount=subtotal,
            delivery_type='pickup',
            delivery_address='Самовывоз',
            delivery_time='По готовности',
            anonymous=False,
            card_text='',
            recipient_name='',
            recipient_phone=''
        )

        if not order_id:
            raise Exception("Не удалось создать заказ")

        # Запланировать запрос на отзыв
        schedule_feedback_request(user.id, 'flower_order', order_id)

        # Начислить бонусы
        if subtotal >= BONUS_THRESHOLD:
            bonus_earn = int(subtotal * BONUS_PERCENT / 100)
            add_bonus_points(user.id, bonus_earn, f"Заказ цветов #{order_id}")
        
        # Уведомление админу
        admin_text = (
            f"🆕 <b>НОВЫЙ ЗАКАЗ ЦВЕТОВ</b>\n\n"
            f"📋 Номер: #{order_id}\n"
            f"👤 Клиент: {user.first_name}"
        )
        if user.username:
            admin_text += f" (@{user.username})"
        admin_text += f"\n\n🛒 Состав:\n{composition}\n\n💵 Итого: {format_price(subtotal)}"

        await send_to_user_topic(context, user.id, user.first_name, admin_text, None)

        # Ответ клиенту
        response_text = f"🎉 Заказ #{order_id} успешно создан!\n\n"
        if subtotal >= BONUS_THRESHOLD:
            bonus_earn = int(subtotal * BONUS_PERCENT / 100)
            response_text += f"🎁 Вам начислено {format_price(bonus_earn)} бонусов!\n\n"
        response_text += "Администратор свяжется с вами для уточнения."
        
        await query.edit_message_text(
            response_text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")
            ]])
        )
        
        context.user_data['cart'] = []
        logger.info(f"Создан заказ цветов #{order_id}")
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка создания заказа: {e}")
        await query.edit_message_text(
            "❌ Произошла ошибка при создании заказа.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 В меню", callback_data="main_menu")
            ]])
        )
        return ConversationHandler.END


# =================================================================
# ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ОФОРМЛЕНИЯ ЗАКАЗА
# =================================================================

async def flowers_select_delivery_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбор способа доставки: самовывоз или курьер"""

    query = update.callback_query
    await query.answer()

    if query.data == "delivery_pickup":
        context.user_data['delivery_type'] = "Самовывоз"
        context.user_data['delivery_address'] = "Самовывоз из салона"
        context.user_data['delivery_time'] = "По готовности"
        # Пропускаем адрес и время, сразу к анонимности
        return await flowers_ask_anonymous_delivery(update, context)

    elif query.data == "delivery_courier":
        context.user_data['delivery_type'] = "Доставка"
        # Переходим к вводу адреса
        return await flowers_ask_address(update, context)

    return FLOWERS_DELIVERY_TYPE


async def flowers_ask_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрос адреса доставки (сохраненные или новый)"""

    query = update.callback_query
    user_id = update.effective_user.id
    addresses = get_addresses(user_id)

    keyboard = []

    # Показать сохраненные адреса
    if addresses:
        for addr_id, address, is_default in addresses[:5]:
            prefix = "✅ " if is_default else "   "
            keyboard.append([InlineKeyboardButton(
                f"{prefix}{address[:35]}...",
                callback_data=f"select_address_{addr_id}"
            )])

    keyboard.append([InlineKeyboardButton("✍️ Ввести новый адрес", callback_data="new_address")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_delivery")])

    await query.edit_message_text(
        "📍 Адрес доставки:\n\n"
        "Выберите сохраненный адрес или введите новый:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return FLOWERS_ADDRESS


async def flowers_handle_address_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора сохраненного адреса"""

    query = update.callback_query
    await query.answer()

    if query.data == "new_address":
        await query.edit_message_text(
            "📍 Введите адрес доставки:\n\n"
            "Укажите полный адрес:\n"
            "Улица, дом, подъезд, этаж, квартира\n\n"
            "Пример: ул. Ленина, 50, подъезд 2, кв. 10"
        )
        return FLOWERS_ADDRESS

    if query.data == "back_to_delivery":
        # Вернуться к выбору способа доставки
        keyboard = [
            [InlineKeyboardButton("📦 Самовывоз (бесплатно)", callback_data="delivery_pickup")],
            [InlineKeyboardButton("🚗 Доставка по Челябинску", callback_data="delivery_courier")],
            [InlineKeyboardButton("◀️ Назад к корзине", callback_data="view_cart")]
        ]
        await query.edit_message_text(
            "🚚 Способ получения:\n\nВыберите удобный вариант:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return FLOWERS_DELIVERY_TYPE

    # Выбран сохраненный адрес
    if query.data.startswith("select_address_"):
        addr_id = int(query.data.replace("select_address_", ""))
        addresses = get_addresses(update.effective_user.id)
        address = next((addr[1] for addr in addresses if addr[0] == addr_id), None)

        if address:
            context.user_data['delivery_address'] = address
            return await flowers_ask_delivery_time(update, context)

    await query.answer("❌ Адрес не найден", show_alert=True)
    return FLOWERS_ADDRESS


async def flowers_enter_new_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ввод нового адреса доставки"""

    address = update.message.text

    # Валидация длины
    if len(address) < 10:
        await update.message.reply_text(
            "❌ Адрес слишком короткий.\n"
            "Укажите полный адрес (минимум 10 символов)."
        )
        return FLOWERS_ADDRESS

    context.user_data['delivery_address'] = address

    # Сохранить в БД
    try:
        add_address(update.effective_user.id, address, is_default=False)
        logger.info(f"Сохранен новый адрес для пользователя {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Ошибка сохранения адреса: {e}")

    return await flowers_ask_delivery_time(update, context)


async def flowers_ask_delivery_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбор времени доставки"""

    keyboard = [
        [InlineKeyboardButton("⚡ Как можно скорее", callback_data="time_asap")],
        [InlineKeyboardButton("🕐 К определенному времени", callback_data="time_specific")],
        [InlineKeyboardButton("📅 Выбрать дату и время", callback_data="time_datetime")]
    ]

    text = "⏰ Время доставки:\n\nВыберите удобный вариант:"

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    return FLOWERS_TIME


async def flowers_handle_delivery_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора времени доставки"""

    query = update.callback_query
    await query.answer()

    if query.data == "time_asap":
        context.user_data['delivery_time'] = "Как можно скорее"
        return await flowers_ask_anonymous_delivery(update, context)

    elif query.data == "time_specific":
        await query.edit_message_text(
            "🕐 Введите желаемое время доставки:\n\n"
            "Формат: ЧЧ:ММ (например, 14:30)\n"
            "Или укажите диапазон: 14:00-16:00"
        )
        context.user_data['waiting_for_time_input'] = True
        return FLOWERS_TIME

    elif query.data == "time_datetime":
        # Показать календарь
        from utils.calendar import create_calendar
        calendar_keyboard = create_calendar()
        await query.edit_message_text(
            "📅 Выберите дату доставки:",
            reply_markup=calendar_keyboard
        )
        context.user_data['waiting_for_date_input'] = True
        return FLOWERS_TIME

    return FLOWERS_TIME


async def flowers_enter_delivery_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ввод конкретного времени или обработка выбора даты"""

    # Обработка выбора даты из календаря
    if update.callback_query and context.user_data.get('waiting_for_date_input'):
        query = update.callback_query
        callback_data = query.data

        # Навигация по календарю
        if callback_data.startswith("calendar_prev_") or callback_data.startswith("calendar_next_"):
            from utils.calendar import create_calendar, handle_calendar_navigation
            parts = callback_data.split("_")
            year = int(parts[2])
            month = int(parts[3])
            new_year, new_month = handle_calendar_navigation(callback_data, year, month)
            calendar_keyboard = create_calendar(new_year, new_month)
            await query.edit_message_text(
                "📅 Выберите дату доставки:",
                reply_markup=calendar_keyboard
            )
            return FLOWERS_TIME

        # Выбрана дата
        if callback_data.startswith("calendar_"):
            selected_date = callback_data.replace("calendar_", "")
            context.user_data['delivery_date'] = selected_date
            context.user_data['waiting_for_date_input'] = False

            await query.edit_message_text(
                f"📅 Выбрана дата: {selected_date}\n\n"
                "🕐 Теперь введите время:\n"
                "Формат: ЧЧ:ММ (например, 14:30)"
            )
            context.user_data['waiting_for_time_input'] = True
            return FLOWERS_TIME

    # Обработка ввода времени текстом
    if update.message:
        time_text = update.message.text.strip()

        # Простая валидация
        import re
        if re.match(r'^\d{1,2}:\d{2}$', time_text) or re.match(r'^\d{1,2}:\d{2}-\d{1,2}:\d{2}$', time_text):
            if context.user_data.get('delivery_date'):
                from utils.helpers import format_datetime
                context.user_data['delivery_time'] = f"{context.user_data['delivery_date']} {time_text}"
            else:
                context.user_data['delivery_time'] = f"Сегодня {time_text}"

            context.user_data.pop('waiting_for_time_input', None)
            return await flowers_ask_anonymous_delivery(update, context)
        else:
            await update.message.reply_text(
                "❌ Неверный формат времени.\n"
                "Используйте формат ЧЧ:ММ (например, 14:30)"
            )
            return FLOWERS_TIME

    return FLOWERS_TIME


async def flowers_ask_anonymous_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Спросить об анонимной доставке"""

    keyboard = [
        [InlineKeyboardButton("Да, анонимно 🎭", callback_data="anonymous_yes")],
        [InlineKeyboardButton("Нет, обычная доставка", callback_data="anonymous_no")]
    ]

    text = (
        "🎭 Сделать доставку анонимной?\n\n"
        "Курьер не будет называть отправителя получателю."
    )

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    return FLOWERS_ANONYMOUS


async def flowers_handle_anonymous(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора анонимности"""

    query = update.callback_query
    await query.answer()

    context.user_data['is_anonymous'] = (query.data == "anonymous_yes")

    return await flowers_ask_card_text(update, context)


async def flowers_ask_card_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Спросить о тексте для открытки"""

    query = update.callback_query

    keyboard = [[InlineKeyboardButton("Пропустить", callback_data="skip_card")]]

    text = (
        "💌 Текст для открытки:\n\n"
        "Напишите поздравление или пожелание (до 200 символов)\n"
        "Или нажмите 'Пропустить':"
    )

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    return FLOWERS_CARD


async def flowers_handle_card_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка текста открытки"""

    if update.callback_query and update.callback_query.data == "skip_card":
        query = update.callback_query
        await query.answer()
        context.user_data['card_text'] = ""
        return await flowers_ask_recipient_data(update, context)

    # Ввод текста
    if update.message:
        card_text = update.message.text.strip()

        if len(card_text) > 200:
            await update.message.reply_text(
                "❌ Текст слишком длинный (максимум 200 символов).\n"
                "Попробуйте сократить."
            )
            return FLOWERS_CARD

        context.user_data['card_text'] = card_text
        return await flowers_ask_recipient_data(update, context)

    return FLOWERS_CARD


async def flowers_ask_recipient_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрос данных получателя"""

    text = (
        "👤 Данные получателя:\n\n"
        "Укажите имя и телефон получателя:\n\n"
        "Формат: Имя, телефон\n"
        "Пример: Мария Иванова, +7 (912) 345-67-89"
    )

    if update.message:
        await update.message.reply_text(text)
    else:
        await update.callback_query.edit_message_text(text)

    return FLOWERS_RECIPIENT


async def flowers_handle_recipient_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение данных получателя"""

    text = update.message.text.strip()

    # Попытка разбить на имя и телефон
    if ',' in text:
        parts = text.split(',', 1)
        recipient_name = parts[0].strip()
        recipient_phone = parts[1].strip()
    else:
        # Если нет запятой, считаем что это просто имя
        recipient_name = text
        recipient_phone = ""

    # Валидация телефона если указан
    if recipient_phone:
        from utils.validators import validate_phone, format_phone
        if not validate_phone(recipient_phone):
            await update.message.reply_text(
                "❌ Неверный формат телефона.\n"
                "Используйте формат: +7 (XXX) XXX-XX-XX\n\n"
                "Или укажите только имя, телефон необязателен."
            )
            return FLOWERS_RECIPIENT
        recipient_phone = format_phone(recipient_phone)

    context.user_data['recipient_name'] = recipient_name
    context.user_data['recipient_phone'] = recipient_phone

    return await flowers_ask_payment_method(update, context)


async def flowers_ask_payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбор способа оплаты с учетом бонусов и привилегий подписки"""

    user_id = update.effective_user.id
    cart = context.user_data.get('cart', [])

    # Преобразовать корзину в формат для расчета
    cart_items = [{'price': item['price'], 'quantity': item['quantity'], 'type': 'flower'} for item in cart]

    delivery_type = context.user_data.get('delivery_type', 'Самовывоз')
    base_subtotal = sum(item['price'] * item['quantity'] for item in cart)
    delivery_cost = 0 if delivery_type == "Самовывоз" else calculate_delivery_cost(base_subtotal)

    # Рассчитать с учетом подписки
    pricing_info = calculate_cart_total(user_id, cart_items, delivery_cost)
    total = pricing_info['final_total']

    # Получить баланс бонусов
    bonus_balance = get_bonus_balance(user_id)

    # Максимум можно использовать 50% от суммы
    max_bonus_use = int(total * MAX_BONUS_PAYMENT_PERCENT / 100)
    available_bonus = min(bonus_balance, max_bonus_use)

    text = "💳 Оплата заказа:\n\n"
    text += format_price_summary(pricing_info, show_delivery=True)

    if bonus_balance > 0:
        text += (
            f"\n🎁 У вас {bonus_balance} бонусов\n"
            f"Можно использовать до {available_bonus} бонусов (50% от суммы)\n"
        )

    text += "\nВыберите способ оплаты:"

    # Сохранить информацию о ценах для последующего использования
    context.user_data['pricing_info'] = pricing_info

    keyboard = [
        [InlineKeyboardButton("💳 Оплатить при получении", callback_data="payment_cash")]
    ]

    if available_bonus > 0:
        keyboard.append([
            InlineKeyboardButton(
                f"🎁 Использовать {available_bonus} бонусов",
                callback_data="payment_bonus_max"
            )
        ])
        keyboard.append([
            InlineKeyboardButton("💎 Частично бонусами", callback_data="payment_bonus_partial")
        ])

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    return FLOWERS_PAYMENT


async def flowers_handle_payment_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора способа оплаты"""

    query = update.callback_query
    await query.answer()

    if query.data == "payment_cash":
        context.user_data['bonus_used'] = 0
        return await flowers_show_full_confirmation(update, context)

    elif query.data == "payment_bonus_max":
        # Использовать максимум доступных бонусов
        cart = context.user_data.get('cart', [])
        subtotal = sum(item['price'] * item['quantity'] for item in cart)
        delivery_type = context.user_data.get('delivery_type', 'Самовывоз')
        delivery_cost = 0 if delivery_type == "Самовывоз" else calculate_delivery_cost(subtotal)
        total = subtotal + delivery_cost

        user_id = update.effective_user.id
        bonus_balance = get_bonus_balance(user_id)
        max_bonus_use = int(total * MAX_BONUS_PAYMENT_PERCENT / 100)
        available_bonus = min(bonus_balance, max_bonus_use)

        context.user_data['bonus_used'] = available_bonus
        return await flowers_show_full_confirmation(update, context)

    elif query.data == "payment_bonus_partial":
        await query.edit_message_text(
            "💎 Введите количество бонусов для использования:\n\n"
            "(или напишите 'все' чтобы использовать максимум)"
        )
        context.user_data['waiting_for_bonus_input'] = True
        return FLOWERS_PAYMENT

    return FLOWERS_PAYMENT


async def flowers_enter_bonus_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ввод пользовательского количества бонусов"""

    text = update.message.text.lower().strip()

    cart = context.user_data.get('cart', [])
    subtotal = sum(item['price'] * item['quantity'] for item in cart)
    delivery_type = context.user_data.get('delivery_type', 'Самовывоз')
    delivery_cost = 0 if delivery_type == "Самовывоз" else calculate_delivery_cost(subtotal)
    total = subtotal + delivery_cost

    user_id = update.effective_user.id
    bonus_balance = get_bonus_balance(user_id)
    max_bonus_use = int(total * MAX_BONUS_PAYMENT_PERCENT / 100)
    available_bonus = min(bonus_balance, max_bonus_use)

    if text in ["все", "всё", "все бонусы"]:
        context.user_data['bonus_used'] = available_bonus
    else:
        try:
            amount = int(text)

            if amount < 0:
                await update.message.reply_text("❌ Количество должно быть положительным")
                return FLOWERS_PAYMENT

            if amount > available_bonus:
                await update.message.reply_text(
                    f"❌ Недостаточно бонусов.\n"
                    f"Доступно: {available_bonus}\n"
                    f"Максимум можно использовать: {available_bonus} ({MAX_BONUS_PAYMENT_PERCENT}% от суммы)"
                )
                return FLOWERS_PAYMENT

            context.user_data['bonus_used'] = amount
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат. Введите число или 'все'"
            )
            return FLOWERS_PAYMENT

    context.user_data.pop('waiting_for_bonus_input', None)
    return await flowers_show_full_confirmation(update, context)


async def flowers_show_full_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать полное подтверждение заказа со всеми деталями"""

    cart = context.user_data.get('cart', [])
    delivery_type = context.user_data.get('delivery_type', 'Самовывоз')
    delivery_address = context.user_data.get('delivery_address', '')
    delivery_time = context.user_data.get('delivery_time', 'Не указано')
    is_anonymous = context.user_data.get('is_anonymous', False)
    card_text = context.user_data.get('card_text', '')
    recipient_name = context.user_data.get('recipient_name', 'Не указан')
    recipient_phone = context.user_data.get('recipient_phone', '')
    bonus_used = context.user_data.get('bonus_used', 0)

    # Получить информацию о ценах (была сохранена ранее)
    pricing_info = context.user_data.get('pricing_info')

    if not pricing_info:
        # Если не сохранена, пересчитать
        user_id = update.effective_user.id
        cart_items = [{'price': item['price'], 'quantity': item['quantity'], 'type': 'flower'} for item in cart]
        base_subtotal = sum(item['price'] * item['quantity'] for item in cart)
        delivery_cost = 0 if delivery_type == "Самовывоз" else calculate_delivery_cost(base_subtotal)
        pricing_info = calculate_cart_total(user_id, cart_items, delivery_cost)

    total = pricing_info['final_total']
    total_after_bonus = total - bonus_used

    # Текст подтверждения
    text = "✅ ПОДТВЕРДИТЕ ЗАКАЗ:\n\n"

    text += "🛒 Состав заказа:\n"
    for item in pricing_info['items_with_discount']:
        item_total = item['final_price'] * item['quantity']
        text += f"   • {item.get('name', 'Товар')} × {item['quantity']} = {format_price(item_total)}"

        if item.get('discount_percent', 0) > 0:
            text += f" (скидка {item['discount_percent']}%)"
        text += "\n"

    text += "\n"
    text += format_price_summary(pricing_info, show_delivery=True)

    if bonus_used > 0:
        text += f"💎 Оплачено бонусами: -{format_price(bonus_used)}\n"
        text += f"💵 К оплате: {format_price(total_after_bonus)}\n"

    text += "\n"

    text += f"📦 Получение: {delivery_type}\n"
    if delivery_type == "Доставка":
        text += f"📍 Адрес: {delivery_address}\n"
    text += f"⏰ Время: {delivery_time}\n"
    text += f"🎭 Анонимно: {'Да' if is_anonymous else 'Нет'}\n"

    if card_text:
        text += f"💌 Открытка: \"{card_text[:50]}{'...' if len(card_text) > 50 else ''}\"\n"

    text += f"\n👤 Получатель:\n"
    text += f"   Имя: {recipient_name}\n"
    if recipient_phone:
        text += f"   Телефон: {recipient_phone}\n"

    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить заказ", callback_data="confirm_full_order")],
        [InlineKeyboardButton("◀️ Изменить", callback_data="flowers_shop")]
    ]

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    return FLOWERS_CONFIRM


async def flowers_create_full_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Финальное создание заказа с полными данными"""

    query = update.callback_query
    await query.answer()

    user = update.effective_user
    cart = context.user_data.get('cart', [])

    try:
        # Собрать все данные
        delivery_type = context.user_data.get('delivery_type', 'Самовывоз')
        delivery_address = context.user_data.get('delivery_address', '')
        delivery_time = context.user_data.get('delivery_time', '')
        is_anonymous = context.user_data.get('is_anonymous', False)
        card_text = context.user_data.get('card_text', '')
        recipient_name = context.user_data.get('recipient_name', '')
        recipient_phone = context.user_data.get('recipient_phone', '')
        bonus_used = context.user_data.get('bonus_used', 0)

        # Подсчет
        subtotal = sum(item['price'] * item['quantity'] for item in cart)
        delivery_cost = 0 if delivery_type == "Самовывоз" else calculate_delivery_cost(subtotal)
        total = subtotal + delivery_cost

        # Создать строку состава
        composition = ", ".join([f"{item['name']} x{item['quantity']}" for item in cart])

        # Получить телефон
        user_data = get_user(user.id)
        phone = recipient_phone or (user_data[3] if user_data else '')

        # Создать заказ в БД
        items_json = json.dumps(cart, ensure_ascii=False)

        order_id = add_flower_order(
            user_id=user.id,
            user_name=user.first_name,
            phone=phone,
            items=items_json,
            total_amount=total - bonus_used,
            delivery_type='delivery' if delivery_type == "Доставка" else 'pickup',
            delivery_address=delivery_address,
            delivery_time=delivery_time,
            anonymous=is_anonymous,
            card_text=card_text,
            recipient_name=recipient_name,
            recipient_phone=recipient_phone
        )

        if not order_id:
            raise Exception("Не удалось создать заказ в БД")

        # Запланировать запрос на отзыв
        schedule_feedback_request(user.id, 'flower_order', order_id)

        # Списать бонусы если использовались
        if bonus_used > 0:
            subtract_bonus_points(user.id, bonus_used, f"Оплата заказа цветов #{order_id}")
            logger.info(f"Списано {bonus_used} бонусов у пользователя {user.id}")

        # Начислить бонусы за заказ (5% если >= 3000)
        if total >= FREE_DELIVERY_THRESHOLD:
            bonus_earned = int(total * BONUS_PERCENT / 100)
            add_bonus_points(user.id, bonus_earned, f"Заказ цветов #{order_id}")
            bonus_message = f"\n\n🎁 Вам начислено {bonus_earned} бонусов!"
        else:
            bonus_message = ""

        # Проверить и начислить реферальный бонус
        try:
            check_and_award_referral_bonus(order_id, user.id, total - bonus_used)
            logger.info(f"Проверен реферальный бонус для заказа #{order_id}")
        except Exception as e:
            logger.error(f"Ошибка проверки реферального бонуса: {e}")

        # Обновить статистику конверсий UTM
        try:
            user_data = get_user(user.id)
            if user_data and len(user_data) > 9 and user_data[9]:  # utm_source exists
                utm_code = f"{user_data[9]}__{user_data[10] or ''}__{user_data[11] or ''}__{user_data[12] or ''}__{user_data[13] or ''}"
                update_utm_campaign_stats(utm_code, 'conversion', total - bonus_used)
                logger.info(f"Обновлена UTM-статистика конверсии: {utm_code}")
        except Exception as e:
            logger.error(f"Ошибка обновления UTM-статистики: {e}")

        # Отправить в админ-группу
        admin_text = (
            "🆕 <b>НОВЫЙ ЗАКАЗ ЦВЕТОВ</b>\n\n"
            f"📋 Номер: #{order_id}\n"
            f"👤 Заказчик: {user.first_name}"
        )

        if user.username:
            admin_text += f" (@{user.username})"

        admin_text += (
            f"\n📞 Заказчик: {get_user(user.id)[3] if get_user(user.id) else 'Не указан'}\n\n"
            f"🛒 Состав:\n{composition}\n\n"
            f"💰 Сумма: {format_price(subtotal)}\n"
        )

        if delivery_cost > 0:
            admin_text += f"🚚 Доставка: {format_price(delivery_cost)}\n"
        else:
            admin_text += "🚚 Доставка: БЕСПЛАТНО\n"

        if bonus_used > 0:
            admin_text += f"💎 Оплачено бонусами: {format_price(bonus_used)}\n"

        admin_text += (
            f"━━━━━━━━━━━━━━━\n"
            f"💵 К оплате: {format_price(total - bonus_used)}\n\n"
        )

        if delivery_type == "Доставка":
            admin_text += (
                f"📍 Адрес: {delivery_address}\n"
                f"⏰ Время: {delivery_time}\n"
            )
        else:
            admin_text += "📦 Самовывоз из салона\n"

        admin_text += f"🎭 Анонимно: {'ДА' if is_anonymous else 'НЕТ'}\n"

        if card_text:
            admin_text += f"💌 Открытка: \"{card_text}\"\n"

        admin_text += (
            f"\n👤 Получатель:\n"
            f"   Имя: {recipient_name}\n"
        )

        if recipient_phone:
            admin_text += f"   Телефон: {recipient_phone}\n"

        # Отправить в топик пользователя в админ-группе
        await send_to_user_topic(context, user.id, user.first_name, admin_text, None)

        # TODO: Запланировать запрос отзыва через 24 часа (сделаем позже)

        # Ответить клиенту
        await query.edit_message_text(
            f"🎉 Заказ успешно оформлен!\n\n"
            f"Номер заказа: #{order_id}\n\n"
            f"💵 К оплате: {format_price(total - bonus_used)}\n\n"
            f"Мы свяжемся с вами для подтверждения.\n"
            f"Курьер доставит букет в указанное время.{bonus_message}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")
            ]])
        )

        # Очистить данные
        context.user_data.clear()

        logger.info(f"Создан заказ цветов #{order_id} для пользователя {user.id}")

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка при создании заказа: {e}")
        await query.edit_message_text(
            "❌ Произошла ошибка при создании заказа.\n"
            "Попробуйте позже или свяжитесь с администратором.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 В меню", callback_data="main_menu")
            ]])
        )
        return ConversationHandler.END


# =================================================================
# ИНДИВИДУАЛЬНЫЙ ЗАКАЗ БУКЕТА
# =================================================================

async def custom_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало индивидуального заказа"""

    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🎨 ИНДИВИДУАЛЬНЫЙ БУКЕТ\n\n"
        "Опишите словами, какой букет вы хотите:\n\n"
        "• Какие цветы?\n"
        "• Цветовая гамма?\n"
        "• Размер?\n"
        "• Повод?\n"
        "• Бюджет?\n\n"
        "Пример: \"Хочу букет из розовых пионов и белых роз, "
        "размер средний, на день рождения, бюджет до 4000₽\"\n\n"
        "Напишите ваши пожелания:"
    )

    return 0  # CUSTOM_ORDER_DESCRIPTION


async def custom_order_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка описания индивидуального заказа"""

    description = update.message.text
    user = update.effective_user

    # Отправить в админ-группу
    admin_text = (
        "🎨 <b>ИНДИВИДУАЛЬНЫЙ ЗАКАЗ БУКЕТА</b>\n\n"
        f"👤 От: {user.first_name}"
    )

    if user.username:
        admin_text += f" (@{user.username})"

    user_data = get_user(user.id)
    if user_data and user_data[3]:
        admin_text += f"\n📞 Телефон: {user_data[3]}"

    admin_text += (
        f"\n🆔 User ID: {user.id}\n\n"
        f"📝 Описание:\n{description}"
    )

    admin_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Ответить клиенту", url=f"tg://user?id={user.id}")]
    ])

    # Отправить в топик пользователя в админ-группе
    await send_to_user_topic(context, user.id, user.first_name, admin_text, admin_keyboard)

    await update.message.reply_text(
        "✅ Ваш запрос принят!\n\n"
        "Администратор свяжется с вами в ближайшее время "
        "для уточнения деталей и расчета стоимости.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")
        ]])
    )

    logger.info(f"Индивидуальный заказ от пользователя {user.id}")

    return ConversationHandler.END
