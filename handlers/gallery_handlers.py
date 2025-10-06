"""
Обработчики галереи работ.
Фотогалерея работ салона и букетов.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_gallery_items

logger = logging.getLogger(__name__)


async def gallery_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать галерею"""

    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("💇‍♀️ Работы салона", callback_data="gallery_salon")],
        [InlineKeyboardButton("💐 Наши букеты", callback_data="gallery_flowers")],
        [InlineKeyboardButton("📸 Все фото", callback_data="gallery_all")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
    ]

    await query.edit_message_text(
        "📸 НАШИ РАБОТЫ\n\nВыберите категорию:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def gallery_show_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать фото категории"""

    query = update.callback_query
    await query.answer()

    # Определить категорию
    if query.data == "gallery_salon":
        category = "Салон"
        title = "💇‍♀️ Работы салона"
    elif query.data == "gallery_flowers":
        category = "Цветы"
        title = "💐 Наши букеты"
    else:
        category = None
        title = "📸 Все фото"

    try:
        # Получить фото из БД
        photos = get_gallery_items(category=category)

        if not photos:
            await query.edit_message_text(
                f"{title}\n\n❌ Пока нет фотографий",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="gallery")
                ]])
            )
            return

        # Отправить фото (максимум 10)
        await query.message.reply_text(f"{title}:")

        for photo in photos[:10]:
            photo_url = photo.get('photo_url')
            description = photo.get('description', '')

            caption = description if description else "📸 Наша работа"

            try:
                await query.message.reply_photo(
                    photo=photo_url,
                    caption=caption
                )
            except Exception as e:
                logger.error(f"Ошибка загрузки фото {photo_url}: {e}")
                continue

        # Кнопка назад
        await query.message.reply_text(
            "◀️ Вернуться в галерею",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="gallery")
            ]])
        )

        # Удалить исходное сообщение
        await query.message.delete()

    except Exception as e:
        logger.error(f"Ошибка отображения галереи: {e}")
        await query.edit_message_text(
            "❌ Ошибка загрузки галереи",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="gallery")
            ]])
        )
