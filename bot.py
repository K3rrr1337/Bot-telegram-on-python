# bot.py (полностью исправленная рабочая версия)
import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import json
import os
import random
import string
import ast

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация - через переменные окружения
TOKEN = os.getenv('BOT_TOKEN', '8921783374:AAGUw6hr-hOGNRixtjP4z6u_y97gapo3B-M')

ADMIN_IDS_RAW = os.getenv('ADMIN_IDS', '[1908250518]')
try:
    ADMIN_IDS = ast.literal_eval(ADMIN_IDS_RAW)
except:
    ADMIN_IDS = [1908250518]

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            coins INTEGER DEFAULT 0,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    
    # Таблица конфигов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price INTEGER NOT NULL,
            price_type TEXT DEFAULT 'coins',
            file_path TEXT,
            photo_path TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица заказов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            config_id INTEGER,
            config_name TEXT,
            price INTEGER,
            payment_type TEXT DEFAULT 'coins',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (config_id) REFERENCES configs (id)
        )
    ''')
    
    # Таблица настроек
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Таблица поддержки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            message TEXT,
            admin_response TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица промокодов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promocodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            coins INTEGER NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0
        )
    ''')
    
    # Таблица использованных промокодов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS used_promocodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            promocode_id INTEGER NOT NULL,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (promocode_id) REFERENCES promocodes (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Работа с БД - Пользователи
def register_user(user_id, username, first_name, last_name):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) 
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name))
    conn.commit()
    conn.close()

def get_user_coins(user_id):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('SELECT coins FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def add_coins(user_id, amount):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def spend_coins(user_id, amount):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET coins = coins - ? WHERE user_id = ? AND coins >= ?', (amount, user_id, amount))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def get_user_info(user_id):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name, last_name, coins, registered_at FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# Работа с БД - Конфиги
def get_all_configs():
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, description, price, price_type, file_path, photo_path, is_active FROM configs WHERE is_active = 1 ORDER BY id DESC')
    configs = cursor.fetchall()
    conn.close()
    return configs

def get_config_by_id(config_id):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, description, price, price_type, file_path, photo_path FROM configs WHERE id = ? AND is_active = 1', (config_id,))
    config = cursor.fetchone()
    conn.close()
    return config

def add_config(name, description, price, price_type, file_path, photo_path=None):
    # Проверка на пустые значения
    if not name or not name.strip():
        raise ValueError("Название товара не может быть пустым")
    
    conn = None
    try:
        conn = sqlite3.connect('clamsi_bot.db', timeout=10)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO configs (name, description, price, price_type, file_path, photo_path) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name.strip(), description, price, price_type, file_path, photo_path))
        conn.commit()
        config_id = cursor.lastrowid
        return config_id
    except sqlite3.OperationalError as e:
        logger.error(f"Ошибка БД: {e}")
        raise
    finally:
        if conn:
            conn.close()

def update_config(config_id, name, description, price, price_type, file_path, photo_path=None):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE configs 
        SET name = ?, description = ?, price = ?, price_type = ?, file_path = ?, photo_path = ?
        WHERE id = ?
    ''', (name, description, price, price_type, file_path, photo_path, config_id))
    conn.commit()
    conn.close()

def delete_config(config_id):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('UPDATE configs SET is_active = 0 WHERE id = ?', (config_id,))
    conn.commit()
    conn.close()

# Работа с БД - Заказы
def add_order(user_id, username, config_id, config_name, price, payment_type='coins'):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO orders (user_id, username, config_id, config_name, price, payment_type, status) 
        VALUES (?, ?, ?, ?, ?, ?, 'completed')
    ''', (user_id, username, config_id, config_name, price, payment_type))
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()
    return order_id

def get_user_orders(user_id):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, config_name, price, payment_type, status, created_at 
        FROM orders 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    ''', (user_id,))
    orders = cursor.fetchall()
    conn.close()
    return orders

def get_all_orders():
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('SELECT id, user_id, username, config_name, price, payment_type, status, created_at FROM orders ORDER BY created_at DESC')
    orders = cursor.fetchall()
    conn.close()
    return orders

# Работа с БД - Промокоды
def generate_promocode(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def create_promocode(coins, created_by, max_uses=1, expires_days=None):
    code = generate_promocode()
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    expires_at = None
    if expires_days:
        expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
    cursor.execute('''
        INSERT INTO promocodes (code, coins, created_by, max_uses, expires_at) 
        VALUES (?, ?, ?, ?, ?)
    ''', (code, coins, created_by, max_uses, expires_at))
    conn.commit()
    promocode_id = cursor.lastrowid
    conn.close()
    return code, promocode_id

def get_promocode(code):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, code, coins, is_active, max_uses, used_count, expires_at 
        FROM promocodes 
        WHERE code = ? AND is_active = 1
    ''', (code.upper(),))
    promocode = cursor.fetchone()
    conn.close()
    return promocode

def use_promocode(user_id, promocode_id):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    
    # Проверяем, использовал ли пользователь уже этот промокод
    cursor.execute('SELECT id FROM used_promocodes WHERE user_id = ? AND promocode_id = ?', (user_id, promocode_id))
    if cursor.fetchone():
        conn.close()
        return False, "Вы уже использовали этот промокод"
    
    # Проверяем лимиты
    cursor.execute('SELECT max_uses, used_count, coins FROM promocodes WHERE id = ?', (promocode_id,))
    max_uses, used_count, coins = cursor.fetchone()
    
    if max_uses > 0 and used_count >= max_uses:
        conn.close()
        return False, "Промокод больше не действителен"
    
    # Используем промокод
    cursor.execute('UPDATE promocodes SET used_count = used_count + 1 WHERE id = ?', (promocode_id,))
    cursor.execute('INSERT INTO used_promocodes (user_id, promocode_id) VALUES (?, ?)', (user_id, promocode_id))
    cursor.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?', (coins, user_id))
    
    conn.commit()
    conn.close()
    return True, coins

def get_all_promocodes():
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, code, coins, is_active, max_uses, used_count, expires_at, created_at 
        FROM promocodes 
        ORDER BY created_at DESC
    ''')
    promocodes = cursor.fetchall()
    conn.close()
    return promocodes

def deactivate_promocode(promocode_id):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('UPDATE promocodes SET is_active = 0 WHERE id = ?', (promocode_id,))
    conn.commit()
    conn.close()

# Работа с БД - Поддержка
def create_support_ticket(user_id, username, message):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO support_tickets (user_id, username, message, status) 
        VALUES (?, ?, ?, 'open')
    ''', (user_id, username, message))
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return ticket_id

def get_open_tickets():
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, username, message, created_at 
        FROM support_tickets 
        WHERE status = 'open' 
        ORDER BY created_at DESC
    ''')
    tickets = cursor.fetchall()
    conn.close()
    return tickets

def get_ticket_by_id(ticket_id):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, username, message, status, created_at 
        FROM support_tickets 
        WHERE id = ?
    ''', (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()
    return ticket

def update_ticket_response(ticket_id, admin_response):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE support_tickets 
        SET admin_response = ?, status = 'closed', updated_at = CURRENT_TIMESTAMP 
        WHERE id = ?
    ''', (admin_response, ticket_id))
    conn.commit()
    conn.close()

def get_user_tickets(user_id):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, message, admin_response, status, created_at 
        FROM support_tickets 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    ''', (user_id,))
    tickets = cursor.fetchall()
    conn.close()
    return tickets

# Работа с БД - Настройки
def get_setting(key, default=None):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else default

def set_setting(key, value):
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

def is_admin(user_id):
    return user_id in ADMIN_IDS

# Команды бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text = get_setting('welcome_text', 'Добро пожаловать в магазин конфигов для Clamsi! 🎮\n\nВыберите действие:')
    
    keyboard = [
        [InlineKeyboardButton("📦 Каталог конфигов", callback_data='catalog')],
        [InlineKeyboardButton("👤 Мой профиль", callback_data='profile')],
        [InlineKeyboardButton("📝 Мои заказы", callback_data='my_orders')],
        [InlineKeyboardButton("🎁 Активировать промокод", callback_data='activate_promo')],
        [InlineKeyboardButton("📞 Поддержка", callback_data='support')]
    ]
    
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("⚙️ Админ-панель", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

# Профиль пользователя
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user_info = get_user_info(user_id)
    
    if not user_info:
        await query.edit_message_text("❌ Ошибка загрузки профиля.")
        return
    
    user_id, username, first_name, last_name, coins, registered_at = user_info
    
    text = f"👤 Мой профиль\n\n"
    text += f"🆔 ID: {user_id}\n"
    text += f"👤 Имя: {first_name or 'Не указано'}\n"
    text += f"📛 Юзернейм: @{username or 'Не указан'}\n"
    text += f"🪙 Монет: {coins}\n"
    text += f"📅 Зарегистрирован: {registered_at[:16]}\n"
    
    keyboard = [
        [InlineKeyboardButton("🎁 Активировать промокод", callback_data='activate_promo')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

# Активация промокода
async def activate_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['awaiting_promo'] = True
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='back_to_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🎁 Введите промокод:\n\n"
        "Промокод должен состоять из букв и цифр.",
        reply_markup=reply_markup
    )

async def process_promocode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text.strip().upper()
    
    promocode = get_promocode(code)
    
    if not promocode:
        await update.message.reply_text("❌ Неверный или неактивный промокод.")
        return
    
    promocode_id, code, coins, is_active, max_uses, used_count, expires_at = promocode
    
    # Проверяем срок действия
    if expires_at:
        expires_date = datetime.fromisoformat(expires_at)
        if datetime.now() > expires_date:
            await update.message.reply_text("❌ Срок действия промокода истек.")
            return
    
    success, result = use_promocode(user_id, promocode_id)
    
    if success:
        await update.message.reply_text(
            f"✅ Промокод успешно активирован!\n\n"
            f"🪙 +{result} монет\n"
            f"Текущий баланс: {get_user_coins(user_id)} монет"
        )
    else:
        await update.message.reply_text(f"❌ {result}")

# Каталог конфигов
async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    configs = get_all_configs()
    
    if not configs:
        await query.edit_message_text("😕 К сожалению, конфигов пока нет в наличии.")
        return
    
    keyboard = []
    for config in configs:
        config_id, name, description, price, price_type, file_path, photo_path, is_active = config
        price_symbol = "🪙" if price_type == 'coins' else "💰"
        button_text = f"{name} - {price}{price_symbol}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'buy_{config_id}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📦 Выберите конфиг для покупки:",
        reply_markup=reply_markup
    )

async def buy_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    config_id = int(query.data.split('_')[1])
    config = get_config_by_id(config_id)
    
    if not config:
        await query.edit_message_text("❌ Конфиг не найден.")
        return
    
    config_id, name, description, price, price_type, file_path, photo_path = config
    
    # Проверяем хватает ли монет
    user_id = update.effective_user.id
    coins = get_user_coins(user_id)
    
    text = f"📄 {name}\n\n"
    text += f"📝 {description}\n\n"
    text += f"🪙 Цена: {price} монет\n"
    text += f"Ваш баланс: {coins} монет\n\n"
    
    keyboard = []
    if coins >= price:
        keyboard.append([InlineKeyboardButton("✅ Купить за монеты", callback_data=f'confirm_coin_{config_id}')])
    else:
        keyboard.append([InlineKeyboardButton("🎁 Активировать промокод", callback_data='activate_promo')])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад в каталог", callback_data='catalog')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def confirm_coin_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    config_id = int(query.data.split('_')[2])
    config = get_config_by_id(config_id)
    
    if not config:
        await query.edit_message_text("❌ Конфиг не найден.")
        return
    
    config_id, name, description, price, price_type, file_path, photo_path = config
    user_id = update.effective_user.id
    
    # Проверяем баланс
    if not spend_coins(user_id, price):
        await query.edit_message_text(
            "❌ Недостаточно монет!\n\n"
            "Активируйте промокод в разделе 'Мой профиль'",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎁 Активировать промокод", callback_data='activate_promo')],
                [InlineKeyboardButton("🔙 Назад", callback_data='catalog')]
            ])
        )
        return
    
    # Создаем заказ
    order_id = add_order(user_id, update.effective_user.username, config_id, name, price, 'coins')
    
    # Отправляем конфиг
    await send_config_file(query, config, name)
    
    # Оповещаем админов
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"🛒 Новый заказ!\n"
                f"Заказ №{order_id}\n"
                f"Пользователь: @{update.effective_user.username or update.effective_user.first_name}\n"
                f"Конфиг: {name}\n"
                f"Оплачено: {price} монет"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу: {e}")

async def send_config_file(query, config, name):
    config_id, name, description, price, price_type, file_path, photo_path = config
    
    # Если есть фото - отправляем
    if photo_path and os.path.exists(photo_path):
        with open(photo_path, 'rb') as photo:
            await query.message.reply_photo(
                photo=photo,
                caption=f"✅ Поздравляем! Вы приобрели конфиг: {name}\n\n"
                       f"Спасибо за покупку! ❤️"
            )
    else:
        await query.edit_message_text(
            f"✅ Поздравляем! Вы приобрели конфиг: {name}\n\n"
            f"Спасибо за покупку! ❤️"
        )
    
    # Отправляем файл
    if os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            await query.message.reply_document(
                document=f,
                filename=os.path.basename(file_path),
                caption="📎 Ваш конфиг:"
            )
    else:
        await query.message.reply_text(
            f"⚠️ Файл конфига не найден. Обратитесь к администратору."
        )

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    orders = get_user_orders(user_id)
    
    if not orders:
        await query.edit_message_text(
            "📝 У вас пока нет заказов.\n\n"
            "Перейдите в каталог, чтобы сделать покупку! 🛒"
        )
        return
    
    text = "📝 Ваши заказы:\n\n"
    for order in orders:
        order_id, config_name, price, payment_type, status, created_at = order
        status_emoji = "✅" if status == 'completed' else "⏳"
        text += f"#{order_id} {config_name} - {price}🪙\n"
        text += f"{status_emoji} {status} | 📅 {created_at[:16]}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

# Поддержка
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    support_text = get_setting('support_text', 'По всем вопросам обращайтесь к @admin')
    
    keyboard = [
        [InlineKeyboardButton("📝 Написать в поддержку", callback_data='support_write')],
        [InlineKeyboardButton("📋 Мои обращения", callback_data='my_tickets')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    
    if is_admin(update.effective_user.id):
        keyboard.append([InlineKeyboardButton("📨 Открытые обращения", callback_data='admin_tickets')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📞 {support_text}\n\n"
        f"Вы можете написать нам, и мы ответим вам в ближайшее время.",
        reply_markup=reply_markup
    )

async def support_write(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['support_mode'] = 'write'
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='support')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📝 Напишите ваше сообщение в поддержку.\n\n"
        "Опишите подробно вашу проблему или вопрос, и мы свяжемся с вами.",
        reply_markup=reply_markup
    )

async def my_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    tickets = get_user_tickets(user_id)
    
    if not tickets:
        await query.edit_message_text(
            "📋 У вас нет обращений в поддержку.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='support')]
            ])
        )
        return
    
    text = "📋 Ваши обращения:\n\n"
    for ticket in tickets:
        ticket_id, message, admin_response, status, created_at = ticket
        status_emoji = "🟢" if status == 'open' else "🔴"
        status_text = "Открыто" if status == 'open' else "Закрыто"
        text += f"{status_emoji} #{ticket_id} {status_text}\n"
        text += f"📝 {message[:50]}...\n"
        if admin_response:
            text += f"💬 Ответ: {admin_response[:50]}...\n"
        text += f"📅 {created_at[:16]}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='support')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def admin_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    tickets = get_open_tickets()
    
    if not tickets:
        await query.edit_message_text(
            "📨 Открытых обращений нет.\n\n"
            "Все вопросы решены! 🎉",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='support')]
            ])
        )
        return
    
    text = "📨 Открытые обращения:\n\n"
    keyboard = []
    
    for ticket in tickets:
        ticket_id, user_id, username, message, created_at = ticket
        text += f"#{ticket_id} от @{username or user_id}\n"
        text += f"📝 {message[:50]}...\n"
        text += f"📅 {created_at[:16]}\n\n"
        keyboard.append([
            InlineKeyboardButton(f"💬 Ответить #{ticket_id}", callback_data=f'answer_ticket_{ticket_id}')
        ])
    
    keyboard.append([InlineKeyboardButton("🔄 Обновить", callback_data='admin_tickets')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='support')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def answer_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    ticket_id = int(query.data.split('_')[2])
    ticket = get_ticket_by_id(ticket_id)
    
    if not ticket:
        await query.edit_message_text("❌ Обращение не найдено.")
        return
    
    context.user_data['answering_ticket'] = ticket_id
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_tickets')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"💬 Ответ на обращение #{ticket_id}\n\n"
        f"Пользователь: @{ticket[2] or ticket[1]}\n"
        f"Сообщение: {ticket[3]}\n\n"
        f"Введите ваш ответ:",
        reply_markup=reply_markup
    )

# Админ-панель
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа к админ-панели.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📦 Управление товарами", callback_data='admin_configs')],
        [InlineKeyboardButton("🎁 Промокоды", callback_data='admin_promocodes')],
        [InlineKeyboardButton("📊 Заказы", callback_data='admin_orders')],
        [InlineKeyboardButton("📨 Обращения в поддержку", callback_data='admin_tickets')],
        [InlineKeyboardButton("👥 Пользователи", callback_data='admin_users')],
        [InlineKeyboardButton("⚙️ Настройки", callback_data='admin_settings')],
        [InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "⚙️ Админ-панель\n\n"
        "Выберите раздел для управления:",
        reply_markup=reply_markup
    )

# Управление товарами
async def admin_configs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить товар", callback_data='add_config')],
        [InlineKeyboardButton("📋 Список товаров", callback_data='list_configs')],
        [InlineKeyboardButton("🔙 Назад в админку", callback_data='admin_panel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📦 Управление товарами\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

async def add_config_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    # Инициализация данных
    context.user_data['adding_config'] = True
    context.user_data['config_step'] = 'name'
    context.user_data['config_name'] = ''
    context.user_data['config_description'] = ''
    context.user_data['config_price'] = 0
    context.user_data['config_photo'] = None
    
    await query.edit_message_text(
        "➕ Добавление нового товара\n\n"
        "Введите название товара:"
    )

async def list_configs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    configs = get_all_configs()
    
    if not configs:
        await query.edit_message_text(
            "📋 Список товаров пуст.\n\n"
            "Добавьте новый товар через админ-панель.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_configs')]
            ])
        )
        return
    
    text = "📋 Список товаров:\n\n"
    keyboard = []
    
    for config in configs:
        config_id, name, description, price, price_type, file_path, photo_path, is_active = config
        price_symbol = "🪙" if price_type == 'coins' else "💰"
        text += f"🆔 {config_id}. {name} - {price}{price_symbol}\n"
        text += f"📝 {description[:50]}...\n\n"
        keyboard.append([
            InlineKeyboardButton(f"✏️ {name}", callback_data=f'edit_config_{config_id}')
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='admin_configs')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def edit_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    config_id = int(query.data.split('_')[2])
    config = get_config_by_id(config_id)
    
    if not config:
        await query.edit_message_text("❌ Товар не найден.")
        return
    
    context.user_data['editing_config_id'] = config_id
    
    keyboard = [
        [InlineKeyboardButton("✏️ Редактировать", callback_data=f'edit_config_data_{config_id}')],
        [InlineKeyboardButton("🗑️ Удалить", callback_data=f'delete_config_{config_id}')],
        [InlineKeyboardButton("🔙 Назад", callback_data='list_configs')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    price_symbol = "🪙" if config[4] == 'coins' else "💰"
    
    await query.edit_message_text(
        f"📄 Товар: {config[1]}\n\n"
        f"ID: {config[0]}\n"
        f"Название: {config[1]}\n"
        f"Описание: {config[2]}\n"
        f"Цена: {config[3]}{price_symbol}\n"
        f"Файл: {config[5]}\n"
        f"Фото: {config[6] or 'Нет'}\n\n"
        f"Выберите действие:",
        reply_markup=reply_markup
    )

async def delete_config_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    config_id = int(query.data.split('_')[2])
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f'confirm_delete_{config_id}')],
        [InlineKeyboardButton("❌ Отмена", callback_data=f'edit_config_{config_id}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "⚠️ Вы уверены, что хотите удалить этот товар?",
        reply_markup=reply_markup
    )

async def confirm_delete_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    config_id = int(query.data.split('_')[2])
    delete_config(config_id)
    
    await query.edit_message_text(
        "✅ Товар успешно удален!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data='admin_configs')]
        ])
    )

# Управление промокодами
async def admin_promocodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Создать промокод", callback_data='create_promo')],
        [InlineKeyboardButton("📋 Список промокодов", callback_data='list_promocodes')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🎁 Управление промокодами\n\n"
        "Промокоды дают пользователям монеты.\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

async def create_promo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    context.user_data['creating_promo'] = True
    context.user_data['promo_step'] = 'coins'
    
    await query.edit_message_text(
        "🎁 Создание промокода\n\n"
        "Введите количество монет, которое будет давать промокод:"
    )

async def list_promocodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    promocodes = get_all_promocodes()
    
    if not promocodes:
        await query.edit_message_text(
            "📋 Промокодов пока нет.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_promocodes')]
            ])
        )
        return
    
    text = "🎁 Список промокодов:\n\n"
    keyboard = []
    
    for promo in promocodes[:10]:
        promo_id, code, coins, is_active, max_uses, used_count, expires_at, created_at = promo
        status = "✅ Активен" if is_active else "❌ Неактивен"
        text += f"📌 {code}\n"
        text += f"🪙 {coins} монет | {status}\n"
        text += f"📊 Использован: {used_count}/{max_uses if max_uses > 0 else '∞'}\n"
        if expires_at:
            text += f"⏳ До: {expires_at[:10]}\n"
        text += f"📅 Создан: {created_at[:16]}\n\n"
        
        if is_active:
            keyboard.append([
                InlineKeyboardButton(f"❌ Деактивировать {code}", callback_data=f'deactivate_promo_{promo_id}')
            ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='admin_promocodes')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def deactivate_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    promo_id = int(query.data.split('_')[2])
    deactivate_promocode(promo_id)
    
    await query.edit_message_text(
        "✅ Промокод деактивирован!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить список", callback_data='list_promocodes')]
        ])
    )

# Пользователи
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name, coins, registered_at FROM users ORDER BY registered_at DESC LIMIT 20')
    users = cursor.fetchall()
    conn.close()
    
    if not users:
        await query.edit_message_text(
            "👥 Пользователей пока нет.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')]
            ])
        )
        return
    
    text = "👥 Последние пользователи:\n\n"
    for user in users:
        user_id, username, first_name, coins, registered_at = user
        text += f"🆔 {user_id}\n"
        text += f"👤 @{username or first_name or 'Не указан'}\n"
        text += f"🪙 {coins} монет\n"
        text += f"📅 {registered_at[:16]}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data='admin_users')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

# Заказы
async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    orders = get_all_orders()
    
    if not orders:
        await query.edit_message_text(
            "📊 Заказов пока нет.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')]
            ])
        )
        return
    
    text = "📊 Список заказов:\n\n"
    for order in orders[:10]:
        order_id, user_id, username, config_name, price, payment_type, status, created_at = order
        status_emoji = "✅" if status == 'completed' else "⏳"
        text += f"#{order_id} {config_name} - {price}🪙\n"
        text += f"👤 @{username or user_id}\n"
        text += f"{status_emoji} {status}\n"
        text += f"📅 {created_at[:16]}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data='admin_orders')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

# Настройки
async def admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📝 Приветственное сообщение", callback_data='edit_welcome')],
        [InlineKeyboardButton("📞 Текст поддержки", callback_data='edit_support')],
        [InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome = get_setting('welcome_text', 'Не установлено')
    support = get_setting('support_text', 'Не установлено')
    
    await query.edit_message_text(
        f"⚙️ Настройки бота\n\n"
        f"Приветствие: {welcome[:50]}...\n"
        f"Поддержка: {support[:50]}...\n\n"
        f"Выберите параметр для редактирования:",
        reply_markup=reply_markup
    )

async def edit_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    context.user_data['editing_setting'] = 'welcome_text'
    
    await query.edit_message_text(
        "📝 Введите новое приветственное сообщение:\n\n"
        "Используйте специальные символы для форматирования.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data='admin_settings')]
        ])
    )

async def edit_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    context.user_data['editing_setting'] = 'support_text'
    
    await query.edit_message_text(
        "📞 Введите новый текст для раздела поддержки:\n\n"
        "Например: 'По всем вопросам пишите @support'",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data='admin_settings')]
        ])
    )

# Статистика
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ У вас нет доступа.")
        return
    
    conn = sqlite3.connect('clamsi_bot.db', timeout=10)
    cursor = conn.cursor()
    
    # Количество пользователей
    cursor.execute('SELECT COUNT(*) FROM users')
    users_count = cursor.fetchone()[0]
    
    # Количество заказов
    cursor.execute('SELECT COUNT(*) FROM orders')
    orders_count = cursor.fetchone()[0]
    
    # Сумма продаж в монетах
    cursor.execute('SELECT SUM(price) FROM orders WHERE payment_type = "coins"')
    coins_revenue = cursor.fetchone()[0] or 0
    
    # Количество конфигов
    cursor.execute('SELECT COUNT(*) FROM configs WHERE is_active = 1')
    configs_count = cursor.fetchone()[0]
    
    # Количество открытых тикетов
    cursor.execute('SELECT COUNT(*) FROM support_tickets WHERE status = "open"')
    open_tickets = cursor.fetchone()[0]
    
    # Количество промокодов
    cursor.execute('SELECT COUNT(*) FROM promocodes WHERE is_active = 1')
    promocodes_count = cursor.fetchone()[0]
    
    # Всего монет в системе
    cursor.execute('SELECT SUM(coins) FROM users')
    total_coins = cursor.fetchone()[0] or 0
    
    conn.close()
    
    await query.edit_message_text(
        f"📊 Статистика бота\n\n"
        f"👥 Пользователей: {users_count}\n"
        f"📦 Товаров: {configs_count}\n"
        f"🛒 Заказов: {orders_count}\n"
        f"🪙 Продано монет: {coins_revenue}\n"
        f"🪙 Всего монет: {total_coins}\n"
        f"🎁 Промокодов: {promocodes_count}\n"
        f"📨 Открытых обращений: {open_tickets}\n\n"
        f"📈 Бот работает стабильно!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить", callback_data='admin_stats')],
            [InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')]
        ])
    )

# Назад в главное меню
async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    
    keyboard = [
        [InlineKeyboardButton("📦 Каталог конфигов", callback_data='catalog')],
        [InlineKeyboardButton("👤 Мой профиль", callback_data='profile')],
        [InlineKeyboardButton("📝 Мои заказы", callback_data='my_orders')],
        [InlineKeyboardButton("🎁 Активировать промокод", callback_data='activate_promo')],
        [InlineKeyboardButton("📞 Поддержка", callback_data='support')]
    ]
    
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("⚙️ Админ-панель", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🏠 Главное меню\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

# Обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    
    # Обработка ответа на тикет от админа
    if context.user_data.get('answering_ticket'):
        ticket_id = context.user_data['answering_ticket']
        ticket = get_ticket_by_id(ticket_id)
        
        if ticket:
            # Сохраняем ответ в БД
            update_ticket_response(ticket_id, text)
            
            # Отправляем ответ пользователю
            try:
                await context.bot.send_message(
                    ticket[1],
                    f"💬 Ответ на ваше обращение #{ticket_id}\n\n"
                    f"{text}\n\n"
                    f"Если у вас остались вопросы, вы можете написать снова."
                )
            except Exception as e:
                logger.error(f"Не удалось отправить ответ пользователю: {e}")
            
            context.user_data.clear()
            
            await update.message.reply_text(
                f"✅ Ответ на обращение #{ticket_id} отправлен пользователю!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📨 К списку обращений", callback_data='admin_tickets')]
                ])
            )
        else:
            await update.message.reply_text("❌ Обращение не найдено.")
        return
    
    # Обработка промокода
    if context.user_data.get('awaiting_promo'):
        context.user_data['awaiting_promo'] = False
        await process_promocode(update, context)
        return
    
    # Обработка сообщения в поддержку
    if context.user_data.get('support_mode') == 'write':
        ticket_id = create_support_ticket(
            user.id,
            user.username or user.first_name,
            text
        )
        
        await update.message.reply_text(
            f"✅ Ваше обращение #{ticket_id} отправлено!\n\n"
            f"Мы ответим вам в ближайшее время. 📨"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"📨 Новое обращение в поддержку!\n\n"
                    f"#{ticket_id}\n"
                    f"Пользователь: @{user.username or user.first_name}\n"
                    f"Сообщение: {text}\n\n"
                    f"Ответьте через админ-панель."
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление админу: {e}")
        
        context.user_data['support_mode'] = None
        return
    
    # Обработка добавления товара
    if context.user_data.get('adding_config'):
        step = context.user_data.get('config_step')
        
        if step == 'name':
            if text and text.strip():
                context.user_data['config_name'] = text.strip()
                context.user_data['config_step'] = 'description'
                await update.message.reply_text("📝 Введите описание товара:")
            else:
                await update.message.reply_text("❌ Название не может быть пустым! Введите название товара:")
                return
                
        elif step == 'description':
            context.user_data['config_description'] = text.strip() if text else ''
            context.user_data['config_step'] = 'price'
            await update.message.reply_text(
                "💰 Введите цену товара в монетах:\n\n"
                "Пример: 100"
            )
            
        elif step == 'price':
            try:
                price = int(text)
                if price <= 0:
                    await update.message.reply_text("❌ Цена должна быть больше 0! Введите цену:")
                    return
                context.user_data['config_price'] = price
                context.user_data['config_step'] = 'photo'
                await update.message.reply_text(
                    "📸 Отправьте фото товара (или нажмите /skip для пропуска):"
                )
            except ValueError:
                await update.message.reply_text("❌ Введите корректное число монет.")
                
        elif step == 'photo':
            if text and text.lower() == '/skip':
                context.user_data['config_photo'] = None
                context.user_data['config_step'] = 'file'
                await update.message.reply_text("📎 Отправьте файл товара:")
            elif update.message.photo:
                # Сохраняем фото
                if not os.path.exists('configs'):
                    os.makedirs('configs')
                
                photo_file = await update.message.photo[-1].get_file()
                photo_path = f"configs/photo_{datetime.now().timestamp()}.jpg"
                await photo_file.download_to_drive(photo_path)
                
                context.user_data['config_photo'] = photo_path
                context.user_data['config_step'] = 'file'
                await update.message.reply_text("📎 Отправьте файл товара:")
            else:
                await update.message.reply_text("❌ Пожалуйста, отправьте фото или нажмите /skip")
                
        elif step == 'file':
            if update.message.document:
                file = update.message.document
                file_name = file.file_name
                
                if not os.path.exists('configs'):
                    os.makedirs('configs')
                
                file_path = f"configs/{file_name}"
                new_file = await file.get_file()
                await new_file.download_to_drive(file_path)
                
                # Проверяем, что название не пустое
                config_name = context.user_data.get('config_name')
                if not config_name or not config_name.strip():
                    await update.message.reply_text("❌ Ошибка: название товара не было введено!")
                    context.user_data.clear()
                    return
                
                # Проверяем цену
                config_price = context.user_data.get('config_price', 0)
                if config_price <= 0:
                    await update.message.reply_text("❌ Ошибка: цена должна быть больше 0!")
                    context.user_data.clear()
                    return
                
                # Сохраняем товар
                try:
                    config_id = add_config(
                        config_name.strip(),
                        context.user_data.get('config_description', ''),
                        config_price,
                        'coins',
                        file_path,
                        context.user_data.get('config_photo')
                    )
                    
                    await update.message.reply_text(
                        f"✅ Товар успешно добавлен!\n"
                        f"ID: {config_id}\n"
                        f"Название: {config_name}\n"
                        f"Цена: {config_price} монет"
                    )
                except Exception as e:
                    await update.message.reply_text(f"❌ Ошибка при сохранении: {str(e)}")
                
                context.user_data.clear()
            else:
                await update.message.reply_text("❌ Пожалуйста, отправьте файл.")
        return
    
    # Обработка создания промокода
    if context.user_data.get('creating_promo'):
        step = context.user_data.get('promo_step')
        
        if step == 'coins':
            try:
                coins = int(text)
                if coins <= 0:
                    await update.message.reply_text("❌ Количество монет должно быть больше 0!")
                    return
                context.user_data['promo_coins'] = coins
                context.user_data['promo_step'] = 'max_uses'
                await update.message.reply_text(
                    "📊 Введите максимальное количество использований:\n"
                    "(Введите 0 для бесконечного использования)"
                )
            except ValueError:
                await update.message.reply_text("❌ Введите корректное число монет.")
                
        elif step == 'max_uses':
            try:
                max_uses = int(text)
                if max_uses < 0:
                    await update.message.reply_text("❌ Количество использований не может быть отрицательным!")
                    return
                context.user_data['promo_max_uses'] = max_uses
                context.user_data['promo_step'] = 'expires'
                await update.message.reply_text(
                    "⏳ Введите срок действия в днях:\n"
                    "(Введите 0 для бессрочного промокода)"
                )
            except ValueError:
                await update.message.reply_text("❌ Введите корректное число.")
                
        elif step == 'expires':
            try:
                expires_days = int(text) if int(text) > 0 else None
                
                # Создаем промокод
                code, promo_id = create_promocode(
                    context.user_data['promo_coins'],
                    update.effective_user.id,
                    context.user_data['promo_max_uses'],
                    expires_days
                )
                
                coins = context.user_data['promo_coins']
                max_uses = context.user_data['promo_max_uses']
                
                context.user_data.clear()
                
                await update.message.reply_text(
                    f"✅ Промокод успешно создан!\n\n"
                    f"🎁 Код: {code}\n"
                    f"🪙 Монет: {coins}\n"
                    f"📊 Использований: {max_uses if max_uses > 0 else '∞'}\n"
                    f"⏳ Срок: {'Бессрочный' if not expires_days else f'{expires_days} дней'}\n\n"
                    f"Отправьте код пользователям для активации."
                )
            except ValueError:
                await update.message.reply_text("❌ Введите корректное число дней.")
        return
    
    # Редактирование настроек
    if context.user_data.get('editing_setting'):
        setting_key = context.user_data['editing_setting']
        set_setting(setting_key, text)
        context.user_data.clear()
        
        await update.message.reply_text(
            "✅ Настройка успешно обновлена!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 В админ-панель", callback_data='admin_panel')]
            ])
        )
        return
    
    # Если сообщение не относится ни к чему
    await start(update, context)

def main():
    # Инициализация БД
    init_db()
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("skip", lambda u, c: None))
    
    # Обработчики callback-запросов
    application.add_handler(CallbackQueryHandler(catalog, pattern='^catalog$'))
    application.add_handler(CallbackQueryHandler(profile, pattern='^profile$'))
    application.add_handler(CallbackQueryHandler(activate_promo, pattern='^activate_promo$'))
    application.add_handler(CallbackQueryHandler(buy_config, pattern='^buy_'))
    application.add_handler(CallbackQueryHandler(confirm_coin_purchase, pattern='^confirm_coin_'))
    application.add_handler(CallbackQueryHandler(my_orders, pattern='^my_orders$'))
    application.add_handler(CallbackQueryHandler(support, pattern='^support$'))
    application.add_handler(CallbackQueryHandler(support_write, pattern='^support_write$'))
    application.add_handler(CallbackQueryHandler(my_tickets, pattern='^my_tickets$'))
    application.add_handler(CallbackQueryHandler(admin_tickets, pattern='^admin_tickets$'))
    application.add_handler(CallbackQueryHandler(answer_ticket, pattern='^answer_ticket_'))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    application.add_handler(CallbackQueryHandler(admin_configs, pattern='^admin_configs$'))
    application.add_handler(CallbackQueryHandler(add_config_start, pattern='^add_config$'))
    application.add_handler(CallbackQueryHandler(list_configs, pattern='^list_configs$'))
    application.add_handler(CallbackQueryHandler(edit_config, pattern='^edit_config_'))
    application.add_handler(CallbackQueryHandler(delete_config_confirm, pattern='^delete_config_'))
    application.add_handler(CallbackQueryHandler(confirm_delete_config, pattern='^confirm_delete_'))
    application.add_handler(CallbackQueryHandler(admin_promocodes, pattern='^admin_promocodes$'))
    application.add_handler(CallbackQueryHandler(create_promo_start, pattern='^create_promo$'))
    application.add_handler(CallbackQueryHandler(list_promocodes, pattern='^list_promocodes$'))
    application.add_handler(CallbackQueryHandler(deactivate_promo, pattern='^deactivate_promo_'))
    application.add_handler(CallbackQueryHandler(admin_users, pattern='^admin_users$'))
    application.add_handler(CallbackQueryHandler(admin_orders, pattern='^admin_orders$'))
    application.add_handler(CallbackQueryHandler(admin_settings, pattern='^admin_settings$'))
    application.add_handler(CallbackQueryHandler(edit_welcome, pattern='^edit_welcome$'))
    application.add_handler(CallbackQueryHandler(edit_support, pattern='^edit_support$'))
    application.add_handler(CallbackQueryHandler(admin_stats, pattern='^admin_stats$'))
    application.add_handler(CallbackQueryHandler(back_to_main, pattern='^back_to_main$'))
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.ALL, handle_message))
    
    # Запускаем бота
    print("🤖 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
