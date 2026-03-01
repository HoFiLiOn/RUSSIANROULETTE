import telebot
from telebot import types
import random
import sqlite3
import os
from datetime import datetime
from flask import Flask
import threading
import time

# ========== ТОКЕН ==========
TOKEN = "8412567351:AAG7eEMXlNfDBsNZF08GD-Pr-LH-2z1txSQ"
bot = telebot.TeleBot(TOKEN)

# ========== ID АДМИНА ==========
ADMIN_ID = 8388843828

# ========== ПОДКЛЮЧЕНИЕ К БД ==========
def get_db():
    conn = sqlite3.connect('roulette.db')
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
            money INTEGER DEFAULT 200,
            wins INTEGER DEFAULT 0,
            games INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица лобби
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lobbies (
            lobby_code TEXT PRIMARY KEY,
            chat_id INTEGER,
            creator_id INTEGER,
            status TEXT DEFAULT 'waiting',
            current_turn INTEGER DEFAULT 0,
            chamber INTEGER,
            position INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица игроков в лобби
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lobby_players (
            lobby_code TEXT,
            user_id INTEGER,
            alive BOOLEAN DEFAULT 1,
            turn_order INTEGER,
            PRIMARY KEY (lobby_code, user_id)
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ========== ВЕБ-СЕРВЕР ==========
app = Flask(__name__)

@app.route('/')
def health():
    return "Roulette Bot is alive!"

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
        cursor.execute('''
            INSERT INTO users (user_id, money)
            VALUES (?, 200)
        ''', (user_id,))
        conn.commit()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
    
    conn.close()
    return user

def update_user_money(user_id, amount):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET money = money + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def update_user_stats(user_id, won=False):
    conn = get_db()
    cursor = conn.cursor()
    
    if won:
        cursor.execute('UPDATE users SET wins = wins + 1, games = games + 1 WHERE user_id = ?', (user_id,))
    else:
        cursor.execute('UPDATE users SET games = games + 1 WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()

# ========== ФУНКЦИИ РАБОТЫ С ЛОББИ ==========
def create_lobby(chat_id, creator_id):
    conn = get_db()
    cursor = conn.cursor()
    
    # Генерируем код
    lobby_code = f"LB{random.randint(1000, 9999)}"
    
    cursor.execute('''
        INSERT INTO lobbies (lobby_code, chat_id, creator_id, status)
        VALUES (?, ?, ?, 'waiting')
    ''', (lobby_code, chat_id, creator_id))
    
    cursor.execute('''
        INSERT INTO lobby_players (lobby_code, user_id, turn_order)
        VALUES (?, ?, 0)
    ''', (lobby_code, creator_id))
    
    conn.commit()
    conn.close()
    
    return lobby_code

def join_lobby(lobby_code, user_id):
    conn = get_db()
    cursor = conn.cursor()
    
    # Получаем текущее количество игроков
    cursor.execute('SELECT COUNT(*) FROM lobby_players WHERE lobby_code = ?', (lobby_code,))
    count = cursor.fetchone()[0]
    
    if count >= 6:
        conn.close()
        return False, "Лобби заполнено"
    
    cursor.execute('''
        INSERT INTO lobby_players (lobby_code, user_id, turn_order)
        VALUES (?, ?, ?)
    ''', (lobby_code, user_id, count))
    
    conn.commit()
    conn.close()
    
    return True, "Присоединился"

def start_game(lobby_code):
    conn = get_db()
    cursor = conn.cursor()
    
    # Получаем количество игроков
    cursor.execute('SELECT COUNT(*) FROM lobby_players WHERE lobby_code = ?', (lobby_code,))
    count = cursor.fetchone()[0]
    
    if count < 2:
        conn.close()
        return False
    
    # Инициализируем игру
    chamber = random.randint(1, 6)
    
    cursor.execute('''
        UPDATE lobbies 
        SET status = 'playing', chamber = ?, position = 1, current_turn = 0
        WHERE lobby_code = ?
    ''', (chamber, lobby_code))
    
    # Все живы
    cursor.execute('''
        UPDATE lobby_players 
        SET alive = 1 
        WHERE lobby_code = ?
    ''', (lobby_code,))
    
    conn.commit()
    conn.close()
    
    return True

def get_lobby(lobby_code):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM lobbies WHERE lobby_code = ?', (lobby_code,))
    lobby = cursor.fetchone()
    
    if lobby:
        cursor.execute('''
            SELECT p.*, u.username 
            FROM lobby_players p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.lobby_code = ?
            ORDER BY p.turn_order
        ''', (lobby_code,))
        players = cursor.fetchall()
        
        lobby = dict(lobby)
        lobby['players'] = [dict(p) for p in players]
    
    conn.close()
    return lobby

def get_lobby_by_chat(chat_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM lobbies WHERE chat_id = ? AND status = "waiting"', (chat_id,))
    lobby = cursor.fetchone()
    
    if lobby:
        cursor.execute('''
            SELECT p.*, u.username 
            FROM lobby_players p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.lobby_code = ?
            ORDER BY p.turn_order
        ''', (lobby['lobby_code'],))
        players = cursor.fetchall()
        
        lobby = dict(lobby)
        lobby['players'] = [dict(p) for p in players]
    
    conn.close()
    return lobby

def get_active_game(user_id, chat_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT l.* FROM lobbies l
        JOIN lobby_players p ON l.lobby_code = p.lobby_code
        WHERE l.chat_id = ? AND p.user_id = ? AND p.alive = 1 AND l.status = 'playing'
    ''', (chat_id, user_id))
    
    lobby = cursor.fetchone()
    
    if lobby:
        cursor.execute('''
            SELECT p.*, u.username 
            FROM lobby_players p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.lobby_code = ?
            ORDER BY p.turn_order
        ''', (lobby['lobby_code'],))
        players = cursor.fetchall()
        
        lobby = dict(lobby)
        lobby['players'] = [dict(p) for p in players]
    
    conn.close()
    return lobby

def shoot(lobby_code, user_id):
    conn = get_db()
    cursor = conn.cursor()
    
    # Получаем данные лобби
    cursor.execute('SELECT * FROM lobbies WHERE lobby_code = ?', (lobby_code,))
    lobby = cursor.fetchone()
    
    if not lobby or lobby['status'] != 'playing':
        conn.close()
        return None, "Игра не активна"
    
    # Получаем живых игроков по порядку
    cursor.execute('''
        SELECT * FROM lobby_players 
        WHERE lobby_code = ? AND alive = 1 
        ORDER BY turn_order
    ''', (lobby_code,))
    alive_players = cursor.fetchall()
    
    if not alive_players:
        conn.close()
        return None, "Нет живых игроков"
    
    current_player = alive_players[lobby['current_turn']]
    
    # Проверяем, что стреляет тот, чья очередь
    if current_player['user_id'] != user_id:
        player_name = current_player['username'] or f"Игрок {current_player['turn_order']+1}"
        conn.close()
        return None, f"Сейчас ходит {player_name}"
    
    # Проверяем выстрел
    if lobby['position'] == lobby['chamber']:
        # Убит
        cursor.execute('''
            UPDATE lobby_players 
            SET alive = 0 
            WHERE lobby_code = ? AND user_id = ?
        ''', (lobby_code, user_id))
        
        # Обновляем список живых
        cursor.execute('''
            SELECT * FROM lobby_players 
            WHERE lobby_code = ? AND alive = 1 
            ORDER BY turn_order
        ''', (lobby_code,))
        alive_players = cursor.fetchall()
        
        # Если остался один - конец игры
        if len(alive_players) == 1:
            winner_id = alive_players[0]['user_id']
            
            # Начисляем монеты
            update_user_money(winner_id, 100)  # +100 за победу
            update_user_stats(winner_id, won=True)
            
            # Всем участникам +30
            cursor.execute('''
                SELECT user_id FROM lobby_players 
                WHERE lobby_code = ? AND user_id != ?
            ''', (lobby_code, winner_id))
            losers = cursor.fetchall()
            
            for loser in losers:
                update_user_money(loser['user_id'], 30)
                update_user_stats(loser['user_id'], won=False)
            
            # Удаляем лобби
            cursor.execute('DELETE FROM lobby_players WHERE lobby_code = ?', (lobby_code,))
            cursor.execute('DELETE FROM lobbies WHERE lobby_code = ?', (lobby_code,))
            conn.commit()
            conn.close()
            
            winner_name = alive_players[0]['username'] or f"Игрок {alive_players[0]['turn_order']+1}"
            return "game_over", winner_name
        
        # Перезаряжаем
        new_chamber = random.randint(1, 6)
        cursor.execute('''
            UPDATE lobbies 
            SET chamber = ?, position = 1
            WHERE lobby_code = ?
        ''', (new_chamber, lobby_code))
        
        # Ход следующему
        next_turn = lobby['current_turn']
        if next_turn >= len(alive_players):
            next_turn = 0
        
        cursor.execute('UPDATE lobbies SET current_turn = ? WHERE lobby_code = ?', (next_turn, lobby_code))
        
        conn.commit()
        conn.close()
        
        return "killed", None
    
    else:
        # Промах
        new_position = lobby['position'] + 1
        if new_position > 6:
            new_position = 1
        
        next_turn = (lobby['current_turn'] + 1) % len(alive_players)
        
        cursor.execute('''
            UPDATE lobbies 
            SET position = ?, current_turn = ?
            WHERE lobby_code = ?
        ''', (new_position, next_turn, lobby_code))
        
        conn.commit()
        conn.close()
        
        return "safe", None

# ========== КНОПКА СТРЕЛЬБЫ ==========
def get_shoot_keyboard(lobby_code):
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("🔫 ВЫСТРЕЛИТЬ", url=f"https://t.me/roulette_stage_bot?start=shoot_{lobby_code}")
    markup.add(btn)
    return markup

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or f"User_{user_id}"
    
    # Регистрируем пользователя
    get_user(user_id)
    
    text = f"""
🎲 **РУССКАЯ РУЛЕТКА**

Привет, {username}! 👋

💰 Твой баланс: 200 монет

Команды:
/create — создать лобби
/join КОД — присоединиться
/list — список лобби
/startgame — начать игру
/money — баланс

Минимум 2 игрока, максимум 6.
За участие: +30 монет
За победу: +100 монет
    """
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['money'])
def money_command(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    text = f"""
💰 **ТВОЙ БАЛАНС**

Монет: {user['money']}
Побед: {user['wins']}
Игр: {user['games']}
    """
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['create'])
def create_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем, нет ли уже лобби
    existing = get_lobby_by_chat(chat_id)
    if existing:
        bot.reply_to(message, f"❌ В этом чате уже есть лобби {existing['lobby_code']}")
        return
    
    lobby_code = create_lobby(chat_id, user_id)
    
    text = f"""
✅ Лобби создано!

Код: `{lobby_code}`
Игроков: 1/6

Присоединиться: /join {lobby_code}
Начать: /startgame
    """
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['join'])
def join_command(message):
    user_id = message.from_user.id
    
    try:
        lobby_code = message.text.split()[1].upper()
    except:
        bot.reply_to(message, "❌ Использование: /join КОД")
        return
    
    success, msg = join_lobby(lobby_code, user_id)
    
    if success:
        bot.send_message(message.chat.id, f"✅ Ты присоединился к лобби {lobby_code}")
        
        # Уведомляем всех
        lobby = get_lobby(lobby_code)
        if lobby:
            for player in lobby['players']:
                if player['user_id'] != user_id:
                    try:
                        username = message.from_user.username or message.from_user.first_name
                        bot.send_message(
                            player['user_id'],
                            f"👤 {username} присоединился к лобби {lobby_code}\nИгроков: {len(lobby['players'])}/6"
                        )
                    except:
                        pass
    else:
        bot.reply_to(message, f"❌ {msg}")

@bot.message_handler(commands=['list'])
def list_command(message):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT l.lobby_code, COUNT(p.user_id) as players
        FROM lobbies l
        LEFT JOIN lobby_players p ON l.lobby_code = p.lobby_code
        WHERE l.status = 'waiting'
        GROUP BY l.lobby_code
    ''')
    
    lobbies = cursor.fetchall()
    conn.close()
    
    if lobbies:
        text = "📋 **Доступные лобби:**\n\n"
        for l in lobbies:
            text += f"`{l['lobby_code']}` — {l['players']}/6 игроков\n"
    else:
        text = "📋 Нет доступных лобби. Создай своё: /create"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['startgame'])
def startgame_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    lobby = get_lobby_by_chat(chat_id)
    
    if not lobby:
        bot.reply_to(message, "❌ В этом чате нет лобби")
        return
    
    if lobby['creator_id'] != user_id:
        bot.reply_to(message, "❌ Только создатель может начать игру")
        return
    
    if len(lobby['players']) < 2:
        bot.reply_to(message, "❌ Минимум 2 игрока")
        return
    
    if start_game(lobby['lobby_code']):
        # Обновляем данные
        lobby = get_lobby(lobby['lobby_code'])
        
        players_text = ""
        for i, p in enumerate(lobby['players']):
            name = p['username'] or f"Игрок {i+1}"
            players_text += f"{i+1}. {name}\n"
        
        first_player = lobby['players'][0]['username'] or f"Игрок 1"
        
        text = f"""
🔫 **ИГРА НАЧАЛАСЬ!**

Код лобби: `{lobby['lobby_code']}`

Игроки:
{players_text}
Патрон заряжен.

Сейчас ходит: {first_player}

Нажми на кнопку 🔫 чтобы выстрелить (доступно только тебе)
        """
        
        for player in lobby['players']:
            try:
                bot.send_message(
                    player['user_id'],
                    text,
                    parse_mode="Markdown",
                    reply_markup=get_shoot_keyboard(lobby['lobby_code'])
                )
            except:
                pass
        
        # Отправляем в чат
        bot.send_message(chat_id, f"🔫 Игра началась! Первый ходит {first_player}")
    else:
        bot.reply_to(message, "❌ Не удалось начать игру")

# ========== ОБРАБОТКА СТРЕЛЬБЫ ==========
@bot.message_handler(func=lambda message: message.text and message.text.startswith('/start shoot_'))
def shoot_handler(message):
    user_id = message.from_user.id
    lobby_code = message.text.replace('/start shoot_', '').strip()
    
    result, data = shoot(lobby_code, user_id)
    
    if result == "killed":
        bot.send_message(
            message.chat.id,
            "💥 **БАХ!** Ты застрелился!",
            parse_mode="Markdown"
        )
        
        # Проверяем, не закончилась ли игра
        lobby = get_lobby(lobby_code)
        if lobby:
            alive_players = [p for p in lobby['players'] if p['alive']]
            
            if len(alive_players) == 1:
                winner = alive_players[0]
                winner_name = winner['username'] or f"Игрок {winner['turn_order']+1}"
                
                bot.send_message(
                    message.chat.id,
                    f"🏆 **ИГРА ОКОНЧЕНА!**\nПобедитель: {winner_name}",
                    parse_mode="Markdown"
                )
        
    elif result == "safe":
        bot.send_message(
            message.chat.id,
            "😮‍💨 **Щелчок!** Тебе повезло...",
            parse_mode="Markdown"
        )
        
        lobby = get_lobby(lobby_code)
        if lobby:
            current = lobby['players'][lobby['current_turn']]
            current_name = current['username'] or f"Игрок {current['turn_order']+1}"
            
            bot.send_message(
                message.chat.id,
                f"Сейчас ходит: {current_name}",
                reply_markup=get_shoot_keyboard(lobby_code)
            )
    
    elif result == "game_over":
        bot.send_message(
            message.chat.id,
            f"🏆 **ИГРА ОКОНЧЕНА!**\nПобедитель: {data}",
            parse_mode="Markdown"
        )
    
    else:
        bot.send_message(message.chat.id, f"❌ {data}")

# ========== АДМИН-КОМАНДЫ ==========
@bot.message_handler(commands=['addmoney'])
def addmoney_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        amount = int(parts[2])
        
        update_user_money(user_id, amount)
        bot.reply_to(message, f"✅ {amount} монет выдано пользователю {user_id}")
    except:
        bot.reply_to(message, "❌ Использование: /addmoney ID СУММА")

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    print("🤖 Русская рулетка запущена...")
    print(f"👑 Админ ID: {ADMIN_ID}")
    bot.infinity_polling()