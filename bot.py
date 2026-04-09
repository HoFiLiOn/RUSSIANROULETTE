import telebot
import sqlite3
import random
import time
import threading
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8412567351:AAG7eEMXlNfDBsNZF08GD-Pr-LH-2z1txSQ"
BOT_USERNAME = "RussianRoulette_official_bot"
ADMIN_ID = 7040677455
MAX_PLAYERS_LIMIT = 15

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ========== КД ==========
game_cooldowns = {}

def check_game_cooldown(user_id):
    now = time.time()
    if user_id in game_cooldowns and now - game_cooldowns[user_id] < 3:
        return False
    game_cooldowns[user_id] = now
    return True

def delete_message_later(chat_id, message_id, delay=5):
    def delete():
        time.sleep(delay)
        try: bot.delete_message(chat_id, message_id)
        except: pass
    threading.Thread(target=delete, daemon=True).start()

def next_turn_with_delay(gid, game, delay=4):
    def next_turn():
        time.sleep(delay)
        if gid in games and games[gid]["status"] == "playing":
            current = game["current_player"]
            msg = bot.send_message(gid, f"🔫 <b>ХОД:</b> {get_name(current)} | <b>Ставка:</b> {game['bets'][current]} GC\n\nВыбери действие:", reply_markup=game_action_kb(gid))
            games[gid]["action_message_id"] = msg.message_id
    threading.Thread(target=next_turn, daemon=True).start()

def ban_user_from_chat(chat_id, user_id):
    try:
        bot.ban_chat_member(chat_id, user_id)
        return True
    except:
        return False

# ========== ИСТОРИИ ==========
MAIN_STORIES = [
    "🔫 <b>РУССКАЯ РУЛЕТКА</b>\n\nОднажды в подвале старого дома в Санкт-Петербурге собрались отчаянные игроки. Ставкой была не только GunCoin, но и собственная жизнь.",
    "🔫 <b>РУССКАЯ РУЛЕТКА</b>\n\nСтарик Гром сидит в углу, перебирая патроны. Семь пуль я пережил, хрипит он. Седьмая оставила шрам на сердце.",
    "🔫 <b>РУССКАЯ РУЛЕТКА</b>\n\nВ подвале пахнет порохом и страхом. На столе револьвер, заряженный одним патроном. Шесть гнёзд. Один шанс из шести.",
]
MISS_STORIES = ["<i>{name} медленно взводит курок. Щелчок... Пусто. Пот стекает по лицу.</i>"]
DEATH_STORIES = ["<i>{name} нажимает на курок. БАХ! Мир взрывается болью, тело оседает на пол.</i>"]
SHIELD_STORIES = ["<i>{name} нажимает на курок. БАХ! Но щит принял удар. {name} жив.</i>"]
DIAMOND_STORIES = ["<i>{name} спускает курок. БАХ! Алмазный щит треснул, но выдержал.</i>"]
INSURANCE_STORIES = ["<i>{name} спускает курок. БАХ! Страховка вернула {refund} GC.</i>"]
SPIN_STORIES = ["<i>{name} крутит барабан. Щелчки эхом разносятся по комнате. Где же пуля?</i>"]
GAME_START_STORIES = ["<i>{name} достаёт старый револьвер. Барабан заряжен. Смерть ждёт.</i>"]
WIN_STORIES = ["<i>{name} опускает револьвер. Тела павших у его ног. Выигрыш {win} GC.</i>"]
DRUNK_STORIES = ["<i>{name} пошатнулся и случайно нажал на курок в сторону {victim}... БАХ!</i>"]
BLOOD_MARK_STORIES = ["<i>{name} сжимает револьвер. На руке вспыхивает багровая метка. Пуля найдёт цель.</i>"]
REINCARNATION_STORIES = ["<i>{name} падает... но вдруг его глаза открываются. Реинкарнация сработала.</i>"]
SILENCER_STORIES = ["<i>{name} нажимает на курок. Тишина. Глушитель сделал своё дело.</i>"]
FAKE_BULLET_STORIES = ["<i>{name} нажимает на курок. БАХ! Все вздрагивают... но пули нет. Фальшивка.</i>"]

HARDCORE_DESCRIPTION = "💀 <b>ХАРДКОР РЕЖИМ</b>\n\n• У тебя только <b>1 жизнь</b>\n• Патрон <b>остаётся в барабане</b>\n• Щиты и защиты <b>НЕ РАБОТАЮТ</b>\n• При выборе \"С БАНОМ\" — проигравший получает бан"
MODE_STORIES = {"arcade": "<i>{name} усмехается. В руках револьвер с тремя патронами. Три жизни. Три шанса.</i>"}
HARDCORE_BAN_MESSAGE = "<i>Труп {name} выносят из подвала. Его больше никогда не пустят сюда.</i>"

# ========== БД ==========
def init_db():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, gc INTEGER DEFAULT 100, rating INTEGER DEFAULT 0, wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, total_games INTEGER DEFAULT 0, shields INTEGER DEFAULT 0, double_chance INTEGER DEFAULT 0, insurance INTEGER DEFAULT 0, diamond_shield INTEGER DEFAULT 0, master INTEGER DEFAULT 0, vip_level INTEGER DEFAULT 0, vip_until TEXT, last_daily TEXT, daily_streak INTEGER DEFAULT 1, banned INTEGER DEFAULT 0, blood_mark INTEGER DEFAULT 0, reincarnation INTEGER DEFAULT 0, silencer INTEGER DEFAULT 0, fake_bullet INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_settings (chat_id INTEGER PRIMARY KEY, max_players INTEGER DEFAULT 6, min_bet INTEGER DEFAULT 10, max_bet INTEGER DEFAULT 500, game_enabled INTEGER DEFAULT 1, admin_only INTEGER DEFAULT 0, owner_id INTEGER DEFAULT 0, name TEXT DEFAULT '', bet_buttons TEXT DEFAULT '10,50,100,200,500,1000', winner_bonus INTEGER DEFAULT 0, auto_kick_minutes INTEGER DEFAULT 0, banned INTEGER DEFAULT 0, drunk_shooter INTEGER DEFAULT 0, drunk_shooter_chance INTEGER DEFAULT 15, hardcore_allowed INTEGER DEFAULT 1, shields_allowed INTEGER DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_stats (chat_id INTEGER PRIMARY KEY, total_games INTEGER DEFAULT 0, total_bets INTEGER DEFAULT 0, season_games INTEGER DEFAULT 0, season_bets INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_players (chat_id INTEGER, user_id INTEGER, wins INTEGER DEFAULT 0, games INTEGER DEFAULT 0, season_wins INTEGER DEFAULT 0, season_games INTEGER DEFAULT 0, PRIMARY KEY (chat_id, user_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS seasons (id INTEGER PRIMARY KEY AUTOINCREMENT, number INTEGER DEFAULT 1, start_date TEXT, end_date TEXT, is_active INTEGER DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS rank_settings (rank_name TEXT PRIMARY KEY, min_rating INTEGER, max_rating INTEGER, reward_gc INTEGER, reward_shield INTEGER DEFAULT 0, reward_double INTEGER DEFAULT 0, reward_insurance INTEGER DEFAULT 0, reward_diamond INTEGER DEFAULT 0, reward_vip_days INTEGER DEFAULT 0, bet_bonus INTEGER DEFAULT 0, monthly_gc INTEGER DEFAULT 0, monthly_shield INTEGER DEFAULT 0, monthly_double INTEGER DEFAULT 0, monthly_insurance INTEGER DEFAULT 0, monthly_diamond INTEGER DEFAULT 0, monthly_vip_days INTEGER DEFAULT 0, win_points INTEGER DEFAULT 25, loss_points INTEGER DEFAULT 15)''')
    c.execute('''CREATE TABLE IF NOT EXISTS promocodes (code TEXT PRIMARY KEY, reward_type TEXT, reward_amount TEXT, max_uses INTEGER, used_count INTEGER DEFAULT 0, expires TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS promo_used (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, user_id INTEGER, used_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admin_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, action TEXT, target TEXT, details TEXT, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, report_type TEXT, message TEXT, status TEXT DEFAULT 'new', created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS black_market (id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT, item_type TEXT, price INTEGER, rarity TEXT, effect TEXT, effect_value INTEGER, in_stock INTEGER DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS black_market_purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_name TEXT, purchased_at TEXT)''')
    
    # Добавление колонок для старых таблиц
    for col in ["drunk_shooter", "drunk_shooter_chance", "hardcore_allowed", "shields_allowed"]:
        try: c.execute(f"ALTER TABLE chat_settings ADD COLUMN {col} INTEGER DEFAULT 0")
        except: pass
    for col in ["blood_mark", "reincarnation", "silencer", "fake_bullet"]:
        try: c.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT 0")
        except: pass
    
    # Чёрный рынок товары
    c.execute("SELECT COUNT(*) FROM black_market")
    if c.fetchone()[0] == 0:
        items = [
            ("Кровавая метка", "blood_mark", 400, "эпический", "blood_mark", 1, 1),
            ("Реинкарнация", "reincarnation", 500, "эпический", "reincarnation", 1, 1),
            ("Глушитель", "silencer", 150, "редкий", "silencer", 1, 1),
            ("Фальшивая пуля", "fake_bullet", 100, "редкий", "fake_bullet", 1, 1),
            ("Билет удвоения", "double_chance", 200, "обычный", "double_chance", 1, 1),
        ]
        for item in items:
            c.execute("INSERT INTO black_market (item_name, item_type, price, rarity, effect, effect_value, in_stock) VALUES (?, ?, ?, ?, ?, ?, ?)", item)
    
    c.execute("SELECT * FROM seasons WHERE is_active = 1")
    if not c.fetchone():
        now = datetime.now()
        c.execute("INSERT INTO seasons (number, start_date, end_date) VALUES (1, ?, ?)", (now.isoformat(), (now + timedelta(days=30)).isoformat()))
    
    c.execute("SELECT COUNT(*) FROM rank_settings")
    if c.fetchone()[0] == 0:
        default_ranks = [("Новичок",0,499,100,0,0,0,0,0,0,0,0,0,0,0,0,25,15),("Стрелок",500,999,500,1,0,0,0,0,50,100,0,0,0,0,0,25,15),("Опытный",1000,1499,1000,0,1,0,0,0,100,250,0,0,0,0,0,25,15),("Мастер",1500,1999,2000,0,0,1,0,0,200,500,1,0,0,0,0,25,15),("Элита",2000,2499,4000,0,0,0,1,0,500,1000,0,1,0,0,0,25,15),("Легенда",2500,999999,8000,0,0,0,1,14,1000,2000,0,0,1,3,0,25,15)]
        for r in default_ranks: c.execute("INSERT INTO rank_settings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", r)
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT gc, rating, wins, losses, total_games, shields, double_chance, insurance, diamond_shield, master, vip_level, vip_until, last_daily, daily_streak, banned, blood_mark, reincarnation, silencer, fake_bullet FROM users WHERE user_id = ?", (user_id,))
    u = c.fetchone()
    if not u:
        c.execute("INSERT INTO users (user_id, gc, last_daily) VALUES (?, ?, ?)", (user_id, 100, datetime.now().isoformat()))
        conn.commit()
        c.execute("SELECT gc, rating, wins, losses, total_games, shields, double_chance, insurance, diamond_shield, master, vip_level, vip_until, last_daily, daily_streak, banned, blood_mark, reincarnation, silencer, fake_bullet FROM users WHERE user_id = ?", (user_id,))
        u = c.fetchone()
    conn.close()
    return {"gc":u[0],"rating":u[1],"wins":u[2],"losses":u[3],"total_games":u[4],"shields":u[5],"double_chance":u[6],"insurance":u[7],"diamond_shield":u[8],"master":u[9],"vip_level":u[10],"vip_until":u[11],"last_daily":u[12],"daily_streak":u[13],"banned":u[14],"blood_mark":u[15],"reincarnation":u[16],"silencer":u[17],"fake_bullet":u[18]}

def update_user(user_id, **kwargs):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    for k, v in kwargs.items():
        if v is not None: c.execute(f"UPDATE users SET {k} = ? WHERE user_id = ?", (v, user_id))
    conn.commit()
    conn.close()

def add_gc(user_id, amt):
    u = get_user(user_id)
    update_user(user_id, gc=u["gc"]+amt)

def remove_gc(user_id, amt):
    u = get_user(user_id)
    ng = max(0, u["gc"]-amt)
    update_user(user_id, gc=ng)
    return ng

def get_rank_name(rating):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT rank_name FROM rank_settings WHERE min_rating <= ? AND max_rating >= ?", (rating, rating))
    r = c.fetchone()
    conn.close()
    return r[0] if r else "Новичок"

def get_rank_emoji(rating):
    if rating >= 2500: return "👑"
    elif rating >= 2000: return "🔴"
    elif rating >= 1500: return "🟠"
    elif rating >= 1000: return "🟣"
    elif rating >= 500: return "🔵"
    else: return "🟢"

def update_rating_and_rewards(user_id, won):
    u = get_user(user_id)
    if u["banned"]: return 0
    old = u["rating"]
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT win_points, loss_points FROM rank_settings LIMIT 1")
    pts = c.fetchone()
    conn.close()
    win_pts = pts[0] if pts else 25
    loss_pts = pts[1] if pts else 15
    new = max(0, old + (win_pts if won else -loss_pts))
    update_user(user_id, rating=new)
    if get_rank_name(old) != get_rank_name(new):
        r = get_rank_settings(new)
        if r["reward_gc"] > 0: add_gc(user_id, r["reward_gc"])
        if r["reward_shield"] > 0: update_user(user_id, shields=u["shields"]+r["reward_shield"])
        if r["reward_double"] > 0: update_user(user_id, double_chance=u["double_chance"]+r["reward_double"])
        if r["reward_insurance"] > 0: update_user(user_id, insurance=u["insurance"]+r["reward_insurance"])
        if r["reward_diamond"] > 0: update_user(user_id, diamond_shield=u["diamond_shield"]+r["reward_diamond"])
        if r["reward_vip_days"] > 0: update_user(user_id, vip_level=r["reward_vip_days"], vip_until=(datetime.now()+timedelta(days=r["reward_vip_days"])).isoformat())
        try: bot.send_message(user_id, f"🏆 ПОЗДРАВЛЯЮ! Ты достиг ранга {get_rank_emoji(new)} {r['name']}!\n+{r['reward_gc']} GC")
        except: pass
    return new - old

def get_chat_settings(chat_id):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT max_players, min_bet, max_bet, game_enabled, admin_only, owner_id, name, bet_buttons, winner_bonus, auto_kick_minutes, banned, drunk_shooter, drunk_shooter_chance, hardcore_allowed, shields_allowed FROM chat_settings WHERE chat_id = ?", (chat_id,))
    s = c.fetchone()
    if not s:
        c.execute("INSERT INTO chat_settings (chat_id) VALUES (?)", (chat_id,))
        conn.commit()
        s = (6,10,500,1,0,0,"","10,50,100,200,500,1000",0,0,0,0,15,1,1)
    conn.close()
    return {"max_players":s[0],"min_bet":s[1],"max_bet":s[2],"game_enabled":s[3],"admin_only":s[4],"owner_id":s[5],"name":s[6],"bet_buttons":s[7],"winner_bonus":s[8],"auto_kick_minutes":s[9],"banned":s[10],"drunk_shooter":s[11],"drunk_shooter_chance":s[12],"hardcore_allowed":s[13],"shields_allowed":s[14]}

def update_chat_settings(chat_id, **kwargs):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    for k,v in kwargs.items(): c.execute(f"UPDATE chat_settings SET {k} = ? WHERE chat_id = ?", (v, chat_id))
    conn.commit()
    conn.close()

def get_chat_stats(chat_id):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT total_games, total_bets, season_games, season_bets FROM chat_stats WHERE chat_id = ?", (chat_id,))
    s = c.fetchone()
    conn.close()
    if s: return {"total_games":s[0],"total_bets":s[1],"season_games":s[2],"season_bets":s[3]}
    return {"total_games":0,"total_bets":0,"season_games":0,"season_bets":0}

def update_chat_stats(chat_id, bet):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("UPDATE chat_stats SET total_games = total_games + 1, total_bets = total_bets + ?, season_games = season_games + 1, season_bets = season_bets + ? WHERE chat_id = ?", (bet, bet, chat_id))
    if c.rowcount == 0: c.execute("INSERT INTO chat_stats (chat_id, total_games, total_bets, season_games, season_bets) VALUES (?, 1, ?, 1, ?)", (chat_id, bet, bet))
    conn.commit()
    conn.close()

def update_chat_player(chat_id, user_id, won):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    if won: c.execute("INSERT INTO chat_players (chat_id, user_id, wins, games, season_wins, season_games) VALUES (?, ?, 1, 1, 1, 1) ON CONFLICT(chat_id, user_id) DO UPDATE SET wins = wins + 1, games = games + 1, season_wins = season_wins + 1, season_games = season_games + 1", (chat_id, user_id))
    else: c.execute("INSERT INTO chat_players (chat_id, user_id, wins, games, season_wins, season_games) VALUES (?, ?, 0, 1, 0, 1) ON CONFLICT(chat_id, user_id) DO UPDATE SET games = games + 1, season_games = season_games + 1", (chat_id, user_id))
    conn.commit()
    conn.close()

def get_chat_top_players(chat_id, limit=10):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT user_id, wins, games FROM chat_players WHERE chat_id = ? ORDER BY wins DESC LIMIT ?", (chat_id, limit))
    r = c.fetchall()
    conn.close()
    return r

def get_all_chats_rating():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT chat_id, total_games, total_bets FROM chat_stats ORDER BY (total_games * 10 + total_bets / 10) DESC LIMIT 50")
    r = c.fetchall()
    conn.close()
    return r

def get_name(uid):
    try: u = bot.get_chat(uid); return f"@{u.username}" if u.username else u.first_name
    except: return str(uid)

def get_user_link(uid):
    try:
        u = bot.get_chat(uid)
        return f"@{u.username}" if u.username else f'<a href="tg://user?id={uid}">{u.first_name}</a>'
    except: return str(uid)

def get_chat_name(cid):
    try: return bot.get_chat(cid).title or str(cid)
    except: return str(cid)

def is_chat_admin(uid, cid):
    if uid == ADMIN_ID: return True
    try: return bot.get_chat_member(cid, uid).status in ['creator','administrator']
    except: return False

def get_chat_owner(cid):
    s = get_chat_settings(cid)
    if s["owner_id"] != 0: return s["owner_id"]
    try:
        for a in bot.get_chat_administrators(cid):
            if a.status == 'creator':
                update_chat_settings(cid, owner_id=a.user.id, name=a.user.first_name)
                return a.user.id
    except: pass
    return 0

def log_admin(admin_id, action, target, details=""):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("INSERT INTO admin_logs (admin_id, action, target, details, timestamp) VALUES (?, ?, ?, ?, ?)", (admin_id, action, target, details, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def add_report(user_id, report_type, message):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("INSERT INTO reports (user_id, report_type, message, status, created_at) VALUES (?, ?, ?, 'new', ?)", (user_id, report_type, message, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_reports():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT id, user_id, report_type, message, status, created_at FROM reports ORDER BY created_at DESC")
    r = c.fetchall()
    conn.close()
    return r

def update_report_status(report_id, status):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("UPDATE reports SET status = ? WHERE id = ?", (status, report_id))
    conn.commit()
    conn.close()

# ========== ПРОМОКОДЫ ==========
def create_promo(code, reward_type, reward_amount, max_uses, expires_days=None):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    expires = (datetime.now() + timedelta(days=expires_days)).isoformat() if expires_days else None
    c.execute("INSERT OR REPLACE INTO promocodes (code, reward_type, reward_amount, max_uses, expires) VALUES (?, ?, ?, ?, ?)", (code.upper(), reward_type, str(reward_amount), max_uses, expires))
    conn.commit()
    conn.close()

def use_promo(user_id, code):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT reward_type, reward_amount, max_uses, used_count, expires FROM promocodes WHERE code = ?", (code.upper(),))
    p = c.fetchone()
    if not p: conn.close(); return False, "❌ Промокод не найден!"
    rt, ra, mu, uc, exp = p
    if exp and datetime.now() > datetime.fromisoformat(exp): conn.close(); return False, "❌ Срок действия истёк!"
    if uc >= mu: conn.close(); return False, "❌ Промокод уже использован!"
    c.execute("SELECT * FROM promo_used WHERE code = ? AND user_id = ?", (code.upper(), user_id))
    if c.fetchone(): conn.close(); return False, "❌ Вы уже использовали этот промокод!"
    
    u = get_user(user_id)
    msg = "✅ Промокод активирован!\n\n"
    
    if rt == "gc":
        update_user(user_id, gc=u["gc"] + int(ra))
        msg += f"💰 +{ra} GC"
    elif rt == "shield":
        update_user(user_id, shields=u["shields"] + int(ra))
        msg += f"🛡️ +{ra} Щит"
    elif rt == "double":
        update_user(user_id, double_chance=u["double_chance"] + int(ra))
        msg += f"⚡ +{ra} Двойной шанс"
    elif rt == "insurance":
        update_user(user_id, insurance=u["insurance"] + int(ra))
        msg += f"💰 +{ra} Страховка"
    elif rt == "diamond_shield":
        update_user(user_id, diamond_shield=u["diamond_shield"] + int(ra))
        msg += f"💎 +{ra} Алмазный щит"
    elif rt == "vip":
        update_user(user_id, vip_level=int(ra), vip_until=(datetime.now()+timedelta(days=int(ra))).isoformat())
        msg += f"👑 VIP на {ra} дней"
    elif rt == "all":
        parts = list(map(int, ra.split(',')))
        update_user(user_id, gc=u["gc"] + parts[0])
        update_user(user_id, shields=u["shields"] + parts[1])
        update_user(user_id, double_chance=u["double_chance"] + parts[2])
        update_user(user_id, insurance=u["insurance"] + parts[3])
        update_user(user_id, diamond_shield=u["diamond_shield"] + parts[4])
        if len(parts) > 5:
            update_user(user_id, vip_level=parts[5], vip_until=(datetime.now()+timedelta(days=parts[5])).isoformat())
        msg += f"💰 +{parts[0]} GC\n🛡️ +{parts[1]} Щит\n⚡ +{parts[2]} Двойной шанс\n💰 +{parts[3]} Страховка\n💎 +{parts[4]} Алмазный щит"
        if len(parts) > 5: msg += f"\n👑 VIP на {parts[5]} дней"
    
    c.execute("UPDATE promocodes SET used_count = used_count + 1 WHERE code = ?", (code.upper(),))
    c.execute("INSERT INTO promo_used (code, user_id, used_at) VALUES (?, ?, ?)", (code.upper(), user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True, msg

def get_all_promos():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT code, reward_type, reward_amount, max_uses, used_count, expires FROM promocodes")
    r = c.fetchall()
    conn.close()
    return r

def delete_promo(code):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("DELETE FROM promocodes WHERE code = ?", (code.upper(),))
    conn.commit()
    conn.close()

# ========== ЧЁРНЫЙ РЫНОК ==========
black_market_active = False
black_market_items = []

def start_black_market():
    global black_market_active, black_market_items
    black_market_active = True
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT item_name, item_type, price, rarity, effect, effect_value FROM black_market WHERE in_stock = 1 ORDER BY RANDOM() LIMIT 5")
    black_market_items = c.fetchall()
    conn.close()
    try:
        bot.send_message(ADMIN_ID, f"🌑 Чёрный рынок открыт! 15 минут.")
    except: pass

def end_black_market():
    global black_market_active
    black_market_active = False

def get_black_market_items():
    return black_market_items

def purchase_black_market_item(user_id, item_index):
    global black_market_items
    if not black_market_active:
        return False, "❌ Чёрный рынок закрыт!"
    if item_index >= len(black_market_items):
        return False, "❌ Товар не найден!"
    item = black_market_items[item_index]
    item_name, item_type, price, rarity, effect, effect_value = item
    u = get_user(user_id)
    if u["gc"] < price:
        return False, f"❌ Не хватает GC! Нужно {price}"
    remove_gc(user_id, price)
    if item_type == "shield":
        update_user(user_id, shields=u["shields"] + effect_value)
    elif item_type == "double_chance":
        update_user(user_id, double_chance=u["double_chance"] + effect_value)
    elif item_type == "insurance":
        update_user(user_id, insurance=u["insurance"] + effect_value)
    elif item_type == "diamond_shield":
        update_user(user_id, diamond_shield=u["diamond_shield"] + effect_value)
    elif item_type == "blood_mark":
        update_user(user_id, blood_mark=u["blood_mark"] + effect_value)
    elif item_type == "reincarnation":
        update_user(user_id, reincarnation=u["reincarnation"] + effect_value)
    elif item_type == "silencer":
        update_user(user_id, silencer=u["silencer"] + effect_value)
    elif item_type == "fake_bullet":
        update_user(user_id, fake_bullet=u["fake_bullet"] + effect_value)
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("INSERT INTO black_market_purchases (user_id, item_name, purchased_at) VALUES (?, ?, ?)", (user_id, item_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True, f"✅ Куплено: {item_name} за {price} GC! Редкость: {rarity}"

# ========== КЛАВИАТУРЫ ==========
def private_main_menu(uid, page=1):
    kb = InlineKeyboardMarkup(row_width=1)
    if page == 1:
        kb.add(InlineKeyboardButton("📊 Стата", callback_data="stats"))
        kb.add(InlineKeyboardButton("🎁 Бонус", callback_data="daily"))
        kb.add(InlineKeyboardButton("🛒 Магазин", callback_data="shop_1"))
        if black_market_active:
            kb.add(InlineKeyboardButton("🌑 Чёрный рынок", callback_data="black_market"))
        kb.add(InlineKeyboardButton("➡️ Далее", callback_data="menu_page_2"))
    elif page == 2:
        kb.add(InlineKeyboardButton("🏆 Топы", callback_data="top_menu"))
        kb.add(InlineKeyboardButton("🎮 Активные игры", callback_data="active_games"))
        kb.add(InlineKeyboardButton("⚙️ Настройки чатов", callback_data="my_chats_settings"))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="menu_page_1"))
        kb.add(InlineKeyboardButton("➡️ Далее", callback_data="menu_page_3"))
    elif page == 3:
        kb.add(InlineKeyboardButton("📢 Поддержать", callback_data="donate_menu"))
        kb.add(InlineKeyboardButton("❓ Помощь", callback_data="help_menu"))
        kb.add(InlineKeyboardButton("📝 Жалоба", callback_data="report_menu"))
        kb.add(InlineKeyboardButton("🎫 Промокод", callback_data="enter_promo"))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="menu_page_2"))
    if uid == ADMIN_ID:
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
        1: [("🛡️ Щит", "buy_shield", 100), ("💎 Алмазный щит", "buy_diamond_shield", 400)],
        2: [("⚡ Двойной шанс", "buy_double", 150), ("💰 Страховка", "buy_insurance", 200)],
        3: [("🎯 Мастер", "buy_master", 250), ("💊 Аптечка", "buy_medkit", 80)],
        4: [("🎲 Счастливый билет", "buy_lucky", 90), ("👑 VIP 3 дня", "buy_vip_3", 500)],
        5: [("👑 VIP 7 дней", "buy_vip_7", 1200), ("👑 VIP 30 дней", "buy_vip_30", 3000)]
    }
    for name, cb, price in items.get(page, []):
        kb.add(InlineKeyboardButton(f"{name} — {price} GC", callback_data=cb))
    nav = []
    if page > 1: nav.append(InlineKeyboardButton("◀️", callback_data=f"shop_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page}/5", callback_data="none"))
    if page < 5: nav.append(InlineKeyboardButton("▶️", callback_data=f"shop_{page+1}"))
    kb.row(*nav)
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def black_market_kb():
    items = get_black_market_items()
    kb = InlineKeyboardMarkup(row_width=1)
    for i, item in enumerate(items):
        item_name, item_type, price, rarity, effect, effect_value = item
        emoji = "🟢" if rarity == "обычный" else "🟣" if rarity == "редкий" else "🟠" if rarity == "эпический" else "🔴"
        kb.add(InlineKeyboardButton(f"{emoji} {item_name} — {price} GC", callback_data=f"bm_buy_{i}"))
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

def help_menu_kb():
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(InlineKeyboardButton("1️⃣ Основное", callback_data="help_page_1"))
    kb.add(InlineKeyboardButton("2️⃣ Магазин", callback_data="help_page_2"))
    kb.add(InlineKeyboardButton("3️⃣ Рейтинг", callback_data="help_page_3"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def report_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🚫 На игрока", callback_data="report_player"))
    kb.add(InlineKeyboardButton("🐛 Баг", callback_data="report_bug"))
    kb.add(InlineKeyboardButton("💰 Финансы", callback_data="report_finance"))
    kb.add(InlineKeyboardButton("📢 Другое", callback_data="report_other"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def admin_panel_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"))
    kb.add(InlineKeyboardButton("🎫 Промокоды", callback_data="admin_promocodes"))
    kb.add(InlineKeyboardButton("📝 Жалобы", callback_data="admin_reports"))
    kb.add(InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"))
    kb.add(InlineKeyboardButton("🌑 Чёрный рынок", callback_data="admin_black_market"))
    kb.add(InlineKeyboardButton("💰 Выдать GC", callback_data="admin_add_gc"))
    kb.add(InlineKeyboardButton("💸 Забрать GC", callback_data="admin_remove_gc"))
    kb.add(InlineKeyboardButton("🎁 Выдать предмет", callback_data="admin_give_item"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def admin_promocodes_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("➕ Создать", callback_data="admin_create_promo"))
    kb.add(InlineKeyboardButton("📋 Список", callback_data="admin_list_promos"))
    kb.add(InlineKeyboardButton("🗑️ Удалить", callback_data="admin_delete_promo"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    return kb

def my_chats_kb(uid):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT chat_id, name FROM chat_settings WHERE owner_id = ?", (uid,))
    chats = c.fetchall()
    conn.close()
    kb = InlineKeyboardMarkup(row_width=1)
    for cid, name in chats:
        try: cn = bot.get_chat(cid).title or str(cid)
        except: cn = name or str(cid)
        kb.add(InlineKeyboardButton(f"📌 {cn}", callback_data=f"chat_settings_{cid}"))
    if not chats: kb.add(InlineKeyboardButton("❌ Нет чатов", callback_data="none"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def chat_settings_kb(cid):
    s = get_chat_settings(cid)
    kb = InlineKeyboardMarkup(row_width=1)
    try: cn = bot.get_chat(cid).title or str(cid)
    except: cn = s['name'] or str(cid)
    stats = get_chat_stats(cid)
    rating = get_chat_rating(cid)
    info = f"📌 <b>{cn}</b>\n🆔 ID: <code>{cid}</code>\n🎮 Игр: {stats['total_games']}\n💰 Ставок: {stats['total_bets']} GC\n📊 Рейтинг: {rating}\n\n⚙️ НАСТРОЙКИ:"
    kb.add(InlineKeyboardButton(f"👥 Макс игроков: {s['max_players']}", callback_data=f"set_max_players_{cid}"))
    kb.add(InlineKeyboardButton(f"💰 Мин ставка: {s['min_bet']} GC", callback_data=f"set_min_bet_{cid}"))
    kb.add(InlineKeyboardButton(f"💎 Макс ставка: {s['max_bet']} GC", callback_data=f"set_max_bet_{cid}"))
    kb.add(InlineKeyboardButton(f"🎮 Кнопки: {s['bet_buttons']}", callback_data=f"set_bet_buttons_{cid}"))
    kb.add(InlineKeyboardButton(f"🎮 Игры: {'✅' if s['game_enabled'] else '❌'}", callback_data=f"toggle_game_{cid}"))
    kb.add(InlineKeyboardButton(f"👑 Только админы: {'✅' if s['admin_only'] else '❌'}", callback_data=f"toggle_admin_only_{cid}"))
    kb.add(InlineKeyboardButton(f"🎁 Бонус: {s['winner_bonus']} GC", callback_data=f"set_winner_bonus_{cid}"))
    kb.add(InlineKeyboardButton(f"🛡️ Авто-кик: {s['auto_kick_minutes']} мин", callback_data=f"set_auto_kick_{cid}"))
    kb.add(InlineKeyboardButton(f"🔫 Пьяный стрелок: {'✅' if s['drunk_shooter'] else '❌'} ({s['drunk_shooter_chance']}%)", callback_data=f"toggle_drunk_{cid}"))
    kb.add(InlineKeyboardButton(f"💀 Хардкор: {'✅' if s['hardcore_allowed'] else '❌'}", callback_data=f"toggle_hardcore_{cid}"))
    kb.add(InlineKeyboardButton(f"🛡️ Защиты: {'✅' if s['shields_allowed'] else '❌'}", callback_data=f"toggle_shields_{cid}"))
    kb.add(InlineKeyboardButton("🔄 Сбросить статистику", callback_data=f"reset_stats_{cid}"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="my_chats_settings"))
    return kb, info

def game_lobby_kb(cid):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("➕ Присоединиться", callback_data=f"join_{cid}"))
    kb.add(InlineKeyboardButton("❌ Отменить игру", callback_data=f"cancel_game_{cid}"))
    return kb

def game_start_kb(cid):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🚀 Начать игру", callback_data=f"start_game_{cid}"))
    kb.add(InlineKeyboardButton("➕ Присоединиться", callback_data=f"join_{cid}"))
    kb.add(InlineKeyboardButton("❌ Отменить игру", callback_data=f"cancel_game_{cid}"))
    return kb

def game_action_kb(cid):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("🔫 Выстрелить", callback_data=f"game_shoot_{cid}"))
    kb.add(InlineKeyboardButton("🔄 Крутить", callback_data=f"game_spin_{cid}"))
    return kb

def bet_kb(cid):
    s = get_chat_settings(cid)
    kb = InlineKeyboardMarkup(row_width=3)
    for b in [int(x.strip()) for x in s['bet_buttons'].split(',')]:
        if s['min_bet'] <= b <= s['max_bet']:
            kb.add(InlineKeyboardButton(f"{b} GC", callback_data=f"place_bet_{cid}_{b}"))
    return kb

def mode_choice_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("🎲 Аркадный (3 жизни)", callback_data="mode_arcade"))
    kb.add(InlineKeyboardButton("💀 Хардкор", callback_data="mode_hardcore"))
    return kb

def hardcore_ban_choice_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("⚡ С баном", callback_data="mode_hardcore_ban"))
    kb.add(InlineKeyboardButton("🛡️ Без бана", callback_data="mode_hardcore_noban"))
    return kb

def get_help_text(page):
    if page == 1:
        return "🔫 <b>РУССКАЯ РУЛЕТКА — ПОМОЩЬ</b>\n\n<b>КАК ИГРАТЬ:</b>\n• /game — создать лобби\n• Другие нажимают «Присоединиться»\n• Каждый делает ставку в GC\n• Ход: 🔫 Выстрелить или 🔄 Крутить\n• Пусто → продолжаешь, патрон → выбываешь\n• Последний выживший забирает ВЕСЬ банк!\n\n<b>РЕЖИМЫ:</b>\n🎲 Аркадный: 3 жизни, защиты работают\n💀 Хардкор: 1 жизнь, защиты НЕ работают"
    elif page == 2:
        return "🔫 <b>МАГАЗИН</b>\n\n🛡️ Щит (100 GC) — спасает от 1 патрона\n💎 Алмазный щит (400 GC) — 3 защиты\n⚡ Двойной шанс (150 GC) — +10% к удаче\n💰 Страховка (200 GC) — возврат 50% ставки\n🎯 Мастер (250 GC) — +5% к удаче навсегда\n💊 Аптечка (80 GC) — +50 GC\n🎲 Лотерея (90 GC) — случайный приз\n👑 VIP — +20-50% к выигрышу"
    else:
        return "🔫 <b>РЕЙТИНГ</b>\n\nЗа победу: +25 очков\nЗа поражение: -15 очков\n\nРанги:\n🟢 Новичок (0)\n🔵 Стрелок (500)\n🟣 Опытный (1000)\n🟠 Мастер (1500)\n🔴 Элита (2000)\n👑 Легенда (2500)"

def get_welcome_text():
    return "🔫 <b>РУССКАЯ РУЛЕТКА</b>\n\nПривет! Я бот для игры в Русскую рулетку.\n\n<b>🎲 КАК ИГРАТЬ:</b>\n• Напиши /game — создать лобби\n• Другие присоединяются по кнопке\n• Делаешь ставку в GC\n• Стреляешь, выигрываешь банк!"

# ========== ИГРЫ ==========
games = {}
auto_kick_timers = {}

def start_auto_kick_timer(cid, uid):
    s = get_chat_settings(cid)
    if s['auto_kick_minutes'] <= 0: return
    def kick():
        if cid in games and games[cid]["status"] == "waiting" and uid in games[cid]["players"] and uid not in games[cid]["bets"]:
            games[cid]["players"].remove(uid)
            msg = bot.send_message(cid, f"⏰ {get_user_link(uid)} удалён за бездействие")
            delete_message_later(cid, msg.message_id, 5)
            update_lobby_message(cid)
    t = threading.Timer(s['auto_kick_minutes']*60, kick)
    t.daemon = True
    t.start()
    if cid not in auto_kick_timers: auto_kick_timers[cid] = []
    auto_kick_timers[cid].append(t)

def cancel_auto_kick_timers(cid):
    if cid in auto_kick_timers:
        for t in auto_kick_timers[cid]: t.cancel()
        del auto_kick_timers[cid]

def update_lobby_message(cid):
    g = games.get(cid)
    if not g: return
    all_bets = all(p in g["bets"] for p in g["players"])
    plist = []
    for p in g["players"]:
        if p in g["bets"]: plist.append(f"• {get_user_link(p)} — {g['bets'][p]} GC")
        else: plist.append(f"• {get_user_link(p)} — ожидает")
    total = sum(g["bets"].values()) if g["bets"] else 0
    mode_name = "🎲 Аркадный" if g.get("mode") == "arcade" else f"💀 Хардкор ({'бан' if g.get('hardcore_ban', False) else 'без бана'})"
    text = f"🎮 <b>ЛОББИ</b> | {mode_name}\n\nСоздатель: {get_user_link(g['creator'])}\nУчастники ({len(g['players'])}/{g['max_players']}):\n" + "\n".join(plist) + f"\n\n💰 Банк: {total} GC"
    if not all_bets: text += f"\n\n⚠️ Ожидаем ставки..."
    try: bot.edit_message_text(text, cid, g["message_id"], reply_markup=game_lobby_kb(cid) if not all_bets else game_start_kb(cid), parse_mode="HTML")
    except: pass

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid, cid = m.from_user.id, m.chat.id
    init_db()
    if get_user(uid)["banned"]: bot.send_message(cid, "❌ Вы забанены!"); return
    if m.chat.type == "private":
        bot.send_message(cid, random.choice(MAIN_STORIES), reply_markup=private_main_menu(uid))
    else:
        update_chat_settings(cid, name=m.chat.title)
        o = get_chat_owner(cid)
        if o: update_chat_settings(cid, owner_id=o)
        bot.send_message(cid, get_welcome_text(), reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🎮 Создать игру", callback_data="create_game")))

@bot.message_handler(commands=['game'])
def game_cmd(m):
    uid, cid = m.from_user.id, m.chat.id
    if m.chat.type == "private": bot.send_message(cid, "❌ Игры только в чатах!"); return
    if get_user(uid)["banned"]: bot.send_message(cid, "❌ Вы забанены!"); return
    s = get_chat_settings(cid)
    if s["banned"] or not s['game_enabled']: bot.send_message(cid, "❌ Игры отключены!"); return
    if cid in games: bot.send_message(cid, "❌ Игра уже есть!"); return
    bot.send_message(cid, f"{get_user_link(uid)} создаёт игру. Выберите режим:", reply_markup=mode_choice_kb())

@bot.message_handler(commands=['balance'])
def balance_cmd(m):
    if m.chat.type != "private": bot.send_message(m.chat.id, "❌ Используй в ЛС!"); return
    u = get_user(m.from_user.id)
    if u["banned"]: bot.reply_to(m, "❌ Вы забанены!"); return
    bot.reply_to(m, f"<b>📊 СТАТА</b>\n\n🔫 GC: {u['gc']}\n🏆 Рейтинг: {u['rating']}\n🏅 Ранг: {get_rank_emoji(u['rating'])} {get_rank_name(u['rating'])}\n📈 Побед: {u['wins']} | Поражений: {u['losses']}\n🎮 Игр: {u['total_games']}\n🛡️ Щитов: {u['shields']} | Алмазных: {u['diamond_shield']}")

@bot.message_handler(commands=['daily'])
def daily_cmd(m):
    if m.chat.type != "private": bot.send_message(m.chat.id, "❌ Используй в ЛС!"); return
    u = get_user(m.from_user.id)
    if u["banned"]: bot.reply_to(m, "❌ Вы забанены!"); return
    last = datetime.fromisoformat(u["last_daily"]) if u["last_daily"] else datetime.min
    now = datetime.now()
    if now - last < timedelta(days=1): h = 24 - (now-last).seconds//3600; bot.reply_to(m, f"⏰ Бонус через {h} ч"); return
    bonus = 50
    if u["daily_streak"] >= 7: bonus += 200; update_user(m.from_user.id, daily_streak=1)
    else: update_user(m.from_user.id, daily_streak=u["daily_streak"]+1)
    update_user(m.from_user.id, gc=u["gc"]+bonus, last_daily=now.isoformat())
    bot.reply_to(m, f"🎁 +{bonus} GC\n💰 Баланс: {u['gc']+bonus} GC")

@bot.message_handler(commands=['shop'])
def shop_cmd(m):
    if m.chat.type != "private": bot.send_message(m.chat.id, "❌ Используй в ЛС!"); return
    if get_user(m.from_user.id)["banned"]: bot.reply_to(m, "❌ Вы забанены!"); return
    bot.send_message(m.chat.id, "<b>🛒 МАГАЗИН</b>", reply_markup=shop_kb(1))

@bot.message_handler(commands=['top'])
def top_cmd(m):
    if m.chat.type != "private": bot.send_message(m.chat.id, "❌ Используй в ЛС!"); return
    bot.send_message(m.chat.id, "<b>🏆 ТОПЫ</b>", reply_markup=top_menu_kb())

@bot.message_handler(commands=['promo'])
def promo_cmd(m):
    if m.chat.type != "private": bot.send_message(m.chat.id, "❌ Используй в ЛС!"); return
    args = m.text.split()
    if len(args) < 2: bot.reply_to(m, "Использование: /promo КОД"); return
    ok, msg = use_promo(m.from_user.id, args[1].upper())
    bot.reply_to(m, msg)

@bot.message_handler(commands=['donate'])
def donate_cmd(m):
    if m.chat.type != "private": bot.send_message(m.chat.id, "❌ Используй в ЛС!"); return
    bot.send_message(m.chat.id, "<b>💳 ПОДДЕРЖАТЬ</b>\n\n10 ₽ = 350 GC\n\nКарта: 2202 2081 8206 1235\nDonationAlerts: https://www.donationalerts.com/r/FxHoFiLiOn", reply_markup=donate_menu_kb())

@bot.message_handler(commands=['help'])
def help_cmd(m):
    if m.chat.type != "private": bot.send_message(m.chat.id, "❌ Используй в ЛС!"); return
    bot.send_message(m.chat.id, get_help_text(1), reply_markup=help_menu_kb())

@bot.message_handler(commands=['admin'])
def admin_cmd(m):
    if m.from_user.id != ADMIN_ID: bot.send_message(m.chat.id, "❌ Нет доступа!"); return
    if m.chat.type != "private": bot.send_message(m.chat.id, "❌ Используй в ЛС!"); return
    bot.send_message(m.chat.id, "👑 АДМИН ПАНЕЛЬ", reply_markup=admin_panel_kb())

@bot.callback_query_handler(func=lambda c: True)
def handle_callback(call):
    global games, black_market_active
    uid, cid, mid = call.from_user.id, call.message.chat.id, call.message.message_id
    is_private = (cid == uid)
    u = get_user(uid)
    if u["banned"] and not call.data.startswith("admin"):
        bot.answer_callback_query(call.id, "❌ Вы забанены!", show_alert=True)
        return
    
    # Навигация
    if call.data == "back":
        if is_private:
            bot.edit_message_text(random.choice(MAIN_STORIES), cid, mid, reply_markup=private_main_menu(uid))
        else:
            bot.edit_message_text(get_welcome_text(), cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🎮 Создать игру", callback_data="create_game")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "menu_page_1":
        bot.edit_message_text(random.choice(MAIN_STORIES), cid, mid, reply_markup=private_main_menu(uid, page=1))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "menu_page_2":
        bot.edit_message_text(random.choice(MAIN_STORIES), cid, mid, reply_markup=private_main_menu(uid, page=2))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "menu_page_3":
        bot.edit_message_text(random.choice(MAIN_STORIES), cid, mid, reply_markup=private_main_menu(uid, page=3))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "none":
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "help_menu":
        bot.edit_message_text(get_help_text(1), cid, mid, reply_markup=help_menu_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data in ["help_page_1","help_page_2","help_page_3"]:
        p = int(call.data.split("_")[2])
        bot.edit_message_text(get_help_text(p), cid, mid, reply_markup=help_menu_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "donate_menu":
        bot.edit_message_text("💳 ПОДДЕРЖАТЬ\n\n10 ₽ = 350 GC", cid, mid, reply_markup=donate_menu_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "donate_card":
        bot.edit_message_text("💳 КАРТА\n\n2202 2081 8206 1235", cid, mid, reply_markup=donate_menu_kb())
        bot.answer_callback_query(call.id)
        return
    
    # Стата
    if call.data == "stats":
        bot.edit_message_text(f"<b>📊 СТАТА</b>\n\n🔫 GC: {u['gc']}\n🏆 Рейтинг: {u['rating']}\n🏅 Ранг: {get_rank_emoji(u['rating'])} {get_rank_name(u['rating'])}\n📈 Побед: {u['wins']} | Поражений: {u['losses']}\n🎮 Игр: {u['total_games']}", cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        bot.answer_callback_query(call.id)
        return
    
    # Ежедневный бонус
    if call.data == "daily":
        last = datetime.fromisoformat(u["last_daily"]) if u["last_daily"] else datetime.min
        now = datetime.now()
        if now - last < timedelta(days=1):
            h = 24 - (now-last).seconds//3600
            bot.answer_callback_query(call.id, f"⏰ Бонус через {h} ч", show_alert=True)
            return
        bonus = 50
        if u["daily_streak"] >= 7:
            bonus += 200
            update_user(uid, daily_streak=1)
        else:
            update_user(uid, daily_streak=u["daily_streak"]+1)
        update_user(uid, gc=u["gc"]+bonus, last_daily=now.isoformat())
        bot.edit_message_text(f"🎁 +{bonus} GC\n💰 Баланс: {u['gc']+bonus} GC", cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        bot.answer_callback_query(call.id)
        return
    
    # Магазин
    if call.data.startswith("shop_"):
        p = int(call.data.split("_")[1])
        bot.edit_message_text(f"<b>🛒 МАГАЗИН — {p}/5</b>", cid, mid, reply_markup=shop_kb(p))
        bot.answer_callback_query(call.id)
        return
    
    buy_items = {
        "buy_shield": ("shields", 100, "Щит"),
        "buy_diamond_shield": ("diamond_shield", 400, "Алмазный щит"),
        "buy_double": ("double_chance", 150, "Двойной шанс"),
        "buy_insurance": ("insurance", 200, "Страховка")
    }
    if call.data in buy_items:
        key, price, name = buy_items[call.data]
        if u["gc"] >= price:
            update_user(uid, gc=u["gc"]-price, **{key: u[key] + 1})
            bot.answer_callback_query(call.id, f"✅ {name} куплен!", show_alert=True)
            bot.edit_message_text(f"✅ {name} куплен!", cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        else:
            bot.answer_callback_query(call.id, f"❌ Нужно {price} GC!", show_alert=True)
        return
    
    if call.data == "buy_master":
        if u["master"]:
            bot.answer_callback_query(call.id, "❌ Уже есть мастер!", show_alert=True)
        elif u["gc"] >= 250:
            update_user(uid, gc=u["gc"]-250, master=1)
            bot.answer_callback_query(call.id, "✅ Мастер куплен!", show_alert=True)
            bot.edit_message_text("🎯 Мастер куплен!", cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        else:
            bot.answer_callback_query(call.id, "❌ Нужно 250 GC!", show_alert=True)
        return
    
    if call.data == "buy_medkit":
        if u["gc"] >= 80:
            update_user(uid, gc=u["gc"]-80)
            add_gc(uid, 50)
            bot.answer_callback_query(call.id, "✅ +50 GC", show_alert=True)
            bot.edit_message_text("💊 Аптечка! +50 GC", cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        else:
            bot.answer_callback_query(call.id, "❌ Нужно 80 GC!", show_alert=True)
        return
    
    if call.data == "buy_lucky":
        if u["gc"] >= 90:
            update_user(uid, gc=u["gc"]-90)
            pr = random.choice([20,50,100,200,"shield","double","insurance"])
            if pr == "shield":
                update_user(uid, shields=u["shields"]+1)
                msg = "🛡️ Щит"
            elif pr == "double":
                update_user(uid, double_chance=u["double_chance"]+1)
                msg = "⚡ Двойной шанс"
            elif pr == "insurance":
                update_user(uid, insurance=u["insurance"]+1)
                msg = "💰 Страховка"
            else:
                add_gc(uid, pr)
                msg = f"{pr} GC"
            bot.answer_callback_query(call.id, f"✅ {msg}!", show_alert=True)
            bot.edit_message_text(f"🎲 Лотерея! Выпало: {msg}", cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        else:
            bot.answer_callback_query(call.id, "❌ Нужно 90 GC!", show_alert=True)
        return
    
    if call.data in ["buy_vip_3","buy_vip_7","buy_vip_30"]:
        days = 3 if call.data=="buy_vip_3" else 7 if call.data=="buy_vip_7" else 30
        price = 500 if days==3 else 1200 if days==7 else 3000
        if u["gc"] >= price:
            update_user(uid, gc=u["gc"]-price, vip_level=days, vip_until=(datetime.now()+timedelta(days=days)).isoformat())
            bot.answer_callback_query(call.id, f"✅ VIP {days} дней!", show_alert=True)
            bot.edit_message_text(f"👑 VIP на {days} дней!", cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        else:
            bot.answer_callback_query(call.id, f"❌ Нужно {price} GC!", show_alert=True)
        return
    
    # Чёрный рынок
    if call.data == "black_market":
        if not black_market_active:
            bot.answer_callback_query(call.id, "🌑 Чёрный рынок закрыт!", show_alert=True)
            return
        items = get_black_market_items()
        if not items:
            bot.edit_message_text("🌑 Товаров нет", cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        else:
            text = "<b>🌑 ЧЁРНЫЙ РЫНОК</b>\n\n"
            for i, item in enumerate(items):
                item_name, item_type, price, rarity, effect, effect_value = item
                emoji = "🟢" if rarity == "обычный" else "🟣" if rarity == "редкий" else "🟠" if rarity == "эпический" else "🔴"
                text += f"{emoji} {item_name} — {price} GC\n"
            bot.edit_message_text(text, cid, mid, reply_markup=black_market_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("bm_buy_"):
        if not black_market_active:
            bot.answer_callback_query(call.id, "🌑 Чёрный рынок закрыт!", show_alert=True)
            return
        idx = int(call.data.split("_")[2])
        success, msg = purchase_black_market_item(uid, idx)
        bot.answer_callback_query(call.id, msg, show_alert=True)
        if success:
            bot.edit_message_text(f"✅ {msg}", cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        return
    
    # Топы
    if call.data == "top_menu":
        bot.edit_message_text("<b>🏆 ТОПЫ</b>", cid, mid, reply_markup=top_menu_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "top_rating":
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        c.execute("SELECT user_id, rating, wins FROM users WHERE banned = 0 ORDER BY rating DESC LIMIT 10")
        top = c.fetchall()
        conn.close()
        text = "<b>🏆 ТОП ПО РЕЙТИНГУ</b>\n\n"
        for i, (uid2, r, w) in enumerate(top, 1):
            text += f"{i}. {get_user_link(uid2)} — {r}, {w} побед\n"
        bot.edit_message_text(text, cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="top_menu")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "top_gc":
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        c.execute("SELECT user_id, gc, wins FROM users WHERE banned = 0 ORDER BY gc DESC LIMIT 10")
        top = c.fetchall()
        conn.close()
        text = "<b>💰 ТОП ПО GC</b>\n\n"
        for i, (uid2, gc, w) in enumerate(top, 1):
            text += f"{i}. {get_user_link(uid2)} — {gc} GC\n"
        bot.edit_message_text(text, cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="top_menu")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "top_wins":
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        c.execute("SELECT user_id, wins, rating FROM users WHERE banned = 0 ORDER BY wins DESC LIMIT 10")
        top = c.fetchall()
        conn.close()
        text = "<b>🎮 ТОП ПО ПОБЕДАМ</b>\n\n"
        for i, (uid2, w, r) in enumerate(top, 1):
            text += f"{i}. {get_user_link(uid2)} — {w} побед\n"
        bot.edit_message_text(text, cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="top_menu")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "top_chats":
        chats = get_all_chats_rating()
        text = "<b>🏆 ТОП ЧАТОВ</b>\n\n"
        for i, (cid2, g, b) in enumerate(chats[:10], 1):
            text += f"{i}. {get_chat_name(cid2)}\n"
        bot.edit_message_text(text, cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="top_menu")))
        bot.answer_callback_query(call.id)
        return
    
    # Промокоды
    if call.data == "enter_promo":
        bot.send_message(uid, "Введите промокод:")
        bot.register_next_step_handler_by_chat_id(uid, lambda m: promo_enter_handler(m, cid, mid))
        bot.answer_callback_query(call.id)
        return
    
    # Жалобы
    if call.data == "report_menu":
        bot.edit_message_text("<b>📝 ЖАЛОБА</b>\n\nВыберите тип:", cid, mid, reply_markup=report_menu_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data in ["report_player","report_bug","report_finance","report_other"]:
        types = {"report_player":"на игрока","report_bug":"баг","report_finance":"финансы","report_other":"другое"}
        bot.send_message(uid, f"Опишите жалобу ({types[call.data]}):")
        bot.register_next_step_handler_by_chat_id(uid, lambda m: report_text_handler(m, call.data, cid, mid))
        bot.answer_callback_query(call.id)
        return
    
    # Настройки чатов
    if call.data == "my_chats_settings":
        bot.edit_message_text("<b>⚙️ НАСТРОЙКИ ЧАТОВ</b>", cid, mid, reply_markup=my_chats_kb(uid))
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("chat_settings_"):
        tcid = int(call.data.split("_")[2])
        s = get_chat_settings(tcid)
        if s["owner_id"] != uid and uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Только владелец!", show_alert=True)
            return
        kb, info = chat_settings_kb(tcid)
        bot.edit_message_text(info, cid, mid, reply_markup=kb, parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("toggle_drunk_"):
        tcid = int(call.data.split("_")[2])
        s = get_chat_settings(tcid)
        if s["owner_id"] != uid and uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Только владелец!", show_alert=True)
            return
        new_val = 0 if s["drunk_shooter"] else 1
        update_chat_settings(tcid, drunk_shooter=new_val)
        bot.answer_callback_query(call.id, f"Пьяный стрелок {'вкл' if new_val else 'выкл'}")
        kb, info = chat_settings_kb(tcid)
        bot.edit_message_text(info, cid, mid, reply_markup=kb, parse_mode="HTML")
        return
    
    if call.data.startswith("toggle_hardcore_"):
        tcid = int(call.data.split("_")[2])
        s = get_chat_settings(tcid)
        if s["owner_id"] != uid and uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Только владелец!", show_alert=True)
            return
        new_val = 0 if s["hardcore_allowed"] else 1
        update_chat_settings(tcid, hardcore_allowed=new_val)
        bot.answer_callback_query(call.id, f"Хардкор {'разрешён' if new_val else 'запрещён'}")
        kb, info = chat_settings_kb(tcid)
        bot.edit_message_text(info, cid, mid, reply_markup=kb, parse_mode="HTML")
        return
    
    if call.data.startswith("toggle_shields_"):
        tcid = int(call.data.split("_")[2])
        s = get_chat_settings(tcid)
        if s["owner_id"] != uid and uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Только владелец!", show_alert=True)
            return
        new_val = 0 if s["shields_allowed"] else 1
        update_chat_settings(tcid, shields_allowed=new_val)
        bot.answer_callback_query(call.id, f"Защиты {'разрешены' if new_val else 'запрещены'}")
        kb, info = chat_settings_kb(tcid)
        bot.edit_message_text(info, cid, mid, reply_markup=kb, parse_mode="HTML")
        return
    
    if call.data.startswith("reset_stats_"):
        tcid = int(call.data.split("_")[2])
        s = get_chat_settings(tcid)
        if s["owner_id"] != uid and uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Только владелец!", show_alert=True)
            return
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        c.execute("DELETE FROM chat_stats WHERE chat_id = ?", (tcid,))
        c.execute("INSERT INTO chat_stats (chat_id, total_games, total_bets, season_games, season_bets) VALUES (?, 0, 0, 0, 0)", (tcid,))
        c.execute("DELETE FROM chat_players WHERE chat_id = ?", (tcid,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "✅ Статистика сброшена!")
        kb, info = chat_settings_kb(tcid)
        bot.edit_message_text(info, cid, mid, reply_markup=kb, parse_mode="HTML")
        return
    
    if call.data == "active_games":
        user_games = []
        for gid, g in games.items():
            if uid in g["players"] and g["status"] == "playing":
                user_games.append(f"📌 {get_chat_name(gid)} — ход: {'✅' if g['current_player'] == uid else '❌'}")
        text = "🎮 Ваши игры:\n" + "\n".join(user_games) if user_games else "🎮 Нет активных игр"
        bot.edit_message_text(text, cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back")))
        bot.answer_callback_query(call.id)
        return
    
    # ========== АДМИН-ПАНЕЛЬ ==========
    if call.data == "admin_panel":
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён!", show_alert=True)
            return
        bot.edit_message_text("👑 АДМИН ПАНЕЛЬ", cid, mid, reply_markup=admin_panel_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_stats":
        if uid != ADMIN_ID: return
        conn = sqlite3.connect("roulette.db")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users WHERE banned = 0")
        users = c.fetchone()[0]
        c.execute("SELECT SUM(total_games) FROM users")
        games_total = c.fetchone()[0] or 0
        conn.close()
        bot.edit_message_text(f"<b>📊 СТАТИСТИКА</b>\n\n👥 Игроков: {users}\n🎮 Игр: {games_total}", cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_promocodes":
        if uid != ADMIN_ID: return
        bot.edit_message_text("🎫 ПРОМОКОДЫ", cid, mid, reply_markup=admin_promocodes_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_create_promo":
        if uid != ADMIN_ID: return
        bot.send_message(uid, "Введите: КОД ТИП КОЛ-ВО ЛИМИТ ДНИ\nТипы: gc, shield, double, insurance, diamond_shield, vip, all\nПример: WELCOME250 gc 250 100 7")
        bot.register_next_step_handler_by_chat_id(uid, lambda m: create_promo_handler(m, cid, mid))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_list_promos":
        if uid != ADMIN_ID: return
        promos = get_all_promos()
        text = "<b>📋 ПРОМОКОДЫ</b>\n\n"
        for code, rt, ra, mu, uc, exp in promos:
            status = "✅" if not exp or datetime.now() < datetime.fromisoformat(exp) else "❌"
            text += f"{status} {code} — {rt} x{ra} ({uc}/{mu})\n"
        bot.edit_message_text(text, cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_promocodes")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_delete_promo":
        if uid != ADMIN_ID: return
        bot.send_message(uid, "Введите код:")
        bot.register_next_step_handler_by_chat_id(uid, lambda m: delete_promo_handler(m, cid, mid))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_reports":
        if uid != ADMIN_ID: return
        reports = get_reports()
        text = "<b>📝 ЖАЛОБЫ</b>\n\n"
        for r in reports[:20]:
            status_emoji = "🟡" if r[4] == "new" else "🟢"
            text += f"{status_emoji} #{r[0]} | {r[2]} | {get_name(r[1])}\n{r[3][:50]}\n\n"
        bot.edit_message_text(text, cid, mid, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_black_market":
        if uid != ADMIN_ID: return
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🌑 Запустить сейчас", callback_data="admin_bm_start"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
        bot.edit_message_text(f"🌑 ЧЁРНЫЙ РЫНОК\nСтатус: {'ОТКРЫТ' if black_market_active else 'ЗАКРЫТ'}", cid, mid, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_bm_start":
        if uid != ADMIN_ID: return
        start_black_market()
        bot.answer_callback_query(call.id, "🌑 Чёрный рынок запущен на 15 минут!")
        bot.edit_message_reply_markup(cid, mid, reply_markup=admin_panel_kb())
        return
    
    if call.data == "admin_add_gc":
        if uid != ADMIN_ID: return
        bot.send_message(uid, "Введите: ID GC")
        bot.register_next_step_handler_by_chat_id(uid, lambda m: add_gc_admin_handler(m, cid, mid))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_remove_gc":
        if uid != ADMIN_ID: return
        bot.send_message(uid, "Введите: ID GC")
        bot.register_next_step_handler_by_chat_id(uid, lambda m: remove_gc_admin_handler(m, cid, mid))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_give_item":
        if uid != ADMIN_ID: return
        bot.send_message(uid, "Введите: ID ТИП КОЛ-ВО\nТипы: gc, shield, diamond, double, insurance, blood_mark, reincarnation, silencer, fake_bullet, vip")
        bot.register_next_step_handler_by_chat_id(uid, lambda m: give_item_handler(m, cid, mid))
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_broadcast":
        if uid != ADMIN_ID: return
        bot.send_message(uid, "Введите текст рассылки:")
        bot.register_next_step_handler_by_chat_id(uid, lambda m: broadcast_handler(m, cid, mid))
        bot.answer_callback_query(call.id)
        return
    
    # ========== ВЫБОР РЕЖИМА ==========
    if call.data == "create_game":
        if is_private:
            bot.answer_callback_query(call.id, "❌ Игры только в чатах!", show_alert=True)
            return
        s = get_chat_settings(cid)
        if s["banned"] or not s['game_enabled']:
            bot.answer_callback_query(call.id, "❌ Игры отключены!", show_alert=True)
            return
        if cid in games:
            bot.answer_callback_query(call.id, "❌ Игра уже есть!", show_alert=True)
            return
        bot.send_message(cid, f"{get_user_link(uid)} создаёт игру. Выберите режим:", reply_markup=mode_choice_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "mode_arcade":
        cid = call.message.chat.id
        if cid in games:
            bot.answer_callback_query(call.id, "❌ Игра уже есть!", show_alert=True)
            return
        s = get_chat_settings(cid)
        if s["banned"] or not s['game_enabled']:
            bot.answer_callback_query(call.id, "❌ Игры отключены!", show_alert=True)
            return
        sent = bot.send_message(cid, f"🎮 <b>НОВАЯ ИГРА!</b>\n\n{get_user_link(uid)} создал лобби!\nМакс: {s['max_players']}\nМин ставка: {s['min_bet']} GC", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("➕ Присоединиться", callback_data=f"join_{cid}")))
        games[cid] = {"players":[uid],"bets":{},"chambers":{},"status":"waiting","current_player":None,"creator":uid,"message_id":sent.message_id,"max_players":s['max_players'],"used_shields":{},"used_double":{},"used_insurance":{},"mode":"arcade","lives":{uid:3}}
        bot.send_message(uid, "✅ Сделай ставку:", reply_markup=bet_kb(cid))
        start_auto_kick_timer(cid, uid)
        bot.answer_callback_query(call.id, "Игра создана!")
        return
    
    if call.data == "mode_hardcore":
        bot.edit_message_text(HARDCORE_DESCRIPTION, cid, mid, reply_markup=hardcore_ban_choice_kb())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "mode_hardcore_ban":
        cid = call.message.chat.id
        if cid in games:
            bot.answer_callback_query(call.id, "❌ Игра уже есть!", show_alert=True)
            return
        s = get_chat_settings(cid)
        if not s["hardcore_allowed"]:
            bot.answer_callback_query(call.id, "❌ Хардкор запрещён!", show_alert=True)
            return
        if s["banned"] or not s['game_enabled']:
            bot.answer_callback_query(call.id, "❌ Игры отключены!", show_alert=True)
            return
        sent = bot.send_message(cid, f"💀 <b>ХАРДКОР (С БАНОМ)</b>\n\n{get_user_link(uid)} создал лобби!", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("➕ Присоединиться", callback_data=f"join_{cid}")))
        games[cid] = {"players":[uid],"bets":{},"chambers":{},"status":"waiting","current_player":None,"creator":uid,"message_id":sent.message_id,"max_players":s['max_players'],"used_shields":{},"used_double":{},"used_insurance":{},"mode":"hardcore","hardcore_ban":True,"lives":{uid:1}}
        bot.send_message(uid, "✅ Сделай ставку:", reply_markup=bet_kb(cid))
        start_auto_kick_timer(cid, uid)
        bot.answer_callback_query(call.id, "Хардкор создан!")
        return
    
    if call.data == "mode_hardcore_noban":
        cid = call.message.chat.id
        if cid in games:
            bot.answer_callback_query(call.id, "❌ Игра уже есть!", show_alert=True)
            return
        s = get_chat_settings(cid)
        if not s["hardcore_allowed"]:
            bot.answer_callback_query(call.id, "❌ Хардкор запрещён!", show_alert=True)
            return
        if s["banned"] or not s['game_enabled']:
            bot.answer_callback_query(call.id, "❌ Игры отключены!", show_alert=True)
            return
        sent = bot.send_message(cid, f"💀 <b>ХАРДКОР (БЕЗ БАНА)</b>\n\n{get_user_link(uid)} создал лобби!", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("➕ Присоединиться", callback_data=f"join_{cid}")))
        games[cid] = {"players":[uid],"bets":{},"chambers":{},"status":"waiting","current_player":None,"creator":uid,"message_id":sent.message_id,"max_players":s['max_players'],"used_shields":{},"used_double":{},"used_insurance":{},"mode":"hardcore","hardcore_ban":False,"lives":{uid:1}}
        bot.send_message(uid, "✅ Сделай ставку:", reply_markup=bet_kb(cid))
        start_auto_kick_timer(cid, uid)
        bot.answer_callback_query(call.id, "Хардкор создан!")
        return
    
    if call.data.startswith("join_"):
        gid = int(call.data.split("_")[1])
        if gid not in games or games[gid]["status"] != "waiting":
            bot.answer_callback_query(call.id, "Игра уже началась!", show_alert=True)
            return
        if uid in games[gid]["players"]:
            bot.answer_callback_query(call.id, "Ты уже в игре!", show_alert=True)
            return
        if len(games[gid]["players"]) >= games[gid]["max_players"]:
            bot.answer_callback_query(call.id, "Лобби заполнено!", show_alert=True)
            return
        games[gid]["players"].append(uid)
        games[gid]["lives"][uid] = 3 if games[gid]["mode"] == "arcade" else 1
        update_lobby_message(gid)
        bot.send_message(uid, "🎮 Сделай ставку:", reply_markup=bet_kb(gid))
        start_auto_kick_timer(gid, uid)
        bot.answer_callback_query(call.id, "Ты присоединился!")
        return
    
    if call.data.startswith("cancel_game_"):
        gid = int(call.data.split("_")[2])
        if gid not in games: return
        if games[gid]["creator"] != uid and not is_chat_admin(uid, gid):
            bot.answer_callback_query(call.id, "Только создатель!", show_alert=True)
            return
        cancel_auto_kick_timers(gid)
        del games[gid]
        bot.send_message(gid, "❌ Игра отменена")
        bot.answer_callback_query(call.id, "Игра отменена")
        return
    
    if call.data.startswith("place_bet_"):
        parts = call.data.split("_")
        gid = int(parts[2])
        bet = int(parts[3])
        if gid not in games or games[gid]["status"] != "waiting":
            bot.answer_callback_query(call.id, "Игра неактивна!", show_alert=True)
            return
        if uid not in games[gid]["players"]:
            bot.answer_callback_query(call.id, "Ты не в игре!", show_alert=True)
            return
        if uid in games[gid]["bets"]:
            bot.answer_callback_query(call.id, "Ставка уже сделана!", show_alert=True)
            return
        s = get_chat_settings(gid)
        if bet < s['min_bet'] or bet > s['max_bet']:
            bot.answer_callback_query(call.id, f"Ставка от {s['min_bet']} до {s['max_bet']}!", show_alert=True)
            return
        if u["gc"] < bet:
            bot.answer_callback_query(call.id, f"Не хватает! Нужно {bet}", show_alert=True)
            return
        games[gid]["bets"][uid] = bet
        update_user(uid, gc=u["gc"]-bet)
        cancel_auto_kick_timers(gid)
        update_lobby_message(gid)
        bot.answer_callback_query(call.id, f"Ставка {bet} GC принята!")
        return
    
    if call.data.startswith("start_game_"):
        gid = int(call.data.split("_")[2])
        if gid not in games: return
        g = games[gid]
        if uid != g["creator"]:
            bot.answer_callback_query(call.id, "Только создатель!", show_alert=True)
            return
        if len(g["players"]) < 2:
            bot.answer_callback_query(call.id, "Нужно минимум 2 игрока!", show_alert=True)
            return
        for p in g["players"]:
            if p not in g["bets"]:
                bot.answer_callback_query(call.id, "Не все сделали ставки!", show_alert=True)
                return
        g["status"] = "playing"
        players = g["players"].copy()
        random.shuffle(players)
        g["players"] = players
        g["current_player"] = players[0]
        for p in players:
            g["chambers"][p] = random.randint(1, 6)
        total = sum(g["bets"].values())
        plist = "\n".join([f"• {get_user_link(p)} — {g['bets'][p]} GC" for p in players])
        mode_name = "🎲 Аркадный" if g["mode"] == "arcade" else f"💀 Хардкор ({'бан' if g.get('hardcore_ban', False) else 'без бана'})"
        bot.edit_message_text(f"🎲 <b>ИГРА НАЧАЛАСЬ!</b> | {mode_name}\n\n{plist}\n\n💰 Банк: {total} GC", gid, g["message_id"])
        cur = g["current_player"]
        msg = bot.send_message(gid, f"🔫 <b>ХОД:</b> {get_name(cur)} | <b>Ставка:</b> {g['bets'][cur]} GC\n\nВыбери действие:", reply_markup=game_action_kb(gid))
        g["action_message_id"] = msg.message_id
        update_chat_stats(gid, total)
        bot.answer_callback_query(call.id, "Игра начата!")
        return
    
    # ========== ИГРОВЫЕ ДЕЙСТВИЯ ==========
    if call.data.startswith("game_spin_"):
        if not check_game_cooldown(uid):
            bot.answer_callback_query(call.id, "⏰ Подожди 3 секунды!", show_alert=True)
            return
        gid = int(call.data.split("_")[2])
        if gid not in games or games[gid]["status"] != "playing":
            bot.answer_callback_query(call.id, "❌ Игра неактивна!", show_alert=True)
            return
        g = games[gid]
        if g["current_player"] != uid:
            bot.answer_callback_query(call.id, "❌ Сейчас не ваш ход!", show_alert=True)
            return
        g["chambers"][uid] = random.randint(1, 6)
        bot.answer_callback_query(call.id, "Барабан прокручен!")
        return
    
    if call.data.startswith("game_shoot_"):
        if not check_game_cooldown(uid):
            bot.answer_callback_query(call.id, "⏰ Подожди 3 секунды!", show_alert=True)
            return
        gid = int(call.data.split("_")[2])
        if gid not in games or games[gid]["status"] != "playing":
            bot.answer_callback_query(call.id, "❌ Игра неактивна!", show_alert=True)
            return
        g = games[gid]
        if g["current_player"] != uid:
            bot.answer_callback_query(call.id, "❌ Сейчас не ваш ход!", show_alert=True)
            return
        
        u2 = get_user(uid)
        bet = g["bets"][uid]
        chamber = g["chambers"][uid]
        s = get_chat_settings(gid)
        is_dead = (chamber == 1)
        
        # Защиты
        if is_dead and g["mode"] == "arcade" and s["shields_allowed"]:
            if u2["shields"] > 0 and g["used_shields"].get(uid, 0) == 0:
                is_dead = False
                g["used_shields"][uid] = 1
                update_user(uid, shields=u2["shields"]-1)
                bot.send_message(uid, "🛡️ ЩИТ!")
            elif u2["diamond_shield"] > 0:
                is_dead = False
                update_user(uid, diamond_shield=u2["diamond_shield"]-1)
                bot.send_message(uid, "💎 АЛМАЗНЫЙ ЩИТ!")
        
        if is_dead:
            refund = 0
            if u2["insurance"] > 0 and g["used_insurance"].get(uid, 0) == 0 and g["mode"] == "arcade" and s["shields_allowed"]:
                refund = bet // 2
                g["used_insurance"][uid] = 1
                update_user(uid, insurance=u2["insurance"]-1)
                bot.send_message(uid, f"💰 СТРАХОВКА! +{refund} GC")
            
            # Реинкарнация
            if u2["reincarnation"] > 0 and g["mode"] == "arcade":
                update_user(uid, reincarnation=u2["reincarnation"]-1)
                bot.edit_message_text(f"🔄 Реинкарнация! {get_name(uid)} воскрес!", gid, call.message.message_id)
                delete_message_later(gid, call.message.message_id, 4)
                next_turn_with_delay(gid, g, 3)
                bot.answer_callback_query(call.id, "Ты воскрес!")
                return
            
            g["lives"][uid] -= 1
            if g["lives"][uid] > 0:
                bot.edit_message_text(f"💀 {get_name(uid)} потерял жизнь! Осталось: {g['lives'][uid]}", gid, call.message.message_id)
                delete_message_later(gid, call.message.message_id, 4)
                next_turn_with_delay(gid, g, 3)
                bot.answer_callback_query(call.id, "Ты потерял жизнь!")
                return
            else:
                bot.edit_message_text(f"💀 {get_name(uid)} ВЫБЫЛ!", gid, call.message.message_id)
                delete_message_later(gid, call.message.message_id, 4)
                g["players"].remove(uid)
                update_user(uid, losses=u2["losses"]+1, gc=u2["gc"]+refund)
                update_rating_and_rewards(uid, False)
                update_chat_player(gid, uid, False)
                
                if g["mode"] == "hardcore" and g.get("hardcore_ban", False):
                    ban_user_from_chat(gid, uid)
                    bot.send_message(gid, HARDCORE_BAN_MESSAGE.replace("{name}", get_name(uid)))
                
                if len(g["players"]) == 1:
                    winner = g["players"][0]
                    total = sum(g["bets"].values())
                    win = get_user(winner)
                    win_amt = int(total)
                    if s["winner_bonus"] > 0:
                        win_amt += s["winner_bonus"]
                    update_user(winner, gc=win["gc"]+win_amt, wins=win["wins"]+1)
                    update_rating_and_rewards(winner, True)
                    update_chat_player(gid, winner, True)
                    bot.send_message(gid, f"🏆 ПОБЕДИТЕЛЬ: {get_name(winner)}\n💰 Выигрыш: {win_amt} GC")
                    del games[gid]
                    bot.answer_callback_query(call.id, "Ты выбыл")
                    return
                
                g["current_player"] = g["players"][0]
                cur = g["current_player"]
                msg2 = bot.send_message(gid, f"🔫 <b>ХОД:</b> {get_name(cur)} | <b>Ставка:</b> {g['bets'][cur]} GC", reply_markup=game_action_kb(gid))
                g["action_message_id"] = msg2.message_id
                bot.answer_callback_query(call.id, "Ты выбыл")
                return
        else:
            bot.edit_message_text(f"🍀 {get_name(uid)} ВЫЖИЛ! Банк: {sum(g['bets'].values())} GC", gid, call.message.message_id)
            delete_message_later(gid, call.message.message_id, 4)
            g["chambers"][uid] = random.randint(1, 6)
            idx = g["players"].index(uid)
            next_idx = (idx + 1) % len(g["players"])
            g["current_player"] = g["players"][next_idx]
            cur = g["current_player"]
            msg2 = bot.send_message(gid, f"🔫 <b>ХОД:</b> {get_name(cur)} | <b>Ставка:</b> {g['bets'][cur]} GC", reply_markup=game_action_kb(gid))
            g["action_message_id"] = msg2.message_id
            bot.answer_callback_query(call.id, "Пусто! Ты выжил")
            return

# ========== ОБРАБОТЧИКИ ==========
def promo_enter_handler(m, ocid, omid):
    ok, msg = use_promo(m.from_user.id, m.text.upper())
    bot.send_message(m.chat.id, msg)
    bot.edit_message_reply_markup(ocid, omid)

def report_text_handler(m, report_type, ocid, omid):
    types = {"report_player":"на игрока","report_bug":"баг","report_finance":"финансы","report_other":"другое"}
    add_report(m.from_user.id, types.get(report_type, "другое"), m.text)
    bot.send_message(m.chat.id, "✅ Жалоба отправлена!")
    bot.edit_message_reply_markup(ocid, omid)

def create_promo_handler(m, ocid, omid):
    if m.from_user.id != ADMIN_ID: return
    try:
        p = m.text.split()
        cd = p[0].upper()
        rt = p[1].lower()
        ra = p[2]
        mu = int(p[3])
        d = int(p[4]) if len(p) > 4 else None
        create_promo(cd, rt, ra, mu, d)
        bot.send_message(m.chat.id, f"✅ {cd} создан!")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ {e}")
    bot.edit_message_reply_markup(ocid, omid, reply_markup=admin_promocodes_kb())

def delete_promo_handler(m, ocid, omid):
    if m.from_user.id != ADMIN_ID: return
    delete_promo(m.text.upper())
    bot.send_message(m.chat.id, f"✅ {m.text.upper()} удалён!")
    bot.edit_message_reply_markup(ocid, omid, reply_markup=admin_promocodes_kb())

def give_item_handler(m, ocid, omid):
    if m.from_user.id != ADMIN_ID: return
    try:
        p = m.text.split()
        user_id = int(p[0])
        item_type = p[1].lower()
        amount = int(p[2])
        u = get_user(user_id)
        if item_type == "gc":
            update_user(user_id, gc=u["gc"]+amount)
        elif item_type == "shield":
            update_user(user_id, shields=u["shields"]+amount)
        elif item_type == "diamond":
            update_user(user_id, diamond_shield=u["diamond_shield"]+amount)
        elif item_type == "double":
            update_user(user_id, double_chance=u["double_chance"]+amount)
        elif item_type == "insurance":
            update_user(user_id, insurance=u["insurance"]+amount)
        elif item_type == "blood_mark":
            update_user(user_id, blood_mark=u["blood_mark"]+amount)
        elif item_type == "reincarnation":
            update_user(user_id, reincarnation=u["reincarnation"]+amount)
        elif item_type == "silencer":
            update_user(user_id, silencer=u["silencer"]+amount)
        elif item_type == "fake_bullet":
            update_user(user_id, fake_bullet=u["fake_bullet"]+amount)
        elif item_type == "vip":
            update_user(user_id, vip_level=amount, vip_until=(datetime.now()+timedelta(days=amount)).isoformat())
        else:
            bot.send_message(m.chat.id, f"❌ Неизвестный тип: {item_type}")
            return
        bot.send_message(m.chat.id, f"✅ {amount} x {item_type} выдано {get_name(user_id)}")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ {e}")
    bot.edit_message_reply_markup(ocid, omid, reply_markup=admin_panel_kb())

def broadcast_handler(m, ocid, omid):
    if m.from_user.id != ADMIN_ID: return
    text = m.text
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT chat_id FROM chat_settings WHERE banned = 0")
    chats = c.fetchall()
    conn.close()
    ok = 0
    for (cid,) in chats:
        try:
            bot.send_message(cid, f"📢 РАССЫЛКА\n\n{text}")
            ok += 1
        except:
            pass
    bot.send_message(ADMIN_ID, f"✅ Отправлено в {ok} чатов")
    bot.edit_message_reply_markup(ocid, omid, reply_markup=admin_panel_kb())

def add_gc_admin_handler(m, ocid, omid):
    if m.from_user.id != ADMIN_ID: return
    try:
        uid, amt = map(int, m.text.split())
        add_gc(uid, amt)
        bot.send_message(m.chat.id, f"✅ {amt} GC выдано")
    except:
        bot.send_message(m.chat.id, "❌ Ошибка!")
    bot.edit_message_reply_markup(ocid, omid, reply_markup=admin_panel_kb())

def remove_gc_admin_handler(m, ocid, omid):
    if m.from_user.id != ADMIN_ID: return
    try:
        uid, amt = map(int, m.text.split())
        remove_gc(uid, amt)
        bot.send_message(m.chat.id, f"✅ {amt} GC списано")
    except:
        bot.send_message(m.chat.id, "❌ Ошибка!")
    bot.edit_message_reply_markup(ocid, omid, reply_markup=admin_panel_kb())

def set_max_players_handler(m, tcid, ocid, omid):
    try:
        v = int(m.text)
        if 2 <= v <= MAX_PLAYERS_LIMIT:
            update_chat_settings(tcid, max_players=v)
            bot.send_message(m.chat.id, f"✅ Макс игроков: {v}")
            kb, info = chat_settings_kb(tcid)
            bot.edit_message_text(info, ocid, omid, reply_markup=kb, parse_mode="HTML")
        else:
            bot.send_message(m.chat.id, f"❌ От 2 до {MAX_PLAYERS_LIMIT}")
    except:
        bot.send_message(m.chat.id, "❌ Введите число!")

def set_min_bet_handler(m, tcid, ocid, omid):
    try:
        v = int(m.text)
        if 1 <= v <= 1000:
            update_chat_settings(tcid, min_bet=v)
            bot.send_message(m.chat.id, f"✅ Мин ставка: {v}")
            kb, info = chat_settings_kb(tcid)
            bot.edit_message_text(info, ocid, omid, reply_markup=kb, parse_mode="HTML")
        else:
            bot.send_message(m.chat.id, "❌ От 1 до 1000")
    except:
        bot.send_message(m.chat.id, "❌ Введите число!")

def set_max_bet_handler(m, tcid, ocid, omid):
    try:
        v = int(m.text)
        if 10 <= v <= 10000:
            update_chat_settings(tcid, max_bet=v)
            bot.send_message(m.chat.id, f"✅ Макс ставка: {v}")
            kb, info = chat_settings_kb(tcid)
            bot.edit_message_text(info, ocid, omid, reply_markup=kb, parse_mode="HTML")
        else:
            bot.send_message(m.chat.id, "❌ От 10 до 10000")
    except:
        bot.send_message(m.chat.id, "❌ Введите число!")

def set_bet_buttons_handler(m, tcid, ocid, omid):
    try:
        bt = m.text.strip()
        bts = [int(x.strip()) for x in bt.split(',')]
        if all(1 <= b <= 10000 for b in bts) and len(bts) <= 10:
            update_chat_settings(tcid, bet_buttons=bt)
            bot.send_message(m.chat.id, f"✅ Кнопки: {bt}")
            kb, info = chat_settings_kb(tcid)
            bot.edit_message_text(info, ocid, omid, reply_markup=kb, parse_mode="HTML")
        else:
            bot.send_message(m.chat.id, "❌ Пример: 10,50,100,200,500,1000")
    except:
        bot.send_message(m.chat.id, "❌ Ошибка!")

def set_winner_bonus_handler(m, tcid, ocid, omid):
    try:
        v = int(m.text)
        if 0 <= v <= 500:
            update_chat_settings(tcid, winner_bonus=v)
            bot.send_message(m.chat.id, f"✅ Бонус: {v} GC")
            kb, info = chat_settings_kb(tcid)
            bot.edit_message_text(info, ocid, omid, reply_markup=kb, parse_mode="HTML")
        else:
            bot.send_message(m.chat.id, "❌ От 0 до 500")
    except:
        bot.send_message(m.chat.id, "❌ Введите число!")

def set_auto_kick_handler(m, tcid, ocid, omid):
    try:
        v = int(m.text)
        if 0 <= v <= 10:
            update_chat_settings(tcid, auto_kick_minutes=v)
            bot.send_message(m.chat.id, f"✅ Авто-кик: {v} мин")
            kb, info = chat_settings_kb(tcid)
            bot.edit_message_text(info, ocid, omid, reply_markup=kb, parse_mode="HTML")
        else:
            bot.send_message(m.chat.id, "❌ От 0 до 10")
    except:
        bot.send_message(m.chat.id, "❌ Введите число!")

if __name__ == "__main__":
    init_db()
    print("✅ Бот запущен!")
    print(f"📱 @{BOT_USERNAME}")
    print(f"👑 Admin ID: {ADMIN_ID}")
    
    def schedule_black_market():
        while True:
            now = datetime.now()
            next_run = now.replace(hour=21, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            time.sleep((next_run - now).total_seconds())
            start_black_market()
            time.sleep(15 * 60)
            end_black_market()
    
    thread = threading.Thread(target=schedule_black_market, daemon=True)
    thread.start()
    
    bot.infinity_polling()