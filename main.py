# main.py — ПОЛНОЦЕННЫЙ БОТ С БАЗОЙ ДАННЫХ
import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from database import init_db, add_user, get_balance, update_balance, create_walk_request

dp = Dispatcher()

# 🐕 Команда /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Неизвестный"
    
    # Добавляем пользователя в БД
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
    
    await message.answer(
        f"💳 Ваш баланс: {balance} ₽\n\n"
        f"💡 Для пополнения используйте: /topup"
    )

# 💳 Команда /topup (пока заглушка)
@dp.message(Command("topup"))
async def cmd_topup(message: Message):
    await message.answer(
        "💳 Пополнение баланса\n\n"
        "📝 Напишите сумму (например: 500)\n"
        "💡 Или напишите админу: @admin_username"
    )

# 🐕 Команда /walk (пока заглушка)
@dp.message(Command("walk"))
async def cmd_walk(message: Message):
    await message.answer(
        "🐕 Заявка на выгул\n\n"
        "📅 Введите дату (ДД.ММ.ГГГГ):\n"
        "⏰ Затем время (ЧЧ:ММ)\n"
        "⏱ Затем длительность (30, 40, 50, 60 мин)"
    )

# 📋 Команда /mywalks
@dp.message(Command("mywalks"))
async def cmd_mywalks(message: Message):
    user_id = message.from_user.id
    requests = await get_user_requests(user_id)
    
    if not requests:
        await message.answer("📭 У вас пока нет заявок")
        return
    
    text = "📋 Ваши заявки:\n\n"
    for req in requests:
        text += (
            f"🆔 #{req['id']} | Статус: {req['status']}\n"
            f"📅 {req['walk_date']} в {req['walk_time']}\n"
            f"⏱ {req['duration_min']} мин | 💰 {req['price']} ₽\n\n"
        )
    
    await message.answer(text)

async def main():
    token = os.getenv("BOT_TOKEN")
    
    if not token:
        print("❌ ОШИБКА: Токен не найден!")
        return
    
    # Инициализируем базу данных
    await init_db()
    
    bot = Bot(token=token)
    print("✅ Бот запущен с базой данных!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
