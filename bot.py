import telebot
import sqlite3
import random
import json
import os
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ========== КОНФИГ ==========
BOT_TOKEN = "8412567351:AAG7eEMXlNfDBsNZF08GD-Pr-LH-2z1txSQ"
BOT_USERNAME = "RussianRoulette_official_bot"
ADMIN_ID = 7040677455
MAX_PLAYERS_LIMIT = 15
SEASON_DAYS = 30

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ========== БД ==========
def init_db():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    
    # Пользователи
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  gc INTEGER DEFAULT 100,
                  rating INTEGER DEFAULT 0,
                  best_rating INTEGER DEFAULT 0,
                  wins INTEGER DEFAULT 0,
                  losses INTEGER DEFAULT 0,
                  total_games INTEGER DEFAULT 0,
                  win_streak INTEGER DEFAULT 0,
                  best_streak INTEGER DEFAULT 0,
                  shields INTEGER DEFAULT 0,
                  double_chance INTEGER DEFAULT 0,
                  insurance INTEGER DEFAULT 0,
                  diamond_shield INTEGER DEFAULT 0,
                  master INTEGER DEFAULT 0,
                  vip_level INTEGER DEFAULT 0,
                  vip_until TEXT,
                  last_daily TEXT,
                  daily_streak INTEGER DEFAULT 1,
                  referrer_id INTEGER DEFAULT 0)''')
    
    # Чат настройки
    c.execute('''CREATE TABLE IF NOT EXISTS chat_settings
                 (chat_id INTEGER PRIMARY KEY,
                  max_players INTEGER DEFAULT 6,
                  min_bet INTEGER DEFAULT 10,
                  max_bet INTEGER DEFAULT 500,
                  game_enabled INTEGER DEFAULT 1,
                  admin_only INTEGER DEFAULT 0,
                  owner_id INTEGER DEFAULT 0,
                  name TEXT DEFAULT '')''')
    
    # Чат статистика
    c.execute('''CREATE TABLE IF NOT EXISTS chat_stats
                 (chat_id INTEGER PRIMARY KEY,
                  total_games INTEGER DEFAULT 0,
                  total_bets INTEGER DEFAULT 0)''')
    
    # Сезоны
    c.execute('''CREATE TABLE IF NOT EXISTS seasons
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  number INTEGER DEFAULT 1,
                  start_date TEXT,
                  end_date TEXT,
                  is_active INTEGER DEFAULT 1)''')
    
    # Промокоды
    c.execute('''CREATE TABLE IF NOT EXISTS promocodes
                 (code TEXT PRIMARY KEY,
                  reward_type TEXT,
                  reward_amount INTEGER,
                  max_uses INTEGER,
                  used_count INTEGER DEFAULT 0,
                  expires TEXT,
                  created_by INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS promo_used
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  code TEXT,
                  user_id INTEGER,
                  used_at TEXT)''')
    
    # Сообщения в чатах (активность)
    c.execute('''CREATE TABLE IF NOT EXISTS message_count
                 (user_id INTEGER PRIMARY KEY,
                  count INTEGER DEFAULT 0,
                  last_message TEXT)''')
    
    # Активация сезона
    c.execute("SELECT * FROM seasons")
    if not c.fetchone():
        now = datetime.now()
        end = now + timedelta(days=SEASON_DAYS)
        c.execute("INSERT INTO seasons (number, start_date, end_date) VALUES (1, ?, ?)",
                  (now.isoformat(), end.isoformat()))
    
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT gc, rating, best_rating, wins, losses, total_games, win_streak, best_streak, "
              "shields, double_chance, insurance, diamond_shield, master, vip_level, vip_until, "
              "last_daily, daily_streak, referrer_id FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (user_id, gc, last_daily) VALUES (?, ?, ?)",
                  (user_id, 100, datetime.now().isoformat()))
        conn.commit()
        c.execute("SELECT gc, rating, best_rating, wins, losses, total_games, win_streak, best_streak, "
                  "shields, double_chance, insurance, diamond_shield, master, vip_level, vip_until, "
                  "last_daily, daily_streak, referrer_id FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
    conn.close()
    return {
        "gc": user[0],
        "rating": user[1],
        "best_rating": user[2],
        "wins": user[3],
        "losses": user[4],
        "total_games": user[5],
        "win_streak": user[6],
        "best_streak": user[7],
        "shields": user[8],
        "double_chance": user[9],
        "insurance": user[10],
        "diamond_shield": user[11],
        "master": user[12],
        "vip_level": user[13],
        "vip_until": user[14],
        "last_daily": user[15],
        "daily_streak": user[16],
        "referrer_id": user[17]
    }

def update_user(user_id, **kwargs):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    for key, value in kwargs.items():
        if value is not None:
            c.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

def add_gc(user_id, amount):
    user = get_user(user_id)
    update_user(user_id, gc=user["gc"] + amount)

def get_chat_settings(chat_id):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT max_players, min_bet, max_bet, game_enabled, admin_only, owner_id, name FROM chat_settings WHERE chat_id = ?", (chat_id,))
    settings = c.fetchone()
    if not settings:
        c.execute("INSERT INTO chat_settings (chat_id) VALUES (?)", (chat_id,))
        conn.commit()
        settings = (6, 10, 500, 1, 0, 0, "")
    conn.close()
    return {
        "max_players": settings[0],
        "min_bet": settings[1],
        "max_bet": settings[2],
        "game_enabled": settings[3],
        "admin_only": settings[4],
        "owner_id": settings[5],
        "name": settings[6]
    }

def update_chat_settings(chat_id, **kwargs):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    for key, value in kwargs.items():
        c.execute(f"UPDATE chat_settings SET {key} = ? WHERE chat_id = ?", (value, chat_id))
    conn.commit()
    conn.close()

def get_current_season():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT id, number, start_date, end_date FROM seasons WHERE is_active = 1")
    season = c.fetchone()
    conn.close()
    if season:
        return {"id": season[0], "number": season[1], "start_date": season[2], "end_date": season[3]}
    return None

def get_rank_name(rating):
    if rating < 500:
        return "🟢 Новичок"
    elif rating < 1000:
        return "🔵 Стрелок"
    elif rating < 1500:
        return "🟣 Опытный"
    elif rating < 2000:
        return "🟠 Мастер"
    elif rating < 2500:
        return "🔴 Элита"
    else:
        return "👑 Легенда"

def update_rating(user_id, won, bet_amount=0, win_amount=0):
    user = get_user(user_id)
    old_rating = user["rating"]
    rating_change = 25 if won else -15
    
    if won and win_amount > 0:
        rating_change += 5
    
    if won:
        new_streak = user["win_streak"] + 1
        if new_streak == 2:
            rating_change += 5
        elif new_streak == 3:
            rating_change += 10
        elif new_streak >= 5:
            rating_change += 20
        update_user(user_id, win_streak=new_streak, best_streak=max(user["best_streak"], new_streak))
    else:
        update_user(user_id, win_streak=0)
    
    new_rating = max(0, old_rating + rating_change)
    update_user(user_id, rating=new_rating, best_rating=max(user["best_rating"], new_rating))
    return rating_change

def get_vip_multiplier(user_id):
    user = get_user(user_id)
    if user["vip_until"]:
        vip_until = datetime.fromisoformat(user["vip_until"])
        if datetime.now() < vip_until:
            if user["vip_level"] >= 30:
                return 1.5
            elif user["vip_level"] >= 7:
                return 1.3
            elif user["vip_level"] >= 3:
                return 1.2
    return 1.0

def get_name(user_id):
    try:
        user = bot.get_chat(user_id)
        return f"@{user.username}" if user.username else user.first_name
    except:
        return str(user_id)

def get_user_link(user_id):
    try:
        user = bot.get_chat(user_id)
        name = user.first_name
        if user.username:
            return f"@{user.username}"
        else:
            return f'<a href="tg://user?id={user_id}">{name}</a>'
    except:
        return str(user_id)

def is_chat_admin(user_id, chat_id):
    if user_id == ADMIN_ID:
        return True
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except:
        return False

def is_chat_creator(user_id, chat_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status == 'creator'
    except:
        return False

def get_chat_name(chat_id):
    try:
        chat = bot.get_chat(chat_id)
        return chat.title or str(chat_id)
    except:
        return str(chat_id)

def get_top_players(category, limit=10):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    if category == "rating":
        c.execute("SELECT user_id, rating, wins FROM users ORDER BY rating DESC LIMIT ?", (limit,))
    elif category == "gc":
        c.execute("SELECT user_id, gc, wins FROM users ORDER BY gc DESC LIMIT ?", (limit,))
    elif category == "wins":
        c.execute("SELECT user_id, wins, rating FROM users ORDER BY wins DESC LIMIT ?", (limit,))
    else:
        return []
    return c.fetchall()

def add_message_count(user_id):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT count FROM message_count WHERE user_id = ?", (user_id,))
    res = c.fetchone()
    if res:
        new_count = res[0] + 1
        c.execute("UPDATE message_count SET count = ?, last_message = ? WHERE user_id = ?", (new_count, datetime.now().isoformat(), user_id))
        if new_count % 50 == 0:
            add_gc(user_id, 10)
            bot.send_message(user_id, f"🎁 Бонус за активность! +10 GC (50 сообщений)")
    else:
        c.execute("INSERT INTO message_count (user_id, count, last_message) VALUES (?, ?, ?)", (user_id, 1, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ========== ХРАНИЛИЩЕ ИГР ==========
games = {}

# ========== КЛАВИАТУРЫ ==========
def main_menu(chat_id, user_id):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🎮 Создать игру", callback_data="create_game"))
    kb.add(InlineKeyboardButton("📊 Стата", callback_data="stats"))
    kb.add(InlineKeyboardButton("🎁 Бонус", callback_data="daily"))
    kb.add(InlineKeyboardButton("🛒 Магазин", callback_data="shop_1"))
    kb.add(InlineKeyboardButton("🏆 Топы", callback_data="top_menu"))
    kb.add(InlineKeyboardButton("🎫 Промокод", callback_data="promo_menu"))
    
    if is_chat_creator(user_id, chat_id):
        kb.add(InlineKeyboardButton("⚙️ Настройки чата", callback_data="chat_settings"))
    
    if user_id == ADMIN_ID:
        kb.add(InlineKeyboardButton("👑 Админ панель", callback_data="admin_panel"))
    
    return kb

def shop_kb(page):
    kb = InlineKeyboardMarkup(row_width=2)
    
    items = {
        1: [
            ("🛡️ Щит", "buy_shield", 100),
            ("💎 Алмазный щит", "buy_diamond_shield", 400),
            ("🔄 Реинкарнация", "buy_reincarnation", 300)
        ],
        2: [
            ("⚡ Двойной шанс", "buy_double", 150),
            ("🔫 Точный выстрел", "buy_accurate", 120),
            ("🎯 Мастер", "buy_master", 250)
        ],
        3: [
            ("💰 Страховка", "buy_insurance", 200),
            ("💊 Аптечка", "buy_medkit", 80),
            ("🎲 Счастливый билет", "buy_lucky", 90)
        ],
        4: [
            ("👑 VIP 3 дня", "buy_vip_3", 500),
            ("👑 VIP 7 дней", "buy_vip_7", 1200),
            ("👑 VIP 30 дней", "buy_vip_30", 3000)
        ]
    }
    
    for name, callback, price in items.get(page, []):
        kb.add(InlineKeyboardButton(f"{name} — {price} GC", callback_data=callback))
    
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"shop_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(f"{page}/4", callback_data="none"))
    if page < 4:
        nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"shop_{page+1}"))
    kb.row(*nav_buttons)
    
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def stats_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def top_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🏆 По рейтингу", callback_data="top_rating"))
    kb.add(InlineKeyboardButton("💰 По GunCoin", callback_data="top_gc"))
    kb.add(InlineKeyboardButton("🎮 По победам", callback_data="top_wins"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def promo_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🎫 Ввести промокод", callback_data="enter_promo"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def admin_panel_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"))
    kb.add(InlineKeyboardButton("📋 Список чатов", callback_data="admin_chats"))
    kb.add(InlineKeyboardButton("👥 Список игроков", callback_data="admin_players"))
    kb.add(InlineKeyboardButton("🎫 Промокоды", callback_data="admin_promocodes"))
    kb.add(InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"))
    kb.add(InlineKeyboardButton("🎮 Активные игры", callback_data="admin_games"))
    kb.add(InlineKeyboardButton("📅 Сезон", callback_data="admin_season"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def admin_promocodes_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("➕ Создать промокод", callback_data="admin_create_promo"))
    kb.add(InlineKeyboardButton("📋 Список промокодов", callback_data="admin_list_promos"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    return kb

def chat_settings_kb(chat_id):
    settings = get_chat_settings(chat_id)
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"👥 Макс игроков: {settings['max_players']}", callback_data=f"set_max_players"))
    kb.add(InlineKeyboardButton(f"💰 Мин ставка: {settings['min_bet']} GC", callback_data=f"set_min_bet"))
    kb.add(InlineKeyboardButton(f"💎 Макс ставка: {settings['max_bet']} GC", callback_data=f"set_max_bet"))
    kb.add(InlineKeyboardButton(f"🎮 Игры: {'✅ Вкл' if settings['game_enabled'] else '❌ Выкл'}", callback_data=f"toggle_game"))
    kb.add(InlineKeyboardButton(f"👑 Только админы: {'✅ Да' if settings['admin_only'] else '❌ Нет'}", callback_data=f"toggle_admin_only"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def game_lobby_kb(chat_id):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("➕ Присоединиться", callback_data=f"join_{chat_id}"))
    kb.add(InlineKeyboardButton("❌ Отменить игру", callback_data=f"cancel_game_{chat_id}"))
    return kb

def game_start_kb(chat_id):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🚀 Начать игру", callback_data=f"start_game_{chat_id}"))
    kb.add(InlineKeyboardButton("❌ Отменить игру", callback_data=f"cancel_game_{chat_id}"))
    return kb

def game_action_kb(chat_id, user_id, bet):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🔫 Выстрелить", callback_data=f"shoot_{chat_id}_{user_id}_{bet}"))
    kb.add(InlineKeyboardButton("🔄 Крутить барабан", callback_data=f"spin_{chat_id}_{user_id}_{bet}"))
    return kb

def bet_kb(chat_id):
    settings = get_chat_settings(chat_id)
    kb = InlineKeyboardMarkup(row_width=1)
    bets = [10, 50, 100, 200, 500, 1000]
    for bet in bets:
        if settings['min_bet'] <= bet <= settings['max_bet']:
            kb.add(InlineKeyboardButton(f"{bet} GC", callback_data=f"place_bet_{chat_id}_{bet}"))
    return kb

def back_button():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def get_rules():
    return (
        "<b>🔫 РУССКАЯ РУЛЕТКА</b>\n\n"
        "<b>🎲 Правила игры:</b>\n"
        "• Один игрок создает лобби\n"
        "• Другие присоединяются (до 15 игроков)\n"
        "• Каждый делает ставку 🔫 GC\n"
        "• Игроки ходят по очереди\n"
        "• Если выпадает пусто → игрок продолжает\n"
        "• Если выпадает патрон → игрок выбывает, теряет ставку\n"
        "• Последний выживший забирает банк!\n\n"
        "<b>🛡️ Защиты (купить в магазине):</b>\n"
        "• Щит — спасает от 1 патрона\n"
        "• Алмазный щит — спасает от 3 патронов\n"
        "• Двойной шанс — +10% к удаче на 1 игру\n"
        "• Точный выстрел — +15% шанс попадания\n"
        "• Мастер — постоянный +5% к удаче\n"
        "• Страховка — возврат 50% ставки при вылете\n"
        "• Реинкарнация — воскрешение 1 раз\n\n"
        "<b>💰 Как получить GC:</b>\n"
        "• Ежедневный бонус — 50 GC (+200 за 7 дней)\n"
        "• Активность в чате — 10 GC за 50 сообщений\n"
        "• Победа в игре — +5 GC\n"
        "• Приглашение друга — 50 GC\n"
        "• Друг выиграл — 10% от его выигрыша"
    )

def update_lobby_message(chat_id):
    game = games.get(chat_id)
    if not game:
        return
    
    players_count = len(game["players"])
    all_bets_placed = all(p in game["bets"] for p in game["players"])
    
    players_list = []
    for p in game["players"]:
        if p in game["bets"]:
            players_list.append(f"• {get_user_link(p)} — {game['bets'][p]} GC")
        else:
            players_list.append(f"• {get_user_link(p)} — ожидает ставку")
    
    players_text = "\n".join(players_list)
    total_pot = sum(game["bets"].values()) if game["bets"] else 0
    
    text = (
        f"🎮 <b>ЛОББИ ИГРЫ</b>\n\n"
        f"Создатель: {get_user_link(game['creator'])}\n"
        f"Участники ({players_count}/{game['max_players']}):\n{players_text}\n"
    )
    
    if not all_bets_placed:
        text += f"\n⚠️ Ожидаем ставки от всех игроков..."
        kb = game_lobby_kb(chat_id)
    else:
        text += f"\n✅ Все ставки сделаны!\n💰 Общий банк: {total_pot} GC"
        kb = game_start_kb(chat_id)
    
    try:
        bot.edit_message_text(
            text,
            chat_id,
            game["message_id"],
            reply_markup=kb,
            parse_mode="HTML"
        )
    except:
        pass

# ========== ПРОМОКОДЫ ==========
def create_promo(code, reward_type, reward_amount, max_uses, expires_days=None):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    expires = None
    if expires_days:
        expires = (datetime.now() + timedelta(days=expires_days)).isoformat()
    c.execute("INSERT OR REPLACE INTO promocodes (code, reward_type, reward_amount, max_uses, expires) VALUES (?, ?, ?, ?, ?)",
              (code, reward_type, reward_amount, max_uses, expires))
    conn.commit()
    conn.close()

def use_promo(user_id, code):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    
    c.execute("SELECT reward_type, reward_amount, max_uses, used_count, expires FROM promocodes WHERE code = ?", (code,))
    promo = c.fetchone()
    if not promo:
        conn.close()
        return False, "Промокод не найден!"
    
    reward_type, reward_amount, max_uses, used_count, expires = promo
    
    if expires:
        if datetime.now() > datetime.fromisoformat(expires):
            conn.close()
            return False, "Срок действия промокода истек!"
    
    if used_count >= max_uses:
        conn.close()
        return False, "Промокод уже использован максимальное количество раз!"
    
    c.execute("SELECT * FROM promo_used WHERE code = ? AND user_id = ?", (code, user_id))
    if c.fetchone():
        conn.close()
        return False, "Вы уже использовали этот промокод!"
    
    user = get_user(user_id)
    if reward_type == "gc":
        update_user(user_id, gc=user["gc"] + reward_amount)
    elif reward_type == "shield":
        update_user(user_id, shields=user["shields"] + reward_amount)
    elif reward_type == "double":
        update_user(user_id, double_chance=user["double_chance"] + reward_amount)
    elif reward_type == "insurance":
        update_user(user_id, insurance=user["insurance"] + reward_amount)
    elif reward_type == "diamond_shield":
        update_user(user_id, diamond_shield=user["diamond_shield"] + reward_amount)
    elif reward_type == "vip":
        update_user(user_id, vip_level=reward_amount, vip_until=(datetime.now() + timedelta(days=reward_amount)).isoformat())
    
    c.execute("UPDATE promocodes SET used_count = used_count + 1 WHERE code = ?", (code,))
    c.execute("INSERT INTO promo_used (code, user_id, used_at) VALUES (?, ?, ?)", (code, user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    return True, f"Промокод активирован! Получено: {reward_amount} {reward_type.upper()}"

def get_all_promos():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT code, reward_type, reward_amount, max_uses, used_count, expires FROM promocodes")
    promos = c.fetchall()
    conn.close()
    return promos

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    init_db()
    user_id = message.from_user.id
    chat_id = message.chat.id
    get_user(user_id)
    
    # Сохраняем информацию о чате
    if message.chat.type != "private":
        update_chat_settings(chat_id, name=message.chat.title)
        # Сохраняем владельца если он создатель
        if is_chat_creator(user_id, chat_id):
            update_chat_settings(chat_id, owner_id=user_id)
    
    bot.send_message(
        chat_id,
        f"<b>🔫 Добро пожаловать в Русскую Рулетку, {message.from_user.first_name}!</b>\n\n{get_rules()}",
        reply_markup=main_menu(chat_id, user_id)
    )

@bot.message_handler(commands=['promo'])
def promo_command(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Использование: /promo КОД")
        return
    success, msg = use_promo(message.from_user.id, args[1].upper())
    bot.reply_to(message, msg)

@bot.message_handler(func=lambda m: m.chat.type != "private")
def track_messages(message):
    user_id = message.from_user.id
    add_message_count(user_id)

# ========== КОЛБЭКИ ==========
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    global games
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    # Назад
    if call.data == "back":
        bot.edit_message_text(
            f"<b>🔫 Главное меню</b>\n\n{get_rules()}",
            chat_id,
            message_id,
            reply_markup=main_menu(chat_id, user_id)
        )
        bot.answer_callback_query(call.id)
        return
    
    # None (заглушка)
    if call.data == "none":
        bot.answer_callback_query(call.id)
        return
    
    # Стата
    if call.data == "stats":
        user = get_user(user_id)
        season = get_current_season()
        vip_text = "Нет"
        if user["vip_until"]:
            vip_until = datetime.fromisoformat(user["vip_until"])
            if datetime.now() < vip_until:
                days_left = (vip_until - datetime.now()).days
                vip_text = f"{user['vip_level']} дней (осталось {days_left})"
        
        win_percent = 0
        if user["total_games"] > 0:
            win_percent = int(user["wins"] / user["total_games"] * 100)
        
        text = (
            f"<b>📊 ТВОЯ СТАТА</b>\n\n"
            f"🔫 GunCoin: {user['gc']} GC\n"
            f"🏆 Рейтинг: {user['rating']}\n"
            f"🏅 Ранг: {get_rank_name(user['rating'])}\n\n"
            f"<b>📈 Статистика:</b>\n"
            f"├─ Побед: {user['wins']}\n"
            f"├─ Поражений: {user['losses']}\n"
            f"├─ Всего игр: {user['total_games']}\n"
            f"├─ Лучший стрик: {user['best_streak']}\n"
            f"└─ Процент побед: {win_percent}%\n\n"
            f"<b>🛡️ Защиты:</b>\n"
            f"├─ Щитов: {user['shields']}\n"
            f"├─ Алмазных щитов: {user['diamond_shield']}\n"
            f"├─ Двойных шансов: {user['double_chance']}\n"
            f"├─ Страховок: {user['insurance']}\n"
            f"└─ Мастер: {'✅' if user['master'] else '❌'}\n\n"
            f"👑 VIP: {vip_text}\n\n"
            f"📅 Сезон #{season['number'] if season else '?'} до {season['end_date'][:10] if season else '?'}"
        )
        bot.edit_message_text(text, chat_id, message_id, reply_markup=stats_kb())
        bot.answer_callback_query(call.id)
        return
    
    # Ежедневный бонус
    if call.data == "daily":
        user = get_user(user_id)
        last = datetime.fromisoformat(user["last_daily"]) if user["last_daily"] else datetime.min
        now = datetime.now()
        
        if now - last < timedelta(days=1):
            hours_left = 24 - (now - last).seconds // 3600
            bot.answer_callback_query(call.id, f"⏰ Бонус будет через {hours_left} ч", show_alert=True)
            return
        
        streak = user["daily_streak"]
        bonus = 50
        if streak >= 7:
            bonus += 200
            update_user(user_id, daily_streak=1)
        else:
            update_user(user_id, daily_streak=streak + 1)
        
        new_gc = user["gc"] + bonus
        update_user(user_id, gc=new_gc, last_daily=now.isoformat())
        
        text = f"🎁 Ежедневный бонус!\n\n+{bonus} GC\n💰 Новый баланс: {new_gc} GC"
        if streak >= 7:
            text += "\n\n🔥 Бонус за 7 дней подряд! +200 GC"
        
        bot.edit_message_text(text, chat_id, message_id, reply_markup=stats_kb())
        bot.answer_callback_query(call.id)
        return
    
    # Магазин
    if call.data.startswith("shop_"):
        page = int(call.data.split("_")[1])
        bot.edit_message_text(
            f"<b>🛒 МАГАЗИН — страница {page}/4</b>\n\nВыбери предмет для покупки:",
            chat_id,
            message_id,
            reply_markup=shop_kb(page)
        )
        bot.answer_callback_query(call.id)
        return
    
    # Покупки
    if call.data == "buy_shield":
        user = get_user(user_id)
        if user["gc"] >= 100:
            update_user(user_id, gc=user["gc"] - 100, shields=user["shields"] + 1)
            bot.answer_callback_query(call.id, "✅ Куплен щит!", show_alert=True)
            bot.edit_message_text(
                f"🛡️ Щит куплен!\n💰 Осталось: {user['gc'] - 100} GC\nЩитов: {user['shields'] + 1}",
                chat_id,
                message_id,
                reply_markup=back_button()
            )
        else:
            bot.answer_callback_query(call.id, f"❌ Не хватает GC! Нужно 100", show_alert=True)
        return
    
    if call.data == "buy_diamond_shield":
        user = get_user(user_id)
        if user["gc"] >= 400:
            update_user(user_id, gc=user["gc"] - 400, diamond_shield=user["diamond_shield"] + 1)
            bot.answer_callback_query(call.id, "✅ Куплен алмазный щит!", show_alert=True)
            bot.edit_message_text(
                f"💎 Алмазный щит куплен!\n💰 Осталось: {user['gc'] - 400} GC\nАлмазных щитов: {user['diamond_shield'] + 1}",
                chat_id,
                message_id,
                reply_markup=back_button()
            )
        else:
            bot.answer_callback_query(call.id, f"❌ Не хватает GC! Нужно 400", show_alert=True)
        return
    
    if call.data == "buy_reincarnation":
        user = get_user(user_id)
        if user["gc"] >= 300:
            update_user(user_id, gc=user["gc"] - 300)
            bot.answer_callback_query(call.id, "✅ Куплена реинкарнация!", show_alert=True)
            bot.edit_message_text(
                f"🔄 Реинкарнация куплена!\n💰 Осталось: {user['gc'] - 300} GC",
                chat_id,
                message_id,
                reply_markup=back_button()
            )
        else:
            bot.answer_callback_query(call.id, f"❌ Не хватает GC! Нужно 300", show_alert=True)
        return
    
    if call.data == "buy_double":
        user = get_user(user_id)
        if user["gc"] >= 150:
            update_user(user_id, gc=user["gc"] - 150, double_chance=user["double_chance"] + 1)
            bot.answer_callback_query(call.id, "✅ Куплен двойной шанс!", show_alert=True)
            bot.edit_message_text(
                f"⚡ Двойной шанс куплен!\n💰 Осталось: {user['gc'] - 150} GC\nДвойных шансов: {user['double_chance'] + 1}",
                chat_id,
                message_id,
                reply_markup=back_button()
            )
        else:
            bot.answer_callback_query(call.id, f"❌ Не хватает GC! Нужно 150", show_alert=True)
        return
    
    if call.data == "buy_accurate":
        user = get_user(user_id)
        if user["gc"] >= 120:
            update_user(user_id, gc=user["gc"] - 120)
            bot.answer_callback_query(call.id, "✅ Куплен точный выстрел!", show_alert=True)
            bot.edit_message_text(
                f"🔫 Точный выстрел куплен!\n💰 Осталось: {user['gc'] - 120} GC",
                chat_id,
                message_id,
                reply_markup=back_button()
            )
        else:
            bot.answer_callback_query(call.id, f"❌ Не хватает GC! Нужно 120", show_alert=True)
        return
    
    if call.data == "buy_master":
        user = get_user(user_id)
        if user["gc"] >= 250 and user["master"] == 0:
            update_user(user_id, gc=user["gc"] - 250, master=1)
            bot.answer_callback_query(call.id, "✅ Куплен мастер!", show_alert=True)
            bot.edit_message_text(
                f"🎯 Мастер куплен! +5% к удаче навсегда.\n💰 Осталось: {user['gc'] - 250} GC",
                chat_id,
                message_id,
                reply_markup=back_button()
            )
        elif user["master"] == 1:
            bot.answer_callback_query(call.id, "❌ У тебя уже есть мастер!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"❌ Не хватает GC! Нужно 250", show_alert=True)
        return
    
    if call.data == "buy_insurance":
        user = get_user(user_id)
        if user["gc"] >= 200:
            update_user(user_id, gc=user["gc"] - 200, insurance=user["insurance"] + 1)
            bot.answer_callback_query(call.id, "✅ Куплена страховка!", show_alert=True)
            bot.edit_message_text(
                f"💰 Страховка куплена!\n💰 Осталось: {user['gc'] - 200} GC\nСтраховок: {user['insurance'] + 1}",
                chat_id,
                message_id,
                reply_markup=back_button()
            )
        else:
            bot.answer_callback_query(call.id, f"❌ Не хватает GC! Нужно 200", show_alert=True)
        return
    
    if call.data == "buy_medkit":
        user = get_user(user_id)
        if user["gc"] >= 80:
            update_user(user_id, gc=user["gc"] - 80)
            add_gc(user_id, 50)
            bot.answer_callback_query(call.id, "✅ Куплена аптечка!", show_alert=True)
            bot.edit_message_text(
                f"💊 Аптечка использована! +50 GC\n💰 Новый баланс: {user['gc'] - 80 + 50} GC",
                chat_id,
                message_id,
                reply_markup=back_button()
            )
        else:
            bot.answer_callback_query(call.id, f"❌ Не хватает GC! Нужно 80", show_alert=True)
        return
    
    if call.data == "buy_lucky":
        user = get_user(user_id)
        if user["gc"] >= 90:
            update_user(user_id, gc=user["gc"] - 90)
            prize = random.choice([20, 30, 50, 80, 100, 150, 200, "shield", "double", "insurance"])
            if prize == "shield":
                update_user(user_id, shields=user["shields"] + 1)
                msg = "🛡️ Щит!"
            elif prize == "double":
                update_user(user_id, double_chance=user["double_chance"] + 1)
                msg = "⚡ Двойной шанс!"
            elif prize == "insurance":
                update_user(user_id, insurance=user["insurance"] + 1)
                msg = "💰 Страховка!"
            else:
                add_gc(user_id, prize)
                msg = f"{prize} GC"
            bot.answer_callback_query(call.id, f"✅ Счастливый билет! {msg}", show_alert=True)
            bot.edit_message_text(
                f"🎲 Счастливый билет!\n\nВыпало: {msg}",
                chat_id,
                message_id,
                reply_markup=back_button()
            )
        else:
            bot.answer_callback_query(call.id, f"❌ Не хватает GC! Нужно 90", show_alert=True)
        return
    
    if call.data == "buy_vip_3":
        user = get_user(user_id)
        if user["gc"] >= 500:
            update_user(user_id, gc=user["gc"] - 500, vip_level=3, vip_until=(datetime.now() + timedelta(days=3)).isoformat())
            bot.answer_callback_query(call.id, "✅ Куплен VIP на 3 дня!", show_alert=True)
            bot.edit_message_text(
                f"👑 VIP на 3 дня активирован!\n💰 Осталось: {user['gc'] - 500} GC",
                chat_id,
                message_id,
                reply_markup=back_button()
            )
        else:
            bot.answer_callback_query(call.id, f"❌ Не хватает GC! Нужно 500", show_alert=True)
        return
    
    if call.data == "buy_vip_7":
        user = get_user(user_id)
        if user["gc"] >= 1200:
            update_user(user_id, gc=user["gc"] - 1200, vip_level=7, vip_until=(datetime.now() + timedelta(days=7)).isoformat())
            bot.answer_callback_query(call.id, "✅ Куплен VIP на 7 дней!", show_alert=True)
            bot.edit_message_text(
                f"👑 VIP на 7 дней активирован!\n💰 Осталось: {user['gc'] - 1200} GC",
                chat_id,
                message_id,
                reply_markup=back_button()
            )
        else:
            bot.answer_callback_query(call.id, f"❌ Не хватает GC! Нужно 1200", show_alert=True)
        return
    
    if call.data == "buy_vip_30":
        user = get_user(user_id)
        if user["gc"] >= 3000:
            update_user(user_id, gc=user["gc"] - 3000, vip_level=30, vip_until=(datetime.now() + timedelta(days=30)).isoformat())
            bot.answer_callback_query(call.id, "✅ Куплен VIP на 30 дней!", show_alert=True)
            bot.edit_message_text(
                f"👑 VIP на 30 дней активирован!\n💰 Осталось: {user['gc'] - 3000} GC",
                chat_id,
                message_id,
                reply_markup=back_button()
            )
        else:
            bot.answer_callback_query(call.id, f"❌ Не хватает GC! Нужно 3000", show_alert=True)
        return
    
    # Топы
    if call.data == "top_menu":
        bot.edit_message_text(
            "<b>🏆 ТОПЫ</b>\n\nВыбери категорию:",
            chat_id,
            message_id,
            reply_markup=top_menu_kb()
        )
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "top_rating":
        top = get_top_players("rating", 10)
        text = "<b>🏆 ТОП ПО РЕЙТИНГУ</b>\n\n"
        for i, (uid, rating, wins) in enumerate(top, 1):
            text += f"{i}. {get_user_link(uid)} — {rating} рейтинга, {wins} побед\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_button(), parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "top_gc":
        top = get_top_players("gc", 10)
        text = "<b>💰 ТОП ПО GUNCOIN</b>\n\n"
        for i, (uid, gc, wins) in enumerate(top, 1):
            text += f"{i}. {get_user_link(uid)} — {gc} GC, {wins} побед\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_button(), parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "top_wins":
        top = get_top_players("wins", 10)
        text = "<b>🎮 ТОП ПО ПОБЕДАМ</b>\n\n"
        for i, (uid, wins, rating) in enumerate(top, 1):
            text += f"{i}. {get_user_link(uid)} — {wins} побед, {rating} рейтинга\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_button(), parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return
    
    # Промокод меню
    if call.data == "promo_menu":
        bot.edit_message_text(
            "<b>🎫 ПРОМОКОДЫ</b>\n\nВведи промокод через команду /promo КОД\n\nИли нажми кнопку ниже:",
            chat_id,
            message_id,
            reply_markup=promo_menu_kb()
        )
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "enter_promo":
        msg = bot.send_message(user_id, "Введите промокод:")
        bot.register_next_step_handler(msg, lambda m: use_promo_and_respond(m, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    # АДМИН ПАНЕЛЬ
    if call.data == "admin_panel":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
            return
        bot.edit_message_text(
            "<b>👑 АДМИН ПАНЕЛЬ</b>\n\nВыбери раздел:",
            chat_id,
            message_id,
            reply_markup=admin_panel_kb()
        )
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_stats":
        if user_id != ADMIN_ID:
            return
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT SUM(total_games) FROM users")
        total_games = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM chat_settings WHERE name != ''")
        total_chats = c.fetchone()[0]
        conn.close()
        season = get_current_season()
        
        text = (
            f"<b>📊 ОБЩАЯ СТАТИСТИКА</b>\n\n"
            f"📱 Всего чатов: {total_chats}\n"
            f"👥 Всего игроков: {total_users}\n"
            f"🎮 Всего игр: {total_games}\n"
            f"📅 Текущий сезон: #{season['number'] if season else '?'}\n"
            f"📆 До конца сезона: {(datetime.fromisoformat(season['end_date']) - datetime.now()).days if season else '?'} дней"
        )
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_chats":
        if user_id != ADMIN_ID:
            return
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        c.execute("SELECT chat_id, name FROM chat_settings WHERE name != ''")
        chats = c.fetchall()
        conn.close()
        text = "<b>📋 СПИСОК ЧАТОВ</b>\n\n"
        for chat_id_db, name in chats[:20]:
            text += f"📌 {name or chat_id_db}\n   ID: {chat_id_db}\n\n"
        if len(chats) > 20:
            text += f"\n... и еще {len(chats) - 20} чатов"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_players":
        if user_id != ADMIN_ID:
            return
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        c.execute("SELECT user_id, gc, rating, wins, losses FROM users ORDER BY rating DESC LIMIT 20")
        players = c.fetchall()
        conn.close()
        text = "<b>👥 ТОП-20 ИГРОКОВ</b>\n\n"
        for i, (uid, gc, rating, wins, losses) in enumerate(players, 1):
            text += f"{i}. {get_name(uid)} — Рейтинг: {rating}, GC: {gc}, Побед: {wins}\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_promocodes":
        if user_id != ADMIN_ID:
            return
        bot.edit_message_text(
            "<b>🎫 УПРАВЛЕНИЕ ПРОМОКОДАМИ</b>\n\nВыбери действие:",
            chat_id,
            message_id,
            reply_markup=admin_promocodes_kb()
        )
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_create_promo":
        if user_id != ADMIN_ID:
            return
        msg = bot.send_message(user_id, "Введите промокод в формате: КОД ТИП КОЛИЧЕСТВО ЛИМИТ [ДНИ]\n\nТипы: gc, shield, double, insurance, diamond_shield, vip\n\nПример: WELCOME100 gc 100 50 30")
        bot.register_next_step_handler(msg, create_promo_callback, chat_id, message_id)
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_list_promos":
        if user_id != ADMIN_ID:
            return
        promos = get_all_promos()
        text = "<b>📋 СПИСОК ПРОМОКОДОВ</b>\n\n"
        for code, rtype, ramount, max_uses, used, expires in promos:
            status = "✅ активен"
            if expires and datetime.now() > datetime.fromisoformat(expires):
                status = "❌ истек"
            elif used >= max_uses:
                status = "⛔ использован"
            text += f"📌 {code} — {rtype} x{ramount}\n   Использовано: {used}/{max_uses} | {status}\n\n"
        if not promos:
            text += "Нет промокодов"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_broadcast":
        if user_id != ADMIN_ID:
            return
        msg = bot.send_message(user_id, "Введите текст для рассылки:")
        bot.register_next_step_handler(msg, broadcast_message)
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_games":
        if user_id != ADMIN_ID:
            return
        if not games:
            text = "Нет активных игр"
        else:
            text = "<b>🎮 АКТИВНЫЕ ИГРЫ</b>\n\n"
            for gid, game in games.items():
                chat_name = get_chat_name(gid)
                text += f"📌 {chat_name}\n   ID: {gid}\n   Игроков: {len(game['players'])}/{game['max_players']}\n   Статус: {game['status']}\n\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_season":
        if user_id != ADMIN_ID:
            return
        season = get_current_season()
        if season:
            text = (
                f"<b>📅 ИНФОРМАЦИЯ О СЕЗОНЕ</b>\n\n"
                f"Номер сезона: #{season['number']}\n"
                f"Начало: {season['start_date'][:10]}\n"
                f"Конец: {season['end_date'][:10]}\n"
                f"Осталось: {(datetime.fromisoformat(season['end_date']) - datetime.now()).days} дней\n\n"
                f"Топ-10 получит награды в конце сезона!"
            )
        else:
            text = "Нет активного сезона"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
        kb.add(InlineKeyboardButton("🏆 Награды сезона", callback_data="admin_season_rewards"))
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_season_rewards":
        if user_id != ADMIN_ID:
            return
        text = (
            "<b>🏆 НАГРАДЫ ЗА СЕЗОН</b>\n\n"
            "🥇 1 место: 5000 GC + Алмазный щит + VIP 30 дней\n"
            "🥈 2 место: 3500 GC + VIP 21 день + Щит\n"
            "🥉 3 место: 2500 GC + VIP 14 дней + Щит\n"
            "4-5 место: 1500 GC + VIP 7 дней\n"
            "6-10 место: 1000 GC + Страховка\n"
            "11-20 место: 500 GC\n"
            "21-50 место: 300 GC\n"
            "51-100 место: 150 GC\n"
            "Участники: 50 GC"
        )
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    # Настройки чата
    if call.data == "chat_settings":
        if not is_chat_creator(user_id, chat_id):
            bot.answer_callback_query(call.id, "❌ Только создатель чата может менять настройки!", show_alert=True)
            return
        settings = get_chat_settings(chat_id)
        text = (
            f"<b>⚙️ НАСТРОЙКИ ЧАТА</b>\n\n"
            f"📌 Название: {settings['name'] or get_chat_name(chat_id)}\n"
            f"👥 Макс игроков: {settings['max_players']}\n"
            f"💰 Мин ставка: {settings['min_bet']} GC\n"
            f"💎 Макс ставка: {settings['max_bet']} GC\n"
            f"🎮 Игры: {'✅ Вкл' if settings['game_enabled'] else '❌ Выкл'}\n"
            f"👑 Только админы: {'✅ Да' if settings['admin_only'] else '❌ Нет'}"
        )
        bot.edit_message_text(text, chat_id, message_id, reply_markup=chat_settings_kb(chat_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "set_max_players":
        if not is_chat_creator(user_id, chat_id):
            bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
            return
        msg = bot.send_message(user_id, "Введите максимальное количество игроков (от 2 до 15):")
        bot.register_next_step_handler(msg, set_max_players_callback, chat_id, chat_id, message_id)
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "set_min_bet":
        if not is_chat_creator(user_id, chat_id):
            bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
            return
        msg = bot.send_message(user_id, "Введите минимальную ставку (от 1 до 1000):")
        bot.register_next_step_handler(msg, set_min_bet_callback, chat_id, chat_id, message_id)
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "set_max_bet":
        if not is_chat_creator(user_id, chat_id):
            bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
            return
        msg = bot.send_message(user_id, "Введите максимальную ставку (от 10 до 10000):")
        bot.register_next_step_handler(msg, set_max_bet_callback, chat_id, chat_id, message_id)
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "toggle_game":
        if not is_chat_creator(user_id, chat_id):
            bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
            return
        settings = get_chat_settings(chat_id)
        new_state = 0 if settings['game_enabled'] else 1
        update_chat_settings(chat_id, game_enabled=new_state)
        bot.answer_callback_query(call.id, f"Игры {'включены' if new_state else 'выключены'}")
        settings = get_chat_settings(chat_id)
        text = (
            f"<b>⚙️ НАСТРОЙКИ ЧАТА</b>\n\n"
            f"📌 Название: {settings['name'] or get_chat_name(chat_id)}\n"
            f"👥 Макс игроков: {settings['max_players']}\n"
            f"💰 Мин ставка: {settings['min_bet']} GC\n"
            f"💎 Макс ставка: {settings['max_bet']} GC\n"
            f"🎮 Игры: {'✅ Вкл' if settings['game_enabled'] else '❌ Выкл'}\n"
            f"👑 Только админы: {'✅ Да' if settings['admin_only'] else '❌ Нет'}"
        )
        bot.edit_message_text(text, chat_id, message_id, reply_markup=chat_settings_kb(chat_id))
        return
    
    if call.data == "toggle_admin_only":
        if not is_chat_creator(user_id, chat_id):
            bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
            return
        settings = get_chat_settings(chat_id)
        new_state = 0 if settings['admin_only'] else 1
        update_chat_settings(chat_id, admin_only=new_state)
        bot.answer_callback_query(call.id, f"Игры {'только для админов' if new_state else 'для всех'}")
        settings = get_chat_settings(chat_id)
        text = (
            f"<b>⚙️ НАСТРОЙКИ ЧАТА</b>\n\n"
            f"📌 Название: {settings['name'] or get_chat_name(chat_id)}\n"
            f"👥 Макс игроков: {settings['max_players']}\n"
            f"💰 Мин ставка: {settings['min_bet']} GC\n"
            f"💎 Макс ставка: {settings['max_bet']} GC\n"
            f"🎮 Игры: {'✅ Вкл' if settings['game_enabled'] else '❌ Выкл'}\n"
            f"👑 Только админы: {'✅ Да' if settings['admin_only'] else '❌ Нет'}"
        )
        bot.edit_message_text(text, chat_id, message_id, reply_markup=chat_settings_kb(chat_id))
        return
    
    # СОЗДАТЬ ИГРУ
    if call.data == "create_game":
        settings = get_chat_settings(chat_id)
        
        if not settings['game_enabled']:
            bot.answer_callback_query(call.id, "❌ Игры отключены создателем чата!", show_alert=True)
            return
        
        if settings['admin_only'] and not is_chat_admin(user_id, chat_id):
            bot.answer_callback_query(call.id, "❌ Только админы могут создавать игры!", show_alert=True)
            return
        
        if chat_id in games and games[chat_id]["status"] in ["waiting", "playing"]:
            bot.answer_callback_query(call.id, "В этом чате уже есть активная игра!", show_alert=True)
            return
        
        sent_msg = bot.send_message(
            chat_id,
            f"🎮 <b>НОВАЯ ИГРА!</b>\n\n"
            f"{get_user_link(user_id)} создал лобби!\n"
            f"Макс игроков: {settings['max_players']}\n"
            f"Мин ставка: {settings['min_bet']} GC\n"
            f"Макс ставка: {settings['max_bet']} GC\n\n"
            f"⬇️ Нажми кнопку, чтобы присоединиться!",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("➕ Присоединиться", callback_data=f"join_{chat_id}")
            )
        )
        
        games[chat_id] = {
            "players": [user_id],
            "bets": {},
            "chambers": {},
            "status": "waiting",
            "current_player": None,
            "creator": user_id,
            "message_id": sent_msg.message_id,
            "max_players": settings['max_players'],
            "used_shields": {},
            "used_double": {},
            "used_insurance": {},
            "used_reincarnation": {}
        }
        
        bot.send_message(
            user_id,
            f"✅ Игра создана в чате {get_chat_name(chat_id)}!\n\nСделай ставку (выбери сумму GC):",
            reply_markup=bet_kb(chat_id)
        )
        
        bot.answer_callback_query(call.id, "Игра создана! Сделай ставку в ЛС.")
        return
    
    # ПРИСОЕДИНИТЬСЯ
    if call.data.startswith("join_"):
        game_chat_id = int(call.data.split("_")[1])
        
        if game_chat_id not in games or games[game_chat_id]["status"] != "waiting":
            bot.answer_callback_query(call.id, "Игра уже началась или удалена!", show_alert=True)
            return
        
        if user_id in games[game_chat_id]["players"]:
            bot.answer_callback_query(call.id, "Ты уже в игре!", show_alert=True)
            return
        
        if len(games[game_chat_id]["players"]) >= games[game_chat_id]["max_players"]:
            bot.answer_callback_query(call.id, "Лобби заполнено!", show_alert=True)
            return
        
        games[game_chat_id]["players"].append(user_id)
        update_lobby_message(game_chat_id)
        
        bot.send_message(
            user_id,
            f"🎮 Ты присоединился к игре в чате {get_chat_name(game_chat_id)}!\n\nСделай ставку (выбери сумму GC):",
            reply_markup=bet_kb(game_chat_id)
        )
        
        bot.answer_callback_query(call.id, "Ты присоединился! Сделай ставку в ЛС.")
        return
    
    # ОТМЕНИТЬ ИГРУ
    if call.data.startswith("cancel_game_"):
        game_chat_id = int(call.data.split("_")[2])
        
        if game_chat_id not in games:
            bot.answer_callback_query(call.id, "Игра не найдена!", show_alert=True)
            return
        
        if games[game_chat_id]["creator"] != user_id and not is_chat_admin(user_id, game_chat_id):
            bot.answer_callback_query(call.id, "Только создатель может отменить игру!", show_alert=True)
            return
        
        del games[game_chat_id]
        bot.send_message(game_chat_id, "❌ Игра отменена")
        bot.answer_callback_query(call.id, "Игра отменена")
        return
    
    # СТАВКА
    if call.data.startswith("place_bet_"):
        parts = call.data.split("_")
        game_chat_id = int(parts[2])
        bet = int(parts[3])
        
        if game_chat_id not in games:
            bot.answer_callback_query(call.id, "Игра удалена!", show_alert=True)
            return
        
        if games[game_chat_id]["status"] != "waiting":
            bot.answer_callback_query(call.id, "Игра уже началась!", show_alert=True)
            return
        
        if user_id not in games[game_chat_id]["players"]:
            bot.answer_callback_query(call.id, "Ты не в игре!", show_alert=True)
            return
        
        if user_id in games[game_chat_id]["bets"]:
            bot.answer_callback_query(call.id, "Ты уже сделал ставку!", show_alert=True)
            return
        
        user = get_user(user_id)
        
        if user["gc"] < bet:
            bot.answer_callback_query(call.id, f"Не хватает GC! Нужно {bet}", show_alert=True)
            return
        
        games[game_chat_id]["bets"][user_id] = bet
        update_user(user_id, gc=user["gc"] - bet)
        
        bot.send_message(user_id, f"✅ Ставка {bet} GC принята!\nОжидай начала игры...")
        bot.answer_callback_query(call.id, f"Ставка {bet} GC принята!")
        
        update_lobby_message(game_chat_id)
        return
    
    # НАЧАТЬ ИГРУ
    if call.data.startswith("start_game_"):
        game_chat_id = int(call.data.split("_")[2])
        
        if game_chat_id not in games:
            bot.answer_callback_query(call.id, "Игра не найдена!", show_alert=True)
            return
        
        game = games[game_chat_id]
        
        if user_id != game["creator"]:
            bot.answer_callback_query(call.id, "Только создатель может начать игру!", show_alert=True)
            return
        
        if len(game["players"]) < 2:
            bot.answer_callback_query(call.id, "Нужно минимум 2 игрока!", show_alert=True)
            return
        
        for p in game["players"]:
            if p not in game["bets"]:
                bot.answer_callback_query(call.id, "Не все игроки сделали ставки!", show_alert=True)
                return
        
        game["status"] = "playing"
        players_list = game["players"].copy()
        random.shuffle(players_list)
        game["players"] = players_list
        game["current_player"] = players_list[0]
        
        for p in players_list:
            game["chambers"][p] = random.randint(1, 6)
        
        total_pot = sum(game["bets"].values())
        
        players_names = "\n".join([f"• {get_user_link(p)} — {game['bets'][p]} GC" for p in players_list])
        
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        c.execute("UPDATE chat_stats SET total_games = total_games + 1, total_bets = total_bets + ? WHERE chat_id = ?", (total_pot, game_chat_id))
        if c.rowcount == 0:
            c.execute("INSERT INTO chat_stats (chat_id, total_games, total_bets) VALUES (?, 1, ?)", (game_chat_id, total_pot))
        conn.commit()
        conn.close()
        
        for p in players_list:
            user = get_user(p)
            update_user(p, total_games=user["total_games"] + 1)
        
        bot.edit_message_text(
            f"🎲 <b>ИГРА НАЧАЛАСЬ!</b>\n\n"
            f"Участники:\n{players_names}\n\n"
            f"💰 Общий банк: {total_pot} GC\n"
            f"🔫 Первый ход: {get_user_link(game['current_player'])}\n\n"
            f"Игроки, проверьте личные сообщения!",
            game_chat_id,
            game["message_id"]
        )
        
        current = game["current_player"]
        current_bet = game["bets"][current]
        
        bot.send_message(
            current,
            f"🔫 <b>ТВОЙ ХОД!</b>\n\n"
            f"Ставка: {current_bet} GC\n\n"
            f"Выбери действие:",
            reply_markup=game_action_kb(game_chat_id, current, current_bet)
        )
        
        bot.answer_callback_query(call.id, "Игра начата!")
        return
    
    # КРУТИТЬ БАРАБАН
    if call.data.startswith("spin_"):
        parts = call.data.split("_")
        game_chat_id = int(parts[1])
        player_id = int(parts[2])
        bet = int(parts[3])
        
        if game_chat_id not in games or games[game_chat_id]["status"] != "playing":
            bot.answer_callback_query(call.id, "Игра не активна!", show_alert=True)
            return
        
        game = games[game_chat_id]
        
        if game["current_player"] != player_id:
            bot.answer_callback_query(call.id, "Сейчас не твой ход!", show_alert=True)
            return
        
        game["chambers"][player_id] = random.randint(1, 6)
        
        bot.send_message(
            player_id,
            f"🔄 Барабан прокручен!\n\nСтавка: {bet} GC\n\nГотов выстрелить?",
            reply_markup=game_action_kb(game_chat_id, player_id, bet)
        )
        
        bot.answer_callback_query(call.id, "Барабан прокручен!")
        return
    
    # ВЫСТРЕЛИТЬ
    if call.data.startswith("shoot_"):
        parts = call.data.split("_")
        game_chat_id = int(parts[1])
        player_id = int(parts[2])
        bet = int(parts[3])
        
        if game_chat_id not in games or games[game_chat_id]["status"] != "playing":
            bot.answer_callback_query(call.id, "Игра не активна!", show_alert=True)
            return
        
        game = games[game_chat_id]
        
        if game["current_player"] != player_id:
            bot.answer_callback_query(call.id, "Сейчас не твой ход!", show_alert=True)
            return
        
        chamber = game["chambers"][player_id]
        trigger = random.randint(1, 6)
        
        user = get_user(player_id)
        
        # Мастер (+5% к удаче)
        if user["master"] == 1:
            trigger = random.randint(1, 5)
            bot.send_message(player_id, "🎯 МАСТЕР АКТИВИРОВАН! +5% к удаче")
        
        # Двойной шанс
        if user["double_chance"] > 0 and game["used_double"].get(player_id, 0) == 0:
            trigger = random.randint(1, 5)
            game["used_double"][player_id] = 1
            update_user(player_id, double_chance=user["double_chance"] - 1)
            bot.send_message(player_id, "⚡ ДВОЙНОЙ ШАНС АКТИВИРОВАН!")
        
        is_dead = (trigger == chamber)
        
        # Щит
        if is_dead:
            if user["shields"] > 0 and game["used_shields"].get(player_id, 0) == 0:
                is_dead = False
                game["used_shields"][player_id] = 1
                update_user(player_id, shields=user["shields"] - 1)
                bot.send_message(player_id, "🛡️ ЩИТ АКТИВИРОВАН! Ты выжил!")
        
        # Алмазный щит
        if is_dead:
            if user["diamond_shield"] > 0:
                is_dead = False
                update_user(player_id, diamond_shield=user["diamond_shield"] - 1)
                bot.send_message(player_id, "💎 АЛМАЗНЫЙ ЩИТ АКТИВИРОВАН! Ты выжил!")
        
        if is_dead:
            refund = 0
            if user["insurance"] > 0 and game["used_insurance"].get(player_id, 0) == 0:
                refund = bet // 2
                game["used_insurance"][player_id] = 1
                update_user(player_id, insurance=user["insurance"] - 1)
                bot.send_message(player_id, f"💰 СТРАХОВКА! Возвращено: {refund} GC")
            
            game["players"].remove(player_id)
            update_user(player_id, losses=user["losses"] + 1, gc=user["gc"] + refund)
            update_rating(player_id, False, bet, 0)
            
            if len(game["players"]) == 1:
                winner_id = game["players"][0]
                total_pot = sum(game["bets"].values())
                
                winner = get_user(winner_id)
                vip_mult = get_vip_multiplier(winner_id)
                win_amount = int(total_pot * vip_mult)
                update_user(winner_id, gc=winner["gc"] + win_amount, wins=winner["wins"] + 1)
                update_rating(winner_id, True, bet, win_amount)
                add_gc(winner_id, 5)
                
                bot.edit_message_text(
                    f"💀 <b>{get_user_link(player_id)} ВЫБЫЛ!</b>\n\n"
                    f"🏆 <b>ПОБЕДИТЕЛЬ: {get_user_link(winner_id)}</b>\n"
                    f"💰 Выигрыш: {win_amount} GC",
                    game_chat_id,
                    game["message_id"]
                )
                
                bot.send_message(winner_id, f"🏆 Ты победил! Выигрыш: {win_amount} GC")
                del games[game_chat_id]
                bot.answer_callback_query(call.id, "Ты выбыл!")
                return
            
            game["current_player"] = game["players"][0]
            current = game["current_player"]
            current_bet = game["bets"][current]
            
            players_list = "\n".join([f"• {get_user_link(p)}" for p in game["players"]])
            total_pot = sum(game["bets"].values())
            
            bot.edit_message_text(
                f"💀 <b>{get_user_link(player_id)} ВЫБЫЛ!</b>\n\n"
                f"Остались:\n{players_list}\n\n"
                f"💰 Банк: {total_pot} GC\n"
                f"🔫 Ход: {get_user_link(current)}",
                game_chat_id,
                game["message_id"]
            )
            
            bot.send_message(
                current,
                f"🔫 <b>ТВОЙ ХОД!</b>\n\n"
                f"Ставка: {current_bet} GC\n\n"
                f"Выбери действие:",
                reply_markup=game_action_kb(game_chat_id, current, current_bet)
            )
            
            bot.answer_callback_query(call.id, "Ты выбыл!")
            
        else:
            current_index = game["players"].index(player_id)
            next_index = (current_index + 1) % len(game["players"])
            game["current_player"] = game["players"][next_index]
            current = game["current_player"]
            current_bet = game["bets"][current]
            
            total_pot = sum(game["bets"].values())
            
            bot.edit_message_text(
                f"🍀 <b>{get_user_link(player_id)} ВЫЖИЛ!</b>\n\n"
                f"💰 Банк: {total_pot} GC\n"
                f"🔫 Ход: {get_user_link(current)}",
                game_chat_id,
                game["message_id"]
            )
            
            bot.send_message(
                current,
                f"🔫 <b>ТВОЙ ХОД!</b>\n\n"
                f"Ставка: {current_bet} GC\n\n"
                f"Выбери действие:",
                reply_markup=game_action_kb(game_chat_id, current, current_bet)
            )
            
            bot.answer_callback_query(call.id, "Пусто! Ты выжил.")
        
        return

# ========== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ==========
def use_promo_and_respond(message, original_chat_id, original_message_id):
    success, msg = use_promo(message.from_user.id, message.text.upper())
    bot.send_message(message.chat.id, msg)
    bot.edit_message_reply_markup(original_chat_id, original_message_id, reply_markup=promo_menu_kb())

def create_promo_callback(message, original_chat_id, original_message_id):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        code = parts[0].upper()
        reward_type = parts[1].lower()
        reward_amount = int(parts[2])
        max_uses = int(parts[3])
        expires_days = int(parts[4]) if len(parts) > 4 else None
        
        create_promo(code, reward_type, reward_amount, max_uses, expires_days)
        bot.send_message(message.chat.id, f"✅ Промокод {code} создан!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}\nФормат: КОД ТИП КОЛИЧЕСТВО ЛИМИТ [ДНИ]")
    bot.edit_message_reply_markup(original_chat_id, original_message_id, reply_markup=admin_promocodes_kb())

def broadcast_message(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    text = message.text
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT chat_id FROM chat_settings WHERE name != ''")
    chats = c.fetchall()
    conn.close()
    success = 0
    fail = 0
    
    for chat_id_db, in chats:
        try:
            bot.send_message(chat_id_db, f"📢 <b>РАССЫЛКА ОТ АДМИНА</b>\n\n{text}")
            success += 1
        except:
            fail += 1
    
    bot.send_message(ADMIN_ID, f"✅ Рассылка завершена!\nУспешно: {success}\n❌ Ошибок: {fail}")

def set_max_players_callback(message, original_chat_id, target_chat_id, original_message_id):
    try:
        val = int(message.text)
        if 2 <= val <= MAX_PLAYERS_LIMIT:
            update_chat_settings(target_chat_id, max_players=val)
            bot.send_message(message.chat.id, f"✅ Максимум игроков установлен: {val}")
            settings = get_chat_settings(target_chat_id)
            text = (
                f"<b>⚙️ НАСТРОЙКИ ЧАТА</b>\n\n"
                f"📌 Название: {settings['name'] or get_chat_name(target_chat_id)}\n"
                f"👥 Макс игроков: {settings['max_players']}\n"
                f"💰 Мин ставка: {settings['min_bet']} GC\n"
                f"💎 Макс ставка: {settings['max_bet']} GC\n"
                f"🎮 Игры: {'✅ Вкл' if settings['game_enabled'] else '❌ Выкл'}\n"
                f"👑 Только админы: {'✅ Да' if settings['admin_only'] else '❌ Нет'}"
            )
            bot.edit_message_text(text, original_chat_id, original_message_id, reply_markup=chat_settings_kb(target_chat_id))
        else:
            bot.send_message(message.chat.id, f"❌ Введите число от 2 до {MAX_PLAYERS_LIMIT}")
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")

def set_min_bet_callback(message, original_chat_id, target_chat_id, original_message_id):
    try:
        val = int(message.text)
        if 1 <= val <= 1000:
            update_chat_settings(target_chat_id, min_bet=val)
            bot.send_message(message.chat.id, f"✅ Минимальная ставка: {val} GC")
            settings = get_chat_settings(target_chat_id)
            text = (
                f"<b>⚙️ НАСТРОЙКИ ЧАТА</b>\n\n"
                f"📌 Название: {settings['name'] or get_chat_name(target_chat_id)}\n"
                f"👥 Макс игроков: {settings['max_players']}\n"
                f"💰 Мин ставка: {settings['min_bet']} GC\n"
                f"💎 Макс ставка: {settings['max_bet']} GC\n"
                f"🎮 Игры: {'✅ Вкл' if settings['game_enabled'] else '❌ Выкл'}\n"
                f"👑 Только админы: {'✅ Да' if settings['admin_only'] else '❌ Нет'}"
            )
            bot.edit_message_text(text, original_chat_id, original_message_id, reply_markup=chat_settings_kb(target_chat_id))
        else:
            bot.send_message(message.chat.id, "❌ Введите число от 1 до 1000")
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")

def set_max_bet_callback(message, original_chat_id, target_chat_id, original_message_id):
    try:
        val = int(message.text)
        if 10 <= val <= 10000:
            update_chat_settings(target_chat_id, max_bet=val)
            bot.send_message(message.chat.id, f"✅ Максимальная ставка: {val} GC")
            settings = get_chat_settings(target_chat_id)
            text = (
                f"<b>⚙️ НАСТРОЙКИ ЧАТА</b>\n\n"
                f"📌 Название: {settings['name'] or get_chat_name(target_chat_id)}\n"
                f"👥 Макс игроков: {settings['max_players']}\n"
                f"💰 Мин ставка: {settings['min_bet']} GC\n"
                f"💎 Макс ставка: {settings['max_bet']} GC\n"
                f"🎮 Игры: {'✅ Вкл' if settings['game_enabled'] else '❌ Выкл'}\n"
                f"👑 Только админы: {'✅ Да' if settings['admin_only'] else '❌ Нет'}"
            )
            bot.edit_message_text(text, original_chat_id, original_message_id, reply_markup=chat_settings_kb(target_chat_id))
        else:
            bot.send_message(message.chat.id, "❌ Введите число от 10 до 10000")
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    init_db()
    print("✅ Бот запущен!")
    print(f"📱 Username: @{BOT_USERNAME}")
    print(f"👑 Admin ID: {ADMIN_ID}")
    bot.infinity_polling()