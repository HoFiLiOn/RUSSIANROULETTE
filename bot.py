import telebot
import sqlite3
import random
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ========== КОНФИГ ==========
BOT_TOKEN = "8412567351:AAG7eEMXlNfDBsNZF08GD-Pr-LH-2z1txSQ"
BOT_USERNAME = "RussianRoulette_official_bot"
ADMIN_ID = 7040677455
MAX_PLAYERS_LIMIT = 15

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ========== БД ==========
def init_db():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  bullets INTEGER DEFAULT 100,
                  last_daily TEXT,
                  wins INTEGER DEFAULT 0,
                  losses INTEGER DEFAULT 0,
                  total_games INTEGER DEFAULT 0,
                  shields INTEGER DEFAULT 0,
                  double_chance INTEGER DEFAULT 0,
                  insurance INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS chat_settings
                 (chat_id INTEGER PRIMARY KEY,
                  max_players INTEGER DEFAULT 6,
                  min_bet INTEGER DEFAULT 10,
                  max_bet INTEGER DEFAULT 500,
                  game_enabled INTEGER DEFAULT 1,
                  admin_only INTEGER DEFAULT 0,
                  owner_id INTEGER DEFAULT 0,
                  name TEXT DEFAULT '')''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS chat_stats
                 (chat_id INTEGER PRIMARY KEY,
                  total_games INTEGER DEFAULT 0,
                  total_bets INTEGER DEFAULT 0)''')
    
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT bullets, last_daily, wins, losses, total_games, shields, double_chance, insurance FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (user_id, bullets, last_daily) VALUES (?, ?, ?)",
                  (user_id, 100, datetime.now().isoformat()))
        conn.commit()
        c.execute("SELECT bullets, last_daily, wins, losses, total_games, shields, double_chance, insurance FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
    conn.close()
    return {
        "bullets": user[0],
        "last_daily": user[1],
        "wins": user[2],
        "losses": user[3],
        "total_games": user[4],
        "shields": user[5],
        "double_chance": user[6],
        "insurance": user[7]
    }

def update_user(user_id, bullets=None, wins=None, losses=None, total_games=None, 
                last_daily=None, shields=None, double_chance=None, insurance=None):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    if bullets is not None:
        c.execute("UPDATE users SET bullets = ? WHERE user_id = ?", (bullets, user_id))
    if wins is not None:
        c.execute("UPDATE users SET wins = ? WHERE user_id = ?", (wins, user_id))
    if losses is not None:
        c.execute("UPDATE users SET losses = ? WHERE user_id = ?", (losses, user_id))
    if total_games is not None:
        c.execute("UPDATE users SET total_games = ? WHERE user_id = ?", (total_games, user_id))
    if last_daily is not None:
        c.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", (last_daily, user_id))
    if shields is not None:
        c.execute("UPDATE users SET shields = ? WHERE user_id = ?", (shields, user_id))
    if double_chance is not None:
        c.execute("UPDATE users SET double_chance = ? WHERE user_id = ?", (double_chance, user_id))
    if insurance is not None:
        c.execute("UPDATE users SET insurance = ? WHERE user_id = ?", (insurance, user_id))
    conn.commit()
    conn.close()

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

def update_chat_settings(chat_id, max_players=None, min_bet=None, max_bet=None, game_enabled=None, admin_only=None, owner_id=None, name=None):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    if max_players is not None:
        c.execute("UPDATE chat_settings SET max_players = ? WHERE chat_id = ?", (max_players, chat_id))
    if min_bet is not None:
        c.execute("UPDATE chat_settings SET min_bet = ? WHERE chat_id = ?", (min_bet, chat_id))
    if max_bet is not None:
        c.execute("UPDATE chat_settings SET max_bet = ? WHERE chat_id = ?", (max_bet, chat_id))
    if game_enabled is not None:
        c.execute("UPDATE chat_settings SET game_enabled = ? WHERE chat_id = ?", (game_enabled, chat_id))
    if admin_only is not None:
        c.execute("UPDATE chat_settings SET admin_only = ? WHERE chat_id = ?", (admin_only, chat_id))
    if owner_id is not None:
        c.execute("UPDATE chat_settings SET owner_id = ? WHERE chat_id = ?", (owner_id, chat_id))
    if name is not None:
        c.execute("UPDATE chat_settings SET name = ? WHERE chat_id = ?", (name, chat_id))
    conn.commit()
    conn.close()

def update_chat_stats(chat_id, total_games=None, total_bets=None):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    if total_games is not None:
        c.execute("UPDATE chat_stats SET total_games = total_games + ? WHERE chat_id = ?", (total_games, chat_id))
    if total_bets is not None:
        c.execute("UPDATE chat_stats SET total_bets = total_bets + ? WHERE chat_id = ?", (total_bets, chat_id))
    conn.commit()
    conn.close()

def get_all_chats():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT chat_id, name FROM chat_settings WHERE name != ''")
    chats = c.fetchall()
    conn.close()
    return chats

def get_user_chats(user_id):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT chat_id, name FROM chat_settings WHERE owner_id = ?", (user_id,))
    chats = c.fetchall()
    conn.close()
    return chats

def get_top_players(category, limit=10):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    if category == "wins":
        c.execute("SELECT user_id, wins, bullets FROM users ORDER BY wins DESC LIMIT ?", (limit,))
    elif category == "bullets":
        c.execute("SELECT user_id, bullets, wins FROM users ORDER BY bullets DESC LIMIT ?", (limit,))
    elif category == "games":
        c.execute("SELECT user_id, total_games, wins FROM users ORDER BY total_games DESC LIMIT ?", (limit,))
    else:
        return []
    return c.fetchall()

def get_all_users_count():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_total_games():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT SUM(total_games) FROM users")
    total = c.fetchone()[0] or 0
    conn.close()
    return total

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

def is_chat_owner(user_id, chat_id):
    settings = get_chat_settings(chat_id)
    if settings["owner_id"] == user_id:
        return True
    try:
        member = bot.get_chat_member(chat_id, user_id)
        if member.status == 'creator':
            update_chat_settings(chat_id, owner_id=user_id, name=member.chat.title)
            return True
        return False
    except:
        return False

def is_chat_admin(user_id, chat_id):
    if user_id == ADMIN_ID:
        return True
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except:
        return False

# ========== ХРАНИЛИЩЕ ИГР ==========
games = {}

# ========== КЛАВИАТУРЫ ==========
def main_menu(user_id):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🎮 Создать игру", callback_data="create_game"))
    kb.add(InlineKeyboardButton("💰 Баланс", callback_data="balance"))
    kb.add(InlineKeyboardButton("🎁 Бонус", callback_data="daily"))
    kb.add(InlineKeyboardButton("🛒 Магазин", callback_data="shop"))
    kb.add(InlineKeyboardButton("🏆 Топы", callback_data="top_menu"))
    
    # Настройки чатов для владельца
    user_chats = get_user_chats(user_id)
    if user_chats:
        kb.add(InlineKeyboardButton("⚙️ Настройки чатов", callback_data="my_chats_settings"))
    
    if user_id == ADMIN_ID:
        kb.add(InlineKeyboardButton("👑 Админ панель", callback_data="admin_panel"))
    
    return kb

def chat_settings_kb(chat_id):
    settings = get_chat_settings(chat_id)
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"👥 Макс игроков: {settings['max_players']}", callback_data=f"set_max_players_{chat_id}"))
    kb.add(InlineKeyboardButton(f"💰 Мин ставка: {settings['min_bet']} 💎", callback_data=f"set_min_bet_{chat_id}"))
    kb.add(InlineKeyboardButton(f"💎 Макс ставка: {settings['max_bet']} 💎", callback_data=f"set_max_bet_{chat_id}"))
    kb.add(InlineKeyboardButton(f"🎮 Игры: {'✅ Вкл' if settings['game_enabled'] else '❌ Выкл'}", callback_data=f"toggle_game_{chat_id}"))
    kb.add(InlineKeyboardButton(f"👑 Только админы: {'✅ Да' if settings['admin_only'] else '❌ Нет'}", callback_data=f"toggle_admin_only_{chat_id}"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def shop_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🛡️ Щит (100 💎) - спасает от 1 патрона", callback_data="buy_shield"))
    kb.add(InlineKeyboardButton("⚡ Двойной шанс (150 💎) - +10% к удаче", callback_data="buy_double"))
    kb.add(InlineKeyboardButton("💰 Страховка (200 💎) - возврат 50% при вылете", callback_data="buy_insurance"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def top_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🏆 По победам", callback_data="top_wins"))
    kb.add(InlineKeyboardButton("💰 По балансу", callback_data="top_bullets"))
    kb.add(InlineKeyboardButton("🎮 По играм", callback_data="top_games"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def admin_panel_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📊 Общая статистика", callback_data="admin_stats"))
    kb.add(InlineKeyboardButton("📋 Список чатов", callback_data="admin_chats"))
    kb.add(InlineKeyboardButton("🏆 Топ игроков", callback_data="admin_top"))
    kb.add(InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"))
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
            kb.add(InlineKeyboardButton(f"{bet} 💎", callback_data=f"place_bet_{chat_id}_{bet}"))
    return kb

def back_button():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def get_rules():
    return (
        "<b>🔫 РУССКАЯ РУЛЕТКА 🔫</b>\n\n"
        "<b>🎲 Правила игры:</b>\n"
        "• Один игрок создает лобби\n"
        "• Другие присоединяются (до 15 игроков)\n"
        "• Каждый делает ставку 💎\n"
        "• Игроки ходят по очереди\n"
        "• Если выпадает пусто → игрок продолжает\n"
        "• Если выпадает патрон → игрок выбывает, теряет ставку\n"
        "• Последний выживший забирает банк!\n\n"
        "<b>🛡️ Защиты (купить в магазине):</b>\n"
        "• Щит — спасает от 1 патрона\n"
        "• Двойной шанс — +10% к удаче на 1 игру\n"
        "• Страховка — возврат 50% при вылете\n\n"
        "<b>💰 Как получить 💎:</b>\n"
        "• Ежедневный бонус — 50 💎\n"
        "• Победы в игре — банк всех ставок"
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
            players_list.append(f"• {get_user_link(p)} — {game['bets'][p]} 💎")
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
        text += f"\n✅ Все ставки сделаны!\n💰 Общий банк: {total_pot} 💎"
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

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    init_db()
    get_user(message.from_user.id)
    
    # Если это групповой чат, сохраняем информацию
    if message.chat.type != "private":
        update_chat_settings(message.chat.id, name=message.chat.title)
        # Проверяем владельца
        try:
            member = bot.get_chat_member(message.chat.id, message.from_user.id)
            if member.status == 'creator':
                update_chat_settings(message.chat.id, owner_id=message.from_user.id)
        except:
            pass
        bot.send_message(
            message.chat.id,
            f"<b>🔫 Русская Рулетка</b>\n\nИспользуй команды в личных сообщениях с ботом для создания игр и настроек!",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🎮 Открыть в ЛС", url=f"https://t.me/{BOT_USERNAME}")
            )
        )
        return
    
    # В личке
    bot.send_message(
        message.chat.id,
        f"<b>🔫 Добро пожаловать в Русскую Рулетку, {message.from_user.first_name}!</b>\n\n{get_rules()}",
        reply_markup=main_menu(message.from_user.id)
    )

@bot.message_handler(commands=['balance'])
def balance_command(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    bot.reply_to(
        message,
        f"💰 <b>Твой баланс:</b> {user['bullets']} 💎\n"
        f"🏆 Побед: {user['wins']} | 💀 Поражений: {user['losses']}\n"
        f"🎮 Всего игр: {user['total_games']}\n\n"
        f"🛡️ Щитов: {user['shields']}\n"
        f"⚡ Двойных шансов: {user['double_chance']}\n"
        f"💰 Страховок: {user['insurance']}"
    )

@bot.message_handler(commands=['daily'])
def daily_command(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    last = datetime.fromisoformat(user["last_daily"]) if user["last_daily"] else datetime.min
    now = datetime.now()
    
    if now - last < timedelta(days=1):
        hours_left = 24 - (now - last).seconds // 3600
        bot.reply_to(message, f"⏰ Бонус будет через {hours_left} ч")
        return
    
    new_bullets = user["bullets"] + 50
    update_user(user_id, bullets=new_bullets, last_daily=now.isoformat())
    bot.reply_to(message, f"🎁 Ты получил 50 💎!\n\n💰 Новый баланс: {new_bullets} 💎")

@bot.message_handler(commands=['shop'])
def shop_command(message):
    kb = shop_kb()
    bot.send_message(
        message.chat.id,
        "<b>🛒 МАГАЗИН</b>\n\n"
        "Покупай защиты за 💎:\n\n"
        "🛡️ <b>Щит</b> (100 💎) — спасает от 1 патрона\n"
        "⚡ <b>Двойной шанс</b> (150 💎) — +10% к удаче на 1 игру\n"
        "💰 <b>Страховка</b> (200 💎) — возврат 50% ставки при вылете\n\n"
        "Защиты активируются автоматически во время игры!",
        reply_markup=kb
    )

@bot.message_handler(commands=['top'])
def top_command(message):
    kb = top_menu_kb()
    bot.send_message(
        message.chat.id,
        "<b>🏆 ТОПЫ</b>\n\nВыбери категорию:",
        reply_markup=kb
    )

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
            reply_markup=main_menu(user_id)
        )
        bot.answer_callback_query(call.id)
        return
    
    # Мои чаты для настроек
    if call.data == "my_chats_settings":
        user_chats = get_user_chats(user_id)
        if not user_chats:
            bot.answer_callback_query(call.id, "❌ У тебя нет чатов с ботом!", show_alert=True)
            return
        
        kb = InlineKeyboardMarkup(row_width=1)
        for chat_id_db, name in user_chats:
            kb.add(InlineKeyboardButton(f"⚙️ {name}", callback_data=f"chat_settings_{chat_id_db}"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
        
        bot.edit_message_text(
            "<b>⚙️ НАСТРОЙКИ ЧАТОВ</b>\n\nВыбери чат для настройки:",
            chat_id,
            message_id,
            reply_markup=kb
        )
        bot.answer_callback_query(call.id)
        return
    
    # Настройки конкретного чата
    if call.data.startswith("chat_settings_"):
        target_chat_id = int(call.data.split("_")[2])
        if not is_chat_owner(user_id, target_chat_id):
            bot.answer_callback_query(call.id, "❌ Ты не владелец этого чата!", show_alert=True)
            return
        
        bot.edit_message_text(
            f"<b>⚙️ НАСТРОЙКИ ЧАТА</b>\n\nЧат ID: {target_chat_id}\nВыбери параметр:",
            chat_id,
            message_id,
            reply_markup=chat_settings_kb(target_chat_id)
        )
        bot.answer_callback_query(call.id)
        return
    
    # Установка макс игроков
    if call.data.startswith("set_max_players_"):
        target_chat_id = int(call.data.split("_")[3])
        if not is_chat_owner(user_id, target_chat_id):
            bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
            return
        msg = bot.send_message(user_id, "Введите максимальное количество игроков (от 2 до 15):")
        bot.register_next_step_handler(msg, set_max_players_callback, target_chat_id, chat_id, message_id)
        bot.answer_callback_query(call.id)
        return
    
    # Установка мин ставки
    if call.data.startswith("set_min_bet_"):
        target_chat_id = int(call.data.split("_")[3])
        if not is_chat_owner(user_id, target_chat_id):
            bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
            return
        msg = bot.send_message(user_id, "Введите минимальную ставку (от 1 до 1000):")
        bot.register_next_step_handler(msg, set_min_bet_callback, target_chat_id, chat_id, message_id)
        bot.answer_callback_query(call.id)
        return
    
    # Установка макс ставки
    if call.data.startswith("set_max_bet_"):
        target_chat_id = int(call.data.split("_")[3])
        if not is_chat_owner(user_id, target_chat_id):
            bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
            return
        msg = bot.send_message(user_id, "Введите максимальную ставку (от 10 до 10000):")
        bot.register_next_step_handler(msg, set_max_bet_callback, target_chat_id, chat_id, message_id)
        bot.answer_callback_query(call.id)
        return
    
    # Вкл/выкл игры
    if call.data.startswith("toggle_game_"):
        target_chat_id = int(call.data.split("_")[2])
        if not is_chat_owner(user_id, target_chat_id):
            bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
            return
        settings = get_chat_settings(target_chat_id)
        new_state = 0 if settings['game_enabled'] else 1
        update_chat_settings(target_chat_id, game_enabled=new_state)
        bot.answer_callback_query(call.id, f"Игры {'включены' if new_state else 'выключены'}")
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=chat_settings_kb(target_chat_id))
        return
    
    # Только админы
    if call.data.startswith("toggle_admin_only_"):
        target_chat_id = int(call.data.split("_")[3])
        if not is_chat_owner(user_id, target_chat_id):
            bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
            return
        settings = get_chat_settings(target_chat_id)
        new_state = 0 if settings['admin_only'] else 1
        update_chat_settings(target_chat_id, admin_only=new_state)
        bot.answer_callback_query(call.id, f"Игры {'только для админов' if new_state else 'для всех'}")
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=chat_settings_kb(target_chat_id))
        return
    
    # Магазин
    if call.data == "shop":
        bot.edit_message_text(
            "<b>🛒 МАГАЗИН</b>\n\n"
            "Покупай защиты за 💎:\n\n"
            "🛡️ <b>Щит</b> (100 💎) — спасает от 1 патрона\n"
            "⚡ <b>Двойной шанс</b> (150 💎) — +10% к удаче на 1 игру\n"
            "💰 <b>Страховка</b> (200 💎) — возврат 50% ставки при вылете\n\n"
            "Защиты активируются автоматически во время игры!",
            chat_id,
            message_id,
            reply_markup=shop_kb()
        )
        bot.answer_callback_query(call.id)
        return
    
    # Покупка щита
    if call.data == "buy_shield":
        user = get_user(user_id)
        if user["bullets"] >= 100:
            update_user(user_id, bullets=user["bullets"] - 100, shields=user["shields"] + 1)
            bot.answer_callback_query(call.id, "✅ Куплен щит!", show_alert=True)
            bot.edit_message_text(
                f"🛡️ Щит куплен!\n💰 Осталось: {user['bullets'] - 100} 💎\nЩитов: {user['shields'] + 1}",
                chat_id,
                message_id,
                reply_markup=back_button()
            )
        else:
            bot.answer_callback_query(call.id, f"❌ Не хватает 💎! Нужно 100", show_alert=True)
        return
    
    # Покупка двойного шанса
    if call.data == "buy_double":
        user = get_user(user_id)
        if user["bullets"] >= 150:
            update_user(user_id, bullets=user["bullets"] - 150, double_chance=user["double_chance"] + 1)
            bot.answer_callback_query(call.id, "✅ Куплен двойной шанс!", show_alert=True)
            bot.edit_message_text(
                f"⚡ Двойной шанс куплен!\n💰 Осталось: {user['bullets'] - 150} 💎\nДвойных шансов: {user['double_chance'] + 1}",
                chat_id,
                message_id,
                reply_markup=back_button()
            )
        else:
            bot.answer_callback_query(call.id, f"❌ Не хватает 💎! Нужно 150", show_alert=True)
        return
    
    # Покупка страховки
    if call.data == "buy_insurance":
        user = get_user(user_id)
        if user["bullets"] >= 200:
            update_user(user_id, bullets=user["bullets"] - 200, insurance=user["insurance"] + 1)
            bot.answer_callback_query(call.id, "✅ Куплена страховка!", show_alert=True)
            bot.edit_message_text(
                f"💰 Страховка куплена!\n💰 Осталось: {user['bullets'] - 200} 💎\nСтраховок: {user['insurance'] + 1}",
                chat_id,
                message_id,
                reply_markup=back_button()
            )
        else:
            bot.answer_callback_query(call.id, f"❌ Не хватает 💎! Нужно 200", show_alert=True)
        return
    
    # Топ меню
    if call.data == "top_menu":
        bot.edit_message_text(
            "<b>🏆 ТОПЫ</b>\n\nВыбери категорию:",
            chat_id,
            message_id,
            reply_markup=top_menu_kb()
        )
        bot.answer_callback_query(call.id)
        return
    
    # Топ по победам
    if call.data == "top_wins":
        top = get_top_players("wins", 10)
        text = "<b>🏆 ТОП ПО ПОБЕДАМ</b>\n\n"
        for i, (uid, wins, bullets) in enumerate(top, 1):
            text += f"{i}. {get_user_link(uid)} — {wins} побед, {bullets} 💎\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_button(), parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return
    
    # Топ по балансу
    if call.data == "top_bullets":
        top = get_top_players("bullets", 10)
        text = "<b>💰 ТОП ПО БАЛАНСУ</b>\n\n"
        for i, (uid, bullets, wins) in enumerate(top, 1):
            text += f"{i}. {get_user_link(uid)} — {bullets} 💎, {wins} побед\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_button(), parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return
    
    # Топ по играм
    if call.data == "top_games":
        top = get_top_players("games", 10)
        text = "<b>🎮 ТОП ПО ИГРАМ</b>\n\n"
        for i, (uid, games_count, wins) in enumerate(top, 1):
            text += f"{i}. {get_user_link(uid)} — {games_count} игр, {wins} побед\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_button(), parse_mode="HTML")
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
    
    # Админ статистика
    if call.data == "admin_stats":
        if user_id != ADMIN_ID:
            return
        total_users = get_all_users_count()
        total_games = get_total_games()
        chats = get_all_chats()
        total_chats = len(chats)
        
        text = (
            f"<b>📊 ОБЩАЯ СТАТИСТИКА</b>\n\n"
            f"📱 Всего чатов: {total_chats}\n"
            f"👥 Всего игроков: {total_users}\n"
            f"🎮 Всего игр: {total_games}\n"
        )
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    # Админ список чатов
    if call.data == "admin_chats":
        if user_id != ADMIN_ID:
            return
        chats = get_all_chats()
        text = "<b>📋 СПИСОК ЧАТОВ</b>\n\n"
        for chat_id_db, name in chats[:20]:
            text += f"📌 {name or chat_id_db}\n   ID: {chat_id_db}\n\n"
        if len(chats) > 20:
            text += f"\n... и еще {len(chats) - 20} чатов"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    # Админ топ игроков
    if call.data == "admin_top":
        if user_id != ADMIN_ID:
            return
        top = get_top_players("wins", 20)
        text = "<b>🏆 ТОП ИГРОКОВ (по победам)</b>\n\n"
        for i, (uid, wins, bullets) in enumerate(top, 1):
            text += f"{i}. {get_user_link(uid)} — {wins} побед, {bullets} 💎\n"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_button(), parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return
    
    # Админ рассылка
    if call.data == "admin_broadcast":
        if user_id != ADMIN_ID:
            return
        msg = bot.send_message(user_id, "Введите текст для рассылки во все чаты:")
        bot.register_next_step_handler(msg, broadcast_message)
        bot.answer_callback_query(call.id)
        return
    
    # Баланс
    if call.data == "balance":
        user = get_user(user_id)
        text = (
            f"💰 <b>ТВОЙ БАЛАНС</b>\n\n"
            f"💎 Кристаллов: {user['bullets']}\n"
            f"🏆 Побед: {user['wins']}\n"
            f"💀 Поражений: {user['losses']}\n"
            f"🎮 Всего игр: {user['total_games']}\n\n"
            f"🛡️ Щитов: {user['shields']}\n"
            f"⚡ Двойных шансов: {user['double_chance']}\n"
            f"💰 Страховок: {user['insurance']}"
        )
        bot.edit_message_text(text, chat_id, message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    # Бонус
    if call.data == "daily":
        user = get_user(user_id)
        last = datetime.fromisoformat(user["last_daily"]) if user["last_daily"] else datetime.min
        now = datetime.now()
        
        if now - last < timedelta(days=1):
            hours_left = 24 - (now - last).seconds // 3600
            bot.answer_callback_query(call.id, f"⏰ Бонус будет через {hours_left} ч", show_alert=True)
            return
        
        new_bullets = user["bullets"] + 50
        update_user(user_id, bullets=new_bullets, last_daily=now.isoformat())
        bot.edit_message_text(
            f"🎁 Ты получил 50 💎!\n\n💰 Новый баланс: {new_bullets} 💎",
            chat_id,
            message_id,
            reply_markup=back_button()
        )
        bot.answer_callback_query(call.id)
        return
    
    # СОЗДАТЬ ИГРУ - показываем список чатов
    if call.data == "create_game":
        user_chats = get_user_chats(user_id)
        if not user_chats:
            bot.edit_message_text(
                "❌ У тебя нет чатов с ботом!\n\n"
                "Добавь бота в групповой чат, чтобы создавать игры.",
                chat_id,
                message_id,
                reply_markup=back_button()
            )
            bot.answer_callback_query(call.id)
            return
        
        kb = InlineKeyboardMarkup(row_width=1)
        for chat_id_db, name in user_chats:
            settings = get_chat_settings(chat_id_db)
            status = "✅" if settings['game_enabled'] else "❌"
            kb.add(InlineKeyboardButton(f"{status} {name}", callback_data=f"select_chat_{chat_id_db}"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
        
        bot.edit_message_text(
            "<b>🎮 ВЫБЕРИ ЧАТ ДЛЯ ИГРЫ</b>\n\n"
            "Выбери чат, в котором хочешь создать игру:",
            chat_id,
            message_id,
            reply_markup=kb
        )
        bot.answer_callback_query(call.id)
        return
    
    # ВЫБРАН ЧАТ ДЛЯ ИГРЫ
    if call.data.startswith("select_chat_"):
        target_chat_id = int(call.data.split("_")[2])
        
        settings = get_chat_settings(target_chat_id)
        
        if not settings['game_enabled']:
            bot.answer_callback_query(call.id, "❌ Игры отключены владельцем чата!", show_alert=True)
            return
        
        if settings['admin_only'] and not is_chat_admin(user_id, target_chat_id):
            bot.answer_callback_query(call.id, "❌ Только админы могут создавать игры!", show_alert=True)
            return
        
        if target_chat_id in games and games[target_chat_id]["status"] in ["waiting", "playing"]:
            bot.answer_callback_query(call.id, "В этом чате уже есть активная игра!", show_alert=True)
            return
        
        # Создаем игру в выбранном чате
        sent_msg = bot.send_message(
            target_chat_id,
            f"🎮 <b>НОВАЯ ИГРА!</b>\n\n"
            f"{get_user_link(user_id)} создал лобби!\n"
            f"Макс игроков: {settings['max_players']}\n"
            f"Мин ставка: {settings['min_bet']} 💎\n"
            f"Макс ставка: {settings['max_bet']} 💎\n\n"
            f"⬇️ Нажми кнопку, чтобы присоединиться!",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("➕ Присоединиться", callback_data=f"join_{target_chat_id}")
            )
        )
        
        games[target_chat_id] = {
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
            "used_insurance": {}
        }
        
        bot.send_message(
            user_id,
            f"✅ Игра создана в чате {settings['name']}!\n\n"
            f"Сделай ставку (выбери сумму 💎):",
            reply_markup=bet_kb(target_chat_id)
        )
        
        bot.edit_message_text(
            f"✅ Игра создана в чате {settings['name']}!",
            chat_id,
            message_id,
            reply_markup=back_button()
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
        
        # Обновляем сообщение в чате
        update_lobby_message(game_chat_id)
        
        bot.send_message(
            user_id,
            f"🎮 Ты присоединился к игре!\n\nСделай ставку (выбери сумму 💎):",
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
        
        if user["bullets"] < bet:
            bot.answer_callback_query(call.id, f"Не хватает 💎! Нужно {bet}", show_alert=True)
            return
        
        games[game_chat_id]["bets"][user_id] = bet
        update_user(user_id, bullets=user["bullets"] - bet)
        
        bot.send_message(user_id, f"✅ Ставка {bet} 💎 принята!\nОжидай начала игры...")
        bot.answer_callback_query(call.id, f"Ставка {bet} 💎 принята!")
        
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
        
        players_names = "\n".join([f"• {get_user_link(p)} — {game['bets'][p]} 💎" for p in players_list])
        
        update_chat_stats(game_chat_id, total_games=1, total_bets=total_pot)
        for p in players_list:
            user = get_user(p)
            update_user(p, total_games=user["total_games"] + 1)
        
        bot.edit_message_text(
            f"🎲 <b>ИГРА НАЧАЛАСЬ!</b>\n\n"
            f"Участники:\n{players_names}\n\n"
            f"💰 Общий банк: {total_pot} 💎\n"
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
            f"Ставка: {current_bet} 💎\n\n"
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
            f"🔄 Барабан прокручен!\n\nСтавка: {bet} 💎\n\nГотов выстрелить?",
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
        if user["double_chance"] > 0 and game["used_double"].get(player_id, 0) == 0:
            trigger = random.randint(1, 5)
            game["used_double"][player_id] = 1
            update_user(player_id, double_chance=user["double_chance"] - 1)
            bot.send_message(player_id, "⚡ ДВОЙНОЙ ШАНС АКТИВИРОВАН!")
        
        is_dead = (trigger == chamber)
        
        if is_dead:
            if user["shields"] > 0 and game["used_shields"].get(player_id, 0) == 0:
                is_dead = False
                game["used_shields"][player_id] = 1
                update_user(player_id, shields=user["shields"] - 1)
                bot.send_message(player_id, "🛡️ ЩИТ АКТИВИРОВАН! Ты выжил!")
        
        if is_dead:
            refund = 0
            if user["insurance"] > 0 and game["used_insurance"].get(player_id, 0) == 0:
                refund = bet // 2
                game["used_insurance"][player_id] = 1
                update_user(player_id, insurance=user["insurance"] - 1)
                bot.send_message(player_id, f"💰 СТРАХОВКА! Возвращено: {refund} 💎")
            
            game["players"].remove(player_id)
            update_user(player_id, losses=user["losses"] + 1, bullets=user["bullets"] + refund)
            
            if len(game["players"]) == 1:
                winner_id = game["players"][0]
                total_pot = sum(game["bets"].values())
                
                winner = get_user(winner_id)
                update_user(winner_id, bullets=winner["bullets"] + total_pot, wins=winner["wins"] + 1)
                
                bot.edit_message_text(
                    f"💀 <b>{get_user_link(player_id)} ВЫБЫЛ!</b>\n\n"
                    f"🏆 <b>ПОБЕДИТЕЛЬ: {get_user_link(winner_id)}</b>\n"
                    f"💰 Выигрыш: {total_pot} 💎",
                    game_chat_id,
                    game["message_id"]
                )
                
                bot.send_message(winner_id, f"🏆 Ты победил! Выигрыш: {total_pot} 💎")
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
                f"💰 Банк: {total_pot} 💎\n"
                f"🔫 Ход: {get_user_link(current)}",
                game_chat_id,
                game["message_id"]
            )
            
            bot.send_message(
                current,
                f"🔫 <b>ТВОЙ ХОД!</b>\n\n"
                f"Ставка: {current_bet} 💎\n\n"
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
                f"💰 Банк: {total_pot} 💎\n"
                f"🔫 Ход: {get_user_link(current)}",
                game_chat_id,
                game["message_id"]
            )
            
            bot.send_message(
                current,
                f"🔫 <b>ТВОЙ ХОД!</b>\n\n"
                f"Ставка: {current_bet} 💎\n\n"
                f"Выбери действие:",
                reply_markup=game_action_kb(game_chat_id, current, current_bet)
            )
            
            bot.answer_callback_query(call.id, "Пусто! Ты выжил.")
        
        return

# ========== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ==========
def set_max_players_callback(message, target_chat_id, original_chat_id, original_message_id):
    try:
        val = int(message.text)
        if 2 <= val <= MAX_PLAYERS_LIMIT:
            update_chat_settings(target_chat_id, max_players=val)
            bot.send_message(message.chat.id, f"✅ Максимум игроков установлен: {val}")
            
            # Обновляем сообщение с настройками
            bot.edit_message_reply_markup(original_chat_id, original_message_id, reply_markup=chat_settings_kb(target_chat_id))
        else:
            bot.send_message(message.chat.id, f"❌ Введите число от 2 до {MAX_PLAYERS_LIMIT}")
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")

def set_min_bet_callback(message, target_chat_id, original_chat_id, original_message_id):
    try:
        val = int(message.text)
        if 1 <= val <= 1000:
            update_chat_settings(target_chat_id, min_bet=val)
            bot.send_message(message.chat.id, f"✅ Минимальная ставка: {val} 💎")
            bot.edit_message_reply_markup(original_chat_id, original_message_id, reply_markup=chat_settings_kb(target_chat_id))
        else:
            bot.send_message(message.chat.id, "❌ Введите число от 1 до 1000")
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")

def set_max_bet_callback(message, target_chat_id, original_chat_id, original_message_id):
    try:
        val = int(message.text)
        if 10 <= val <= 10000:
            update_chat_settings(target_chat_id, max_bet=val)
            bot.send_message(message.chat.id, f"✅ Максимальная ставка: {val} 💎")
            bot.edit_message_reply_markup(original_chat_id, original_message_id, reply_markup=chat_settings_kb(target_chat_id))
        else:
            bot.send_message(message.chat.id, "❌ Введите число от 10 до 10000")
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")

def broadcast_message(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    text = message.text
    chats = get_all_chats()
    success = 0
    fail = 0
    
    for chat_id_db, name in chats:
        try:
            bot.send_message(chat_id_db, f"📢 <b>РАССЫЛКА ОТ АДМИНА</b>\n\n{text}")
            success += 1
        except:
            fail += 1
    
    bot.send_message(ADMIN_ID, f"✅ Рассылка завершена!\nУспешно: {success}\n❌ Ошибок: {fail}")

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    init_db()
    print("✅ Бот запущен!")
    print(f"📱 Username: @{BOT_USERNAME}")
    print(f"👑 Admin ID: {ADMIN_ID}")
    bot.infinity_polling()