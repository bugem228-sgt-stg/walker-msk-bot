# main.py — ИСПРАВЛЕННЫЙ КОД (aiogram 3.x compatible)
import asyncio
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database import init_db, add_user, get_balance, update_balance, create_walk_request, get_user_requests

dp = Dispatcher(storage=MemoryStorage())

# 🔹 Состояния для форм
class TopupState(StatesGroup):
    amount = State()

class WalkState(StatesGroup):
    date = State()
    time = State()
    duration = State()

# 🐕 Команда /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Неизвестный"
    await add_user(user_id, username)
    
    await message.answer(
        f"🐕 Привет, {username}!\n\n"
        f"📋 Доступные команды:\n"
        f"/balance — Проверить баланс\n"
        f"/topup — Пополнить баланс\n"
        f"/walk — Подать заявку на выгул\n"
        f"/mywalks — Мои заявки"
    )

# 💰 Команда /balance
@dp.message(Command("balance"))
async def cmd_balance(message: Message):
    user_id = message.from_user.id
    balance = await get_balance(user_id)
    await message.answer(f"💳 Ваш баланс: {balance} ₽\n\n💡 Для пополнения: /topup")

# 💳 Начало пополнения
@dp.message(Command("topup"))
async def cmd_topup_start(message: Message, state: FSMContext):
    await message.answer(
        "💳 Пополнение баланса\n\n"
        "📝 Напишите сумму в рублях (например: 500)\n"
        "❌ /cancel — отмена"
    )
    await state.set_state(TopupState.amount)  # ✅ Исправлено!

# Обработка суммы пополнения
@dp.message(TopupState.amount)
async def process_topup_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return
        
        await update_balance(message.from_user.id, amount)
        new_balance = await get_balance(message.from_user.id)
        
        await message.answer(f"✅ Баланс пополнен на {amount} ₽\n💳 Новый баланс: {new_balance} ₽")
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите корректное число (например: 500)")

# 🐕 Начало заявки на выгул
@dp.message(Command("walk"))
async def cmd_walk_start(message: Message, state: FSMContext):
    await message.answer("🐕 Заявка на выгул\n\n📅 Введите дату (ДД.ММ.ГГГГ):\n❌ /cancel — отмена")
    await state.set_state(WalkState.date)  # ✅ Исправлено!

# Обработка даты
@dp.message(WalkState.date)
async def process_walk_date(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%d.%m.%Y")  # Проверяем формат
        await state.update_data(walk_date=message.text)
        await message.answer("⏰ Введите время (ЧЧ:ММ):\nНапример: 10:30 или 18:00")
        await state.set_state(WalkState.time)
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ДД.ММ.ГГГГ")

# Обработка времени
@dp.message(WalkState.time)
async def process_walk_time(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%H:%M")  # Проверяем формат
        await state.update_data(walk_time=message.text)
        await message.answer("⏱ Выберите длительность (минут):\n30, 40, 50, 60, 75, 90\n\n💰 Стоимость: 50₽ за 10 мин")
        await state.set_state(WalkState.duration)
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ЧЧ:ММ")

# Обработка длительности и создание заявки
@dp.message(WalkState.duration)
async def process_walk_duration(message: Message, state: FSMContext):
    try:
        duration = int(message.text)
        if duration < 30:
            await message.answer("❌ Минимум 30 минут")
            return
        
        price = (duration // 10) * 50
        data = await state.get_data()
        user_id = message.from_user.id
        
        # Создаём заявку (строки date/time теперь работают!)
        await create_walk_request(
            user_id=user_id,
            date=data['walk_date'],
            time=data['walk_time'],
            duration=duration,
            price=price
        )
        
        await message.answer(
            f"✅ Заявка создана!\n\n"
            f"📅 Дата: {data['walk_date']}\n"
            f"⏰ Время: {data['walk_time']}\n"
            f"⏱ Длительность: {duration} мин\n"
            f"💰 Стоимость: {price} ₽\n\n"
            f"📋 Статус: Ожидает подтверждения\n"
            f"👀 Проверить: /mywalks"
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число (например: 30)")

# 📋 Мои заявки
@dp.message(Command("mywalks"))
async def cmd_mywalks(message: Message):
    user_id = message.from_user.id
    requests = await get_user_requests(user_id)
    
    if not requests:
        await message.answer("📭 У вас пока нет заявок")
        return
    
    text = "📋 Ваши заявки:\n\n"
    for req in requests:
        status_emoji = "⏳" if req['status'] == 'pending' else "✅" if req['status'] == 'approved' else "❌"
        text += (
            f"{status_emoji} Заявка #{req['id']} | {req['status']}\n"
            f"📅 {req['walk_date']} в {req['walk_time']}\n"
            f"⏱ {req['duration_min']} мин | 💰 {req['price']} ₽\n\n"
        )
    await message.answer(text)

# ❌ Отмена
@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено. Используйте /start для главного меню")

async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("❌ ОШИБКА: Токен не найден!")
        return
    
    await init_db()
    bot = Bot(token=token)
    print("✅ Бот запущен с исправленным FSM!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
