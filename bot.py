import asyncio
import sqlite3
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ========== КОНФИГ ==========
BOT_TOKEN = "8412567351:AAG7eEMXlNfDBsNZF08GD-Pr-LH-2z1txSQ"
STARS_TO_BULLETS = 100  # 1 Star = 100 💎
BET_AMOUNTS = [10, 50, 100, 500]

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

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

# ========== КНОПКИ ==========
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Играть", callback_data="play")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
         InlineKeyboardButton(text="🎁 Ежедневный бонус", callback_data="daily")],
        [InlineKeyboardButton(text="⭐ Купить 💎 за Stars", callback_data="buy_stars")]
    ])

def bet_menu():
    kb = []
    for bet in BET_AMOUNTS:
        kb.append([InlineKeyboardButton(text=f"💎 {bet}", callback_data=f"bet_{bet}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def game_menu(bet_amount):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔫 Выстрелить", callback_data=f"shoot_{bet_amount}"),
         InlineKeyboardButton(text="🔄 Крутить барабан", callback_data=f"spin_{bet_amount}")],
        [InlineKeyboardButton(text="🏠 Выход", callback_data="back")]
    ])

# ========== СОСТОЯНИЯ ==========
class GameState(StatesGroup):
    waiting_for_bet = State()
    in_game = State()

# ========== КОМАНДА /START ==========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    init_db()
    get_user(message.from_user.id)
    await message.answer(
        f"🔫 Добро пожаловать в Русскую Рулетку, {message.from_user.first_name}!\n\n"
        f"Правила:\n"
        f"• Ставишь 💎, стреляешь\n"
        f"• Если пусто → выигрываешь x2\n"
        f"• Если патрон → проигрываешь ставку\n\n"
        f"У тебя уже есть 100 💎 на первый запуск!\n"
        f"Каждый день забирай бонус и покупай 💎 за Stars.",
        reply_markup=main_menu()
    )

# ========== ОБРАБОТКА КНОПОК ==========
@dp.callback_query(F.data == "back")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text("🔫 Главное меню:", reply_markup=main_menu())
    await callback.answer()

@dp.callback_query(F.data == "balance")
async def show_balance(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    await callback.message.edit_text(
        f"💰 Твой баланс: *{user['bullets']} 💎*\n"
        f"🏆 Побед: {user['wins']} | 💀 Поражений: {user['losses']}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "daily")
async def daily_bonus(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    last = datetime.fromisoformat(user["last_daily"]) if user["last_daily"] else datetime.min
    now = datetime.now()
    
    if now - last < timedelta(days=1):
        hours_left = 24 - (now - last).seconds // 3600
        await callback.answer(f"⏰ Бонус будет через {hours_left} ч", show_alert=True)
        return
    
    new_bullets = user["bullets"] + 50
    update_user(callback.from_user.id, bullets=new_bullets, last_daily=now.isoformat())
    await callback.message.edit_text(
        f"🎁 Ты получил 50 💎!\n\n💰 Новый баланс: {new_bullets} 💎",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В меню", callback_data="back")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "play")
async def play_game(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    if user["bullets"] < min(BET_AMOUNTS):
        await callback.answer(f"❌ Не хватает 💎! Нужно минимум {min(BET_AMOUNTS)}", show_alert=True)
        return
    await callback.message.edit_text(
        f"💰 Твой баланс: {user['bullets']} 💎\n\nВыбери ставку:",
        reply_markup=bet_menu()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("bet_"))
async def place_bet(callback: CallbackQuery, state: FSMContext):
    bet = int(callback.data.split("_")[1])
    user = get_user(callback.from_user.id)
    
    if user["bullets"] < bet:
        await callback.answer(f"❌ Не хватает 💎! Нужно {bet}", show_alert=True)
        return
    
    await state.update_data(bet=bet, chamber=random.randint(1, 6))
    await callback.message.edit_text(
        f"🎲 Ставка: *{bet} 💎*\n"
        f"Барабан заряжен.\n\n"
        f"Что делаешь?",
        reply_markup=game_menu(bet)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("spin_"))
async def spin_chamber(callback: CallbackQuery, state: FSMContext):
    bet = int(callback.data.split("_")[1])
    data = await state.get_data()
    new_chamber = random.randint(1, 6)
    await state.update_data(chamber=new_chamber)
    await callback.message.edit_text(
        f"🔄 Барабан прокручен...\n"
        f"Ставка: {bet} 💎\n\n"
        f"Готов стрелять?",
        reply_markup=game_menu(bet)
    )
    await callback.answer("Барабан прокручен", show_alert=False)

@dp.callback_query(F.data.startswith("shoot_"))
async def shoot(callback: CallbackQuery, state: FSMContext):
    bet = int(callback.data.split("_")[1])
    data = await state.get_data()
    chamber = data.get("chamber", random.randint(1, 6))
    trigger = random.randint(1, 6)
    
    user = get_user(callback.from_user.id)
    
    if trigger == chamber:
        # Проигрыш
        new_bullets = user["bullets"] - bet
        update_user(callback.from_user.id, bullets=new_bullets, losses=user["losses"] + 1)
        
        await callback.message.edit_text(
            f"💀 *БАХ!*\n\n"
            f"Выпал патрон. Ты проиграл *{bet} 💎*\n"
            f"💰 Новый баланс: {new_bullets} 💎",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎰 Играть снова", callback_data="play"),
                 InlineKeyboardButton(text="🏠 В меню", callback_data="back")]
            ])
        )
    else:
        # Выигрыш
        win = bet * 2
        new_bullets = user["bullets"] + win
        update_user(callback.from_user.id, bullets=new_bullets, wins=user["wins"] + 1)
        
        await callback.message.edit_text(
            f"🍀 *ЩЕЛЧОК...*\n\n"
            f"Пусто! Ты выиграл *{win} 💎*\n"
            f"💰 Новый баланс: {new_bullets} 💎",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎰 Играть снова", callback_data="play"),
                 InlineKeyboardButton(text="🏠 В меню", callback_data="back")]
            ])
        )
    
    await state.clear()
    await callback.answer()

# ========== ПОКУПКА ЗА STARS ==========
@dp.callback_query(F.data == "buy_stars")
async def buy_bullets(callback: CallbackQuery):
    await callback.message.edit_text(
        "⭐ *Покупка 💎 за Telegram Stars*\n\n"
        "1 Star = 100 💎\n\n"
        "Выбери количество:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="10 Stars → 1000 💎", callback_data="buy_10")],
            [InlineKeyboardButton(text="50 Stars → 5000 💎", callback_data="buy_50")],
            [InlineKeyboardButton(text="100 Stars → 10000 💎", callback_data="buy_100")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: CallbackQuery):
    stars = int(callback.data.split("_")[1])
    bullets = stars * STARS_TO_BULLETS
    
    prices = [LabeledPrice(label=f"{bullets} 💎", amount=stars)]
    
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Покупка 💎",
        description=f"{bullets} патронов для русской рулетки",
        payload=f"bullets_{bullets}",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="buy_bullets",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="buy_stars")]
        ])
    )
    await callback.answer()

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    bullets = int(payload.split("_")[1])
    
    user = get_user(message.from_user.id)
    new_bullets = user["bullets"] + bullets
    update_user(message.from_user.id, bullets=new_bullets)
    
    await message.answer(
        f"✅ Оплата прошла успешно!\n\n"
        f"Ты получил *{bullets} 💎*\n"
        f"💰 Новый баланс: {new_bullets} 💎",
        reply_markup=main_menu()
    )

# ========== ЗАПУСК ==========
async def main():
    init_db()
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())