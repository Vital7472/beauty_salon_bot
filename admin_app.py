"""
Админ-панель для бота салона красоты и цветов - MVP версия
Функционал: Галерея, Заказы цветов, Пользователи, Техподдержка
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import os
from datetime import datetime

# Импорты из database
from database import (
    # Пользователи
    get_all_users, get_user,
    # Галерея
    get_gallery_photos, get_gallery_photo_by_id, add_gallery_photo, delete_gallery_photo,
    # Заказы цветов
    get_flower_orders, get_flower_order_by_id, update_flower_order_status,
    # Техподдержка
    get_support_messages, get_support_message_by_id, get_user_support_messages,
    send_support_message_to_user
)

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev_secret_key_change_in_production')

# Конфигурация загрузки файлов
UPLOAD_FOLDER = 'static/uploads/gallery'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 МБ

# =================================================================
# АВТОРИЗАЦИЯ
# =================================================================

def login_required(f):
    """Декоратор для защиты маршрутов"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Простая авторизация (в продакшене использовать хеширование)
        if username == 'admin' and password == 'admin123':
            session['logged_in'] = True
            session['username'] = username
            flash('Вход выполнен успешно!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Выход"""
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))


# =================================================================
# ГЛАВНАЯ СТРАНИЦА
# =================================================================

@app.route('/')
@login_required
def index():
    """Дашборд"""
    # Статистика
    users = get_all_users()
    orders = get_flower_orders(status='new')
    support_messages = get_support_messages()

    # Непрочитанные сообщения поддержки
    unread_support = [msg for msg in support_messages if not msg.get('admin_reply')]

    stats = {
        'users_total': len(users),
        'orders_new': len(orders),
        'support_unread': len(unread_support),
    }

    return render_template('index.html', stats=stats)


# =================================================================
# ГАЛЕРЕЯ
# =================================================================

@app.route('/gallery')
@login_required
def gallery_list():
    """Список фото галереи"""
    category = request.args.get('category', 'all')

    if category == 'all':
        photos = get_gallery_photos()
    else:
        photos = [p for p in get_gallery_photos() if p.get('category') == category]

    return render_template('gallery/list.html', photos=photos, category=category)


def allowed_file(filename):
    """Проверка расширения файла"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/gallery/add', methods=['GET', 'POST'])
@login_required
def gallery_add():
    """Добавить фото"""
    if request.method == 'POST':
        category = request.form.get('category')
        description = request.form.get('description')

        if 'photo' not in request.files:
            flash('Не выбран файл', 'error')
            return redirect(request.url)

        file = request.files['photo']

        if file.filename == '':
            flash('Не выбран файл', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            # Генерация уникального имени
            import uuid
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"

            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            # Создать папку если не существует
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

            file.save(filepath)

            # Сохранить в БД
            add_gallery_photo(filename, category, description)

            flash('Фото добавлено в галерею', 'success')
            return redirect(url_for('gallery_list'))
        else:
            flash('Недопустимый формат файла. Используйте: PNG, JPG, JPEG, GIF', 'error')

    return render_template('gallery/add.html')


@app.route('/gallery/<int:photo_id>/delete', methods=['POST'])
@login_required
def gallery_delete(photo_id):
    """Удалить фото"""
    photo = get_gallery_photo_by_id(photo_id)

    if photo:
        # Удалить файл
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], photo['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)

        # Удалить из БД
        delete_gallery_photo(photo_id)
        flash('Фото удалено', 'success')
    else:
        flash('Фото не найдено', 'error')

    return redirect(url_for('gallery_list'))


# =================================================================
# ЗАКАЗЫ ЦВЕТОВ
# =================================================================

@app.route('/orders')
@login_required
def orders_list():
    """Список заказов"""
    status_filter = request.args.get('status', 'all')

    if status_filter == 'all':
        orders = get_flower_orders()
    else:
        orders = get_flower_orders(status=status_filter)

    return render_template('orders/list.html', orders=orders, status_filter=status_filter)


@app.route('/orders/<int:order_id>')
@login_required
def order_detail(order_id):
    """Детали заказа"""
    order = get_flower_order_by_id(order_id)

    if not order:
        flash('Заказ не найден', 'error')
        return redirect(url_for('orders_list'))

    return render_template('orders/detail.html', order=order)


@app.route('/orders/<int:order_id>/status', methods=['POST'])
@login_required
def order_update_status(order_id):
    """Обновить статус заказа"""
    new_status = request.form.get('status')

    if new_status not in ['new', 'accepted', 'delivering', 'delivered', 'cancelled']:
        flash('Недопустимый статус', 'error')
        return redirect(url_for('order_detail', order_id=order_id))

    # Обновить статус с отправкой уведомления
    update_flower_order_status(order_id, new_status, send_notification=True)

    flash(f'Статус заказа обновлен на: {new_status}', 'success')
    return redirect(url_for('order_detail', order_id=order_id))


# =================================================================
# ПОЛЬЗОВАТЕЛИ
# =================================================================

@app.route('/users')
@login_required
def users_list():
    """Список пользователей"""
    users = get_all_users()
    return render_template('users/list.html', users=users)


@app.route('/users/<int:user_id>')
@login_required
def user_detail(user_id):
    """Детали пользователя"""
    user = get_user(user_id)

    if not user:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('users_list'))

    # Получить заказы пользователя
    user_orders = get_flower_orders(user_id=user_id)

    # Получить сообщения поддержки
    support_messages = get_user_support_messages(user_id)

    return render_template('users/detail.html',
                         user=user,
                         orders=user_orders,
                         support_messages=support_messages)


# =================================================================
# ТЕХПОДДЕРЖКА
# =================================================================

@app.route('/support')
@login_required
def support_list():
    """Список обращений"""
    messages = get_support_messages()
    return render_template('support/list.html', messages=messages)


@app.route('/support/<int:message_id>')
@login_required
def support_detail(message_id):
    """Детали обращения"""
    message = get_support_message_by_id(message_id)

    if not message:
        flash('Сообщение не найдено', 'error')
        return redirect(url_for('support_list'))

    return render_template('support/detail.html', message=message)


@app.route('/support/<int:message_id>/reply', methods=['POST'])
@login_required
def support_reply(message_id):
    """Ответить на обращение"""
    reply_text = request.form.get('reply_text')

    if not reply_text:
        flash('Введите текст ответа', 'error')
        return redirect(url_for('support_detail', message_id=message_id))

    message = get_support_message_by_id(message_id)

    if message:
        # Отправить ответ пользователю
        success = send_support_message_to_user(message['user_id'], reply_text, message_id)

        if success:
            flash('Ответ отправлен пользователю', 'success')
        else:
            flash('Ошибка отправки ответа', 'error')
    else:
        flash('Сообщение не найдено', 'error')

    return redirect(url_for('support_detail', message_id=message_id))


# =================================================================
# ЗАПУСК
# =================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Запуск админ-панели MVP...")
    print("📍 URL: http://localhost:5000")
    print("👤 Логин: admin")
    print("🔑 Пароль: admin123")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)
