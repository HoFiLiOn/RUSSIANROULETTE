import telebot
import sqlite3
import random
import time
import threading
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ========== КОНФИГ ==========
BOT_TOKEN = "8412567351:AAG7eEMXlNfDBsNZF08GD-Pr-LH-2z1txSQ"
BOT_USERNAME = "RussianRoulette_official_bot"
ADMIN_ID = 7040677455
MAX_PLAYERS_LIMIT = 15

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ========== КД ТОЛЬКО ДЛЯ ИГРОВЫХ ДЕЙСТВИЙ ==========
game_cooldowns = {}  # user_id -> время последнего действия

def check_game_cooldown(user_id):
    """Проверяет КД для игровых действий (5 секунд)"""
    now = time.time()
    if user_id in game_cooldowns:
        if now - game_cooldowns[user_id] < 5:
            return False
    game_cooldowns[user_id] = now
    return True

# ========== БД ==========
def init_db():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  gc INTEGER DEFAULT 100,
                  rating INTEGER DEFAULT 0,
                  wins INTEGER DEFAULT 0,
                  losses INTEGER DEFAULT 0,
                  total_games INTEGER DEFAULT 0,
                  shields INTEGER DEFAULT 0,
                  double_chance INTEGER DEFAULT 0,
                  insurance INTEGER DEFAULT 0,
                  diamond_shield INTEGER DEFAULT 0,
                  master INTEGER DEFAULT 0,
                  vip_level INTEGER DEFAULT 0,
                  vip_until TEXT,
                  last_daily TEXT,
                  daily_streak INTEGER DEFAULT 1,
                  last_monthly_bonus TEXT,
                  banned INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS chat_settings
                 (chat_id INTEGER PRIMARY KEY,
                  max_players INTEGER DEFAULT 6,
                  min_bet INTEGER DEFAULT 10,
                  max_bet INTEGER DEFAULT 500,
                  game_enabled INTEGER DEFAULT 1,
                  admin_only INTEGER DEFAULT 0,
                  owner_id INTEGER DEFAULT 0,
                  name TEXT DEFAULT '',
                  bet_buttons TEXT DEFAULT '10,50,100,200,500,1000',
                  welcome_message TEXT DEFAULT '',
                  winner_bonus INTEGER DEFAULT 0,
                  auto_kick_minutes INTEGER DEFAULT 0,
                  banned INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS chat_stats
                 (chat_id INTEGER PRIMARY KEY,
                  total_games INTEGER DEFAULT 0,
                  total_bets INTEGER DEFAULT 0,
                  season_games INTEGER DEFAULT 0,
                  season_bets INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS chat_players
                 (chat_id INTEGER,
                  user_id INTEGER,
                  wins INTEGER DEFAULT 0,
                  games INTEGER DEFAULT 0,
                  season_wins INTEGER DEFAULT 0,
                  season_games INTEGER DEFAULT 0,
                  PRIMARY KEY (chat_id, user_id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS seasons
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  number INTEGER DEFAULT 1,
                  start_date TEXT,
                  end_date TEXT,
                  is_active INTEGER DEFAULT 1)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS rank_settings
                 (rank_name TEXT PRIMARY KEY,
                  min_rating INTEGER,
                  max_rating INTEGER,
                  reward_gc INTEGER,
                  reward_shield INTEGER DEFAULT 0,
                  reward_double INTEGER DEFAULT 0,
                  reward_insurance INTEGER DEFAULT 0,
                  reward_diamond INTEGER DEFAULT 0,
                  reward_vip_days INTEGER DEFAULT 0,
                  bet_bonus INTEGER DEFAULT 0,
                  monthly_gc INTEGER DEFAULT 0,
                  monthly_shield INTEGER DEFAULT 0,
                  monthly_double INTEGER DEFAULT 0,
                  monthly_insurance INTEGER DEFAULT 0,
                  monthly_diamond INTEGER DEFAULT 0,
                  monthly_vip_days INTEGER DEFAULT 0,
                  win_points INTEGER DEFAULT 25,
                  loss_points INTEGER DEFAULT 15)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS promocodes
                 (code TEXT PRIMARY KEY,
                  reward_type TEXT,
                  reward_amount INTEGER,
                  max_uses INTEGER,
                  used_count INTEGER DEFAULT 0,
                  expires TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS promo_used
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  code TEXT,
                  user_id INTEGER,
                  used_at TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS admin_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  admin_id INTEGER,
                  action TEXT,
                  target TEXT,
                  details TEXT,
                  timestamp TEXT)''')
    
    c.execute("SELECT * FROM seasons WHERE is_active = 1")
    if not c.fetchone():
        now = datetime.now()
        end = now + timedelta(days=30)
        c.execute("INSERT INTO seasons (number, start_date, end_date) VALUES (1, ?, ?)",
                  (now.isoformat(), end.isoformat()))
    
    c.execute("SELECT COUNT(*) FROM rank_settings")
    if c.fetchone()[0] == 0:
        default_ranks = [
            ("Новичок", 0, 499, 100, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 25, 15),
            ("Стрелок", 500, 999, 500, 1, 0, 0, 0, 0, 50, 100, 0, 0, 0, 0, 0, 25, 15),
            ("Опытный", 1000, 1499, 1000, 0, 1, 0, 0, 0, 100, 250, 0, 0, 0, 0, 0, 25, 15),
            ("Мастер", 1500, 1999, 2000, 0, 0, 1, 0, 0, 200, 500, 1, 0, 0, 0, 0, 25, 15),
            ("Элита", 2000, 2499, 4000, 0, 0, 0, 1, 0, 500, 1000, 0, 1, 0, 0, 0, 25, 15),
            ("Легенда", 2500, 999999, 8000, 0, 0, 0, 1, 14, 1000, 2000, 0, 0, 1, 3, 0, 25, 15)
        ]
        for rank in default_ranks:
            c.execute("""INSERT INTO rank_settings 
                         (rank_name, min_rating, max_rating, reward_gc, reward_shield, reward_double, 
                          reward_insurance, reward_diamond, reward_vip_days, bet_bonus, monthly_gc, 
                          monthly_shield, monthly_double, monthly_insurance, monthly_diamond, monthly_vip_days,
                          win_points, loss_points)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", rank)
    
    conn.commit()
    conn.close()

def log_admin(admin_id, action, target, details=""):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("INSERT INTO admin_logs (admin_id, action, target, details, timestamp) VALUES (?, ?, ?, ?, ?)",
              (admin_id, action, target, details, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT gc, rating, wins, losses, total_games, shields, double_chance, insurance, diamond_shield, master, vip_level, vip_until, last_daily, daily_streak, last_monthly_bonus, banned FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (user_id, gc, last_daily) VALUES (?, ?, ?)",
                  (user_id, 100, datetime.now().isoformat()))
        conn.commit()
        c.execute("SELECT gc, rating, wins, losses, total_games, shields, double_chance, insurance, diamond_shield, master, vip_level, vip_until, last_daily, daily_streak, last_monthly_bonus, banned FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
    conn.close()
    return {
        "gc": user[0], "rating": user[1], "wins": user[2], "losses": user[3],
        "total_games": user[4], "shields": user[5], "double_chance": user[6],
        "insurance": user[7], "diamond_shield": user[8], "master": user[9],
        "vip_level": user[10], "vip_until": user[11], "last_daily": user[12],
        "daily_streak": user[13], "last_monthly_bonus": user[14], "banned": user[15]
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

def remove_gc(user_id, amount):
    user = get_user(user_id)
    new_gc = max(0, user["gc"] - amount)
    update_user(user_id, gc=new_gc)
    return new_gc

def get_rank_settings(rating):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT rank_name, reward_gc, reward_shield, reward_double, reward_insurance, reward_diamond, reward_vip_days, bet_bonus FROM rank_settings WHERE min_rating <= ? AND max_rating >= ?", (rating, rating))
    rank = c.fetchone()
    conn.close()
    if rank:
        return {"name": rank[0], "reward_gc": rank[1], "reward_shield": rank[2], 
                "reward_double": rank[3], "reward_insurance": rank[4], 
                "reward_diamond": rank[5], "reward_vip_days": rank[6], "bet_bonus": rank[7]}
    return {"name": "Новичок", "reward_gc": 0, "reward_shield": 0, "reward_double": 0, 
            "reward_insurance": 0, "reward_diamond": 0, "reward_vip_days": 0, "bet_bonus": 0}

def get_monthly_bonus(rating):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT monthly_gc, monthly_shield, monthly_double, monthly_insurance, monthly_diamond, monthly_vip_days FROM rank_settings WHERE min_rating <= ? AND max_rating >= ?", (rating, rating))
    bonus = c.fetchone()
    conn.close()
    if bonus:
        return {"gc": bonus[0], "shield": bonus[1], "double": bonus[2], 
                "insurance": bonus[3], "diamond": bonus[4], "vip_days": bonus[5]}
    return {"gc": 0, "shield": 0, "double": 0, "insurance": 0, "diamond": 0, "vip_days": 0}

def get_rank_name(rating):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT rank_name FROM rank_settings WHERE min_rating <= ? AND max_rating >= ?", (rating, rating))
    rank = c.fetchone()
    conn.close()
    return rank[0] if rank else "Новичок"

def get_rank_emoji(rating):
    if rating >= 2500:
        return "👑"
    elif rating >= 2000:
        return "🔴"
    elif rating >= 1500:
        return "🟠"
    elif rating >= 1000:
        return "🟣"
    elif rating >= 500:
        return "🔵"
    else:
        return "🟢"

def check_monthly_bonus(user_id):
    user = get_user(user_id)
    now = datetime.now()
    
    if user["last_monthly_bonus"]:
        last = datetime.fromisoformat(user["last_monthly_bonus"])
        if now.month == last.month and now.year == last.year:
            return False
    
    bonus = get_monthly_bonus(user["rating"])
    if bonus["gc"] > 0:
        add_gc(user_id, bonus["gc"])
    
    if bonus["shield"] > 0:
        update_user(user_id, shields=user["shields"] + bonus["shield"])
    if bonus["double"] > 0:
        update_user(user_id, double_chance=user["double_chance"] + bonus["double"])
    if bonus["insurance"] > 0:
        update_user(user_id, insurance=user["insurance"] + bonus["insurance"])
    if bonus["diamond"] > 0:
        update_user(user_id, diamond_shield=user["diamond_shield"] + bonus["diamond"])
    if bonus["vip_days"] > 0:
        vip_until = datetime.now() + timedelta(days=bonus["vip_days"])
        update_user(user_id, vip_level=bonus["vip_days"], vip_until=vip_until.isoformat())
    
    update_user(user_id, last_monthly_bonus=now.isoformat())
    return True

def update_rating_and_rewards(user_id, won):
    user = get_user(user_id)
    if user["banned"]:
        return 0
    
    old_rating = user["rating"]
    
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT win_points, loss_points FROM rank_settings LIMIT 1")
    points = c.fetchone()
    conn.close()
    
    win_points = points[0] if points else 25
    loss_points = points[1] if points else 15
    
    change = win_points if won else -loss_points
    new_rating = max(0, old_rating + change)
    update_user(user_id, rating=new_rating)
    
    old_rank = get_rank_name(old_rating)
    new_rank = get_rank_name(new_rating)
    
    if old_rank != new_rank:
        rank = get_rank_settings(new_rating)
        if rank["reward_gc"] > 0:
            add_gc(user_id, rank["reward_gc"])
        if rank["reward_shield"] > 0:
            update_user(user_id, shields=user["shields"] + rank["reward_shield"])
        if rank["reward_double"] > 0:
            update_user(user_id, double_chance=user["double_chance"] + rank["reward_double"])
        if rank["reward_insurance"] > 0:
            update_user(user_id, insurance=user["insurance"] + rank["reward_insurance"])
        if rank["reward_diamond"] > 0:
            update_user(user_id, diamond_shield=user["diamond_shield"] + rank["reward_diamond"])
        if rank["reward_vip_days"] > 0:
            vip_until = datetime.now() + timedelta(days=rank["reward_vip_days"])
            update_user(user_id, vip_level=rank["reward_vip_days"], vip_until=vip_until.isoformat())
        
        try:
            bot.send_message(user_id, 
                f"🏆 ПОЗДРАВЛЯЮ! Ты достиг ранга {get_rank_emoji(new_rating)} {new_rank}!\n"
                f"+{rank['reward_gc']} GC\n"
                f"{'🛡️ Щит ' if rank['reward_shield'] else ''}"
                f"{'⚡ Двойной шанс ' if rank['reward_double'] else ''}"
                f"{'💰 Страховка ' if rank['reward_insurance'] else ''}"
                f"{'💎 Алмазный щит ' if rank['reward_diamond'] else ''}"
                f"{'👑 VIP ' + str(rank['reward_vip_days']) + ' дней' if rank['reward_vip_days'] else ''}")
        except:
            pass
    
    return change

def get_chat_settings(chat_id):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT max_players, min_bet, max_bet, game_enabled, admin_only, owner_id, name, bet_buttons, welcome_message, winner_bonus, auto_kick_minutes, banned FROM chat_settings WHERE chat_id = ?", (chat_id,))
    settings = c.fetchone()
    if not settings:
        c.execute("INSERT INTO chat_settings (chat_id) VALUES (?)", (chat_id,))
        conn.commit()
        settings = (6, 10, 500, 1, 0, 0, "", "10,50,100,200,500,1000", "", 0, 0, 0)
    conn.close()
    return {
        "max_players": settings[0], "min_bet": settings[1], "max_bet": settings[2],
        "game_enabled": settings[3], "admin_only": settings[4], "owner_id": settings[5],
        "name": settings[6], "bet_buttons": settings[7], "welcome_message": settings[8],
        "winner_bonus": settings[9], "auto_kick_minutes": settings[10], "banned": settings[11]
    }

def update_chat_settings(chat_id, **kwargs):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    for key, value in kwargs.items():
        c.execute(f"UPDATE chat_settings SET {key} = ? WHERE chat_id = ?", (value, chat_id))
    conn.commit()
    conn.close()

def get_chat_stats(chat_id):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT total_games, total_bets, season_games, season_bets FROM chat_stats WHERE chat_id = ?", (chat_id,))
    stats = c.fetchone()
    conn.close()
    if stats:
        return {"total_games": stats[0], "total_bets": stats[1], "season_games": stats[2], "season_bets": stats[3]}
    return {"total_games": 0, "total_bets": 0, "season_games": 0, "season_bets": 0}

def update_chat_stats(chat_id, bet_amount):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("UPDATE chat_stats SET total_games = total_games + 1, total_bets = total_bets + ?, season_games = season_games + 1, season_bets = season_bets + ? WHERE chat_id = ?", (bet_amount, bet_amount, chat_id))
    if c.rowcount == 0:
        c.execute("INSERT INTO chat_stats (chat_id, total_games, total_bets, season_games, season_bets) VALUES (?, 1, ?, 1, ?)", (chat_id, bet_amount, bet_amount))
    conn.commit()
    conn.close()

def get_chat_rating(chat_id):
    stats = get_chat_stats(chat_id)
    return (stats["total_games"] * 10) + (stats["total_bets"] // 10)

def get_all_chats_rating():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT chat_id, total_games, total_bets FROM chat_stats ORDER BY (total_games * 10 + total_bets / 10) DESC LIMIT 50")
    chats = c.fetchall()
    conn.close()
    return chats

def update_chat_player(chat_id, user_id, won):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    if won:
        c.execute("INSERT INTO chat_players (chat_id, user_id, wins, games, season_wins, season_games) VALUES (?, ?, 1, 1, 1, 1) ON CONFLICT(chat_id, user_id) DO UPDATE SET wins = wins + 1, games = games + 1, season_wins = season_wins + 1, season_games = season_games + 1", (chat_id, user_id))
    else:
        c.execute("INSERT INTO chat_players (chat_id, user_id, wins, games, season_wins, season_games) VALUES (?, ?, 0, 1, 0, 1) ON CONFLICT(chat_id, user_id) DO UPDATE SET games = games + 1, season_games = season_games + 1", (chat_id, user_id))
    conn.commit()
    conn.close()

def get_chat_top_players(chat_id, limit=10):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT user_id, wins, games FROM chat_players WHERE chat_id = ? ORDER BY wins DESC LIMIT ?", (chat_id, limit))
    players = c.fetchall()
    conn.close()
    return players

def get_all_users():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT user_id, gc, rating, wins, banned FROM users ORDER BY rating DESC LIMIT 50")
    users = c.fetchall()
    conn.close()
    return users

def get_top_players(category, limit=10):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    if category == "rating":
        c.execute("SELECT user_id, rating, wins FROM users WHERE banned = 0 ORDER BY rating DESC LIMIT ?", (limit,))
    elif category == "gc":
        c.execute("SELECT user_id, gc, wins FROM users WHERE banned = 0 ORDER BY gc DESC LIMIT ?", (limit,))
    elif category == "wins":
        c.execute("SELECT user_id, wins, rating FROM users WHERE banned = 0 ORDER BY wins DESC LIMIT ?", (limit,))
    else:
        return []
    return c.fetchall()

def get_total_stats():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE banned = 0")
    users = c.fetchone()[0]
    c.execute("SELECT SUM(total_games) FROM users")
    games = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM chat_settings WHERE name != '' AND banned = 0")
    chats = c.fetchone()[0]
    conn.close()
    return {"users": users, "games": games, "chats": chats}

def get_current_season():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT id, number, start_date, end_date FROM seasons WHERE is_active = 1")
    season = c.fetchone()
    conn.close()
    if season:
        return {"id": season[0], "number": season[1], "start_date": season[2], "end_date": season[3]}
    return None

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

def get_chat_name(chat_id):
    try:
        chat = bot.get_chat(chat_id)
        return chat.title or str(chat_id)
    except:
        return str(chat_id)

def is_chat_admin(user_id, chat_id):
    if user_id == ADMIN_ID:
        return True
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except:
        return False

def is_chat_owner(user_id, chat_id):
    settings = get_chat_settings(chat_id)
    if settings["owner_id"] == user_id:
        return True
    try:
        member = bot.get_chat_member(chat_id, user_id)
        if member.status == 'creator':
            update_chat_settings(chat_id, owner_id=user_id, name=member.user.first_name)
            return True
    except:
        pass
    return False

def get_chat_owner(chat_id):
    settings = get_chat_settings(chat_id)
    if settings["owner_id"] != 0:
        return settings["owner_id"]
    try:
        admins = bot.get_chat_administrators(chat_id)
        for admin in admins:
            if admin.status == 'creator':
                owner_id = admin.user.id
                update_chat_settings(chat_id, owner_id=owner_id, name=admin.user.first_name)
                return owner_id
    except:
        pass
    return 0

def get_vip_multiplier(user_id):
    user = get_user(user_id)
    if user["vip_until"] and not user["banned"]:
        vip_until = datetime.fromisoformat(user["vip_until"])
        if datetime.now() < vip_until:
            if user["vip_level"] >= 30:
                return 1.5
            elif user["vip_level"] >= 7:
                return 1.3
            elif user["vip_level"] >= 3:
                return 1.2
    return 1.0

def send_chat_message(chat_id, text, delete_after=0):
    try:
        msg = bot.send_message(chat_id, text, parse_mode="HTML")
        if delete_after > 0:
            time.sleep(delete_after)
            try:
                bot.delete_message(chat_id, msg.message_id)
            except:
                pass
        return msg
    except:
        return None

def delete_message_later(chat_id, message_id, delay=5):
    """Удаляет сообщение через delay секунд"""
    def delete():
        time.sleep(delay)
        try:
            bot.delete_message(chat_id, message_id)
        except:
            pass
    threading.Thread(target=delete, daemon=True).start()

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
    
    if expires and datetime.now() > datetime.fromisoformat(expires):
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

def delete_promo(code):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("DELETE FROM promocodes WHERE code = ?", (code,))
    conn.commit()
    conn.close()

# ========== СЕЗОННЫЕ НАГРАДЫ ==========
def give_season_rewards():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    
    c.execute("SELECT id, number FROM seasons WHERE is_active = 1")
    season = c.fetchone()
    if not season:
        conn.close()
        return
    
    season_id, season_num = season
    
    c.execute("SELECT user_id, rating FROM users WHERE banned = 0")
    users = c.fetchall()
    
    for user_id, rating in users:
        rank = get_rank_settings(rating)
        if rank["reward_gc"] > 0:
            add_gc(user_id, rank["reward_gc"])
        if rank["reward_shield"] > 0:
            user = get_user(user_id)
            update_user(user_id, shields=user["shields"] + rank["reward_shield"])
        if rank["reward_double"] > 0:
            user = get_user(user_id)
            update_user(user_id, double_chance=user["double_chance"] + rank["reward_double"])
        if rank["reward_insurance"] > 0:
            user = get_user(user_id)
            update_user(user_id, insurance=user["insurance"] + rank["reward_insurance"])
        if rank["reward_diamond"] > 0:
            user = get_user(user_id)
            update_user(user_id, diamond_shield=user["diamond_shield"] + rank["reward_diamond"])
        if rank["reward_vip_days"] > 0:
            vip_until = datetime.now() + timedelta(days=rank["reward_vip_days"])
            update_user(user_id, vip_level=rank["reward_vip_days"], vip_until=vip_until.isoformat())
        
        try:
            bot.send_message(user_id, 
                f"📅 СЕЗОН #{season_num} ЗАВЕРШЁН!\n\n"
                f"🏆 Твой рейтинг: {rating}\n"
                f"🎁 Награда: +{rank['reward_gc']} GC\n"
                f"{'🛡️ Щит ' if rank['reward_shield'] else ''}"
                f"{'⚡ Двойной шанс ' if rank['reward_double'] else ''}"
                f"{'💰 Страховка ' if rank['reward_insurance'] else ''}"
                f"{'💎 Алмазный щит ' if rank['reward_diamond'] else ''}"
                f"{'👑 VIP ' + str(rank['reward_vip_days']) + ' дней' if rank['reward_vip_days'] else ''}\n\n"
                f"🔥 Новый сезон начался! Играй и поднимай рейтинг!")
        except:
            pass
    
    c.execute("SELECT chat_id, total_games, total_bets FROM chat_stats ORDER BY (total_games * 10 + total_bets / 10) DESC")
    chats = c.fetchall()
    
    chat_rewards = {}
    for idx, (chat_id, games, bets) in enumerate(chats, 1):
        if idx == 1:
            reward = 2500
            reward_owner = 2500
            shield = "diamond"
        elif idx == 2:
            reward = 2500
            reward_owner = 2500
            shield = "shield"
        elif idx == 3:
            reward = 2500
            reward_owner = 2500
            shield = "insurance"
        elif idx <= 10:
            reward = 2500
            reward_owner = 1500
            shield = "double"
        elif idx <= 25:
            reward = 1000
            reward_owner = 500
            shield = None
        elif idx <= 50:
            reward = 500
            reward_owner = 250
            shield = None
        elif idx <= 100:
            reward = 250
            reward_owner = 100
            shield = None
        else:
            reward = 100
            reward_owner = 50
            shield = None
        
        chat_rewards[chat_id] = {"reward": reward, "reward_owner": reward_owner, "shield": shield, "place": idx}
    
    c.execute("SELECT chat_id, user_id, season_games FROM chat_players WHERE season_games > 0")
    players = c.fetchall()
    
    for chat_id, user_id, games in players:
        if chat_id in chat_rewards:
            reward = chat_rewards[chat_id]["reward"]
            if reward > 0:
                add_gc(user_id, reward)
            
            shield = chat_rewards[chat_id]["shield"]
            if shield:
                user = get_user(user_id)
                if shield == "diamond":
                    update_user(user_id, diamond_shield=user["diamond_shield"] + 1)
                elif shield == "shield":
                    update_user(user_id, shields=user["shields"] + 1)
                elif shield == "insurance":
                    update_user(user_id, insurance=user["insurance"] + 1)
                elif shield == "double":
                    update_user(user_id, double_chance=user["double_chance"] + 1)
            
            try:
                bot.send_message(user_id,
                    f"🏆 ЧАТ {get_chat_name(chat_id)} ЗАНЯЛ {chat_rewards[chat_id]['place']} МЕСТО В СЕЗОНЕ!\n"
                    f"🎁 Твоя награда: +{reward} GC")
            except:
                pass
    
    for chat_id, reward in chat_rewards.items():
        settings = get_chat_settings(chat_id)
        owner_id = settings["owner_id"]
        if owner_id:
            add_gc(owner_id, reward["reward_owner"])
            if reward["shield"]:
                user = get_user(owner_id)
                if reward["shield"] == "diamond":
                    update_user(owner_id, diamond_shield=user["diamond_shield"] + 1)
                elif reward["shield"] == "shield":
                    update_user(owner_id, shields=user["shields"] + 1)
                elif reward["shield"] == "insurance":
                    update_user(owner_id, insurance=user["insurance"] + 1)
                elif reward["shield"] == "double":
                    update_user(owner_id, double_chance=user["double_chance"] + 1)
            if reward["reward_owner"] >= 2500:
                vip_until = datetime.now() + timedelta(days=30)
                update_user(owner_id, vip_level=30, vip_until=vip_until.isoformat())
            elif reward["reward_owner"] >= 1500:
                vip_until = datetime.now() + timedelta(days=14)
                update_user(owner_id, vip_level=14, vip_until=vip_until.isoformat())
            elif reward["reward_owner"] >= 500:
                vip_until = datetime.now() + timedelta(days=7)
                update_user(owner_id, vip_level=7, vip_until=vip_until.isoformat())
            elif reward["reward_owner"] >= 250:
                vip_until = datetime.now() + timedelta(days=3)
                update_user(owner_id, vip_level=3, vip_until=vip_until.isoformat())
    
    c.execute("UPDATE chat_stats SET season_games = 0, season_bets = 0")
    c.execute("UPDATE chat_players SET season_wins = 0, season_games = 0")
    
    c.execute("UPDATE seasons SET is_active = 0 WHERE is_active = 1")
    now = datetime.now()
    end = now + timedelta(days=30)
    c.execute("INSERT INTO seasons (number, start_date, end_date) VALUES (?, ?, ?)", (season_num + 1, now.isoformat(), end.isoformat()))
    
    conn.commit()
    conn.close()
    
    log_admin(ADMIN_ID, "season_end", "all", f"Сезон #{season_num} завершён, начат сезон #{season_num + 1}")

# ========== ТЕКСТЫ ==========
def get_story():
    return (
        "🔫 <b>РУССКАЯ РУЛЕТКА</b>\n\n"
        "Однажды в подвале старого дома в Санкт-Петербурге собрались отчаянные игроки. "
        "Ставкой была не только GunCoin, но и собственная жизнь. Барабан крутился, пуля искала свою жертву, "
        "а победитель забирал всё.\n\n"
        "Спустя годы игра ушла в тень. Но легенда ожила. Теперь ты можешь испытать удачу в цифровом перерождении "
        "той самой роковой рулетки.\n\n"
        "Сделай ставку, крути барабан и докажи, что сегодня звёзды на твоей стороне.\n\n"
        "<b>🎮 ВЫБЕРИ ДЕЙСТВИЕ:</b>"
    )

def get_help_text(page):
    if page == 1:
        return (
            "🔫 <b>РУССКАЯ РУЛЕТКА — ПОМОЩЬ</b>\n\n"
            "<i>🎮 Игры создаются только в чатах</i>\n\n"
            "<b>🎮 КАК ИГРАТЬ:</b>\n"
            "• /game — создать лобби в чате\n"
            "• Другие нажимают «Присоединиться»\n"
            "• Каждый делает ставку в GC (GunCoin)\n"
            "• Ход: 🔫 Выстрелить или 🔄 Крутить барабан\n"
            "• Пусто → продолжаешь, патрон → выбываешь\n"
            "• Последний выживший забирает ВЕСЬ банк!\n\n"
            "<b>💰 КАК ПОЛУЧИТЬ GC (GunCoin):</b>\n"
            "• /daily — 50 GC (+200 за 7 дней подряд)\n"
            "• Победа в игре — +5 GC\n"
            "• Повышение ранга — крупные бонусы\n"
            "• Ежемесячный бонус за ранг\n"
            "• Поддержать проект — /donate\n\n"
            "<b>💳 ПОДДЕРЖАТЬ ПРОЕКТ:</b>\n"
            "• 10 ₽ = 350 GC\n\n"
            "<b>📌 ВАЖНО:</b>\n"
            "• Все действия игроков пишутся в чате"
        )
    elif page == 2:
        return (
            "🔫 <b>МАГАЗИН И ЗАЩИТЫ</b>\n\n"
            "<b>🛡️ ЗАЩИТЫ (в ЛС с ботом → Магазин):</b>\n"
            "• Щит (100 GC) — спасает от 1 патрона\n"
            "• Алмазный щит (400 GC) — спасает от 3 патронов\n"
            "• Двойной шанс (150 GC) — +10% к удаче на 1 игру\n"
            "• Страховка (200 GC) — возврат 50% ставки при вылете\n"
            "• Мастер (250 GC) — +5% к удаче НАВСЕГДА\n\n"
            "<b>💊 ВОССТАНОВЛЕНИЕ:</b>\n"
            "• Аптечка (80 GC) — +50 GC\n"
            "• Счастливый билет (90 GC) — рандом 20-200 GC или защита\n\n"
            "<b>👑 VIP (в ЛС с ботом → Магазин):</b>\n"
            "• VIP 3 дня (500 GC) — +20% к выигрышу\n"
            "• VIP 7 дней (1200 GC) — +30% к выигрышу + щит\n"
            "• VIP 30 дней (3000 GC) — +50% к выигрышу + щит + страховка"
        )
    else:
        return (
            "🔫 <b>РЕЙТИНГ И КОМАНДЫ</b>\n\n"
            "<b>🏆 РЕЙТИНГ И РАНГИ:</b>\n"
            "• Начальный рейтинг: 0\n"
            "• За победу: +25 | За поражение: -15\n"
            "• Ранги: Новичок (0) → Стрелок (500) → Опытный (1000) → Мастер (1500) → Элита (2000) → Легенда (2500)\n"
            "• При повышении ранга — крупные награды GC и защиты!\n"
            "• Ежемесячный бонус за ранг!\n\n"
            "<b>📊 КОМАНДЫ (в ЛС с ботом):</b>\n"
            "• /start — главное меню\n"
            "• /balance — баланс и стата\n"
            "• /daily — бонус\n"
            "• /shop — магазин\n"
            "• /top — топы\n"
            "• /promo КОД — активировать промокод\n"
            "• /donate — поддержать проект\n"
            "• /help — эта помощь\n\n"
            "<b>📊 КОМАНДЫ (в чатах):</b>\n"
            "• /chatrating — топ игроков этого чата\n"
            "• /chattop — топ чатов по рейтингу\n\n"
            "<b>⚙️ ДЛЯ СОЗДАТЕЛЯ ЧАТА:</b>\n"
            "• Настройки чата — в ЛС с ботом → «Настройки чатов»\n\n"
            "<b>👑 АДМИН БОТА:</b>\n"
            "• @HoFiLiOnclkc"
        )

def get_welcome_text():
    return (
        "🔫 <b>РУССКАЯ РУЛЕТКА</b>\n\n"
        "Привет! Я бот для игры в Русскую рулетку.\n\n"
        "<b>🎲 КАК ИГРАТЬ:</b>\n"
        "• Напиши /game — создать лобби\n"
        "• Другие присоединяются по кнопке\n"
        "• Делаешь ставку в GC (GunCoin)\n"
        "• Стреляешь, выигрываешь банк!\n\n"
        "<b>💰 БОНУСЫ:</b>\n"
        "• Ежедневный бонус — /daily\n"
        "• Повышай рейтинг — получай крупные награды\n"
        "• Ежемесячный бонус за ранг\n\n"
        "<b>💳 ПОДДЕРЖАТЬ ПРОЕКТ:</b>\n"
        "• 10 ₽ = 350 GC\n"
        "• /donate — реквизиты\n\n"
        "<b>📌 ВАЖНО:</b>\n"
        "• Все действия игроков пишутся в чате\n\n"
        "<b>📌 ПОДРОБНЕЕ:</b>\n"
        "• /help — вся информация\n\n"
        "👇 Нажми кнопку, чтобы начать!"
    )

# ========== КЛАВИАТУРЫ ==========
def private_main_menu(user_id):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📊 Стата", callback_data="stats"))
    kb.add(InlineKeyboardButton("🎁 Бонус", callback_data="daily"))
    kb.add(InlineKeyboardButton("🛒 Магазин", callback_data="shop_1"))
    kb.add(InlineKeyboardButton("🏆 Топы", callback_data="top_menu"))
    kb.add(InlineKeyboardButton("🎫 Промокод", callback_data="promo_menu"))
    kb.add(InlineKeyboardButton("💳 Поддержать", callback_data="donate_menu"))
    kb.add(InlineKeyboardButton("❓ Помощь", callback_data="help_menu"))
    
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT chat_id, name FROM chat_settings WHERE owner_id = ?", (user_id,))
    chats = c.fetchall()
    conn.close()
    
    if chats:
        kb.add(InlineKeyboardButton("⚙️ Настройки чатов", callback_data="my_chats_settings"))
    else:
        kb.add(InlineKeyboardButton("❌ Нет чатов", callback_data="none"))
    
    if user_id == ADMIN_ID:
        kb.add(InlineKeyboardButton("👑 Админ панель", callback_data="admin_panel"))
    
    return kb

def donate_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("💳 Карта", callback_data="donate_card"))
    kb.add(InlineKeyboardButton("🎁 DonationAlerts", url="https://www.donationalerts.com/r/FxHoFiLiOn"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def shop_kb(page):
    kb = InlineKeyboardMarkup(row_width=2)
    items = {
        1: [("🛡️ Щит", "buy_shield", 100), ("💎 Алмазный щит", "buy_diamond_shield", 400), ("🔄 Реинкарнация", "buy_reincarnation", 300)],
        2: [("⚡ Двойной шанс", "buy_double", 150), ("🔫 Точный выстрел", "buy_accurate", 120), ("🎯 Мастер", "buy_master", 250)],
        3: [("💰 Страховка", "buy_insurance", 200), ("💊 Аптечка", "buy_medkit", 80), ("🎲 Счастливый билет", "buy_lucky", 90)],
        4: [("👑 VIP 3 дня", "buy_vip_3", 500), ("👑 VIP 7 дней", "buy_vip_7", 1200), ("👑 VIP 30 дней", "buy_vip_30", 3000)]
    }
    for name, callback, price in items.get(page, []):
        kb.add(InlineKeyboardButton(f"{name} — {price} GC", callback_data=callback))
    
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"shop_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page}/4", callback_data="none"))
    if page < 4:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"shop_{page+1}"))
    kb.row(*nav)
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def top_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🏆 По рейтингу", callback_data="top_rating"))
    kb.add(InlineKeyboardButton("💰 По GunCoin", callback_data="top_gc"))
    kb.add(InlineKeyboardButton("🎮 По победам", callback_data="top_wins"))
    kb.add(InlineKeyboardButton("📊 По чатам", callback_data="top_chats"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def promo_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🎫 Ввести промокод", callback_data="enter_promo"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def help_menu_kb():
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("1️⃣ Основное", callback_data="help_page_1"),
        InlineKeyboardButton("2️⃣ Магазин", callback_data="help_page_2"),
        InlineKeyboardButton("3️⃣ Рейтинг", callback_data="help_page_3")
    )
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
    kb.add(InlineKeyboardButton("📅 Сезон", callback_data="admin_season_menu"))
    kb.add(InlineKeyboardButton("🎖️ Ранги", callback_data="admin_ranks_menu"))
    kb.add(InlineKeyboardButton("🏆 Рейтинг чатов", callback_data="admin_chat_rating_menu"))
    kb.add(InlineKeyboardButton("💰 Выдать GC", callback_data="admin_add_gc"))
    kb.add(InlineKeyboardButton("💸 Забрать GC", callback_data="admin_remove_gc"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def admin_season_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📅 Информация", callback_data="admin_season_info"))
    kb.add(InlineKeyboardButton("✅ Завершить сезон", callback_data="admin_season_end"))
    kb.add(InlineKeyboardButton("🎁 Выдать награды", callback_data="admin_season_give"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    return kb

def admin_ranks_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📊 Текущие пороги", callback_data="admin_ranks_view"))
    kb.add(InlineKeyboardButton("✏️ Изменить пороги", callback_data="admin_ranks_edit"))
    kb.add(InlineKeyboardButton("🎁 Изменить награды", callback_data="admin_ranks_rewards"))
    kb.add(InlineKeyboardButton("📈 Изменить коэффициенты", callback_data="admin_ranks_coeff"))
    kb.add(InlineKeyboardButton("🔄 Сбросить", callback_data="admin_ranks_reset"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    return kb

def admin_chat_rating_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📊 Просмотр топа", callback_data="admin_chat_top"))
    kb.add(InlineKeyboardButton("🔄 Сбросить рейтинг", callback_data="admin_chat_reset"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    return kb

def my_chats_kb(user_id):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT chat_id, name FROM chat_settings WHERE owner_id = ?", (user_id,))
    chats = c.fetchall()
    conn.close()
    
    kb = InlineKeyboardMarkup(row_width=1)
    for chat_id_db, name in chats:
        try:
            chat = bot.get_chat(chat_id_db)
            chat_name = chat.title or str(chat_id_db)
        except:
            chat_name = name or str(chat_id_db)
        
        kb.add(InlineKeyboardButton(f"📌 {chat_name}", callback_data=f"chat_settings_{chat_id_db}"))
    
    if not chats:
        kb.add(InlineKeyboardButton("❌ Нет чатов", callback_data="none"))
    
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def chat_settings_kb(chat_id):
    settings = get_chat_settings(chat_id)
    kb = InlineKeyboardMarkup(row_width=1)
    
    try:
        chat = bot.get_chat(chat_id)
        chat_name = chat.title or str(chat_id)
    except:
        chat_name = settings['name'] or str(chat_id)
    
    stats = get_chat_stats(chat_id)
    rating = get_chat_rating(chat_id)
    
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM chat_stats WHERE (total_games * 10 + total_bets / 10) > ?", (rating,))
    place = c.fetchone()[0] + 1
    conn.close()
    
    info_text = (
        f"📌 <b>{chat_name}</b>\n"
        f"🆔 ID: <code>{chat_id}</code>\n"
        f"🎮 Всего игр: {stats['total_games']}\n"
        f"💰 Всего ставок: {stats['total_bets']} GC\n"
        f"📊 Рейтинг: {rating} (место #{place})\n\n"
        f"⚙️ <b>НАСТРОЙКИ:</b>"
    )
    
    kb.add(InlineKeyboardButton(f"👥 Макс игроков: {settings['max_players']}", callback_data=f"set_max_players_{chat_id}"))
    kb.add(InlineKeyboardButton(f"💰 Мин ставка: {settings['min_bet']} GC", callback_data=f"set_min_bet_{chat_id}"))
    kb.add(InlineKeyboardButton(f"💎 Макс ставка: {settings['max_bet']} GC", callback_data=f"set_max_bet_{chat_id}"))
    kb.add(InlineKeyboardButton(f"🎮 Кнопки: {settings['bet_buttons']}", callback_data=f"set_bet_buttons_{chat_id}"))
    kb.add(InlineKeyboardButton(f"🎮 Игры: {'✅ Вкл' if settings['game_enabled'] else '❌ Выкл'}", callback_data=f"toggle_game_{chat_id}"))
    kb.add(InlineKeyboardButton(f"👑 Только админы: {'✅ Да' if settings['admin_only'] else '❌ Нет'}", callback_data=f"toggle_admin_only_{chat_id}"))
    
    welcome_preview = settings['welcome_message'][:30] + "..." if len(settings['welcome_message']) > 30 else settings['welcome_message']
    if not settings['welcome_message']:
        welcome_preview = "Не установлено"
    kb.add(InlineKeyboardButton(f"🎉 Приветствие", callback_data=f"set_welcome_{chat_id}"))
    
    kb.add(InlineKeyboardButton(f"🎁 Бонус: {settings['winner_bonus']} GC", callback_data=f"set_winner_bonus_{chat_id}"))
    kb.add(InlineKeyboardButton(f"🛡️ Авто-кик: {settings['auto_kick_minutes']} мин", callback_data=f"set_auto_kick_{chat_id}"))
    kb.add(InlineKeyboardButton("🔄 Сбросить статистику", callback_data=f"reset_stats_{chat_id}"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="my_chats_settings"))
    
    return kb, info_text

def game_lobby_kb(chat_id):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("➕ Присоединиться", callback_data=f"join_{chat_id}"))
    kb.add(InlineKeyboardButton("❌ Отменить игру", callback_data=f"cancel_game_{chat_id}"))
    return kb

def game_start_kb(chat_id):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🚀 Начать игру", callback_data=f"start_game_{chat_id}"))
    kb.add(InlineKeyboardButton("➕ Присоединиться", callback_data=f"join_{chat_id}"))
    kb.add(InlineKeyboardButton("❌ Отменить игру", callback_data=f"cancel_game_{chat_id}"))
    return kb

def game_action_kb(chat_id, user_id, bet):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🔫 Выстрелить", callback_data=f"shoot_{chat_id}_{user_id}_{bet}"),
        InlineKeyboardButton("🔄 Крутить", callback_data=f"spin_{chat_id}_{user_id}_{bet}")
    )
    return kb

def bet_kb(chat_id):
    settings = get_chat_settings(chat_id)
    kb = InlineKeyboardMarkup(row_width=3)
    bets = [int(x.strip()) for x in settings['bet_buttons'].split(',')]
    for bet in bets:
        if settings['min_bet'] <= bet <= settings['max_bet']:
            kb.add(InlineKeyboardButton(f"{bet} GC", callback_data=f"place_bet_{chat_id}_{bet}"))
    return kb

# ========== ХРАНИЛИЩЕ ИГР ==========
games = {}
auto_kick_timers = {}

def start_auto_kick_timer(chat_id, user_id):
    settings = get_chat_settings(chat_id)
    minutes = settings['auto_kick_minutes']
    if minutes <= 0:
        return
    
    def kick():
        if chat_id in games and games[chat_id]["status"] == "waiting":
            if user_id in games[chat_id]["players"] and user_id not in games[chat_id]["bets"]:
                games[chat_id]["players"].remove(user_id)
                msg = bot.send_message(chat_id, f"⏰ {get_user_link(user_id)} удалён за бездействие")
                delete_message_later(chat_id, msg.message_id, 5)
                update_lobby_message(chat_id)
    
    timer = threading.Timer(minutes * 60, kick)
    timer.daemon = True
    timer.start()
    
    if chat_id not in auto_kick_timers:
        auto_kick_timers[chat_id] = []
    auto_kick_timers[chat_id].append(timer)

def cancel_auto_kick_timers(chat_id):
    if chat_id in auto_kick_timers:
        for timer in auto_kick_timers[chat_id]:
            timer.cancel()
        del auto_kick_timers[chat_id]

def update_lobby_message(chat_id):
    game = games.get(chat_id)
    if not game:
        return
    
    players_count = len(game["players"])
    all_bets = all(p in game["bets"] for p in game["players"])
    
    players_list = []
    for p in game["players"]:
        if p in game["bets"]:
            players_list.append(f"• {get_user_link(p)} — {game['bets'][p]} GC")
        else:
            players_list.append(f"• {get_user_link(p)} — ожидает")
    
    players_text = "\n".join(players_list)
    total_pot = sum(game["bets"].values()) if game["bets"] else 0
    
    text = f"🎮 <b>ЛОББИ</b>\n\nСоздатель: {get_user_link(game['creator'])}\nУчастники ({players_count}/{game['max_players']}):\n{players_text}\n"
    
    if not all_bets:
        text += f"\n⚠️ Ожидаем ставки..."
        kb = game_lobby_kb(chat_id)
    else:
        text += f"\n✅ Все ставки сделаны!\n💰 Банк: {total_pot} GC"
        kb = game_start_kb(chat_id)
    
    try:
        bot.edit_message_text(text, chat_id, game["message_id"], reply_markup=kb, parse_mode="HTML")
    except:
        pass

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    init_db()
    
    user = get_user(user_id)
    if user["banned"]:
        bot.send_message(chat_id, "❌ Вы забанены!")
        return
    
    check_monthly_bonus(user_id)
    
    if message.chat.type == "private":
        bot.send_message(chat_id, get_story(), reply_markup=private_main_menu(user_id))
    else:
        update_chat_settings(chat_id, name=message.chat.title)
        owner_id = get_chat_owner(chat_id)
        if owner_id:
            update_chat_settings(chat_id, owner_id=owner_id)
        
        bot.send_message(chat_id, get_welcome_text(),
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🎮 Создать игру", callback_data="create_game")))

@bot.message_handler(commands=['game'])
def game_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.chat.type == "private":
        send_chat_message(chat_id, "❌ Игры только в чатах!", 0)
        return
    
    user = get_user(user_id)
    if user["banned"]:
        send_chat_message(chat_id, "❌ Вы забанены!", 0)
        return
    
    settings = get_chat_settings(chat_id)
    if settings["banned"] or not settings['game_enabled']:
        send_chat_message(chat_id, "❌ Игры отключены!", 0)
        return
    
    if chat_id in games:
        send_chat_message(chat_id, "❌ Игра уже есть!", 0)
        return
    
    welcome = settings['welcome_message']
    if welcome:
        welcome = welcome.replace("{user}", get_user_link(user_id)).replace("{chat}", get_chat_name(chat_id))
        sent = bot.send_message(chat_id, welcome)
        delete_message_later(chat_id, sent.message_id, 10)
    else:
        sent = bot.send_message(chat_id, f"🎮 <b>НОВАЯ ИГРА!</b>\n\n{get_user_link(user_id)} создал лобби!\nМакс: {settings['max_players']}\nМин ставка: {settings['min_bet']} GC",
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("➕ Присоединиться", callback_data=f"join_{chat_id}")))
    
    games[chat_id] = {
        "players": [user_id], "bets": {}, "chambers": {}, "status": "waiting",
        "current_player": None, "creator": user_id, "message_id": sent.message_id,
        "max_players": settings['max_players'], "used_shields": {}, "used_double": {},
        "used_insurance": {}
    }
    
    bot.send_message(user_id, "✅ Сделай ставку:", reply_markup=bet_kb(chat_id))
    start_auto_kick_timer(chat_id, user_id)

@bot.message_handler(commands=['balance'])
def balance_command(message):
    if message.chat.type != "private":
        send_chat_message(message.chat.id, "❌ Используй в ЛС!", 0)
        return
    
    user_id = message.from_user.id
    user = get_user(user_id)
    if user["banned"]:
        bot.reply_to(message, "❌ Вы забанены!")
        return
    
    check_monthly_bonus(user_id)
    
    win_percent = int(user["wins"] / max(1, user["total_games"]) * 100)
    vip_text = f"{user['vip_level']} дней" if user["vip_until"] and datetime.now() < datetime.fromisoformat(user["vip_until"]) else "Нет"
    rank_name = get_rank_name(user["rating"])
    rank_emoji = get_rank_emoji(user["rating"])
    
    text = (f"<b>📊 СТАТА</b>\n\n"
        f"🔫 GC: {user['gc']}\n🏆 Рейтинг: {user['rating']}\n🏅 Ранг: {rank_emoji} {rank_name}\n\n"
        f"📈 Побед: {user['wins']} | Поражений: {user['losses']}\n🎮 Игр: {user['total_games']} | % побед: {win_percent}%\n\n"
        f"🛡️ Щитов: {user['shields']} | Алмазных: {user['diamond_shield']}\n"
        f"⚡ Двойных: {user['double_chance']} | 💰 Страховок: {user['insurance']}\n"
        f"🎯 Мастер: {'✅' if user['master'] else '❌'}\n👑 VIP: {vip_text}")
    bot.reply_to(message, text)

@bot.message_handler(commands=['daily'])
def daily_command(message):
    if message.chat.type != "private":
        send_chat_message(message.chat.id, "❌ Используй в ЛС!", 0)
        return
    
    user_id = message.from_user.id
    user = get_user(user_id)
    if user["banned"]:
        bot.reply_to(message, "❌ Вы забанены!")
        return
    
    last = datetime.fromisoformat(user["last_daily"]) if user["last_daily"] else datetime.min
    now = datetime.now()
    
    if now - last < timedelta(days=1):
        hours = 24 - (now - last).seconds // 3600
        bot.reply_to(message, f"⏰ Бонус через {hours} ч")
        return
    
    bonus = 50
    streak = user["daily_streak"]
    if streak >= 7:
        bonus += 200
        update_user(user_id, daily_streak=1)
    else:
        update_user(user_id, daily_streak=streak + 1)
    
    update_user(user_id, gc=user["gc"] + bonus, last_daily=now.isoformat())
    bot.reply_to(message, f"🎁 +{bonus} GC\n💰 Баланс: {user['gc'] + bonus} GC")

@bot.message_handler(commands=['shop'])
def shop_command(message):
    if message.chat.type != "private":
        send_chat_message(message.chat.id, "❌ Используй в ЛС!", 0)
        return
    
    user_id = message.from_user.id
    user = get_user(user_id)
    if user["banned"]:
        bot.reply_to(message, "❌ Вы забанены!")
        return
    
    bot.send_message(message.chat.id, "<b>🛒 МАГАЗИН — 1/4</b>", reply_markup=shop_kb(1))

@bot.message_handler(commands=['top'])
def top_command(message):
    if message.chat.type != "private":
        send_chat_message(message.chat.id, "❌ Используй в ЛС!", 0)
        return
    
    user_id = message.from_user.id
    user = get_user(user_id)
    if user["banned"]:
        bot.reply_to(message, "❌ Вы забанены!")
        return
    
    bot.send_message(message.chat.id, "<b>🏆 ТОПЫ</b>", reply_markup=top_menu_kb())

@bot.message_handler(commands=['chatrating'])
def chat_rating_command(message):
    if message.chat.type == "private":
        send_chat_message(message.chat.id, "❌ Команда в чате!", 0)
        return
    
    players = get_chat_top_players(message.chat.id, 10)
    text = "<b>🏆 ТОП ЧАТА</b>\n\n"
    for i, (uid, wins, games) in enumerate(players, 1):
        text += f"{i}. {get_user_link(uid)} — {wins} побед ({games} игр)\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['chattop'])
def chat_top_command(message):
    chats = get_all_chats_rating()
    text = "<b>🏆 ТОП ЧАТОВ</b>\n\n"
    for i, (cid, games, bets) in enumerate(chats[:10], 1):
        rating = (games * 10) + (bets // 10)
        text += f"{i}. {get_chat_name(cid)}\n   📊 {rating} | 🎮 {games} | 💰 {bets}\n\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['promo'])
def promo_command(message):
    if message.chat.type != "private":
        send_chat_message(message.chat.id, "❌ Используй в ЛС!", 0)
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Использование: /promo КОД")
        return
    success, msg = use_promo(message.from_user.id, args[1].upper())
    bot.reply_to(message, msg)

@bot.message_handler(commands=['donate'])
def donate_command(message):
    if message.chat.type != "private":
        send_chat_message(message.chat.id, "❌ Используй в ЛС!", 0)
        return
    
    text = "💳 ПОДДЕРЖАТЬ\n\n10 ₽ = 350 GC"
    bot.send_message(message.chat.id, text, reply_markup=donate_menu_kb())

@bot.message_handler(commands=['help'])
def help_command(message):
    if message.chat.type != "private":
        send_chat_message(message.chat.id, "❌ Используй в ЛС!", 0)
        return
    
    bot.send_message(message.chat.id, get_help_text(1), reply_markup=help_menu_kb())

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, "👑 АДМИН ПАНЕЛЬ", reply_markup=admin_panel_kb())

@bot.my_chat_member_handler()
def handle_my_chat_member(update):
    try:
        if update.new_chat_member.status in ['member', 'administrator']:
            chat_id = update.chat.id
            update_chat_settings(chat_id, name=update.chat.title)
            owner_id = get_chat_owner(chat_id)
            if owner_id:
                update_chat_settings(chat_id, owner_id=owner_id)
            bot.send_message(chat_id, get_welcome_text(),
                reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🎮 Создать игру", callback_data="create_game")))
    except:
        pass

# ========== ОСНОВНОЙ КОЛБЭК ==========
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    global games
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    is_private = (chat_id == user_id)
    
    user = get_user(user_id)
    if user["banned"]:
        bot.answer_callback_query(call.id, "❌ Вы забанены!", show_alert=True)
        return
    
    if call.data == "back":
        if is_private:
            bot.edit_message_text(get_story(), chat_id, message_id, reply_markup=private_main_menu(user_id))
        else:
            bot.edit_message_text(get_welcome_text(), chat_id, message_id,
                reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🎮 Создать игру", callback_data="create_game")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "none":
        bot.answer_callback_query(call.id)
        return
    
    # ========== HELP ==========
    if call.data == "help_menu":
        bot.edit_message_text(get_help_text(1), chat_id, message_id, reply_markup=help_menu_kb())
        bot.answer_callback_query(call.id)
        return
    if call.data in ["help_page_1", "help_page_2", "help_page_3"]:
        page = int(call.data.split("_")[2])
        bot.edit_message_text(get_help_text(page), chat_id, message_id, reply_markup=help_menu_kb())
        bot.answer_callback_query(call.id)
        return
    
    # ========== ДОНАТ ==========
    if call.data == "donate_menu":
        bot.edit_message_text("💳 ПОДДЕРЖАТЬ\n\n10 ₽ = 350 GC", chat_id, message_id, reply_markup=donate_menu_kb())
        bot.answer_callback_query(call.id)
        return
    if call.data == "donate_card":
        bot.edit_message_text("💳 КАРТА\n\n2202 2081 8206 1235\n\nПосле перевода отправьте чек @HoFiLiOnclkc", 
            chat_id, message_id, reply_markup=donate_menu_kb())
        bot.answer_callback_query(call.id)
        return
    
    # ========== СТАТА ==========
    if call.data == "stats":
        win_percent = int(user["wins"] / max(1, user["total_games"]) * 100)
        vip_text = f"{user['vip_level']} дней" if user["vip_until"] and datetime.now() < datetime.fromisoformat(user["vip_until"]) else "Нет"
        rank_name = get_rank_name(user["rating"])
        rank_emoji = get_rank_emoji(user["rating"])
        text = (f"<b>📊 СТАТА</b>\n\n"
            f"🔫 GC: {user['gc']}\n🏆 Рейтинг: {user['rating']}\n🏅 Ранг: {rank_emoji} {rank_name}\n\n"
            f"📈 Побед: {user['wins']} | Поражений: {user['losses']}\n🎮 Игр: {user['total_games']} | % побед: {win_percent}%\n\n"
            f"🛡️ Щитов: {user['shields']} | Алмазных: {user['diamond_shield']}\n"
            f"⚡ Двойных: {user['double_chance']} | 💰 Страховок: {user['insurance']}\n"
            f"🎯 Мастер: {'✅' if user['master'] else '❌'}\n👑 VIP: {vip_text}")
        bot.edit_message_text(text, chat_id, message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        bot.answer_callback_query(call.id)
        return
    
    # ========== БОНУС ==========
    if call.data == "daily":
        last = datetime.fromisoformat(user["last_daily"]) if user["last_daily"] else datetime.min
        now = datetime.now()
        if now - last < timedelta(days=1):
            hours = 24 - (now - last).seconds // 3600
            bot.answer_callback_query(call.id, f"⏰ Бонус через {hours} ч", show_alert=True)
            return
        bonus = 50
        streak = user["daily_streak"]
        if streak >= 7:
            bonus += 200
            update_user(user_id, daily_streak=1)
        else:
            update_user(user_id, daily_streak=streak + 1)
        update_user(user_id, gc=user["gc"] + bonus, last_daily=now.isoformat())
        bot.edit_message_text(f"🎁 +{bonus} GC\n💰 Баланс: {user['gc'] + bonus} GC", chat_id, message_id, 
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        bot.answer_callback_query(call.id)
        return
    
    # ========== МАГАЗИН ==========
    if call.data.startswith("shop_"):
        page = int(call.data.split("_")[1])
        bot.edit_message_text(f"<b>🛒 МАГАЗИН — {page}/4</b>", chat_id, message_id, reply_markup=shop_kb(page))
        bot.answer_callback_query(call.id)
        return
    
    buy_items = {
        "buy_shield": ("shields", 100, "Щит"),
        "buy_diamond_shield": ("diamond_shield", 400, "Алмазный щит"),
        "buy_double": ("double_chance", 150, "Двойной шанс"),
        "buy_insurance": ("insurance", 200, "Страховка"),
        "buy_reincarnation": (None, 300, "Реинкарнация"),
    }
    if call.data in buy_items:
        item = buy_items[call.data]
        if user["gc"] >= item[1]:
            new_gc = user["gc"] - item[1]
            if item[0]:
                update_user(user_id, gc=new_gc, **{item[0]: user[item[0]] + 1})
            else:
                update_user(user_id, gc=new_gc)
            bot.answer_callback_query(call.id, f"✅ {item[2]} куплен!", show_alert=True)
            bot.edit_message_text(f"✅ {item[2]} куплен!\n💰 Осталось: {new_gc} GC", chat_id, message_id,
                reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        else:
            bot.answer_callback_query(call.id, f"❌ Нужно {item[1]} GC!", show_alert=True)
        return
    
    if call.data == "buy_accurate":
        if user["gc"] >= 120:
            update_user(user_id, gc=user["gc"] - 120)
            bot.answer_callback_query(call.id, "✅ Точный выстрел!", show_alert=True)
            bot.edit_message_text("🔫 Точный выстрел куплен!", chat_id, message_id,
                reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        else:
            bot.answer_callback_query(call.id, f"❌ Нужно 120 GC!", show_alert=True)
        return
    
    if call.data == "buy_master":
        if user["master"]:
            bot.answer_callback_query(call.id, "❌ Уже есть мастер!", show_alert=True)
        elif user["gc"] >= 250:
            update_user(user_id, gc=user["gc"] - 250, master=1)
            bot.answer_callback_query(call.id, "✅ Мастер +5% к удаче!", show_alert=True)
            bot.edit_message_text("🎯 Мастер куплен!", chat_id, message_id,
                reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        else:
            bot.answer_callback_query(call.id, f"❌ Нужно 250 GC!", show_alert=True)
        return
    
    if call.data == "buy_medkit":
        if user["gc"] >= 80:
            update_user(user_id, gc=user["gc"] - 80)
            add_gc(user_id, 50)
            bot.answer_callback_query(call.id, "✅ +50 GC", show_alert=True)
            bot.edit_message_text("💊 Аптечка! +50 GC", chat_id, message_id,
                reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        else:
            bot.answer_callback_query(call.id, f"❌ Нужно 80 GC!", show_alert=True)
        return
    
    if call.data == "buy_lucky":
        if user["gc"] >= 90:
            update_user(user_id, gc=user["gc"] - 90)
            prize = random.choice([20, 30, 50, 80, 100, 150, 200, "shield", "double", "insurance"])
            if prize == "shield":
                update_user(user_id, shields=user["shields"] + 1)
                msg = "🛡️ Щит"
            elif prize == "double":
                update_user(user_id, double_chance=user["double_chance"] + 1)
                msg = "⚡ Двойной шанс"
            elif prize == "insurance":
                update_user(user_id, insurance=user["insurance"] + 1)
                msg = "💰 Страховка"
            else:
                add_gc(user_id, prize)
                msg = f"{prize} GC"
            bot.answer_callback_query(call.id, f"✅ {msg}!", show_alert=True)
            bot.edit_message_text(f"🎲 Счастливый билет!\nВыпало: {msg}", chat_id, message_id,
                reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        else:
            bot.answer_callback_query(call.id, f"❌ Нужно 90 GC!", show_alert=True)
        return
    
    if call.data in ["buy_vip_3", "buy_vip_7", "buy_vip_30"]:
        days = 3 if call.data == "buy_vip_3" else 7 if call.data == "buy_vip_7" else 30
        price = 500 if days == 3 else 1200 if days == 7 else 3000
        if user["gc"] >= price:
            update_user(user_id, gc=user["gc"] - price, vip_level=days, vip_until=(datetime.now() + timedelta(days=days)).isoformat())
            bot.answer_callback_query(call.id, f"✅ VIP {days} дней!", show_alert=True)
            bot.edit_message_text(f"👑 VIP на {days} дней!\n💰 Осталось: {user['gc'] - price} GC", chat_id, message_id,
                reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        else:
            bot.answer_callback_query(call.id, f"❌ Нужно {price} GC!", show_alert=True)
        return
    
    # ========== ТОПЫ ==========
    if call.data == "top_menu":
        bot.edit_message_text("<b>🏆 ТОПЫ</b>", chat_id, message_id, reply_markup=top_menu_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "top_rating":
        top = get_top_players("rating", 10)
        text = "<b>🏆 ТОП ПО РЕЙТИНГУ</b>\n\n"
        for i, (uid, rating, wins) in enumerate(top, 1):
            text += f"{i}. {get_user_link(uid)} — {get_rank_emoji(rating)} {rating}, {wins} побед\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="top_menu")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "top_gc":
        top = get_top_players("gc", 10)
        text = "<b>💰 ТОП ПО GC</b>\n\n"
        for i, (uid, gc, wins) in enumerate(top, 1):
            text += f"{i}. {get_user_link(uid)} — {gc} GC, {wins} побед\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="top_menu")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "top_wins":
        top = get_top_players("wins", 10)
        text = "<b>🎮 ТОП ПО ПОБЕДАМ</b>\n\n"
        for i, (uid, wins, rating) in enumerate(top, 1):
            text += f"{i}. {get_user_link(uid)} — {wins} побед, {get_rank_emoji(rating)} {rating}\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="top_menu")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "top_chats":
        chats = get_all_chats_rating()
        text = "<b>🏆 ТОП ЧАТОВ</b>\n\n"
        for i, (cid, games, bets) in enumerate(chats[:10], 1):
            rating = (games * 10) + (bets // 10)
            text += f"{i}. {get_chat_name(cid)}\n   📊 {rating} | 🎮 {games} | 💰 {bets} GC\n\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="top_menu")))
        bot.answer_callback_query(call.id)
        return
    
    # ========== ПРОМОКОД ==========
    if call.data == "promo_menu":
        bot.edit_message_text("<b>🎫 ПРОМОКОДЫ</b>\n\nВведи /promo КОД", chat_id, message_id, reply_markup=promo_menu_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "enter_promo":
        bot.send_message(user_id, "Введите промокод:")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: promo_enter_handler(m, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    # ========== НАСТРОЙКИ ЧАТОВ ==========
    if call.data == "my_chats_settings":
        kb = my_chats_kb(user_id)
        bot.edit_message_text("<b>⚙️ НАСТРОЙКИ ЧАТОВ</b>\n\nВыбери чат:", chat_id, message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("chat_settings_"):
        target_chat_id = int(call.data.split("_")[2])
        settings = get_chat_settings(target_chat_id)
        if settings["owner_id"] != user_id and user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Только владелец!", show_alert=True)
            return
        kb, info = chat_settings_kb(target_chat_id)
        bot.edit_message_text(info, chat_id, message_id, reply_markup=kb, parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("reset_stats_"):
        target_chat_id = int(call.data.split("_")[2])
        settings = get_chat_settings(target_chat_id)
        if settings["owner_id"] != user_id and user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Только владелец!", show_alert=True)
            return
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        c.execute("DELETE FROM chat_stats WHERE chat_id = ?", (target_chat_id,))
        c.execute("INSERT INTO chat_stats (chat_id, total_games, total_bets, season_games, season_bets) VALUES (?, 0, 0, 0, 0)", (target_chat_id,))
        c.execute("DELETE FROM chat_players WHERE chat_id = ?", (target_chat_id,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "✅ Статистика сброшена!", show_alert=True)
        kb, info = chat_settings_kb(target_chat_id)
        bot.edit_message_text(info, chat_id, message_id, reply_markup=kb, parse_mode="HTML")
        return
    
    if call.data.startswith("set_welcome_"):
        target_chat_id = int(call.data.split("_")[2])
        bot.send_message(user_id, "Введите текст приветствия.\nПеременные: {user}, {chat}\nПусто = отключить:")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: set_welcome_handler(m, target_chat_id, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("set_winner_bonus_"):
        target_chat_id = int(call.data.split("_")[3])
        bot.send_message(user_id, "Введите бонус победителю (0-500 GC):")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: set_winner_bonus_handler(m, target_chat_id, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("set_auto_kick_"):
        target_chat_id = int(call.data.split("_")[3])
        bot.send_message(user_id, "Введите авто-кик в минутах (0-10):")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: set_auto_kick_handler(m, target_chat_id, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("set_max_players_"):
        target_chat_id = int(call.data.split("_")[3])
        bot.send_message(user_id, "Введите макс. игроков (2-15):")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: set_max_players_handler(m, target_chat_id, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("set_min_bet_"):
        target_chat_id = int(call.data.split("_")[3])
        bot.send_message(user_id, "Введите мин. ставку (1-1000):")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: set_min_bet_handler(m, target_chat_id, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("set_max_bet_"):
        target_chat_id = int(call.data.split("_")[3])
        bot.send_message(user_id, "Введите макс. ставку (10-10000):")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: set_max_bet_handler(m, target_chat_id, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("set_bet_buttons_"):
        target_chat_id = int(call.data.split("_")[3])
        bot.send_message(user_id, "Введите кнопки через запятую (10,50,100,200,500,1000):")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: set_bet_buttons_handler(m, target_chat_id, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("toggle_game_"):
        target_chat_id = int(call.data.split("_")[2])
        settings = get_chat_settings(target_chat_id)
        new_state = 0 if settings['game_enabled'] else 1
        update_chat_settings(target_chat_id, game_enabled=new_state)
        bot.answer_callback_query(call.id, f"Игры {'вкл' if new_state else 'выкл'}")
        kb, info = chat_settings_kb(target_chat_id)
        bot.edit_message_text(info, chat_id, message_id, reply_markup=kb, parse_mode="HTML")
        return
    
    if call.data.startswith("toggle_admin_only_"):
        target_chat_id = int(call.data.split("_")[3])
        settings = get_chat_settings(target_chat_id)
        new_state = 0 if settings['admin_only'] else 1
        update_chat_settings(target_chat_id, admin_only=new_state)
        bot.answer_callback_query(call.id, f"Только админы: {'Да' if new_state else 'Нет'}")
        kb, info = chat_settings_kb(target_chat_id)
        bot.edit_message_text(info, chat_id, message_id, reply_markup=kb, parse_mode="HTML")
        return
    
    # ========== АДМИН ==========
    if call.data == "admin_panel":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
            return
        bot.edit_message_text("<b>👑 АДМИН ПАНЕЛЬ</b>", chat_id, message_id, reply_markup=admin_panel_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_stats":
        if user_id != ADMIN_ID: return
        stats = get_total_stats()
        season = get_current_season()
        text = f"<b>📊 СТАТИСТИКА</b>\n\n📱 Чатов: {stats['chats']}\n👥 Игроков: {stats['users']}\n🎮 Игр: {stats['games']}\n📅 Сезон #{season['number'] if season else '?'}"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_chats":
        if user_id != ADMIN_ID: return
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        c.execute("SELECT chat_id, name, owner_id, game_enabled FROM chat_settings WHERE name != ''")
        chats = c.fetchall()
        conn.close()
        text = "<b>📋 СПИСОК ЧАТОВ</b>\n\n"
        for cid, name, owner, enabled in chats[:30]:
            text += f"{'✅' if enabled else '❌'} {name or cid}\n   ID: {cid}\n   Владелец: {get_name(owner) if owner else '?'}\n\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_players":
        if user_id != ADMIN_ID: return
        users = get_all_users()
        text = "<b>👥 ТОП-50 ИГРОКОВ</b>\n\n"
        for i, (uid, gc, rating, wins, banned) in enumerate(users[:30], 1):
            text += f"{i}. {'🚫' if banned else '✅'} {get_name(uid)} — {get_rank_emoji(rating)} {rating}, {gc} GC, {wins} побед\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_promocodes":
        if user_id != ADMIN_ID: return
        bot.edit_message_text("<b>🎫 ПРОМОКОДЫ</b>", chat_id, message_id, reply_markup=admin_promocodes_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_create_promo":
        if user_id != ADMIN_ID: return
        bot.send_message(user_id, "Введите: КОД ТИП КОЛ-ВО ЛИМИТ [ДНИ]\nТипы: gc,shield,double,insurance,diamond_shield,vip")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: create_promo_handler(m, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_list_promos":
        if user_id != ADMIN_ID: return
        promos = get_all_promos()
        text = "<b>📋 ПРОМОКОДЫ</b>\n\n"
        for code, rtype, ramount, max_uses, used, expires in promos:
            status = "✅" if not expires or datetime.now() < datetime.fromisoformat(expires) else "❌"
            text += f"{status} {code} — {rtype} x{ramount} ({used}/{max_uses})\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_promocodes")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_delete_promo":
        if user_id != ADMIN_ID: return
        bot.send_message(user_id, "Введите код промокода:")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: delete_promo_handler(m, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_broadcast":
        if user_id != ADMIN_ID: return
        bot.send_message(user_id, "Введите текст рассылки:")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: broadcast_handler(m, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_games":
        if user_id != ADMIN_ID: return
        if not games:
            text = "Нет активных игр"
        else:
            text = "<b>🎮 АКТИВНЫЕ ИГРЫ</b>\n\n"
            for gid, game in games.items():
                text += f"📌 {get_chat_name(gid)}\n   {len(game['players'])}/{game['max_players']} | {game['status']}\n\n"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("⏹️ Завершить все", callback_data="admin_end_all_games"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_end_all_games":
        if user_id != ADMIN_ID: return
        for gid in list(games.keys()):
            del games[gid]
            cancel_auto_kick_timers(gid)
        bot.answer_callback_query(call.id, "Все игры завершены")
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=admin_panel_kb())
        return
    
    if call.data == "admin_season_menu":
        if user_id != ADMIN_ID: return
        bot.edit_message_text("<b>📅 УПРАВЛЕНИЕ СЕЗОНОМ</b>", chat_id, message_id, reply_markup=admin_season_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_season_info":
        if user_id != ADMIN_ID: return
        season = get_current_season()
        if season:
            days_left = (datetime.fromisoformat(season['end_date']) - datetime.now()).days
            text = f"<b>📅 СЕЗОН #{season['number']}</b>\n\nНачало: {season['start_date'][:10]}\nКонец: {season['end_date'][:10]}\nОсталось: {days_left} дней"
        else:
            text = "Нет активного сезона"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_season_menu")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_season_end":
        if user_id != ADMIN_ID: return
        give_season_rewards()
        bot.answer_callback_query(call.id, "✅ Сезон завершён!")
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=admin_season_kb())
        return
    
    if call.data == "admin_season_give":
        if user_id != ADMIN_ID: return
        give_season_rewards()
        bot.answer_callback_query(call.id, "✅ Награды выданы!")
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=admin_season_kb())
        return
    
    if call.data == "admin_ranks_menu":
        if user_id != ADMIN_ID: return
        bot.edit_message_text("<b>🎖️ УПРАВЛЕНИЕ РАНГАМИ</b>", chat_id, message_id, reply_markup=admin_ranks_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_ranks_view":
        if user_id != ADMIN_ID: return
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        c.execute("SELECT rank_name, min_rating, max_rating, reward_gc, bet_bonus FROM rank_settings ORDER BY min_rating")
        ranks = c.fetchall()
        conn.close()
        text = "<b>📊 РАНГИ</b>\n\n"
        for rank in ranks:
            text += f"{rank[0]}: {rank[1]}-{rank[2]}\n   🎁 {rank[3]} GC | 📈 +{rank[4]}\n\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_ranks_menu")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_ranks_edit":
        if user_id != ADMIN_ID: return
        bot.send_message(user_id, "Введите пороги:\nСтрелок:500,Опытный:1000,Мастер:1500,Элита:2000,Легенда:2500")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: edit_ranks_handler(m, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_ranks_rewards":
        if user_id != ADMIN_ID: return
        bot.send_message(user_id, "Введите награды:\nСтрелок:500,Опытный:1000,Мастер:2000,Элита:4000,Легенда:8000")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: edit_rank_rewards_handler(m, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_ranks_coeff":
        if user_id != ADMIN_ID: return
        bot.send_message(user_id, "Введите коэффициенты:\nПобеда:25,Поражение:15")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: edit_rank_coeff_handler(m, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_ranks_reset":
        if user_id != ADMIN_ID: return
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        c.execute("DELETE FROM rank_settings")
        default_ranks = [
            ("Новичок", 0, 499, 100, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 25, 15),
            ("Стрелок", 500, 999, 500, 1, 0, 0, 0, 0, 50, 100, 0, 0, 0, 0, 0, 25, 15),
            ("Опытный", 1000, 1499, 1000, 0, 1, 0, 0, 0, 100, 250, 0, 0, 0, 0, 0, 25, 15),
            ("Мастер", 1500, 1999, 2000, 0, 0, 1, 0, 0, 200, 500, 1, 0, 0, 0, 0, 25, 15),
            ("Элита", 2000, 2499, 4000, 0, 0, 0, 1, 0, 500, 1000, 0, 1, 0, 0, 0, 25, 15),
            ("Легенда", 2500, 999999, 8000, 0, 0, 0, 1, 14, 1000, 2000, 0, 0, 1, 3, 0, 25, 15)
        ]
        for rank in default_ranks:
            c.execute("INSERT INTO rank_settings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rank)
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "✅ Сброшено!")
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=admin_ranks_kb())
        return
    
    if call.data == "admin_chat_rating_menu":
        if user_id != ADMIN_ID: return
        bot.edit_message_text("<b>🏆 РЕЙТИНГ ЧАТОВ</b>", chat_id, message_id, reply_markup=admin_chat_rating_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_chat_top":
        if user_id != ADMIN_ID: return
        chats = get_all_chats_rating()
        text = "<b>🏆 ТОП-50 ЧАТОВ</b>\n\n"
        for i, (cid, games, bets) in enumerate(chats[:50], 1):
            rating = (games * 10) + (bets // 10)
            text += f"{i}. {get_chat_name(cid)}\n   📊 {rating} | 🎮 {games} | 💰 {bets}\n\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_chat_rating_menu")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_chat_reset":
        if user_id != ADMIN_ID: return
        bot.send_message(user_id, "Введите ID чата:")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: reset_chat_rating_handler(m, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_add_gc":
        if user_id != ADMIN_ID: return
        bot.send_message(user_id, "Введите ID и GC (123456789 500):")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: add_gc_handler(m, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_remove_gc":
        if user_id != ADMIN_ID: return
        bot.send_message(user_id, "Введите ID и GC для списания (123456789 100):")
        bot.register_next_step_handler_by_chat_id(user_id, lambda m: remove_gc_handler(m, chat_id, message_id))
        bot.answer_callback_query(call.id)
        return
    
    # ========== ИГРОВЫЕ КОЛБЭКИ ==========
    if call.data == "create_game":
        if is_private:
            bot.answer_callback_query(call.id, "❌ Игры только в чатах!", show_alert=True)
            return
        settings = get_chat_settings(chat_id)
        if settings["banned"] or not settings['game_enabled']:
            bot.answer_callback_query(call.id, "❌ Игры отключены!", show_alert=True)
            return
        if chat_id in games:
            bot.answer_callback_query(call.id, "❌ Игра уже есть!", show_alert=True)
            return
        
        welcome = settings['welcome_message']
        if welcome:
            welcome = welcome.replace("{user}", get_user_link(user_id)).replace("{chat}", get_chat_name(chat_id))
            sent = bot.send_message(chat_id, welcome)
            delete_message_later(chat_id, sent.message_id, 10)
        else:
            sent = bot.send_message(chat_id, f"🎮 <b>НОВАЯ ИГРА!</b>\n\n{get_user_link(user_id)} создал лобби!\nМакс: {settings['max_players']}\nМин ставка: {settings['min_bet']} GC",
                reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("➕ Присоединиться", callback_data=f"join_{chat_id}")))
        
        games[chat_id] = {
            "players": [user_id], "bets": {}, "chambers": {}, "status": "waiting",
            "current_player": None, "creator": user_id, "message_id": sent.message_id,
            "max_players": settings['max_players'], "used_shields": {}, "used_double": {},
            "used_insurance": {}
        }
        bot.send_message(user_id, "✅ Сделай ставку:", reply_markup=bet_kb(chat_id))
        start_auto_kick_timer(chat_id, user_id)
        bot.answer_callback_query(call.id, "Игра создана!")
        return
    
    if call.data.startswith("join_"):
        gid = int(call.data.split("_")[1])
        if gid not in games or games[gid]["status"] != "waiting":
            bot.answer_callback_query(call.id, "Игра уже началась!", show_alert=True)
            return
        if user_id in games[gid]["players"]:
            bot.answer_callback_query(call.id, "Ты уже в игре!", show_alert=True)
            return
        if len(games[gid]["players"]) >= games[gid]["max_players"]:
            bot.answer_callback_query(call.id, "Лобби заполнено!", show_alert=True)
            return
        
        games[gid]["players"].append(user_id)
        update_lobby_message(gid)
        msg = bot.send_message(gid, f"➕ {get_name(user_id)} присоединился!")
        delete_message_later(gid, msg.message_id, 5)
        bot.send_message(user_id, "🎮 Сделай ставку:", reply_markup=bet_kb(gid))
        start_auto_kick_timer(gid, user_id)
        bot.answer_callback_query(call.id, "Ты присоединился!")
        return
    
    if call.data.startswith("cancel_game_"):
        gid = int(call.data.split("_")[2])
        if gid not in games:
            return
        if games[gid]["creator"] != user_id and not is_chat_admin(user_id, gid):
            bot.answer_callback_query(call.id, "Только создатель!", show_alert=True)
            return
        cancel_auto_kick_timers(gid)
        del games[gid]
        msg = bot.send_message(gid, "❌ Игра отменена")
        delete_message_later(gid, msg.message_id, 5)
        bot.answer_callback_query(call.id, "Игра отменена")
        return
    
    if call.data.startswith("place_bet_"):
        parts = call.data.split("_")
        gid = int(parts[2])
        bet = int(parts[3])
        if gid not in games or games[gid]["status"] != "waiting":
            bot.answer_callback_query(call.id, "Игра неактивна!", show_alert=True)
            return
        if user_id not in games[gid]["players"]:
            bot.answer_callback_query(call.id, "Ты не в игре!", show_alert=True)
            return
        if user_id in games[gid]["bets"]:
            bot.answer_callback_query(call.id, "Ставка уже сделана!", show_alert=True)
            return
        
        settings = get_chat_settings(gid)
        if bet < settings['min_bet'] or bet > settings['max_bet']:
            bot.answer_callback_query(call.id, f"Ставка от {settings['min_bet']} до {settings['max_bet']}!", show_alert=True)
            return
        if user["gc"] < bet:
            bot.answer_callback_query(call.id, f"Не хватает! Нужно {bet}", show_alert=True)
            return
        
        games[gid]["bets"][user_id] = bet
        update_user(user_id, gc=user["gc"] - bet)
        msg = bot.send_message(gid, f"💰 {get_name(user_id)} поставил {bet} GC!")
        delete_message_later(gid, msg.message_id, 5)
        bot.send_message(user_id, f"✅ Ставка {bet} GC принята!")
        cancel_auto_kick_timers(gid)
        update_lobby_message(gid)
        bot.answer_callback_query(call.id, f"Ставка {bet} GC принята!")
        return
    
    if call.data.startswith("start_game_"):
        gid = int(call.data.split("_")[2])
        if gid not in games:
            return
        game = games[gid]
        if user_id != game["creator"]:
            bot.answer_callback_query(call.id, "Только создатель!", show_alert=True)
            return
        if len(game["players"]) < 2:
            bot.answer_callback_query(call.id, "Нужно минимум 2 игрока!", show_alert=True)
            return
        for p in game["players"]:
            if p not in game["bets"]:
                bot.answer_callback_query(call.id, "Не все сделали ставки!", show_alert=True)
                return
        
        game["status"] = "playing"
        players = game["players"].copy()
        random.shuffle(players)
        game["players"] = players
        game["current_player"] = players[0]
        for p in players:
            game["chambers"][p] = random.randint(1, 6)
        
        total_pot = sum(game["bets"].values())
        players_text = "\n".join([f"• {get_user_link(p)} — {game['bets'][p]} GC" for p in players])
        bot.edit_message_text(f"🎲 <b>ИГРА НАЧАЛАСЬ!</b>\n\n{players_text}\n\n💰 Банк: {total_pot} GC", gid, game["message_id"])
        
        current = game["current_player"]
        # Отправляем одно сообщение с действием (без лишнего)
        bot.send_message(gid, f"🔫 ХОД: {get_name(current)} | Ставка: {game['bets'][current]} GC\n\nВыбери действие:", 
            reply_markup=game_action_kb(gid, current, game['bets'][current]))
        
        update_chat_stats(gid, total_pot)
        for p in players:
            u = get_user(p)
            update_user(p, total_games=u["total_games"] + 1)
        
        bot.answer_callback_query(call.id, "Игра начата!")
        return
    
    if call.data.startswith("spin_"):
        # КД ТОЛЬКО ДЛЯ ИГРОВЫХ ДЕЙСТВИЙ
        if not check_game_cooldown(user_id):
            bot.answer_callback_query(call.id, "⏰ Подожди 5 секунд!", show_alert=True)
            return
        
        parts = call.data.split("_")
        gid = int(parts[1])
        pid = int(parts[2])
        bet = int(parts[3])
        if gid not in games or games[gid]["status"] != "playing":
            bot.answer_callback_query(call.id, "Игра неактивна!", show_alert=True)
            return
        game = games[gid]
        if game["current_player"] != pid:
            bot.answer_callback_query(call.id, "❌ Не ваш ход!", show_alert=True)
            return
        
        game["chambers"][pid] = random.randint(1, 6)
        # Удаляем старое сообщение с кнопками
        try:
            bot.delete_message(gid, call.message.message_id)
        except:
            pass
        # Отправляем новое с обновлёнными кнопками
        bot.send_message(gid, f"🔄 {get_name(pid)} прокрутил барабан!\n\n🔫 Теперь стреляй:", 
            reply_markup=game_action_kb(gid, pid, bet))
        bot.answer_callback_query(call.id, "Барабан прокручен!")
        return
    
    if call.data.startswith("shoot_"):
        # КД ТОЛЬКО ДЛЯ ИГРОВЫХ ДЕЙСТВИЙ
        if not check_game_cooldown(user_id):
            bot.answer_callback_query(call.id, "⏰ Подожди 5 секунд!", show_alert=True)
            return
        
        parts = call.data.split("_")
        gid = int(parts[1])
        pid = int(parts[2])
        bet = int(parts[3])
        if gid not in games or games[gid]["status"] != "playing":
            bot.answer_callback_query(call.id, "Игра неактивна!", show_alert=True)
            return
        game = games[gid]
        if game["current_player"] != pid:
            bot.answer_callback_query(call.id, "❌ Не ваш ход!", show_alert=True)
            return
        
        # Удаляем сообщение с кнопками
        try:
            bot.delete_message(gid, call.message.message_id)
        except:
            pass
        
        chamber = game["chambers"][pid]
        trigger = random.randint(1, 6)
        u = get_user(pid)
        
        if u["master"]:
            trigger = random.randint(1, 5)
            bot.send_message(pid, "🎯 МАСТЕР!")
        if u["double_chance"] > 0 and game["used_double"].get(pid, 0) == 0:
            trigger = random.randint(1, 5)
            game["used_double"][pid] = 1
            update_user(pid, double_chance=u["double_chance"] - 1)
            bot.send_message(pid, "⚡ ДВОЙНОЙ ШАНС!")
        
        is_dead = (trigger == chamber)
        if is_dead and u["shields"] > 0 and game["used_shields"].get(pid, 0) == 0:
            is_dead = False
            game["used_shields"][pid] = 1
            update_user(pid, shields=u["shields"] - 1)
            bot.send_message(pid, "🛡️ ЩИТ!")
        if is_dead and u["diamond_shield"] > 0:
            is_dead = False
            update_user(pid, diamond_shield=u["diamond_shield"] - 1)
            bot.send_message(pid, "💎 АЛМАЗНЫЙ ЩИТ!")
        
        if is_dead:
            refund = 0
            if u["insurance"] > 0 and game["used_insurance"].get(pid, 0) == 0:
                refund = bet // 2
                game["used_insurance"][pid] = 1
                update_user(pid, insurance=u["insurance"] - 1)
                bot.send_message(pid, f"💰 СТРАХОВКА! +{refund} GC")
            
            game["players"].remove(pid)
            update_user(pid, losses=u["losses"] + 1, gc=u["gc"] + refund)
            update_rating_and_rewards(pid, False)
            update_chat_player(gid, pid, False)
            msg = bot.send_message(gid, f"💀 {get_name(pid)} ВЫБЫЛ!")
            delete_message_later(gid, msg.message_id, 5)
            
            if len(game["players"]) == 1:
                winner_id = game["players"][0]
                total_pot = sum(game["bets"].values())
                winner = get_user(winner_id)
                vip_mult = get_vip_multiplier(winner_id)
                win_amount = int(total_pot * vip_mult)
                settings = get_chat_settings(gid)
                if settings["winner_bonus"] > 0:
                    win_amount += settings["winner_bonus"]
                    bonus_msg = bot.send_message(gid, f"🎁 Бонус чата: +{settings['winner_bonus']} GC!")
                    delete_message_later(gid, bonus_msg.message_id, 5)
                update_user(winner_id, gc=winner["gc"] + win_amount, wins=winner["wins"] + 1)
                update_rating_and_rewards(winner_id, True)
                add_gc(winner_id, 5)
                update_chat_player(gid, winner_id, True)
                bot.edit_message_text(f"💀 {get_name(pid)} ВЫБЫЛ!\n\n🏆 ПОБЕДИТЕЛЬ: {get_name(winner_id)}\n💰 Выигрыш: {win_amount} GC", gid, game["message_id"])
                win_msg = bot.send_message(gid, f"🏆 {get_name(winner_id)} ПОБЕДИЛ! +{win_amount} GC")
                delete_message_later(gid, win_msg.message_id, 10)
                del games[gid]
                bot.answer_callback_query(call.id, "Ты выбыл")
                return
            
            game["current_player"] = game["players"][0]
            current = game["current_player"]
            total_pot = sum(game["bets"].values())
            bot.edit_message_text(f"💀 {get_name(pid)} ВЫБЫЛ!\n\nОстались: {', '.join([get_name(p) for p in game['players']])}\n💰 Банк: {total_pot} GC", gid, game["message_id"])
            # Отправляем одно сообщение с действием
            bot.send_message(gid, f"🔫 ХОД: {get_name(current)} | Ставка: {game['bets'][current]} GC\n\nВыбери действие:", 
                reply_markup=game_action_kb(gid, current, game['bets'][current]))
            bot.answer_callback_query(call.id, "Ты выбыл")
        else:
            idx = game["players"].index(pid)
            next_idx = (idx + 1) % len(game["players"])
            game["current_player"] = game["players"][next_idx]
            current = game["current_player"]
            total_pot = sum(game["bets"].values())
            bot.edit_message_text(f"🍀 {get_name(pid)} ВЫЖИЛ!\n\n💰 Банк: {total_pot} GC", gid, game["message_id"])
            # Отправляем одно сообщение с действием
            bot.send_message(gid, f"🔫 ХОД: {get_name(current)} | Ставка: {game['bets'][current]} GC\n\nВыбери действие:", 
                reply_markup=game_action_kb(gid, current, game['bets'][current]))
            bot.answer_callback_query(call.id, "Пусто! Ты выжил")
        return

# ========== ОБРАБОТЧИКИ НАСТРОЕК ==========
def promo_enter_handler(message, original_chat_id, original_message_id):
    success, msg = use_promo(message.from_user.id, message.text.upper())
    bot.send_message(message.chat.id, msg)
    bot.edit_message_reply_markup(original_chat_id, original_message_id, reply_markup=promo_menu_kb())

def create_promo_handler(message, original_chat_id, original_message_id):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        code = parts[0].upper()
        rtype = parts[1].lower()
        ramount = int(parts[2])
        max_uses = int(parts[3])
        days = int(parts[4]) if len(parts) > 4 else None
        create_promo(code, rtype, ramount, max_uses, days)
        bot.send_message(message.chat.id, f"✅ {code} создан!")
        log_admin(ADMIN_ID, "create_promo", code, f"{rtype} x{ramount}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ {e}")
    bot.edit_message_reply_markup(original_chat_id, original_message_id, reply_markup=admin_promocodes_kb())

def delete_promo_handler(message, original_chat_id, original_message_id):
    if message.from_user.id != ADMIN_ID: return
    code = message.text.upper()
    delete_promo(code)
    bot.send_message(message.chat.id, f"✅ {code} удалён!")
    log_admin(ADMIN_ID, "delete_promo", code, "")
    bot.edit_message_reply_markup(original_chat_id, original_message_id, reply_markup=admin_promocodes_kb())

def broadcast_handler(message, original_chat_id, original_message_id):
    if message.from_user.id != ADMIN_ID: return
    text = message.text
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT chat_id FROM chat_settings WHERE banned = 0")
    chats = c.fetchall()
    conn.close()
    success, fail = 0, 0
    for (cid,) in chats:
        try:
            bot.send_message(cid, f"📢 РАССЫЛКА\n\n{text}")
            success += 1
        except:
            fail += 1
    bot.send_message(ADMIN_ID, f"✅ {success} успешно, {fail} ошибок")
    log_admin(ADMIN_ID, "broadcast", f"success:{success}", text[:50])
    bot.edit_message_reply_markup(original_chat_id, original_message_id, reply_markup=admin_panel_kb())

def add_gc_handler(message, original_chat_id, original_message_id):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        uid = int(parts[0])
        amount = int(parts[1])
        add_gc(uid, amount)
        bot.send_message(message.chat.id, f"✅ {amount} GC выдано {get_name(uid)}")
        log_admin(ADMIN_ID, "add_gc", str(uid), f"{amount} gc")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ {e}")
    bot.edit_message_reply_markup(original_chat_id, original_message_id, reply_markup=admin_panel_kb())

def remove_gc_handler(message, original_chat_id, original_message_id):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        uid = int(parts[0])
        amount = int(parts[1])
        new_gc = remove_gc(uid, amount)
        bot.send_message(message.chat.id, f"✅ {amount} GC списано. Новый баланс: {new_gc}")
        log_admin(ADMIN_ID, "remove_gc", str(uid), f"{amount} gc")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ {e}")
    bot.edit_message_reply_markup(original_chat_id, original_message_id, reply_markup=admin_panel_kb())

def set_max_players_handler(message, target_chat_id, original_chat_id, original_message_id):
    try:
        val = int(message.text)
        if 2 <= val <= MAX_PLAYERS_LIMIT:
            update_chat_settings(target_chat_id, max_players=val)
            bot.send_message(message.chat.id, f"✅ Макс игроков: {val}")
            kb, info = chat_settings_kb(target_chat_id)
            bot.edit_message_text(info, original_chat_id, original_message_id, reply_markup=kb, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, f"❌ От 2 до {MAX_PLAYERS_LIMIT}")
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")

def set_min_bet_handler(message, target_chat_id, original_chat_id, original_message_id):
    try:
        val = int(message.text)
        if 1 <= val <= 1000:
            update_chat_settings(target_chat_id, min_bet=val)
            bot.send_message(message.chat.id, f"✅ Мин ставка: {val}")
            kb, info = chat_settings_kb(target_chat_id)
            bot.edit_message_text(info, original_chat_id, original_message_id, reply_markup=kb, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, "❌ От 1 до 1000")
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")

def set_max_bet_handler(message, target_chat_id, original_chat_id, original_message_id):
    try:
        val = int(message.text)
        if 10 <= val <= 10000:
            update_chat_settings(target_chat_id, max_bet=val)
            bot.send_message(message.chat.id, f"✅ Макс ставка: {val}")
            kb, info = chat_settings_kb(target_chat_id)
            bot.edit_message_text(info, original_chat_id, original_message_id, reply_markup=kb, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, "❌ От 10 до 10000")
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")

def set_bet_buttons_handler(message, target_chat_id, original_chat_id, original_message_id):
    try:
        buttons = message.text.strip()
        bets = [int(x.strip()) for x in buttons.split(',')]
        if all(1 <= b <= 10000 for b in bets) and len(bets) <= 10:
            update_chat_settings(target_chat_id, bet_buttons=buttons)
            bot.send_message(message.chat.id, f"✅ Кнопки: {buttons}")
            kb, info = chat_settings_kb(target_chat_id)
            bot.edit_message_text(info, original_chat_id, original_message_id, reply_markup=kb, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, "❌ Пример: 10,50,100,200,500,1000")
    except:
        bot.send_message(message.chat.id, "❌ Ошибка!")

def set_welcome_handler(message, target_chat_id, original_chat_id, original_message_id):
    text = message.text.strip()
    if text.lower() == "нет" or text == "":
        update_chat_settings(target_chat_id, welcome_message="")
        bot.send_message(message.chat.id, "✅ Приветствие отключено")
    else:
        update_chat_settings(target_chat_id, welcome_message=text)
        bot.send_message(message.chat.id, f"✅ Приветствие сохранено")
    kb, info = chat_settings_kb(target_chat_id)
    bot.edit_message_text(info, original_chat_id, original_message_id, reply_markup=kb, parse_mode="HTML")

def set_winner_bonus_handler(message, target_chat_id, original_chat_id, original_message_id):
    try:
        val = int(message.text)
        if 0 <= val <= 500:
            update_chat_settings(target_chat_id, winner_bonus=val)
            bot.send_message(message.chat.id, f"✅ Бонус: {val} GC")
            kb, info = chat_settings_kb(target_chat_id)
            bot.edit_message_text(info, original_chat_id, original_message_id, reply_markup=kb, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, "❌ От 0 до 500")
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")

def set_auto_kick_handler(message, target_chat_id, original_chat_id, original_message_id):
    try:
        val = int(message.text)
        if 0 <= val <= 10:
            update_chat_settings(target_chat_id, auto_kick_minutes=val)
            bot.send_message(message.chat.id, f"✅ Авто-кик: {val} мин")
            kb, info = chat_settings_kb(target_chat_id)
            bot.edit_message_text(info, original_chat_id, original_message_id, reply_markup=kb, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, "❌ От 0 до 10")
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")

def edit_ranks_handler(message, original_chat_id, original_message_id):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split(',')
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        for part in parts:
            name, rating = part.split(':')
            rating = int(rating)
            if name == "Стрелок":
                c.execute("UPDATE rank_settings SET min_rating=?, max_rating=? WHERE rank_name='Стрелок'", (rating, rating+499))
                c.execute("UPDATE rank_settings SET max_rating=? WHERE rank_name='Новичок'", (rating-1,))
            elif name == "Опытный":
                c.execute("UPDATE rank_settings SET min_rating=?, max_rating=? WHERE rank_name='Опытный'", (rating, rating+499))
            elif name == "Мастер":
                c.execute("UPDATE rank_settings SET min_rating=?, max_rating=? WHERE rank_name='Мастер'", (rating, rating+499))
            elif name == "Элита":
                c.execute("UPDATE rank_settings SET min_rating=?, max_rating=? WHERE rank_name='Элита'", (rating, rating+499))
            elif name == "Легенда":
                c.execute("UPDATE rank_settings SET min_rating=?, max_rating=? WHERE rank_name='Легенда'", (rating, 999999))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ Пороги обновлены!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ {e}")
    bot.edit_message_reply_markup(original_chat_id, original_message_id, reply_markup=admin_ranks_kb())

def edit_rank_rewards_handler(message, original_chat_id, original_message_id):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split(',')
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        for part in parts:
            name, reward = part.split(':')
            reward = int(reward)
            c.execute(f"UPDATE rank_settings SET reward_gc=? WHERE rank_name=?", (reward, name))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ Награды обновлены!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ {e}")
    bot.edit_message_reply_markup(original_chat_id, original_message_id, reply_markup=admin_ranks_kb())

def edit_rank_coeff_handler(message, original_chat_id, original_message_id):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split(',')
        win_points, loss_points = 0, 0
        for part in parts:
            name, val = part.split(':')
            if name == "Победа":
                win_points = int(val)
            elif name == "Поражение":
                loss_points = int(val)
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        c.execute("UPDATE rank_settings SET win_points=?, loss_points=?", (win_points, loss_points))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ Коэффициенты: победа +{win_points}, поражение -{loss_points}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ {e}")
    bot.edit_message_reply_markup(original_chat_id, original_message_id, reply_markup=admin_ranks_kb())

def reset_chat_rating_handler(message, original_chat_id, original_message_id):
    if message.from_user.id != ADMIN_ID: return
    try:
        chat_id = int(message.text)
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        c.execute("DELETE FROM chat_stats WHERE chat_id=?", (chat_id,))
        c.execute("INSERT INTO chat_stats (chat_id, total_games, total_bets, season_games, season_bets) VALUES (?,0,0,0,0)", (chat_id,))
        c.execute("DELETE FROM chat_players WHERE chat_id=?", (chat_id,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ Рейтинг чата сброшен!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ {e}")
    bot.edit_message_reply_markup(original_chat_id, original_message_id, reply_markup=admin_chat_rating_kb())

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    init_db()
    print("✅ Бот запущен!")
    print(f"📱 @{BOT_USERNAME}")
    print(f"👑 Admin ID: {ADMIN_ID}")
    bot.infinity_polling()