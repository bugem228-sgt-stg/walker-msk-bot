# main.py — ИСПРАВЛЕННАЯ ВЕРСИЯ С КНОПКАМИ
import asyncio
import os
import traceback
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database import init_db, add_user, get_balance, update_balance, create_walk_request, get_user_requests

dp = Dispatcher(storage=MemoryStorage())

# --- 🎨 КЛАВИАТУРЫ ---
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🐕 Заявка на выгул"), KeyboardButton(text="💳 Баланс")],
        [KeyboardButton(text="📋 Мои заявки"), KeyboardButton(text="💰 Пополнить")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие..."
)

def get_duration_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="30 мин (150₽)", callback_data="walk_30"),
         InlineKeyboardButton(text="40 мин (200₽)", callback_data="walk_40")],
        [InlineKeyboardButton(text="50 мин (250₽)", callback_data="walk_50"),
         InlineKeyboardButton(text="60 мин (300₽)", callback_data="walk_60")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_walk")]
    ])

# --- 🔹 FSM ---
class WalkState(StatesGroup):
    date = State()
    time = State()

# --- 📝 ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Друг"
    await add_user(user_id, username)
    await message.answer(f"🐕 Привет, {username}! Используй меню ниже 👇", reply_markup=main_kb)

@dp.message(F.text == "🐕 Заявка на выгул")
async def cmd_walk_menu(message: Message, state: FSMContext):
    await message.answer("📅 Напишите дату выгула (ДД.ММ.ГГГГ):", 
                         reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True))
    await state.set_state(WalkState.date)

@dp.message(F.text == "💳 Баланс")
async def cmd_balance_menu(message: Message):
    balance = await get_balance(message.from_user.id)
    await message.answer(f"💳 Ваш баланс: {balance} ₽", reply_markup=main_kb)

@dp.message(F.text == "📋 Мои заявки")
async def cmd_mywalks_menu(message: Message):
    requests = await get_user_requests(message.from_user.id)
    if not requests:
        await message.answer("📭 У вас пока нет заявок", reply_markup=main_kb)
        return
    text = "📋 Ваши заявки:\n\n"
    for req in requests:
        status_emoji = "⏳" if req['status'] == 'pending' else "✅"
        text += f"{status_emoji} #{req['id']} | {req['walk_date']} в {req['walk_time']} ({req['duration_min']} мин)\n"
    await message.answer(text, reply_markup=main_kb)

@dp.message(F.text == "💰 Пополнить")
async def cmd_topup_menu(message: Message):
    await message.answer("💳 Напишите сумму (например: 500)", 
                         reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True))

# Ввод даты
@dp.message(WalkState.date)
async def process_walk_date(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_kb)
        return
    try:
        datetime.strptime(message.text, "%d.%m.%Y")
        await state.update_data(walk_date=message.text)
        await message.answer("⏰ Теперь время (ЧЧ:ММ):")
        await state.set_state(WalkState.time)
    except ValueError:
        await message.answer("❌ Ошибка формата. Пиши так: 05.04.2026")

# Ввод времени
@dp.message(WalkState.time)
async def process_walk_time(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%H:%M")
        await state.update_data(walk_time=message.text)
        await message.answer("⏱ Выбери длительность:", reply_markup=get_duration_kb())
    except ValueError:
        await message.answer("❌ Ошибка. Пиши так: 10:00")

# 🔥 ГЛАВНОЕ ИСПРАВЛЕНИЕ: Обработка кнопок длительности
@dp.callback_query(F.data.startswith("walk_"))
async def process_duration_click(call: CallbackQuery, state: FSMContext):
    # 1. СРАЗУ убираем "часики" загрузки
    await call.answer()
    
    try:
        duration = int(call.data.split("_")[1])
        price = (duration // 10) * 50
        data = await state.get_data()

        # 2. Проверяем, что данные не потерялись
        if 'walk_date' not in data or 'walk_time' not in data:
            await call.message.answer("❌ Данные потеряны. Попробуйте с /walk")
            await state.clear()
            return

        # 3. Сохраняем в БД
        await create_walk_request(
            user_id=call.from_user.id,
            date=data['walk_date'],
            time=data['walk_time'],
            duration=duration,
            price=price
        )

        # 4. Меняем сообщение с кнопками на итог
        await call.message.edit_text(
            f"✅ Заявка создана!\n📅 {data['walk_date']} в {data['walk_time']}\n⏱ {duration} мин\n💰 {price} ₽"
        )
        await state.clear()
        await call.message.answer("Главное меню:", reply_markup=main_kb)
        
    except Exception as e:
        print(f"❌ ОШИБКА ПРИ СОЗДАНИИ ЗАЯВКИ:\n{traceback.format_exc()}")
        await call.message.answer(f"❌ Ошибка при сохранении. Попробуйте позже.")

@dp.callback_query(F.data == "cancel_walk")
async def cancel_walk_click(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    await call.message.edit_text("❌ Заявка отменена.")
    await call.message.answer("Главное меню:", reply_markup=main_kb)

@dp.message(F.text == "❌ Отмена")
async def cmd_cancel_text(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=main_kb)

@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=main_kb)

async def main():
    token = os.getenv("BOT_TOKEN")
    if not token: return
    await init_db()
    bot = Bot(token=token)
    print("✅ Бот с кнопками запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
