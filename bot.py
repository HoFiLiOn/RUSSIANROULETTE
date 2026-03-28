import telebot
import sqlite3
import random
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ========== КОНФИГ ==========
BOT_TOKEN = "8412567351:AAG7eEMXlNfDBsNZF08GD-Pr-LH-2z1txSQ"
BOT_USERNAME = "RussianRoulette_official_bot"
BET_AMOUNTS = [10, 50, 100, 500]
MAX_PLAYERS = 6

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

def get_name(user_id):
    try:
        user = bot.get_chat(user_id)
        return f"@{user.username}" if user.username else user.first_name
    except:
        return str(user_id)

# ========== ХРАНИЛИЩЕ ИГР ==========
games = {}

# ========== КЛАВИАТУРЫ ==========
def main_menu():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🎮 Создать игру", callback_data="create_game"))
    kb.add(InlineKeyboardButton("💰 Баланс", callback_data="balance"))
    kb.add(InlineKeyboardButton("🎁 Бонус", callback_data="daily"))
    kb.add(InlineKeyboardButton("📜 Правила", callback_data="rules"))
    return kb

def game_lobby_kb(chat_id, creator, all_bets_placed=False):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("➕ Присоединиться", callback_data=f"join_{chat_id}"))
    if creator and all_bets_placed:
        kb.add(InlineKeyboardButton("🚀 Начать игру", callback_data=f"start_game_{chat_id}"))
    kb.add(InlineKeyboardButton("❌ Отменить", callback_data="back"))
    return kb

def action_menu(user_id, bet):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🔫 Выстрелить", callback_data=f"shoot_{user_id}_{bet}"))
    kb.add(InlineKeyboardButton("🔄 Крутить барабан", callback_data=f"spin_{user_id}_{bet}"))
    return kb

def back_button():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="back"))
    return kb

def bet_kb(game_chat_id):
    kb = InlineKeyboardMarkup(row_width=1)
    for bet in BET_AMOUNTS:
        kb.add(InlineKeyboardButton(f"{bet} 💎", callback_data=f"place_bet_{game_chat_id}_{bet}"))
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
    """Обновляет сообщение лобби"""
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
    
    is_creator = (game["creator"] == game["creator"])  # для проверки, но нужно передавать
    # Просто обновляем с правильной кнопкой
    
    bot.edit_message_text(
        text,
        chat_id,
        game["message_id"],
        reply_markup=game_lobby_kb(chat_id, True, all_bets_placed)
    )

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    init_db()
    get_user(message.from_user.id)
    bot.send_message(
        message.chat.id,
        f"<b>🔫 Добро пожаловать в Русскую Рулетку, {message.from_user.first_name}!</b>\n\n{get_rules()}",
        reply_markup=main_menu()
    )

@bot.message_handler(commands=['rules'])
def rules_command(message):
    bot.send_message(
        message.chat.id,
        get_rules(),
        reply_markup=main_menu()
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
            reply_markup=main_menu()
        )
        bot.answer_callback_query(call.id)
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
    
    # СОЗДАТЬ ИГРУ
    if call.data == "create_game":
        # Проверяем, есть ли уже игра в этом чате
        if chat_id in games and games[chat_id]["status"] in ["waiting", "playing"]:
            bot.answer_callback_query(call.id, "В этом чате уже есть активная игра!", show_alert=True)
            return
        
        # Создаем новую игру и отправляем сообщение в чат
        sent_msg = bot.send_message(
            chat_id,
            f"🎮 <b>Создается лобби...</b>",
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔄 Загрузка", callback_data="none"))
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
        
        # Отправляем создателю в ЛС предложение сделать ставку
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
        
        # Обновляем сообщение в чате
        update_lobby_message(game_chat_id)
        
        # Отправляем в ЛС предложение сделать ставку
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
        
        # Сохраняем ставку
        games[game_chat_id]["bets"][user_id] = bet
        # Списываем сразу
        update_user(user_id, bullets=user["bullets"] - bet)
        
        bot.send_message(
            user_id,
            f"✅ Ставка {bet} 💎 принята!\nОжидай начала игры..."
        )
        
        bot.answer_callback_query(call.id, f"Ставка {bet} 💎 принята!")
        
        # Обновляем сообщение лобби
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
        
        # Проверяем ставки
        for p in game["players"]:
            if p not in game["bets"]:
                bot.answer_callback_query(call.id, "Не все игроки сделали ставки!", show_alert=True)
                return
        
        # Инициализируем игру
        game["status"] = "playing"
        players_list = game["players"].copy()
        random.shuffle(players_list)
        game["players"] = players_list
        game["current_player"] = players_list[0]
        
        # Создаем барабаны
        for p in players_list:
            game["chambers"][p] = random.randint(1, 6)
        
        total_pot = sum(game["bets"].values())
        
        players_names = "\n".join([f"• {get_name(p)} — {game['bets'][p]} 💎" for p in players_list])
        
        bot.edit_message_text(
            f"🎲 <b>ИГРА НАЧАЛАСЬ!</b>\n\n"
            f"Участники:\n{players_names}\n\n"
            f"Общий банк: {total_pot} 💎\n\n"
            f"Первый ход: {get_name(game['current_player'])}\n\n"
            f"Игроки, проверьте личные сообщения!",
            game_chat_id,
            game["message_id"]
        )
        
        # Отправляем ход первому игроку в ЛС
        current = game["current_player"]
        bet = game["bets"][current]
        
        bot.send_message(
            current,
            f"🔫 <b>ТВОЙ ХОД!</b>\n\n"
            f"Ставка: {bet} 💎\n\n"
            f"Выбери действие:",
            reply_markup=action_menu(current, bet)
        )
        
        bot.answer_callback_query(call.id, "Игра начата!")
        return
    
    # КРУТИТЬ БАРАБАН
    if call.data.startswith("spin_"):
        parts = call.data.split("_")
        player_id = int(parts[1])
        bet = int(parts[2])
        
        # Находим игру
        game = None
        game_chat_id = None
        for gid, g in games.items():
            if g["status"] == "playing" and g["current_player"] == player_id and player_id in g["players"]:
                game = g
                game_chat_id = gid
                break
        
        if not game:
            bot.answer_callback_query(call.id, "Не твой ход или игра завершена!", show_alert=True)
            return
        
        # Крутим барабан
        game["chambers"][player_id] = random.randint(1, 6)
        
        bot.send_message(
            player_id,
            f"🔄 Барабан прокручен!\n\n"
            f"Ставка: {bet} 💎\n\n"
            f"Готов выстрелить?",
            reply_markup=action_menu(player_id, bet)
        )
        
        bot.answer_callback_query(call.id, "Барабан прокручен!")
        return
    
    # ВЫСТРЕЛИТЬ
    if call.data.startswith("shoot_"):
        parts = call.data.split("_")
        player_id = int(parts[1])
        bet = int(parts[2])
        
        # Находим игру
        game = None
        game_chat_id = None
        for gid, g in games.items():
            if g["status"] == "playing" and g["current_player"] == player_id and player_id in g["players"]:
                game = g
                game_chat_id = gid
                break
        
        if not game:
            bot.answer_callback_query(call.id, "Не твой ход или игра завершена!", show_alert=True)
            return
        
        chamber = game["chambers"][player_id]
        trigger = random.randint(1, 6)
        
        if trigger == chamber:
            # ПРОИГРЫШ - выбывает
            game["players"].remove(player_id)
            update_user(player_id, losses=get_user(player_id)["losses"] + 1)
            
            bot.send_message(
                player_id,
                f"💀 <b>БАХ!</b>\n\n"
                f"Выпал патрон. Ты выбываешь из игры!\n"
                f"Потеряно: {bet} 💎"
            )
            
            bot.send_message(
                game_chat_id,
                f"💀 <b>{get_name(player_id)} выбыл!</b>\nОсталось игроков: {len(game['players'])}"
            )
            
            # Проверяем победителя
            if len(game["players"]) == 1:
                winner_id = game["players"][0]
                total_pot = sum(game["bets"].values())
                
                user = get_user(winner_id)
                update_user(winner_id, bullets=user["bullets"] + total_pot, wins=user["wins"] + 1)
                
                bot.send_message(
                    winner_id,
                    f"🏆 <b>ТЫ ПОБЕДИЛ!</b>\n\n"
                    f"Ты выиграл {total_pot} 💎!"
                )
                
                bot.send_message(
                    game_chat_id,
                    f"🏆 <b>ИГРА ОКОНЧЕНА!</b>\n\n"
                    f"Победитель: {get_name(winner_id)}\n"
                    f"Выигрыш: {total_pot} 💎!"
                )
                
                del games[game_chat_id]
                bot.answer_callback_query(call.id, "Ты выбыл!")
                return
            
            # Следующий ход
            game["current_player"] = game["players"][0]
            current = game["current_player"]
            current_bet = game["bets"][current]
            
            bot.send_message(
                current,
                f"🔫 <b>ТВОЙ ХОД!</b>\n\n"
                f"Ставка: {current_bet} 💎\n\n"
                f"Выбери действие:",
                reply_markup=action_menu(current, current_bet)
            )
            
            bot.send_message(
                game_chat_id,
                f"🔫 Следующий ход: {get_name(current)}"
            )
            
            bot.answer_callback_query(call.id, "Ты выбыл!")
            
        else:
            # ПРОДОЛЖАЕТ
            bot.send_message(
                player_id,
                f"🍀 <b>ЩЕЛЧОК...</b>\n\n"
                f"Пусто! Ты продолжаешь игру."
            )
            
            # Следующий ход
            current_index = game["players"].index(player_id)
            next_index = (current_index + 1) % len(game["players"])
            game["current_player"] = game["players"][next_index]
            current = game["current_player"]
            current_bet = game["bets"][current]
            
            bot.send_message(
                current,
                f"🔫 <b>ТВОЙ ХОД!</b>\n\n"
                f"Ставка: {current_bet} 💎\n\n"
                f"Выбери действие:",
                reply_markup=action_menu(current, current_bet)
            )
            
            bot.send_message(
                game_chat_id,
                f"🍀 {get_name(player_id)} выжил!\n🔫 Следующий ход: {get_name(current)}"
            )
            
            bot.answer_callback_query(call.id, "Пусто! Ты выжил.")
        
        return

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    init_db()
    print("Бот запущен!")
    print(f"Username: @{BOT_USERNAME}")
    bot.infinity_polling()