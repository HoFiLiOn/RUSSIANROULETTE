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
BET_AMOUNTS = [10, 50, 100, 500]
MAX_PLAYERS = 6
ADMIN_ID = 7040677455

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
                  losses INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS chat_settings
                 (chat_id INTEGER PRIMARY KEY,
                  min_bet INTEGER DEFAULT 10,
                  max_bet INTEGER DEFAULT 500,
                  game_enabled INTEGER DEFAULT 1,
                  admin_only INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT bullets, last_daily, wins, losses FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (user_id, bullets, last_daily) VALUES (?, ?, ?)",
                  (user_id, 100, datetime.now().isoformat()))
        conn.commit()
        c.execute("SELECT bullets, last_daily, wins, losses FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
    conn.close()
    return {"bullets": user[0], "last_daily": user[1], "wins": user[2], "losses": user[3]}

def update_user(user_id, bullets=None, wins=None, losses=None, last_daily=None):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    if bullets is not None:
        c.execute("UPDATE users SET bullets = ? WHERE user_id = ?", (bullets, user_id))
    if wins is not None:
        c.execute("UPDATE users SET wins = ? WHERE user_id = ?", (wins, user_id))
    if losses is not None:
        c.execute("UPDATE users SET losses = ? WHERE user_id = ?", (losses, user_id))
    if last_daily is not None:
        c.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", (last_daily, user_id))
    conn.commit()
    conn.close()

def get_chat_settings(chat_id):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT min_bet, max_bet, game_enabled, admin_only FROM chat_settings WHERE chat_id = ?", (chat_id,))
    settings = c.fetchone()
    if not settings:
        c.execute("INSERT INTO chat_settings (chat_id) VALUES (?)", (chat_id,))
        conn.commit()
        settings = (10, 500, 1, 0)
    conn.close()
    return {"min_bet": settings[0], "max_bet": settings[1], "game_enabled": settings[2], "admin_only": settings[3]}

def update_chat_settings(chat_id, min_bet=None, max_bet=None, game_enabled=None, admin_only=None):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    if min_bet is not None:
        c.execute("UPDATE chat_settings SET min_bet = ? WHERE chat_id = ?", (min_bet, chat_id))
    if max_bet is not None:
        c.execute("UPDATE chat_settings SET max_bet = ? WHERE chat_id = ?", (max_bet, chat_id))
    if game_enabled is not None:
        c.execute("UPDATE chat_settings SET game_enabled = ? WHERE chat_id = ?", (game_enabled, chat_id))
    if admin_only is not None:
        c.execute("UPDATE chat_settings SET admin_only = ? WHERE chat_id = ?", (admin_only, chat_id))
    conn.commit()
    conn.close()

def get_name(user_id):
    try:
        user = bot.get_chat(user_id)
        return f"@{user.username}" if user.username else user.first_name
    except:
        return str(user_id)

def is_admin(user_id, chat_id):
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
def main_menu(chat_id):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🎮 Создать игру", callback_data="create_game"))
    kb.add(InlineKeyboardButton("💰 Баланс", callback_data="balance"))
    kb.add(InlineKeyboardButton("🎁 Бонус", callback_data="daily"))
    kb.add(InlineKeyboardButton("📜 Правила", callback_data="rules"))
    
    if is_admin(chat_id, chat_id) or chat_id == ADMIN_ID:
        kb.add(InlineKeyboardButton("⚙️ Админ панель", callback_data="admin_panel"))
    
    return kb

def admin_panel_kb(chat_id):
    settings = get_chat_settings(chat_id)
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"💰 Мин. ставка: {settings['min_bet']}", callback_data="admin_min_bet"))
    kb.add(InlineKeyboardButton(f"💎 Макс. ставка: {settings['max_bet']}", callback_data="admin_max_bet"))
    kb.add(InlineKeyboardButton(f"🎮 Игры: {'✅ Вкл' if settings['game_enabled'] else '❌ Выкл'}", callback_data="admin_toggle_game"))
    kb.add(InlineKeyboardButton(f"👑 Только админы: {'✅ Да' if settings['admin_only'] else '❌ Нет'}", callback_data="admin_toggle_admin_only"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def game_lobby_kb(chat_id, creator, all_bets_placed=False):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("➕ Присоединиться", callback_data=f"join_{chat_id}"))
    if creator and all_bets_placed:
        kb.add(InlineKeyboardButton("🚀 Начать игру", callback_data=f"start_game_{chat_id}"))
    kb.add(InlineKeyboardButton("❌ Отменить", callback_data="cancel_game"))
    return kb

def game_action_kb(chat_id, user_id, bet):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🔫 Выстрелить", callback_data=f"shoot_{chat_id}_{user_id}_{bet}"))
    kb.add(InlineKeyboardButton("🔄 Крутить барабан", callback_data=f"spin_{chat_id}_{user_id}_{bet}"))
    return kb

def bet_kb(chat_id):
    settings = get_chat_settings(chat_id)
    kb = InlineKeyboardMarkup(row_width=1)
    for bet in BET_AMOUNTS:
        if settings['min_bet'] <= bet <= settings['max_bet']:
            kb.add(InlineKeyboardButton(f"{bet} 💎", callback_data=f"place_bet_{chat_id}_{bet}"))
    return kb

def back_button():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

# ========== ОПИСАНИЕ ==========
def get_rules():
    return (
        "<b>🔫 РУССКАЯ РУЛЕТКА 🔫</b>\n\n"
        "<b>🎲 Правила игры:</b>\n"
        "• Один игрок создает лобби\n"
        "• Другие присоединяются (до 6 игроков)\n"
        "• Каждый делает ставку 💎\n"
        "• Игроки ходят по очереди\n"
        "• Если выпадает пусто → игрок продолжает\n"
        "• Если выпадает патрон → игрок выбывает, теряет ставку\n"
        "• Последний выживший забирает банк!\n\n"
        "<b>💰 Как получить 💎:</b>\n"
        "• Ежедневный бонус — 50 💎\n"
        "• Победы в игре — банк всех ставок\n\n"
        "<b>📌 Команды:</b>\n"
        "/start — главное меню\n"
        "/balance — баланс\n"
        "/daily — бонус\n"
        "/rules — правила"
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
            players_list.append(f"• {get_name(p)} — {game['bets'][p]} 💎")
        else:
            players_list.append(f"• {get_name(p)} — ожидает ставку")
    
    players_text = "\n".join(players_list)
    total_pot = sum(game["bets"].values()) if game["bets"] else 0
    
    status_text = ""
    if not all_bets_placed:
        status_text = "\n\n⚠️ Ожидаем ставки от всех игроков..."
    else:
        status_text = f"\n\n✅ Все ставки сделаны!\n💰 Общий банк: {total_pot} 💎"
    
    text = (
        f"🎮 <b>ЛОББИ ИГРЫ</b>\n\n"
        f"Создатель: {get_name(game['creator'])}\n"
        f"Участники ({players_count}/{MAX_PLAYERS}):\n{players_text}"
        f"{status_text}"
    )
    
    try:
        bot.edit_message_text(
            text,
            chat_id,
            game["message_id"],
            reply_markup=game_lobby_kb(chat_id, game["creator"] == game["creator"], all_bets_placed)
        )
    except:
        pass

def update_game_message(chat_id):
    game = games.get(chat_id)
    if not game or game["status"] != "playing":
        return
    
    players_list = []
    for p in game["players"]:
        status = "🔫 в игре"
        if p == game["current_player"]:
            status = "🎯 ХОДИТ"
        players_list.append(f"• {get_name(p)} — {status}")
    
    players_text = "\n".join(players_list)
    total_pot = sum(game["bets"].values())
    
    text = (
        f"🎲 <b>ИГРА ИДЕТ!</b>\n\n"
        f"Участники:\n{players_text}\n\n"
        f"💰 Общий банк: {total_pot} 💎\n"
        f"🔫 Ход: {get_name(game['current_player'])}"
    )
    
    try:
        bot.edit_message_text(
            text,
            chat_id,
            game["message_id"]
        )
    except:
        pass

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    init_db()
    get_user(message.from_user.id)
    
    bot.send_message(
        message.chat.id,
        f"<b>🔫 Добро пожаловать в Русскую Рулетку, {message.from_user.first_name}!</b>\n\n{get_rules()}",
        reply_markup=main_menu(message.chat.id)
    )

@bot.message_handler(commands=['rules'])
def rules_command(message):
    bot.send_message(
        message.chat.id,
        get_rules(),
        reply_markup=main_menu(message.chat.id)
    )

@bot.message_handler(commands=['balance'])
def balance_command(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    bot.reply_to(
        message,
        f"💰 <b>Баланс:</b> {user['bullets']} 💎\n"
        f"🏆 Побед: {user['wins']} | 💀 Поражений: {user['losses']}"
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

# ========== КОЛБЭКИ ==========
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    # Назад
    if call.data == "back":
        bot.edit_message_text(
            f"<b>🔫 Главное меню</b>\n\n{get_rules()}",
            chat_id,
            message_id,
            reply_markup=main_menu(chat_id)
        )
        bot.answer_callback_query(call.id)
        return
    
    # Админ панель
    if call.data == "admin_panel":
        if not is_admin(user_id, chat_id):
            bot.answer_callback_query(call.id, "❌ Только админы чата!", show_alert=True)
            return
        
        bot.edit_message_text(
            f"<b>⚙️ АДМИН ПАНЕЛЬ</b>\n\nНастройки чата:",
            chat_id,
            message_id,
            reply_markup=admin_panel_kb(chat_id)
        )
        bot.answer_callback_query(call.id)
        return
    
    # Админ настройки
    if call.data == "admin_min_bet":
        if not is_admin(user_id, chat_id):
            bot.answer_callback_query(call.id, "❌ Только админы!", show_alert=True)
            return
        bot.send_message(user_id, "Введите новую минимальную ставку (от 1 до 500):")
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_max_bet":
        if not is_admin(user_id, chat_id):
            bot.answer_callback_query(call.id, "❌ Только админы!", show_alert=True)
            return
        bot.send_message(user_id, "Введите новую максимальную ставку (от 10 до 1000):")
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_toggle_game":
        if not is_admin(user_id, chat_id):
            bot.answer_callback_query(call.id, "❌ Только админы!", show_alert=True)
            return
        settings = get_chat_settings(chat_id)
        new_state = 0 if settings['game_enabled'] else 1
        update_chat_settings(chat_id, game_enabled=new_state)
        bot.answer_callback_query(call.id, f"Игры {'включены' if new_state else 'выключены'}")
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=admin_panel_kb(chat_id))
        return
    
    if call.data == "admin_toggle_admin_only":
        if not is_admin(user_id, chat_id):
            bot.answer_callback_query(call.id, "❌ Только админы!", show_alert=True)
            return
        settings = get_chat_settings(chat_id)
        new_state = 0 if settings['admin_only'] else 1
        update_chat_settings(chat_id, admin_only=new_state)
        bot.answer_callback_query(call.id, f"Игры {'только для админов' if new_state else 'для всех'}")
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=admin_panel_kb(chat_id))
        return
    
    # Правила
    if call.data == "rules":
        bot.edit_message_text(
            get_rules(),
            chat_id,
            message_id,
            reply_markup=back_button()
        )
        bot.answer_callback_query(call.id)
        return
    
    # Баланс
    if call.data == "balance":
        user = get_user(user_id)
        bot.edit_message_text(
            f"💰 <b>Твой баланс:</b> {user['bullets']} 💎\n"
            f"🏆 Побед: {user['wins']} | 💀 Поражений: {user['losses']}",
            chat_id,
            message_id,
            reply_markup=back_button()
        )
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
    
    # Отменить игру
    if call.data == "cancel_game":
        if chat_id in games:
            if games[chat_id]["creator"] == user_id or is_admin(user_id, chat_id):
                del games[chat_id]
                bot.edit_message_text(
                    "❌ Игра отменена",
                    chat_id,
                    message_id,
                    reply_markup=main_menu(chat_id)
                )
                bot.answer_callback_query(call.id, "Игра отменена")
            else:
                bot.answer_callback_query(call.id, "Только создатель может отменить игру", show_alert=True)
        return
    
    # СОЗДАТЬ ИГРУ
    if call.data == "create_game":
        settings = get_chat_settings(chat_id)
        
        if not settings['game_enabled']:
            bot.answer_callback_query(call.id, "❌ Игры отключены админом чата!", show_alert=True)
            return
        
        if settings['admin_only'] and not is_admin(user_id, chat_id):
            bot.answer_callback_query(call.id, "❌ Только админы могут создавать игры!", show_alert=True)
            return
        
        if chat_id in games and games[chat_id]["status"] in ["waiting", "playing"]:
            bot.answer_callback_query(call.id, "В этом чате уже есть активная игра!", show_alert=True)
            return
        
        sent_msg = bot.send_message(
            chat_id,
            f"🎮 <b>Создается лобби...</b>"
        )
        
        games[chat_id] = {
            "players": [user_id],
            "bets": {},
            "chambers": {},
            "status": "waiting",
            "current_player": None,
            "creator": user_id,
            "message_id": sent_msg.message_id
        }
        
        players_list = f"• {get_name(user_id)} — ожидает ставку"
        
        bot.edit_message_text(
            f"🎮 <b>ЛОББИ ИГРЫ</b>\n\n"
            f"Создатель: {get_name(user_id)}\n"
            f"Участники (1/{MAX_PLAYERS}):\n{players_list}\n\n"
            f"⚠️ Ожидаем ставки от всех игроков...",
            chat_id,
            sent_msg.message_id,
            reply_markup=game_lobby_kb(chat_id, True, False)
        )
        
        bot.send_message(
            user_id,
            f"🎮 Ты создал игру в чате!\n\n"
            f"Сделай ставку (выбери сумму 💎):",
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
        
        if len(games[game_chat_id]["players"]) >= MAX_PLAYERS:
            bot.answer_callback_query(call.id, "Лобби заполнено!", show_alert=True)
            return
        
        games[game_chat_id]["players"].append(user_id)
        update_lobby_message(game_chat_id)
        
        bot.send_message(
            user_id,
            f"🎮 Ты присоединился к игре в чате!\n\n"
            f"Сделай ставку (выбери сумму 💎):",
            reply_markup=bet_kb(game_chat_id)
        )
        
        bot.answer_callback_query(call.id, "Ты присоединился! Сделай ставку в ЛС.")
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
        
        bot.send_message(
            user_id,
            f"✅ Ставка {bet} 💎 принята!\nОжидай начала игры..."
        )
        
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
        
        players_names = "\n".join([f"• {get_name(p)} — {game['bets'][p]} 💎" for p in players_list])
        
        bot.edit_message_text(
            f"🎲 <b>ИГРА НАЧАЛАСЬ!</b>\n\n"
            f"Участники:\n{players_names}\n\n"
            f"💰 Общий банк: {total_pot} 💎\n"
            f"🔫 Первый ход: {get_name(game['current_player'])}",
            game_chat_id,
            game["message_id"],
            reply_markup=game_action_kb(game_chat_id, game["current_player"], game["bets"][game["current_player"]])
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
        
        bot.edit_message_text(
            f"🔄 Барабан прокручен!\n\n"
            f"Ставка: {bet} 💎\n"
            f"Готов выстрелить?",
            game_chat_id,
            game["message_id"],
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
        
        if trigger == chamber:
            game["players"].remove(player_id)
            update_user(player_id, losses=get_user(player_id)["losses"] + 1)
            
            if len(game["players"]) == 1:
                winner_id = game["players"][0]
                total_pot = sum(game["bets"].values())
                
                user = get_user(winner_id)
                update_user(winner_id, bullets=user["bullets"] + total_pot, wins=user["wins"] + 1)
                
                bot.edit_message_text(
                    f"💀 <b>{get_name(player_id)} ВЫБЫЛ!</b>\n\n"
                    f"🏆 <b>ПОБЕДИТЕЛЬ: {get_name(winner_id)}</b>\n"
                    f"💰 Выигрыш: {total_pot} 💎",
                    game_chat_id,
                    game["message_id"],
                    reply_markup=main_menu(game_chat_id)
                )
                
                bot.send_message(winner_id, f"🏆 Ты победил! Выигрыш: {total_pot} 💎")
                del games[game_chat_id]
                bot.answer_callback_query(call.id, "Ты выбыл!")
                return
            
            game["current_player"] = game["players"][0]
            current = game["current_player"]
            current_bet = game["bets"][current]
            
            players_list = "\n".join([f"• {get_name(p)}" for p in game["players"]])
            total_pot = sum(game["bets"].values())
            
            bot.edit_message_text(
                f"💀 <b>{get_name(player_id)} ВЫБЫЛ!</b>\n\n"
                f"Остались:\n{players_list}\n\n"
                f"💰 Банк: {total_pot} 💎\n"
                f"🔫 Ход: {get_name(current)}",
                game_chat_id,
                game["message_id"],
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
                f"🍀 <b>{get_name(player_id)} ВЫЖИЛ!</b>\n\n"
                f"💰 Банк: {total_pot} 💎\n"
                f"🔫 Ход: {get_name(current)}",
                game_chat_id,
                game["message_id"],
                reply_markup=game_action_kb(game_chat_id, current, current_bet)
            )
            
            bot.answer_callback_query(call.id, "Пусто! Ты выжил.")
        
        return

# ========== ОБРАБОТКА СООБЩЕНИЙ ДЛЯ НАСТРОЕК ==========
@bot.message_handler(func=lambda message: True)
def handle_admin_input(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем, что это админ и сообщение в ЛС
    if message.chat.type != "private":
        return
    
    # Настройка минимальной ставки
    if message.text.isdigit() and int(message.text) > 0:
        # Ищем последнюю админ команду
        settings = get_chat_settings(chat_id)
        # Временное решение: ждем что админ вводит числа
        pass

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    init_db()
    print("Бот запущен!")
    print(f"Username: @{BOT_USERNAME}")
    print(f"Admin ID: {ADMIN_ID}")
    bot.infinity_polling()