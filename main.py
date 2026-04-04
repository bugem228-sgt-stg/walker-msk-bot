# main.py — версия для Render.com
import asyncio
import os
from os import getenv
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

load_dotenv()

dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("🐕 Бот работает! Готовим базу данных и баланс...")

async def main():
    bot = Bot(token=getenv("BOT_TOKEN"))
    print("✅ Бот запущен на Render.com")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())