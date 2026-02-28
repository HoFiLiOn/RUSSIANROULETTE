import telebot
from telebot import types
import random
import json
import os
import threading
import time
from datetime import datetime

# ========== ТОКЕН ==========
TOKEN = "8412567351:AAG7eEMXlNfDBsNZF08GD-Pr-LH-2z1txSQ"
bot = telebot.TeleBot(TOKEN)

# ========== ID АДМИНА ==========
ADMIN_ID = 8388843828

# ========== ФАЙЛЫ ==========
LOBBIES_FILE = "lobbies.json"
USERS_FILE = "users.json"

# ========== ЗАГРУЗКА/СОХРАНЕНИЕ ==========
def load_json(file):
    if os.path.exists(file):
        with open(file, 'r') as f:
            return json.load(f)
    return {}

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

lobbies = load_json(LOBBIES_FILE)
users = load_json(USERS_FILE)

# ========== КНОПКИ ==========
def get_main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("📢 Канал", url="https://t.me/твой_канал")
    btn2 = types.InlineKeyboardButton("💬 Чат", url="https://t.me/твой_чат")
    btn3 = types.InlineKeyboardButton("⭐ Пополнить Stars", url="https://t.me/telegram/stars")
    markup.add(btn1, btn2, btn3)
    return markup

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = str(message.from_user.id)
    
    if user_id not in users:
        users[user_id] = {
            "username": message.from_user.username or message.from_user.first_name,
            "stars": 0,
            "wins": 0,
            "games": 0,
            "inventory": []
        }
        save_json(USERS_FILE, users)
    
    text = """
🎲 **RUSSIAN ROULETTE**

Добро пожаловать в русскую рулетку с мультиплеером!

Команды:
/create — создать лобби
/join — присоединиться к лобби
/list — список лобби
/shop — магазин
/stats — моя статистика

Играть можно в чате или в личке.
Минимум 2 игрока, максимум 6.
    """
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['create'])
def create_command(message):
    user_id = str(message.from_user.id)
    chat_id = str(message.chat.id)
    
    # Проверяем, есть ли уже лобби в этом чате
    for lobby_id, lobby in lobbies.items():
        if lobby["chat_id"] == chat_id:
            bot.reply_to(message, "❌ В этом чате уже есть лобби")
            return
    
    # Генерируем код лобби
    lobby_code = f"LB{random.randint(1000, 9999)}"
    
    lobbies[lobby_code] = {
        "chat_id": chat_id,
        "creator": user_id,
        "players": [user_id],
        "status": "waiting",  # waiting, playing
        "max_players": 6,
        "created_at": str(datetime.now())
    }
    save_json(LOBBIES_FILE, lobbies)
    
    text = f"""
✅ Лобби создано!

Код: `{lobby_code}`
Игроков: 1/6

Приглашай друзей командой:
/join {lobby_code}

Когда все готовы:
/startgame
    """
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['join'])
def join_command(message):
    user_id = str(message.from_user.id)
    
    try:
        lobby_code = message.text.split()[1].upper()
    except:
        bot.reply_to(message, "❌ Использование: /join КОД")
        return
    
    if lobby_code not in lobbies:
        bot.reply_to(message, "❌ Лобби не найдено")
        return
    
    lobby = lobbies[lobby_code]
    
    if lobby["status"] != "waiting":
        bot.reply_to(message, "❌ Игра уже началась")
        return
    
    if len(lobby["players"]) >= lobby["max_players"]:
        bot.reply_to(message, "❌ Лобби заполнено")
        return
    
    if user_id in lobby["players"]:
        bot.reply_to(message, "❌ Ты уже в лобби")
        return
    
    lobby["players"].append(user_id)
    save_json(LOBBIES_FILE, lobbies)
    
    text = f"✅ Ты присоединился!\nИгроков: {len(lobby['players'])}/6"
    bot.send_message(message.chat.id, text)
    
    # Уведомляем всех в лобби
    for player_id in lobby["players"]:
        try:
            bot.send_message(int(player_id), f"👤 Новый игрок в лобби {lobby_code}\nИгроков: {len(lobby['players'])}/6")
        except:
            pass

@bot.message_handler(commands=['list'])
def list_command(message):
    active_lobbies = []
    for code, lobby in lobbies.items():
        if lobby["status"] == "waiting":
            active_lobbies.append(f"`{code}` — {len(lobby['players'])}/6 игроков")
    
    if active_lobbies:
        text = "📋 **Доступные лобби:**\n\n" + "\n".join(active_lobbies)
    else:
        text = "📋 Нет доступных лобби. Создай своё: /create"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['startgame'])
def startgame_command(message):
    user_id = str(message.from_user.id)
    chat_id = str(message.chat.id)
    
    # Ищем лобби в этом чате
    lobby_code = None
    for code, lobby in lobbies.items():
        if lobby["chat_id"] == chat_id:
            lobby_code = code
            break
    
    if not lobby_code:
        bot.reply_to(message, "❌ В этом чате нет лобби")
        return
    
    lobby = lobbies[lobby_code]
    
    if lobby["creator"] != user_id:
        bot.reply_to(message, "❌ Только создатель может начать игру")
        return
    
    if len(lobby["players"]) < 2:
        bot.reply_to(message, "❌ Минимум 2 игрока")
        return
    
    # Инициализируем игру
    lobby["status"] = "playing"
    lobby["current_turn"] = 0
    lobby["chamber"] = random.randint(1, 6)  # Где патрон (1-6)
    lobby["position"] = 1  # Текущая позиция барабана
    lobby["alive"] = lobby["players"].copy()
    lobby["used_items"] = {}
    
    save_json(LOBBIES_FILE, lobbies)
    
    # Уведомляем всех
    players_text = ""
    for i, player_id in enumerate(lobby["players"]):
        username = users.get(player_id, {}).get("username", f"Игрок {i+1}")
        players_text += f"{i+1}. {username}\n"
    
    text = f"""
🔫 **ИГРА НАЧАЛАСЬ!**

Код лобби: `{lobby_code}`

Игроки:
{players_text}

Патрон заряжен.
Ходит: Игрок 1
    """
    
    for player_id in lobby["players"]:
        try:
            bot.send_message(int(player_id), text, parse_mode="Markdown")
        except:
            pass

@bot.message_handler(commands=['shoot'])
def shoot_command(message):
    user_id = str(message.from_user.id)
    
    # Ищем активную игру с этим игроком
    lobby_code = None
    for code, lobby in lobbies.items():
        if lobby["status"] == "playing" and user_id in lobby["alive"]:
            lobby_code = code
            break
    
    if not lobby_code:
        bot.reply_to(message, "❌ Ты не в игре")
        return
    
    lobby = lobbies[lobby_code]
    current_player = lobby["alive"][lobby["current_turn"]]
    
    if user_id != current_player:
        bot.reply_to(message, "❌ Сейчас не твой ход")
        return
    
    # Проверяем выстрел
    if lobby["position"] == lobby["chamber"]:
        # Попал
        username = users.get(user_id, {}).get("username", "Игрок")
        
        # Удаляем игрока
        lobby["alive"].pop(lobby["current_turn"])
        
        # Если остался один
        if len(lobby["alive"]) == 1:
            winner_id = lobby["alive"][0]
            winner_name = users.get(winner_id, {}).get("username", "Игрок")
            
            # Обновляем статистику
            if winner_id in users:
                users[winner_id]["wins"] += 1
                users[winner_id]["games"] += 1
            for player_id in lobby["players"]:
                if player_id in users and player_id != winner_id:
                    users[player_id]["games"] += 1
            save_json(USERS_FILE, users)
            
            text = f"""
💥 **БАХ!** {username} застрелился!

🏆 **ПОБЕДИТЕЛЬ:** {winner_name}

Игра окончена.
            """
            
            for player_id in lobby["players"]:
                try:
                    bot.send_message(int(player_id), text)
                except:
                    pass
            
            # Удаляем лобби
            del lobbies[lobby_code]
            save_json(LOBBIES_FILE, lobbies)
            return
        
        # Если игроков больше 1
        # Перекручиваем барабан на рандом
        lobby["chamber"] = random.randint(1, 6)
        lobby["position"] = 1
        # Ход переходит к следующему
        if lobby["current_turn"] >= len(lobby["alive"]):
            lobby["current_turn"] = 0
        
        text = f"""
💥 **БАХ!** {username} застрелился!

Осталось игроков: {len(lobby['alive'])}
Ходит: Игрок {lobby['current_turn'] + 1}
        """
        
        for player_id in lobby["players"]:
            try:
                bot.send_message(int(player_id), text)
            except:
                pass
        
    else:
        # Не попал
        username = users.get(user_id, {}).get("username", "Игрок")
        
        # Двигаем барабан
        lobby["position"] += 1
        if lobby["position"] > 6:
            lobby["position"] = 1
        
        # Ход следующему
        lobby["current_turn"] += 1
        if lobby["current_turn"] >= len(lobby["alive"]):
            lobby["current_turn"] = 0
        
        text = f"""
😮‍💨 **Щелчок!** {username} повезло...

Ходит: Игрок {lobby['current_turn'] + 1}
        """
        
        for player_id in lobby["players"]:
            try:
                bot.send_message(int(player_id), text)
            except:
                pass
    
    save_json(LOBBIES_FILE, lobbies)

@bot.message_handler(commands=['shop'])
def shop_command(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🔫 Пуля (5⭐)", url="https://t.me/telegram/stars")
    btn2 = types.InlineKeyboardButton("🛡️ Броня (10⭐)", url="https://t.me/telegram/stars")
    btn3 = types.InlineKeyboardButton("🔄 Перекрут (3⭐)", url="https://t.me/telegram/stars")
    btn4 = types.InlineKeyboardButton("👀 Сканер (7⭐)", url="https://t.me/telegram/stars")
    btn5 = types.InlineKeyboardButton("💊 Аптечка (15⭐)", url="https://t.me/telegram/stars")
    markup.add(btn1, btn2, btn3, btn4, btn5)
    
    text = """
🛒 **МАГАЗИН**

Покупки через Telegram Stars.

🔫 Пуля — зарядить ещё 1 патрон — 5⭐
🛡️ Броня — выдержать 1 выстрел — 10⭐
🔄 Перекрут — перекрутить барабан — 3⭐
👀 Сканер — узнать есть ли патрон — 7⭐
💊 Аптечка — воскреснуть (1 раз) — 15⭐

После покупки предмет появится в инвентаре.
Использовать в игре: /use ПРЕДМЕТ
    """
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['buy'])
def buy_command(message):
    try:
        item = message.text.split()[1].lower()
    except:
        bot.reply_to(message, "❌ Использование: /buy ПРЕДМЕТ")
        return
    
    items = {
        "bullet": {"name": "🔫 Пуля", "price": 5},
        "armor": {"name": "🛡️ Броня", "price": 10},
        "reroll": {"name": "🔄 Перекрут", "price": 3},
        "scanner": {"name": "👀 Сканер", "price": 7},
        "revive": {"name": "💊 Аптечка", "price": 15}
    }
    
    if item not in items:
        bot.reply_to(message, "❌ Такого предмета нет. Список: bullet, armor, reroll, scanner, revive")
        return
    
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(
        f"⭐ Купить {items[item]['name']} за {items[item]['price']} Stars",
        url="https://t.me/telegram/stars"
    )
    markup.add(btn)
    
    bot.send_message(
        message.chat.id,
        f"Для покупки {items[item]['name']} нажми кнопку ниже.\nПосле оплаты напиши /confirm, чтобы получить предмет.",
        reply_markup=markup
    )

@bot.message_handler(commands=['stats'])
def stats_command(message):
    user_id = str(message.from_user.id)
    
    if user_id not in users:
        users[user_id] = {
            "username": message.from_user.username or message.from_user.first_name,
            "stars": 0,
            "wins": 0,
            "games": 0,
            "inventory": []
        }
        save_json(USERS_FILE, users)
    
    user = users[user_id]
    winrate = (user["wins"] / user["games"] * 100) if user["games"] > 0 else 0
    
    text = f"""
📊 **ТВОЯ СТАТИСТИКА**

👤 Имя: {user['username']}
🏆 Побед: {user['wins']}
🎮 Игр: {user['games']}
📈 Винрейт: {winrate:.1f}%
⭐ Stars: {user['stars']}

🎒 Инвентарь:
{', '.join(user['inventory']) if user['inventory'] else 'Пусто'}
    """
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    print("🤖 Russian Roulette бот запущен...")
    bot.infinity_polling()