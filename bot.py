import telebot
import sqlite3
import random
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery

# ========== КОНФИГ ==========
BOT_TOKEN = "8412567351:AAG7eEMXlNfDBsNZF08GD-Pr-LH-2z1txSQ"
STARS_TO_BULLETS = 100
BET_AMOUNTS = [10, 50, 100, 500]

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

# ========== КЛАВИАТУРЫ ==========
def main_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎰 Играть", callback_data="play"))
    kb.add(InlineKeyboardButton("💰 Баланс", callback_data="balance"), 
           InlineKeyboardButton("🎁 Бонус", callback_data="daily"))
    kb.add(InlineKeyboardButton("⭐ Купить 💎", callback_data="buy_stars"))
    return kb

def bet_menu():
    kb = InlineKeyboardMarkup()
    for bet in BET_AMOUNTS:
        kb.add(InlineKeyboardButton(f"💎 {bet}", callback_data=f"bet_{bet}"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def game_menu(bet):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔫 Выстрелить", callback_data=f"shoot_{bet}"),
           InlineKeyboardButton("🔄 Крутить", callback_data=f"spin_{bet}"))
    kb.add(InlineKeyboardButton("🏠 Выход", callback_data="back"))
    return kb

def back_button():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="back"))
    return kb

# ========== ОПИСАНИЕ ==========
def get_description():
    return (
        "<b>🔫 РУССКАЯ РУЛЕТКА 🔫</b>\n\n"
        "<b>🎲 Правила игры:</b>\n"
        "• Делаешь ставку в 💎 (патронах)\n"
        "• Нажимаешь выстрел\n"
        "• Если выпадает пусто → выигрываешь x2\n"
        "• Если выпадает патрон → проигрываешь ставку\n"
        "• Можно крутить барабан перед выстрелом\n\n"
        "<b>💰 Как получить 💎:</b>\n"
        "• Ежедневный бонус — 50 💎\n"
        "• Победы в игре — x2 от ставки\n"
        "• Покупка за Stars — 1⭐ = 100 💎\n\n"
        "<b>⭐ Покупка за Stars:</b>\n"
        "Нажми кнопку 'Купить 💎' и выбери сумму\n\n"
        "<b>📌 Команды:</b>\n"
        "/play — начать игру\n"
        "/balance — показать баланс\n"
        "/daily — забрать бонус\n"
        "/buy — купить 💎\n"
        "/help — это сообщение\n\n"
        "🎮 <i>Играть можно прямо в этом чате!</i>"
    )

# ========== ХРАНИЛИЩЕ ИГР ==========
games = {}

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start', 'help'])
def start_command(message):
    init_db()
    get_user(message.from_user.id)
    bot.send_message(
        message.chat.id,
        get_description(),
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

@bot.message_handler(commands=['buy'])
def buy_command(message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("10 Stars → 1000 💎", callback_data="buy_10"))
    kb.add(InlineKeyboardButton("50 Stars → 5000 💎", callback_data="buy_50"))
    kb.add(InlineKeyboardButton("100 Stars → 10000 💎", callback_data="buy_100"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    bot.send_message(
        message.chat.id,
        "<b>⭐ Покупка 💎 за Telegram Stars</b>\n\n1 Star = 100 💎\n\nВыбери количество:",
        reply_markup=kb
    )

# ========== КОЛБЭКИ ==========
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    # Назад в меню
    if call.data == "back":
        bot.edit_message_text(
            get_description(),
            chat_id,
            message_id,
            reply_markup=main_menu()
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
            
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🎰 Играть снова", callback_data="play"),
                   InlineKeyboardButton("🏠 В меню", callback_data="back"))
            
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
            
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🎰 Играть снова", callback_data="play"),
                   InlineKeyboardButton("🏠 В меню", callback_data="back"))
            
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
    
    # Покупка Stars
    if call.data == "buy_stars":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("10 Stars → 1000 💎", callback_data="buy_10"))
        kb.add(InlineKeyboardButton("50 Stars → 5000 💎", callback_data="buy_50"))
        kb.add(InlineKeyboardButton("100 Stars → 10000 💎", callback_data="buy_100"))
        kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
        bot.edit_message_text(
            "<b>⭐ Покупка 💎 за Telegram Stars</b>\n\n1 Star = 100 💎\n\nВыбери количество:",
            chat_id,
            message_id,
            reply_markup=kb
        )
        bot.answer_callback_query(call.id)
        return
    
    # Обработка покупки
    if call.data.startswith("buy_"):
        stars = int(call.data.split("_")[1])
        bullets = stars * STARS_TO_BULLETS
        
        prices = [LabeledPrice(label=f"{bullets} 💎", amount=stars)]
        
        bot.send_invoice(
            chat_id,
            title="Покупка 💎",
            description=f"{bullets} патронов для русской рулетки",
            payload=f"bullets_{bullets}",
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="buy_bullets"
        )
        bot.answer_callback_query(call.id)
        return

# ========== ПЛАТЕЖИ ==========
@bot.pre_checkout_query_handler(func=lambda query: True)
def handle_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    payload = message.successful_payment.invoice_payload
    bullets = int(payload.split("_")[1])
    
    user = get_user(message.from_user.id)
    new_bullets = user["bullets"] + bullets
    update_user(message.from_user.id, bullets=new_bullets)
    
    bot.send_message(
        message.chat.id,
        f"✅ Оплата прошла успешно!\n\n"
        f"Ты получил <b>{bullets} 💎</b>\n"
        f"💰 Новый баланс: {new_bullets} 💎",
        reply_markup=main_menu()
    )

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    init_db()
    print("Бот запущен!")
    bot.infinity_polling()