import telebot
import sqlite3
import random
import json
import os
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery

# ========== КОНФИГ ==========
BOT_TOKEN = "8412567351:AAG7eEMXlNfDBsNZF08GD-Pr-LH-2z1txSQ"
STARS_TO_BULLETS = 100  # 1 Star = 100 💎 (для старой системы, оставлю как запасную)
BET_AMOUNTS = [10, 50, 100, 500]

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ========== ФАЙЛЫ ==========
DONATIONS_FILE = "donations.json"

def load_json(file):
    if os.path.exists(file):
        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"donations": []}

def save_json(file, data):
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ========== БД ==========
def init_db():
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  bullets INTEGER DEFAULT 100,
                  crystals INTEGER DEFAULT 0,
                  donated_stars INTEGER DEFAULT 0,
                  last_daily TEXT,
                  wins INTEGER DEFAULT 0,
                  losses INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    c.execute("SELECT bullets, crystals, donated_stars, last_daily, wins, losses FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (user_id, bullets, crystals, last_daily) VALUES (?, ?, ?, ?)",
                  (user_id, 100, 0, datetime.now().isoformat()))
        conn.commit()
        c.execute("SELECT bullets, crystals, donated_stars, last_daily, wins, losses FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
    conn.close()
    return {
        "bullets": user[0],
        "crystals": user[1],
        "donated_stars": user[2],
        "last_daily": user[3],
        "wins": user[4],
        "losses": user[5]
    }

def update_user(user_id, bullets=None, crystals=None, donated_stars=None, wins=None, losses=None, last_daily=None):
    conn = sqlite3.connect("roulette.db")
    c = conn.cursor()
    if bullets is not None:
        c.execute("UPDATE users SET bullets = ? WHERE user_id = ?", (bullets, user_id))
    if crystals is not None:
        c.execute("UPDATE users SET crystals = ? WHERE user_id = ?", (crystals, user_id))
    if donated_stars is not None:
        c.execute("UPDATE users SET donated_stars = ? WHERE user_id = ?", (donated_stars, user_id))
    if wins is not None:
        c.execute("UPDATE users SET wins = ? WHERE user_id = ?", (wins, user_id))
    if losses is not None:
        c.execute("UPDATE users SET losses = ? WHERE user_id = ?", (losses, user_id))
    if last_daily is not None:
        c.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", (last_daily, user_id))
    conn.commit()
    conn.close()

def add_crystals(user_id, amount):
    user = get_user(user_id)
    new_crystals = user["crystals"] + amount
    update_user(user_id, crystals=new_crystals)

# ========== КЛАВИАТУРЫ ==========
def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🎰 Играть", callback_data="play"),
        InlineKeyboardButton("💰 Баланс", callback_data="balance")
    )
    kb.add(
        InlineKeyboardButton("🎁 Бонус", callback_data="daily"),
        InlineKeyboardButton("⭐ Купить 💎", callback_data="donate_stars_menu")
    )
    kb.add(InlineKeyboardButton("📜 Правила", callback_data="rules"))
    return kb

def bet_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    for bet in BET_AMOUNTS:
        kb.add(InlineKeyboardButton(f"💎 {bet}", callback_data=f"bet_{bet}"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def game_menu(bet):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🔫 Выстрелить", callback_data=f"shoot_{bet}"),
        InlineKeyboardButton("🔄 Крутить", callback_data=f"spin_{bet}")
    )
    kb.add(InlineKeyboardButton("🏠 Выход", callback_data="back"))
    return kb

def back_button():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="back"))
    return kb

def donate_stars_kb():
    kb = InlineKeyboardMarkup(row_width=3)
    stars_list = [1, 2, 5, 10, 20, 50, 100, 150, 200, 250, 300, 400, 500, 750, 1000]
    for s in stars_list:
        # Рассчитываем бонус
        if s == 1:
            bonus = 0
        elif s == 2:
            bonus = 10
        elif s == 5:
            bonus = 30
        elif s == 10:
            bonus = 75
        elif s == 20:
            bonus = 200
        elif s == 50:
            bonus = 600
        elif s == 100:
            bonus = 1500
        elif s == 150:
            bonus = 2500
        elif s == 200:
            bonus = 3500
        elif s == 250:
            bonus = 4500
        elif s == 300:
            bonus = 5500
        elif s == 400:
            bonus = 8000
        elif s == 500:
            bonus = 10000
        elif s == 750:
            bonus = 17000
        elif s == 1000:
            bonus = 25000
        else:
            bonus = 0
        
        total_crystals = s * 50 + bonus
        kb.add(InlineKeyboardButton(f"{s}⭐ → {total_crystals}💎", callback_data=f"donate_{s}_{total_crystals}"))
    
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data="back"))
    return kb

# ========== ОПИСАНИЕ ==========
def get_rules():
    return (
        "<b>🔫 РУССКАЯ РУЛЕТКА 🔫</b>\n\n"
        "<b>🎲 Правила игры:</b>\n"
        "• Делаешь ставку в 💎 (кристаллах)\n"
        "• Нажимаешь выстрел\n"
        "• Если выпадает пусто → выигрываешь x2\n"
        "• Если выпадает патрон → проигрываешь ставку\n"
        "• Можно крутить барабан перед выстрелом\n\n"
        "<b>💰 Как получить 💎:</b>\n"
        "• Ежедневный бонус — 50 💎\n"
        "• Победы в игре — x2 от ставки\n"
        "• Покупка за Stars — бонусная система\n\n"
        "<b>⭐ Курс покупки:</b>\n"
        "1 Star = 50 💎 + бонус\n"
        "Чем больше покупаешь, тем выше бонус!\n\n"
        "<b>📌 Команды:</b>\n"
        "/start — главное меню\n"
        "/play — начать игру\n"
        "/balance — баланс\n"
        "/daily — бонус\n"
        "/rules — правила\n\n"
        "🎮 <i>Играть можно прямо в этом чате!</i>"
    )

# ========== ХРАНИЛИЩЕ ИГР ==========
games = {}

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

@bot.message_handler(commands=['play'])
def play_command(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if user["bullets"] < min(BET_AMOUNTS):
        bot.reply_to(message, f"❌ Не хватает 💎! Нужно минимум {min(BET_AMOUNTS)}")
        return
    bot.send_message(
        message.chat.id,
        f"💰 <b>{message.from_user.first_name}</b>, твой баланс: {user['bullets']} 💎\n\nВыбери ставку:",
        reply_markup=bet_menu()
    )

@bot.message_handler(commands=['balance'])
def balance_command(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    bot.reply_to(
        message,
        f"💰 <b>Баланс:</b> {user['bullets']} 💎\n"
        f"⭐ <b>Всего донатов:</b> {user['donated_stars']} Stars\n"
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
    
    # Назад в меню
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
            f"⭐ <b>Всего донатов:</b> {user['donated_stars']} Stars\n"
            f"🏆 Побед: {user['wins']} | 💀 Поражений: {user['losses']}",
            chat_id,
            message_id,
            reply_markup=back_button()
        )
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
    
    # Меню покупки Stars
    if call.data == "donate_stars_menu":
        bot.edit_message_text(
            "<b>⭐ Покупка 💎 за Telegram Stars</b>\n\n"
            "1 Star = 50 💎 + бонус\n"
            "Чем больше покупаешь, тем выше бонус!\n\n"
            "Выбери количество:",
            chat_id,
            message_id,
            reply_markup=donate_stars_kb()
        )
        bot.answer_callback_query(call.id)
        return
    
    # Играть
    if call.data == "play":
        user = get_user(user_id)
        if user["bullets"] < min(BET_AMOUNTS):
            bot.answer_callback_query(call.id, f"❌ Не хватает 💎! Нужно минимум {min(BET_AMOUNTS)}", show_alert=True)
            return
        bot.edit_message_text(
            f"💰 <b>{call.from_user.first_name}</b>, твой баланс: {user['bullets']} 💎\n\nВыбери ставку:",
            chat_id,
            message_id,
            reply_markup=bet_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    # Ставка
    if call.data.startswith("bet_"):
        bet = int(call.data.split("_")[1])
        user = get_user(user_id)
        
        if user["bullets"] < bet:
            bot.answer_callback_query(call.id, f"❌ Не хватает 💎! Нужно {bet}", show_alert=True)
            return
        
        games[user_id] = {
            "bet": bet,
            "chamber": random.randint(1, 6)
        }
        
        bot.edit_message_text(
            f"🎲 Ставка: <b>{bet} 💎</b>\n"
            f"Барабан заряжен.\n\n"
            f"Что делаешь?",
            chat_id,
            message_id,
            reply_markup=game_menu(bet)
        )
        bot.answer_callback_query(call.id)
        return
    
    # Крутить барабан
    if call.data.startswith("spin_"):
        bet = int(call.data.split("_")[1])
        if user_id in games:
            games[user_id]["chamber"] = random.randint(1, 6)
        
        bot.edit_message_text(
            f"🔄 Барабан прокручен...\n"
            f"Ставка: {bet} 💎\n\n"
            f"Готов стрелять?",
            chat_id,
            message_id,
            reply_markup=game_menu(bet)
        )
        bot.answer_callback_query(call.id, "Барабан прокручен")
        return
    
    # Выстрел
    if call.data.startswith("shoot_"):
        bet = int(call.data.split("_")[1])
        user = get_user(user_id)
        
        chamber = games.get(user_id, {}).get("chamber", random.randint(1, 6))
        trigger = random.randint(1, 6)
        
        if trigger == chamber:
            new_bullets = user["bullets"] - bet
            update_user(user_id, bullets=new_bullets, losses=user["losses"] + 1)
            
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(
                InlineKeyboardButton("🎰 Играть снова", callback_data="play"),
                InlineKeyboardButton("🏠 В меню", callback_data="back")
            )
            
            bot.edit_message_text(
                f"💀 <b>БАХ!</b>\n\n"
                f"Выпал патрон. Ты проиграл <b>{bet} 💎</b>\n"
                f"💰 Новый баланс: {new_bullets} 💎",
                chat_id,
                message_id,
                reply_markup=kb
            )
        else:
            win = bet * 2
            new_bullets = user["bullets"] + win
            update_user(user_id, bullets=new_bullets, wins=user["wins"] + 1)
            
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(
                InlineKeyboardButton("🎰 Играть снова", callback_data="play"),
                InlineKeyboardButton("🏠 В меню", callback_data="back")
            )
            
            bot.edit_message_text(
                f"🍀 <b>ЩЕЛЧОК...</b>\n\n"
                f"Пусто! Ты выиграл <b>{win} 💎</b>\n"
                f"💰 Новый баланс: {new_bullets} 💎",
                chat_id,
                message_id,
                reply_markup=kb
            )
        
        if user_id in games:
            del games[user_id]
        
        bot.answer_callback_query(call.id)
        return
    
    # Обработка доната (покупка за Stars)
    if call.data.startswith("donate_"):
        parts = call.data.split("_")
        stars = int(parts[1])
        crystals = int(parts[2])
        
        prices = [LabeledPrice(label=f"{stars} Stars", amount=stars)]
        
        bot.send_invoice(
            chat_id,
            title="⭐ Поддержка",
            description=f"{stars} Stars\n+{crystals} 💎 кристаллов",
            payload=f"donate_{stars}_{crystals}_{user_id}",
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="donate"
        )
        bot.answer_callback_query(call.id)
        return

# ========== ПЛАТЕЖИ ==========
@bot.pre_checkout_query_handler(func=lambda query: True)
def handle_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    payment = message.successful_payment
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    # Разбираем payload
    parts = payment.invoice_payload.split('_')
    stars = int(parts[1])
    crystals = int(parts[2])
    
    # Начисляем кристаллы
    add_crystals(user_id, crystals)
    
    # Обновляем статистику донатов пользователя
    user = get_user(user_id)
    update_user(user_id, donated_stars=user["donated_stars"] + stars)
    
    # Обновляем баланс кристаллов (добавляем к bullets)
    new_bullets = user["bullets"] + crystals
    update_user(user_id, bullets=new_bullets)
    
    # Сохраняем донат в историю
    donations = load_json(DONATIONS_FILE)
    donations['donations'].append({
        'user_id': user_id,
        'username': username,
        'stars': stars,
        'crystals': crystals,
        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_json(DONATIONS_FILE, donations)
    
    # Отправляем подтверждение пользователю
    bot.send_message(
        user_id,
        f"✅ <b>Спасибо за поддержку!</b>\n\n"
        f"⭐ {stars} Stars\n"
        f"💎 +{crystals} кристаллов\n"
        f"💰 Новый баланс: {new_bullets} 💎",
        reply_markup=main_menu()
    )
    
    # Если сообщение из чата, отправляем уведомление в чат
    if message.chat.id != user_id:
        bot.send_message(
            message.chat.id,
            f"🎉 <b>{username}</b> поддержал бота на {stars} Stars!\nПолучил +{crystals} 💎"
        )

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    init_db()
    print("Бот запущен!")
    bot.infinity_polling()