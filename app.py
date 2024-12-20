from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.utils import secure_filename
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Устанавливаем DB_TYPE в 'sqlite'
app.config['DB_TYPE'] = 'sqlite'

# Остальные настройки приложения
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'секретно-секретный секрет')

# Настройка загрузки файлов
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'RGZ', 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Проверка, является ли файл разрешенным
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_admin():
    return session.get('user_id') and session.get('role') == 'admin'

# Функция для подключения к базе данных
def db_connect():
    db_path = '/home/irinaproskuryakova/RGZ/database.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Используем sqlite3.Row для доступа к данным через ключи
    cur = conn.cursor()
    return conn, cur

# Функция для закрытия соединения с базой данных
def db_close(conn, cur):
    conn.commit()
    cur.close()
    conn.close()

# Главная страница
@app.route('/')
def index():
    conn, cur = db_connect()
    cur.execute("SELECT * FROM advertisements ORDER BY author_id DESC;")
    ads = cur.fetchall()
    db_close(conn, cur)

    # Преобразуем объекты sqlite3.Row в словари
    ads = [dict(ad) for ad in ads]

    # Отладочный вывод
    print(ads)  # Вывод данных в консоль

    # Получение информации о пользователях для каждого объявления
    for ad in ads:
        conn, cur = db_connect()
        cur.execute("SELECT name, email, avatar FROM users WHERE id=?;", (ad['author_id'],))
        user = cur.fetchone()
        db_close(conn, cur)

        # Преобразуем объект sqlite3.Row в словарь
        user = dict(user) if user else {}

        ad['author_name'] = user.get('name', 'Unknown')
        ad['author_email'] = user.get('email') if session.get('user_id') else None
        ad['author_avatar'] = user.get('avatar')  # Добавляем аватар пользователя

    return render_template('index.html', ads=ads)

# Регистрация
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    login = request.form.get('login')
    password = request.form.get('password')
    name = request.form.get('name')
    email = request.form.get('email')
    about = request.form.get('about')

    # Обработка загрузки аватарки
    avatar = request.files.get('avatar')
    avatar_path = None
    if avatar and allowed_file(avatar.filename):
        filename = secure_filename(avatar.filename)
        avatar_path = os.path.join('static', 'uploads', filename).replace('\\', '/')
        avatar.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    if not (login and password and name and email):
        return render_template('register.html', error='Заполните все обязательные поля')

    conn, cur = db_connect()

    # Проверка, существует ли пользователь с таким логином или email
    cur.execute("SELECT * FROM users WHERE login=? OR email=?;", (login, email))
    existing_user = cur.fetchone()
    if existing_user:
        db_close(conn, cur)
        return render_template('register.html', error='Пользователь с таким логином или email уже существует')

    # Хеширование пароля
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

    # Добавление нового пользователя в базу данных
    cur.execute("""
        INSERT INTO users (login, password, name, email, about, avatar)
        VALUES (?, ?, ?, ?, ?, ?);
    """, (login, hashed_password, name, email, about, avatar_path))

    db_close(conn, cur)
    flash('Регистрация прошла успешно', 'success')
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    login = request.form.get('login')
    password = request.form.get('password')

    if not (login and password):
        return render_template('login.html', error='Заполните все поля')

    conn, cur = db_connect()

    cur.execute("SELECT * FROM users WHERE login=?;", (login,))
    user = cur.fetchone()

    if not user or not check_password_hash(user['password'], password):
        db_close(conn, cur)
        return render_template('login.html', error='Неверный логин или пароль')

    db_close(conn, cur)
    session['user_id'] = user['id']
    session['user_name'] = user['name']
    session['role'] = user['role']
    flash('Вы успешно вошли в систему', 'success')
    return redirect(url_for('index'))

# Выход
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('role', None)
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('index'))

@app.route('/create_ad', methods=['GET', 'POST'])
def create_ad():
    if not session.get('user_id'):
        flash('Вы не авторизованы', 'error')
        return redirect(url_for('login'))

    if request.method == 'GET':
        return render_template('create_ad.html')

    title = request.form.get('title')
    text = request.form.get('text')
    image = request.files.get('image')

    if not (title and text):
        return render_template('create_ad.html', error='Заполните все поля')

    # Обработка загрузки изображения
    image_path = None
    if image and allowed_file(image.filename):
        filename = secure_filename(image.filename)
        image_path = os.path.join('static', 'uploads', filename).replace('\\', '/')
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    conn, cur = db_connect()
    cur.execute("""
        INSERT INTO advertisements (title, text, author_id, image)
        VALUES (?, ?, ?, ?);
    """, (title, text, session['user_id'], image_path))
    db_close(conn, cur)

    flash('Объявление успешно создано', 'success')
    return redirect(url_for('index'))

# Редактирование объявления
@app.route('/edit_ad/<int:ad_id>', methods=['GET', 'POST'])
def edit_ad(ad_id):
    if not session.get('user_id'):
        flash('Вы не авторизованы', 'error')
        return redirect(url_for('login'))

    conn, cur = db_connect()
    cur.execute("SELECT * FROM advertisements WHERE id=?;", (ad_id,))
    ad = cur.fetchone()
    db_close(conn, cur)

    if not ad:
        flash('Объявление не найдено', 'error')
        return redirect(url_for('index'))

    # Проверка прав: либо автор объявления, либо администратор
    if ad['author_id'] != session['user_id'] and not is_admin():
        flash('У вас нет прав на редактирование этого объявления', 'error')
        return redirect(url_for('index'))

    if request.method == 'GET':
        return render_template('edit_ad.html', ad=ad)

    title = request.form.get('title')
    text = request.form.get('text')
    image = request.files.get('image')  # Получаем загруженное изображение

    if not (title and text):
        return render_template('edit_ad.html', ad=ad, error='Заполните все поля')

    # Обработка загрузки изображения
    image_path = ad['image']
    if image and allowed_file(image.filename):
        filename = secure_filename(image.filename)
        image_path = os.path.join('uploads', filename).replace('\\', '/')
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    conn, cur = db_connect()
    cur.execute("""
        UPDATE advertisements SET title=?, text=?, image=? WHERE id=?;
    """, (title, text, image_path, ad_id))
    db_close(conn, cur)

    flash('Объявление успешно обновлено', 'success')
    return redirect(url_for('index'))

# Удаление объявления
@app.route('/delete_ad/<int:ad_id>', methods=['POST'])
def delete_ad(ad_id):
    if not session.get('user_id'):
        flash('Вы не авторизованы', 'error')
        return redirect(url_for('login'))

    conn, cur = db_connect()
    cur.execute("SELECT * FROM advertisements WHERE id=?;", (ad_id,))
    ad = cur.fetchone()

    if not ad:
        db_close(conn, cur)
        flash('Объявление не найдено', 'error')
        return redirect(url_for('index'))

    # Проверка прав: либо автор объявления, либо администратор
    if ad['author_id'] != session['user_id'] and not is_admin():
        db_close(conn, cur)
        flash('У вас нет прав на удаление этого объявления', 'error')
        return redirect(url_for('index'))

    cur.execute("DELETE FROM advertisements WHERE id=?;", (ad_id,))
    db_close(conn, cur)

    flash('Объявление успешно удалено', 'success')
    return redirect(url_for('index'))

# Управление пользователями (администратор)
@app.route('/admin/users')
def admin_users():
    if not is_admin():
        flash('У вас нет прав доступа', 'error')
        return redirect(url_for('index'))

    conn, cur = db_connect()
    cur.execute("SELECT id, login, name, email, role FROM users;")
    users = cur.fetchall()
    db_close(conn, cur)

    return render_template('admin_users.html', users=users)

@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
def admin_edit_user(user_id):
    if not is_admin():
        flash('У вас нет прав доступа', 'error')
        return redirect(url_for('index'))

    conn, cur = db_connect()
    cur.execute("SELECT * FROM users WHERE id=?;", (user_id,))
    user = cur.fetchone()
    db_close(conn, cur)

    if not user:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('admin_users'))

    if request.method == 'GET':
        return render_template('admin_edit_user.html', user=user)

    name = request.form.get('name')
    email = request.form.get('email')
    role = request.form.get('role')

    if not (name and email and role):
        return render_template('admin_edit_user.html', user=user, error='Заполните все поля')

    conn, cur = db_connect()
    cur.execute("""
        UPDATE users SET name=?, email=?, role=? WHERE id=?;
    """, (name, email, role, user_id))
    db_close(conn, cur)

    flash('Пользователь успешно обновлен', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    if not is_admin():
        flash('У вас нет прав доступа', 'error')
        return redirect(url_for('index'))

    conn, cur = db_connect()
    cur.execute("SELECT * FROM users WHERE id=?;", (user_id,))
    user = cur.fetchone()

    if not user:
        db_close(conn, cur)
        flash('Пользователь не найден', 'error')
        return redirect(url_for('admin_users'))

    cur.execute("DELETE FROM users WHERE id=?;", (user_id,))
    db_close(conn, cur)

    flash('Пользователь успешно удален', 'success')
    return redirect(url_for('admin_users'))

if __name__ == '__main__':
    # Создание папки для загрузки файлов, если она не существует
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)