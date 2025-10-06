# 🌸 Beauty Salon Bot

Telegram-бот для салона красоты и цветочного магазина.

## 📋 Возможности

### 💇 Салон красоты
- Запись на услуги
- Выбор даты и времени
- Оплата и предоплата
- Система бонусов

### 🌺 Цветочный магазин
- Каталог товаров с фото
- Корзина покупок
- Доставка и самовывоз
- Индивидуальные заказы

### 🎁 Дополнительно
- Подарочные сертификаты
- Галерея работ
- Отзывы клиентов
- Реферальная программа
- Личный кабинет

## 🚀 Быстрый старт

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 2. Настройка окружения
```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

Заполните `.env` файл вашими данными.

### 3. Настройка Google Sheets
См. подробную инструкцию: **[GOOGLE_SETUP.md](GOOGLE_SETUP.md)**

### 4. Проверка подключения
```bash
python test_connection.py
```

### 5. Запуск бота
```bash
python main.py
```

## 📚 Документация

### Начало работы
- **[SETUP_INSTRUCTIONS.md](SETUP_INSTRUCTIONS.md)** - Полная инструкция по установке и настройке
- **[GOOGLE_SETUP.md](GOOGLE_SETUP.md)** - Настройка Google Sheets API
- **[DATA_STRUCTURE.md](DATA_STRUCTURE.md)** - Структура данных в Google Таблице
- **[FORUM_GROUP_SETUP.md](FORUM_GROUP_SETUP.md)** - Настройка форум-группы с топиками (ветками)

### Запуск и тестирование
- **[QUICK_START.md](QUICK_START.md)** - ⚡ Быстрый старт (5 минут)
- **[LOCAL_TESTING.md](LOCAL_TESTING.md)** - 🧪 Полное локальное тестирование (читать первым!)
- **[LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md)** - Чеклист перед запуском (100+ пунктов)
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Руководство по тестированию (58 сценариев)

### Решение проблем
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Решение частых проблем (30+ ошибок)

### Отчеты
- **[RELEASE_REPORT.md](RELEASE_REPORT.md)** - Отчет о готовности к релизу

## 🛠️ Требования

- Python 3.9+
- Google Cloud проект с Google Sheets API
- Telegram Bot токен
- Google Таблица

## 📦 Основные зависимости

- `python-telegram-bot` (21.9+) - Telegram Bot API
- `gspread` (6.1.4+) - Google Sheets API
- `oauth2client` (4.1.3+) - OAuth авторизация
- `APScheduler` (3.10.4+) - Планировщик задач
- `pytz` (2024.2+) - Часовые пояса
- `python-dotenv` (1.0.1+) - Переменные окружения

## 📁 Структура проекта

```
beauty_salon_bot/
├── main.py                    # Точка входа
├── config.py                  # Конфигурация
├── database.py                # База данных SQLite
├── google_sheets.py           # Интеграция с Google Sheets
├── test_connection.py         # Скрипт проверки
├── handlers/                  # Обработчики команд
│   ├── start_handler.py
│   ├── salon_handlers.py
│   ├── flowers_handlers.py
│   ├── profile_handlers.py
│   ├── certificate_handlers.py
│   ├── gallery_handlers.py
│   ├── reviews_handlers.py
│   ├── support_handlers.py
│   └── admin_handlers.py
├── utils/                     # Утилиты
│   ├── calendar.py
│   ├── helpers.py
│   └── validators.py
├── data/                      # База данных (создается автоматически)
├── .env                       # Переменные окружения (создайте сами)
├── .env.example               # Шаблон .env
├── credentials.json           # Google Service Account (создайте сами)
└── requirements.txt           # Зависимости
```

## ⚙️ Конфигурация

### Переменные окружения (.env)

```env
TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather
ADMIN_ID=ваш_telegram_id
ADMIN_GROUP_ID=id_админ_группы (опционально)
GOOGLE_SHEET_ID=id_google_таблицы
```

### Получение токенов

1. **Telegram Bot Token**: [@BotFather](https://t.me/BotFather)
2. **Admin ID**: [@userinfobot](https://t.me/userinfobot)
3. **Admin Group ID**: [@getidsbot](https://t.me/getidsbot)
4. **Google Sheet ID**: Из URL таблицы

## 🔐 Безопасность

- ❌ НЕ коммитьте `.env` в git
- ❌ НЕ коммитьте `credentials.json` в git
- ✅ Используйте `.env.example` как шаблон
- ✅ Файл `.gitignore` уже настроен

## 📊 Google Таблица

Необходимо создать таблицу с **7 листами**:

1. **Услуги** - услуги салона
2. **Товары** - цветочные товары
3. **Записи** - записи клиентов
4. **Заказы_цветы** - заказы цветов
5. **Сертификаты** - подарочные сертификаты
6. **Галерея** - фото работ
7. **Отзывы** - отзывы клиентов

Подробная структура: **[DATA_STRUCTURE.md](DATA_STRUCTURE.md)**

## 🧪 Тестирование

### Проверка подключения
```bash
python test_connection.py
```

### Полное тестирование
См. руководство: **[TESTING_GUIDE.md](TESTING_GUIDE.md)**

## 🐛 Решение проблем

### Частые ошибки

**Ошибка:** `ModuleNotFoundError: No module named 'telegram'`
```bash
pip install python-telegram-bot==21.9
```

**Ошибка:** `TELEGRAM_BOT_TOKEN не установлен`
- Проверьте наличие `.env` файла
- Убедитесь, что токен заполнен

**Ошибка:** `SpreadsheetNotFound`
- Проверьте `GOOGLE_SHEET_ID` в `.env`
- Убедитесь, что Service Account добавлен в доступ к таблице

Больше решений: **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**

## 📈 Статистика проекта

- **Строки кода:** 8,600+
- **Python файлов:** 19
- **Документации:** 6 MD файлов
- **Handlers:** 10 модулей
- **ConversationHandlers:** 7
- **Google Sheets методы:** 20+

## 🎯 Готовность к релизу

**Статус:** ✅ **95% готов**

**Готово:**
- ✅ Код написан (100%)
- ✅ Критические баги исправлены (100%)
- ✅ Безопасность обеспечена (100%)
- ✅ Документация создана (100%)
- ✅ Retry механизм добавлен (100%)

**Требует действий:**
- ⏳ Создание credentials.json
- ⏳ Заполнение .env
- ⏳ Настройка Google Таблицы

## 🔗 Полезные ссылки

### Документация
- [python-telegram-bot](https://docs.python-telegram-bot.org/)
- [gspread](https://docs.gspread.org/)
- [Google Sheets API](https://developers.google.com/sheets/api)

### Сервисы
- [Google Cloud Console](https://console.cloud.google.com/)
- [Telegram BotFather](https://t.me/BotFather)

### Боты-помощники
- [@userinfobot](https://t.me/userinfobot) - узнать Telegram ID
- [@getidsbot](https://t.me/getidsbot) - узнать ID группы
- [@raw_data_bot](https://t.me/raw_data_bot) - получить File ID фото

## 📝 Лицензия

Этот проект создан для салона красоты в г. Челябинск.

## 🤝 Поддержка

При возникновении проблем:
1. Проверьте **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**
2. Запустите `python test_connection.py`
3. Проверьте логи в `bot.log`

## 📞 Контакты

- Город: Челябинск
- Часовой пояс: UTC+5 (Asia/Yekaterinburg)

---

**Удачного запуска! 🚀**

_Telegram Bot для салона красоты и цветочного магазина_
