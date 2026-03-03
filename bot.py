import telebot
from telebot import types
import random
import sqlite3
import os
from datetime import datetime, timedelta
from flask import Flask
import threading
import time
import json

# ========== ТОКЕН ==========
TOKEN = os.environ.get('8412567351:AAG7eEMXlNfDBsNZF08GD-Pr-LH-2z1txSQ')
bot = telebot.TeleBot(TOKEN)

# ========== ID АДМИНА ==========
ADMIN_ID = 8388843828

# ========== ПОДКЛЮЧЕНИЕ К БД ==========
def get_db():
    conn = sqlite3.connect('terminal_trade.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            money REAL DEFAULT 1000,
            day INTEGER DEFAULT 1,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
            used_promos TEXT DEFAULT '[]',
            warns INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0
        )
    ''')
    
    # Таблица портфеля
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            user_id INTEGER,
            ticker TEXT,
            amount INTEGER,
            buy_price REAL,
            PRIMARY KEY (user_id, ticker)
        )
    ''')
    
    # Таблица компаний
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            price REAL,
            prev_price REAL,
            volatility REAL DEFAULT 0.05
        )
    ''')
    
    # Таблица лидеров (кэш)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leaderboard (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            capital REAL,
            day INTEGER,
            last_update TIMESTAMP
        )
    ''')
    
    # Таблица промокодов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY,
            bonus INTEGER,
            max_uses INTEGER,
            used_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица активаций промокодов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promo_activations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            promo_code TEXT,
            user_id INTEGER,
            username TEXT,
            activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица логов админа
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT,
            target_id INTEGER,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица модераторов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS moderators (
            user_id INTEGER PRIMARY KEY,
            can_ban INTEGER DEFAULT 0,
            can_give INTEGER DEFAULT 0,
            can_take INTEGER DEFAULT 0,
            can_promo INTEGER DEFAULT 0,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица настроек
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Таблица сезонов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS seasons (
            id INTEGER PRIMARY KEY CHECK (id=1),
            season_number INTEGER,
            name TEXT,
            start_date TIMESTAMP,
            end_date TIMESTAMP,
            active BOOLEAN,
            prize1 REAL DEFAULT 0,
            prize2 REAL DEFAULT 0,
            prize3 REAL DEFAULT 0
        )
    ''')
    
    # Заполняем компании если пусто
    cursor.execute('SELECT COUNT(*) FROM companies')
    if cursor.fetchone()[0] == 0:
        companies = [
            ('AAPL', 'Apple Inc.', 175.50, 175.50, 0.05),
            ('MSFT', 'Microsoft Corp.', 330.25, 330.25, 0.05),
            ('GOOG', 'Alphabet (Google)', 2800.75, 2800.75, 0.05),
            ('AMZN', 'Amazon.com Inc.', 3450.00, 3450.00, 0.05),
            ('TSLA', 'Tesla Inc.', 900.50, 900.50, 0.08),
            ('META', 'Meta Platforms', 310.80, 310.80, 0.06),
            ('NVDA', 'NVIDIA Corp.', 890.60, 890.60, 0.07),
            ('JPM', 'JPMorgan Chase', 150.30, 150.30, 0.04),
            ('JNJ', 'Johnson & Johnson', 160.40, 160.40, 0.03),
            ('WMT', 'Walmart Inc.', 145.20, 145.20, 0.03),
            ('NFLX', 'Netflix Inc.', 450.30, 450.30, 0.06),
            ('DIS', 'Walt Disney Co.', 110.20, 110.20, 0.04),
            ('PYPL', 'PayPal Holdings', 85.40, 85.40, 0.06),
            ('ADBE', 'Adobe Inc.', 520.10, 520.10, 0.05),
            ('INTC', 'Intel Corp.', 32.80, 32.80, 0.05),
            ('AMD', 'AMD Inc.', 140.60, 140.60, 0.07)
        ]
        cursor.executemany('INSERT INTO companies VALUES (?,?,?,?,?)', companies)
    
    conn.commit()
    conn.close()

init_db()

# ========== ВЕБ-СЕРВЕР ==========
app = Flask(__name__)

@app.route('/')
@app.route('/health')
def health():
    return "Terminal Trade Admin is alive!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# ========== ФУНКЦИИ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ==========
def get_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        now = datetime.now()
        cursor.execute('''
            INSERT INTO users (user_id, first_seen, last_seen)
            VALUES (?, ?, ?)
        ''', (user_id, now, now))
        conn.commit()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
    
    conn.close()
    return user

def update_user(user_id, **kwargs):
    conn = get_db()
    cursor = conn.cursor()
    
    fields = []
    values = []
    for key, value in kwargs.items():
        fields.append(f"{key} = ?")
        values.append(value)
    
    values.append(user_id)
    cursor.execute(f'''
        UPDATE users 
        SET {', '.join(fields)}, last_seen = ?
        WHERE user_id = ?
    ''', (*values, datetime.now(), user_id))
    
    conn.commit()
    conn.close()

def is_moderator(user_id, permission=None):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM moderators WHERE user_id = ?', (user_id,))
    mod = cursor.fetchone()
    conn.close()
    
    if not mod and user_id != ADMIN_ID:
        return False
    
    if user_id == ADMIN_ID:
        return True
    
    if permission == 'ban' and mod['can_ban'] == 0:
        return False
    if permission == 'give' and mod['can_give'] == 0:
        return False
    if permission == 'take' and mod['can_take'] == 0:
        return False
    if permission == 'promo' and mod['can_promo'] == 0:
        return False
    
    return True

def log_admin(admin_id, action, target_id=None, details=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO admin_logs (admin_id, action, target_id, details)
        VALUES (?, ?, ?, ?)
    ''', (admin_id, action, target_id, details))
    conn.commit()
    conn.close()

# ========== ФУНКЦИИ ДЛЯ ПРОМОКОДОВ ==========
def use_promo(promo_code, user_id, username):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM promocodes WHERE code = ?', (promo_code,))
    promo = cursor.fetchone()
    
    if not promo:
        conn.close()
        return False, "Промокод не найден"
    
    if promo['used_count'] >= promo['max_uses']:
        conn.close()
        return False, "Промокод закончился"
    
    cursor.execute('SELECT used_promos FROM users WHERE user_id = ?', (user_id,))
    used = eval(cursor.fetchone()[0])
    
    if promo_code in used:
        conn.close()
        return False, "Ты уже активировал этот промокод"
    
    # Начисляем бонус
    cursor.execute('UPDATE users SET money = money + ? WHERE user_id = ?', (promo['bonus'], user_id))
    
    # Обновляем список использованных
    used.append(promo_code)
    cursor.execute('UPDATE users SET used_promos = ? WHERE user_id = ?', (str(used), user_id))
    
    # Обновляем счетчик
    new_count = promo['used_count'] + 1
    cursor.execute('UPDATE promocodes SET used_count = ? WHERE code = ?', (new_count, promo_code))
    
    # Логируем активацию
    cursor.execute('''
        INSERT INTO promo_activations (promo_code, user_id, username)
        VALUES (?, ?, ?)
    ''', (promo_code, user_id, username))
    
    conn.commit()
    conn.close()
    
    # Уведомление админу
    remaining = promo['max_uses'] - new_count
    try:
        bot.send_message(
            ADMIN_ID,
            f"🎟️ Активация промокода\n"
            f"┌─────────────────────\n"
            f"│ Код: {promo_code}\n"
            f"│ Игрок: @{username} ({user_id})\n"
            f"│ Бонус: +${promo['bonus']}\n"
            f"│ Осталось: {remaining}/{promo['max_uses']}\n"
            f"│ Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n"
            f"└─────────────────────"
        )
    except:
        pass
    
    return True, f"✅ Промокод активирован! +${promo['bonus']}"

def get_promo_info(promo_code):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM promocodes WHERE code = ?', (promo_code,))
    promo = cursor.fetchone()
    conn.close()
    
    return promo

# ========== ФУНКЦИИ ДЛЯ КОМПАНИЙ ==========
def get_companies(page=1, per_page=10):
    conn = get_db()
    cursor = conn.cursor()
    
    offset = (page - 1) * per_page
    cursor.execute('''
        SELECT * FROM companies 
        ORDER BY ticker 
        LIMIT ? OFFSET ?
    ''', (per_page, offset))
    
    companies = cursor.fetchall()
    
    cursor.execute('SELECT COUNT(*) FROM companies')
    total = cursor.fetchone()[0]
    
    conn.close()
    return companies, total

def update_company_prices():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT ticker, price, volatility FROM companies')
    companies = cursor.fetchall()
    
    for ticker, old_price, vol in companies:
        change = random.uniform(-vol, vol)
        new_price = round(old_price * (1 + change), 2)
        
        cursor.execute('''
            UPDATE companies 
            SET price = ?, prev_price = ?
            WHERE ticker = ?
        ''', (new_price, old_price, ticker))
    
    conn.commit()
    conn.close()

def get_price_change(old_price, new_price):
    if old_price == 0:
        return "0.00%"
    change = ((new_price - old_price) / old_price) * 100
    return f"{change:+.2f}%"

def add_company(ticker, name, price, volatility=0.05):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO companies (ticker, name, price, prev_price, volatility)
            VALUES (?, ?, ?, ?, ?)
        ''', (ticker.upper(), name, price, price, volatility))
        conn.commit()
        success = True
    except:
        success = False
    
    conn.close()
    return success

def delete_company(ticker):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM companies WHERE ticker = ?', (ticker.upper(),))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    
    return affected > 0

# ========== ФУНКЦИИ ДЛЯ ИГРОКОВ ==========
def get_portfolio(user_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.*, c.price, c.name 
        FROM portfolio p
        JOIN companies c ON p.ticker = c.ticker
        WHERE p.user_id = ?
    ''', (user_id,))
    
    portfolio = cursor.fetchall()
    conn.close()
    return portfolio

def calculate_capital(user_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT money FROM users WHERE user_id = ?', (user_id,))
    money = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT SUM(p.amount * c.price) 
        FROM portfolio p
        JOIN companies c ON p.ticker = c.ticker
        WHERE p.user_id = ?
    ''', (user_id,))
    
    stocks = cursor.fetchone()[0] or 0
    conn.close()
    
    return round(money + stocks, 2)

def buy_stock(user_id, ticker, amount):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT price FROM companies WHERE ticker = ?', (ticker,))
    company = cursor.fetchone()
    
    if not company:
        conn.close()
        return False, "Нет такой компании"
    
    price = company[0]
    total = price * amount
    
    cursor.execute('SELECT money FROM users WHERE user_id = ?', (user_id,))
    money = cursor.fetchone()[0]
    
    if money >= total:
        new_money = round(money - total, 2)
        cursor.execute('UPDATE users SET money = ? WHERE user_id = ?', (new_money, user_id))
        
        cursor.execute('''
            INSERT INTO portfolio (user_id, ticker, amount, buy_price)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, ticker) 
            DO UPDATE SET amount = amount + excluded.amount
        ''', (user_id, ticker, amount, price))
        
        conn.commit()
        conn.close()
        return True, f"Куплено {amount} {ticker} за ${total:,.2f}"
    else:
        conn.close()
        return False, f"Недостаточно денег. Нужно ${total:,.2f}"

def sell_stock(user_id, ticker, amount):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT amount FROM portfolio 
        WHERE user_id = ? AND ticker = ?
    ''', (user_id, ticker))
    portfolio = cursor.fetchone()
    
    if not portfolio or portfolio[0] < amount:
        conn.close()
        return False, f"У вас только {portfolio[0] if portfolio else 0} акций {ticker}"
    
    cursor.execute('SELECT price FROM companies WHERE ticker = ?', (ticker,))
    price = cursor.fetchone()[0]
    total = price * amount
    
    cursor.execute('SELECT money FROM users WHERE user_id = ?', (user_id,))
    money = cursor.fetchone()[0]
    new_money = round(money + total, 2)
    cursor.execute('UPDATE users SET money = ? WHERE user_id = ?', (new_money, user_id))
    
    if portfolio[0] == amount:
        cursor.execute('DELETE FROM portfolio WHERE user_id = ? AND ticker = ?', (user_id, ticker))
    else:
        cursor.execute('''
            UPDATE portfolio 
            SET amount = amount - ? 
            WHERE user_id = ? AND ticker = ?
        ''', (amount, user_id, ticker))
    
    conn.commit()
    conn.close()
    
    return True, f"Продано {amount} {ticker} за ${total:,.2f}"

# ========== ФУНКЦИИ ДЛЯ ЛИДЕРОВ ==========
def update_leaderboard():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM leaderboard')
    
    cursor.execute('SELECT user_id, username FROM users WHERE banned = 0')
    users = cursor.fetchall()
    
    for user in users:
        user_id = user[0]
        username = user[1] or f"User_{user_id}"
        capital = calculate_capital(user_id)
        
        cursor.execute('''
            INSERT INTO leaderboard (user_id, username, capital, last_update)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, capital, datetime.now()))
    
    conn.commit()
    conn.close()

def get_leaderboard(limit=10):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_id, username, capital 
        FROM leaderboard 
        ORDER BY capital DESC 
        LIMIT ?
    ''', (limit,))
    
    leaderboard = cursor.fetchall()
    conn.close()
    return leaderboard

# ========== КНОПКИ ==========
def get_main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("📊 Статус", callback_data="status")
    btn2 = types.InlineKeyboardButton("📈 Компании", callback_data="list")
    btn3 = types.InlineKeyboardButton("⏩ Next", callback_data="next")
    btn4 = types.InlineKeyboardButton("🏆 Лидеры", callback_data="leaderboard")
    btn5 = types.InlineKeyboardButton("🔄 Сброс", callback_data="reset")
    btn6 = types.InlineKeyboardButton("🎟️ Промо", callback_data="promo")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    return markup

def get_back_keyboard():
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("◀️ Назад", callback_data="back")
    markup.add(btn)
    return markup

def get_companies_keyboard(current_page, total_pages):
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    if total_pages > 1:
        btn1 = types.InlineKeyboardButton("◀️", callback_data=f"comp_page_{current_page-1}")
        btn2 = types.InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="noop")
        btn3 = types.InlineKeyboardButton("▶️", callback_data=f"comp_page_{current_page+1}")
        markup.add(btn1, btn2, btn3)
    
    return markup

# ========== КОМАНДЫ ДЛЯ ИГРОКОВ ==========
@bot.message_handler(commands=['trade'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or f"User_{user_id}"
    
    user = get_user(user_id)
    update_user(user_id, username=username)
    
    text = f"""
╔══════════════════════════════╗
║     TERMINAL TRADER BOT      ║
╚══════════════════════════════╝

Привет, {username}! 👋

💰 Стартовый капитал: $1000

Команды:
/tbuy AAPL 5 — купить
/tsell TSLA 2 — продать
/tnext — следующий день
/tpromo КОД — промокод
    """
    
    bot.send_message(message.chat.id, text, reply_markup=get_main_keyboard())

@bot.message_handler(commands=['tbuy'])
def buy_command(message):
    user_id = message.from_user.id
    
    try:
        parts = message.text.split()
        ticker = parts[1].upper()
        amount = int(parts[2])
        
        success, msg = buy_stock(user_id, ticker, amount)
        bot.reply_to(message, msg)
        
        if success:
            update_leaderboard()
        
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Формат: /tbuy AAPL 5")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['tsell'])
def sell_command(message):
    user_id = message.from_user.id
    
    try:
        parts = message.text.split()
        ticker = parts[1].upper()
        amount = int(parts[2])
        
        success, msg = sell_stock(user_id, ticker, amount)
        bot.reply_to(message, msg)
        
        if success:
            update_leaderboard()
        
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Формат: /tsell AAPL 5")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['tnext'])
def next_command(message):
    update_company_prices()
    update_leaderboard()
    bot.reply_to(message, "⏩ Новый день! Цены обновлены.")

@bot.message_handler(commands=['tpromo'])
def promo_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or f"User_{user_id}"
    
    try:
        promo_code = message.text.split()[1].upper()
        
        # Показываем информацию о промокоде
        promo = get_promo_info(promo_code)
        if promo:
            remaining = promo['max_uses'] - promo['used_count']
            text = f"""
🎟️ Промокод: {promo_code}
💰 Бонус: +${promo['bonus']}
🎫 Доступно: {remaining}/{promo['max_uses']}
            """
            bot.reply_to(message, text)
            
            # Спрашиваем подтверждение
            markup = types.InlineKeyboardMarkup()
            btn1 = types.InlineKeyboardButton("✅ Активировать", callback_data=f"confirm_promo_{promo_code}")
            btn2 = types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_promo")
            markup.add(btn1, btn2)
            
            bot.send_message(message.chat.id, "Активировать промокод?", reply_markup=markup)
        else:
            bot.reply_to(message, "❌ Промокод не найден")
            
    except IndexError:
        bot.reply_to(message, "❌ Использование: /tpromo КОД")

@bot.message_handler(commands=['tlist'])
def list_command(message):
    user_id = message.from_user.id
    companies, total = get_companies(page=1)
    total_pages = (total + 9) // 10
    
    text = f"📋 КОМПАНИИ (1/{total_pages})\n\n"
    
    for c in companies:
        ticker, name, price, prev = c[0], c[1], c[2], c[3]
        change = get_price_change(prev, price)
        
        if change.startswith('+'):
            emoji = "🟢"
        elif change.startswith('-'):
            emoji = "🔴"
        else:
            emoji = "⚪"
        
        text += f"{ticker} — {name[:15]} — ${price:,.2f} {emoji}\n"
    
    bot.send_message(
        message.chat.id, 
        text, 
        reply_markup=get_companies_keyboard(1, total_pages)
    )

# ========== ОБРАБОТКА КНОПОК ==========
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == "back":
        text = f"""
╔══════════════════════════════╗
║     TERMINAL TRADER BOT      ║
╚══════════════════════════════╝

Главное меню
        """
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_main_keyboard()
        )
        bot.answer_callback_query(call.id)
    
    elif call.data.startswith("comp_page_"):
        page = int(call.data.split("_")[2])
        companies, total = get_companies(page=page)
        total_pages = (total + 9) // 10
        
        text = f"📋 КОМПАНИИ ({page}/{total_pages})\n\n"
        
        for c in companies:
            ticker, name, price, prev = c[0], c[1], c[2], c[3]
            change = get_price_change(prev, price)
            
            if change.startswith('+'):
                emoji = "🟢"
            elif change.startswith('-'):
                emoji = "🔴"
            else:
                emoji = "⚪"
            
            text += f"{ticker} — {name[:15]} — ${price:,.2f} {emoji}\n"
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_companies_keyboard(page, total_pages)
        )
        bot.answer_callback_query(call.id)
    
    elif call.data.startswith("confirm_promo_"):
        promo_code = call.data.replace("confirm_promo_", "")
        username = call.from_user.username or call.from_user.first_name or f"User_{user_id}"
        
        success, msg = use_promo(promo_code, user_id, username)
        bot.answer_callback_query(call.id, msg)
        
        if success:
            update_leaderboard()
        
        # Возвращаем в меню
        text = f"""
╔══════════════════════════════╗
║     TERMINAL TRADER BOT      ║
╚══════════════════════════════╝
        """
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_main_keyboard()
        )
    
    elif call.data == "cancel_promo":
        bot.answer_callback_query(call.id, "Отменено")
        text = f"""
╔══════════════════════════════╗
║     TERMINAL TRADER BOT      ║
╚══════════════════════════════╝
        """
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_main_keyboard()
        )
    
    elif call.data == "status":
        user = get_user(user_id)
        money = user[2]
        day = user[3]
        capital = calculate_capital(user_id)
        portfolio = get_portfolio(user_id)
        
        text = f"""
📊 ТВОЙ СТАТУС (День {day})

💰 Баланс: ${money:,.2f}
💵 Капитал: ${capital:,.2f}

📋 Портфель:
        """
        
        if portfolio:
            for p in portfolio:
                text += f"\n{p[1]}: {p[2]} шт. (${p[2] * p[4]:,.2f})"
        else:
            text += "\nУ вас пока нет акций"
        
        leaderboard = get_leaderboard(50)
        for i, entry in enumerate(leaderboard, 1):
            if entry[0] == user_id:
                text += f"\n\n⭐ Место: {i} из {len(leaderboard)}"
                break
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        bot.answer_callback_query(call.id)
    
    elif call.data == "next":
        update_company_prices()
        update_leaderboard()
        bot.edit_message_text(
            "⏩ Новый день! Цены обновлены.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        bot.answer_callback_query(call.id)
    
    elif call.data == "leaderboard":
        leaderboard = get_leaderboard(10)
        
        text = f"🏆 ТАБЛИЦА ЛИДЕРОВ\n\n"
        
        for i, entry in enumerate(leaderboard, 1):
            user_id_lb, username, capital = entry
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            else:
                medal = f"{i}."
            
            name = username[:15] + "..." if len(username) > 15 else username
            text += f"{medal} {name} — ${capital:,.2f}\n"
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        bot.answer_callback_query(call.id)
    
    elif call.data == "reset":
        update_user(user_id, money=1000, day=1)
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM portfolio WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        update_leaderboard()
        
        bot.edit_message_text(
            "🔄 Новая игра! Ты начинаешь заново с $1000",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        bot.answer_callback_query(call.id)
    
    elif call.data == "promo":
        bot.edit_message_text(
            "🎟️ Введи промокод командой /tpromo КОД",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_back_keyboard()
        )
        bot.answer_callback_query(call.id)

# ========== АДМИН-КОМАНДЫ ==========
@bot.message_handler(commands=['tadmin'])
def admin_help(message):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    text = """
👑 **АДМИН-КОМАНДЫ**

**Игроки:**
/tadmin list — список игроков
/tadmin info id — информация об игроке
/tadmin give id сумма — выдать деньги
/tadmin take id сумма — забрать деньги
/tadmin set id сумма — установить баланс
/tadmin reset id — сбросить игрока
/tadmin ban id — забанить
/tadmin unban id — разбанить

**Промокоды:**
/tadmin promos — список промокодов
/tadmin promo add КОД БОНУС МАКС — добавить
/tadmin promo del КОД — удалить
/tadmin promo stats КОД — статистика
/tadmin promo watch — включить слежку

**Компании:**
/tadmin comps — список компаний
/tadmin comp add ТИКЕР НАЗВАНИЕ ЦЕНА — добавить
/tadmin comp del ТИКЕР — удалить
/tadmin comp price ТИКЕР ЦЕНА — изменить цену

**Модераторы:**
/tadmin mod add id — добавить модератора
/tadmin mod remove id — удалить
/tadmin mod list — список

**Статистика:**
/tadmin stats — общая статистика
/tadmin logs — последние действия
    """
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['tadmin', 'promo', 'watch'])
def admin_promo_watch(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    # Просто заглушка, слежка уже в use_promo
    bot.reply_to(message, "✅ Слежка за промокодами активна")

@bot.message_handler(commands=['tadmin', 'promo', 'stats'])
def admin_promo_stats(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        promo_code = message.text.split()[3].upper()
    except:
        bot.reply_to(message, "❌ Использование: /tadmin promo stats КОД")
        return
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM promocodes WHERE code = ?', (promo_code,))
    promo = cursor.fetchone()
    
    if not promo:
        bot.reply_to(message, "❌ Промокод не найден")
        conn.close()
        return
    
    cursor.execute('''
        SELECT * FROM promo_activations 
        WHERE promo_code = ? 
        ORDER BY activated_at DESC
    ''', (promo_code,))
    activations = cursor.fetchall()
    conn.close()
    
    remaining = promo['max_uses'] - promo['used_count']
    
    text = f"""
🎟️ **Промокод:** {promo_code}
💰 **Бонус:** +${promo['bonus']}
🎫 **Активаций:** {promo['used_count']}/{promo['max_uses']}
📊 **Осталось:** {remaining}

**Кто активировал:**
"""
    
    for i, act in enumerate(activations[:10], 1):
        text += f"\n{i}. @{act[3]} — {act[4]}"
    
    if len(activations) > 10:
        text += f"\n... и ещё {len(activations) - 10}"
    
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['tadmin', 'comps'])
def admin_comps(message):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id, 'promo'):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    companies, total = get_companies(page=1, per_page=100)
    
    text = "📋 **ВСЕ КОМПАНИИ**\n\n"
    for c in companies:
        text += f"{c[0]} — {c[1]} — ${c[2]:,.2f}\n"
    
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['tadmin', 'comp', 'add'])
def admin_comp_add(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    try:
        parts = message.text.split()
        ticker = parts[3].upper()
        name = parts[4]
        price = float(parts[5])
        vol = float(parts[6]) if len(parts) > 6 else 0.05
    except:
        bot.reply_to(message, "❌ Использование: /tadmin comp add ТИКЕР НАЗВАНИЕ ЦЕНА [ВОЛАТИЛЬНОСТЬ]")
        return
    
    success = add_company(ticker, name, price, vol)
    
    if success:
        bot.reply_to(message, f"✅ Компания {ticker} добавлена")
        log_admin(message.from_user.id, "add_company", details=f"{ticker} {name} ${price}")
    else:
        bot.reply_to(message, "❌ Ошибка добавления (возможно тикер уже существует)")

@bot.message_handler(commands=['tadmin', 'comp', 'del'])
def admin_comp_del(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    try:
        ticker = message.text.split()[3].upper()
    except:
        bot.reply_to(message, "❌ Использование: /tadmin comp del ТИКЕР")
        return
    
    success = delete_company(ticker)
    
    if success:
        bot.reply_to(message, f"✅ Компания {ticker} удалена")
        log_admin(message.from_user.id, "delete_company", details=ticker)
    else:
        bot.reply_to(message, "❌ Компания не найдена")

@bot.message_handler(commands=['tadmin', 'give'])
def admin_give(message):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id, 'give'):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    try:
        parts = message.text.split()
        target_id = int(parts[2])
        amount = float(parts[3])
    except:
        bot.reply_to(message, "❌ Использование: /tadmin give ID СУММА")
        return
    
    update_user(target_id, money=get_user(target_id)[2] + amount)
    bot.reply_to(message, f"✅ Пользователю {target_id} выдано ${amount:,.2f}")
    log_admin(message.from_user.id, "give_money", target_id, f"+${amount}")

@bot.message_handler(commands=['tadmin', 'take'])
def admin_take(message):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id, 'take'):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    try:
        parts = message.text.split()
        target_id = int(parts[2])
        amount = float(parts[3])
    except:
        bot.reply_to(message, "❌ Использование: /tadmin take ID СУММА")
        return
    
    user = get_user(target_id)
    new_money = max(0, user[2] - amount)
    update_user(target_id, money=new_money)
    bot.reply_to(message, f"✅ У пользователя {target_id} забрано ${amount:,.2f}")
    log_admin(message.from_user.id, "take_money", target_id, f"-${amount}")

@bot.message_handler(commands=['tadmin', 'ban'])
def admin_ban(message):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id, 'ban'):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    try:
        target_id = int(message.text.split()[2])
    except:
        bot.reply_to(message, "❌ Использование: /tadmin ban ID")
        return
    
    update_user(target_id, banned=1)
    bot.reply_to(message, f"✅ Пользователь {target_id} забанен")
    log_admin(message.from_user.id, "ban_user", target_id)

@bot.message_handler(commands=['tadmin', 'unban'])
def admin_unban(message):
    if message.from_user.id != ADMIN_ID and not is_moderator(message.from_user.id, 'ban'):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    try:
        target_id = int(message.text.split()[2])
    except:
        bot.reply_to(message, "❌ Использование: /tadmin unban ID")
        return
    
    update_user(target_id, banned=0)
    bot.reply_to(message, f"✅ Пользователь {target_id} разбанен")
    log_admin(message.from_user.id, "unban_user", target_id)

@bot.message_handler(commands=['tadmin', 'stats'])
def admin_stats(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE banned = 1')
    banned_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(money) FROM users')
    total_money = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM promocodes')
    total_promos = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(used_count) FROM promocodes')
    total_activations = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM companies')
    total_companies = cursor.fetchone()[0]
    
    conn.close()
    
    text = f"""
📊 **ОБЩАЯ СТАТИСТИКА**

👥 Всего игроков: {total_users}
⛔ Забанено: {banned_users}
💰 Всего денег: ${total_money:,.2f}
🎟️ Промокодов: {total_promos}
🎫 Активаций: {total_activations}
🏢 Компаний: {total_companies}
    """
    bot.reply_to(message, text, parse_mode="Markdown")

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    print("🤖 Terminal Trade с супер-админкой запущен...")
    print(f"👑 Админ ID: {ADMIN_ID}")
    bot.infinity_polling()