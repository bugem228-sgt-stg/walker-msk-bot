# main.py — ФИНАЛЬНАЯ ВЕРСИЯ (Ваш ID: 400063653)
import asyncio
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database import (
    init_db, add_user, get_balance, update_balance, deduct_balance, create_walk_request, get_user_requests,
    get_pending_requests, update_request_status, get_statistics, get_request_details
)

dp = Dispatcher(storage=MemoryStorage())

# ✅ АВТОМАТИЧЕСКИ ПОДСТАВЛЕН ВАШ ID
ADMIN_ID = 400063653 

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

# --- 🔹 FSM СОСТОЯНИЯ ---
class WalkState(StatesGroup):
    date = State()
    time = State()

class TopupState(StatesGroup):
    amount = State()

# --- 📝 ХЕНДЛЕРЫ ПОЛЬЗОВАТЕЛЯ ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Друг"
    await add_user(user_id, username)
    await message.answer(f"🐕 Привет, {username}! Используй меню ниже 👇", reply_markup=main_kb)

@dp.message(F.text == "🐕 Заявка на выгул")
async def cmd_walk_menu(message: Message, state: FSMContext):
    await message.answer("📅 Напишите дату (ДД.ММ.ГГГГ):", 
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
        emoji = "⏳" if req['status'] == 'pending' else "✅" if req['status'] == 'approved' else "❌"
        text += f"{emoji} #{req['id']} | {req['walk_date']} в {req['walk_time']} ({req['duration_min']} мин)\n"
    await message.answer(text, reply_markup=main_kb)

@dp.message(F.text == "💰 Пополнить")
async def cmd_topup_menu(message: Message, state: FSMContext):
    await message.answer("💳 Введите сумму пополнения:", 
                         reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True))
    await state.set_state(TopupState.amount)

@dp.message(TopupState.amount)
async def process_topup_amount(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_kb)
        return
    try:
        amount = float(message.text)
        if amount <= 0: raise ValueError
        
        try:
            await message.bot.send_message(
                ADMIN_ID,
                f"💰 <b>Запрос на пополнение!</b>\n"
                f"👤 @{message.from_user.username or 'anon'} (ID: <code>{message.from_user.id}</code>)\n"
                f"💵 Сумма: <b>{amount} ₽</b>\n\n"
                f"Для зачисления:\n<code>/addbalance {message.from_user.id} {int(amount)}</code>",
                parse_mode="HTML"
            )
        except Exception as e: print(f"⚠️ Ошибка уведомления: {e}")

        await message.answer(f"✅ Заявка на {amount}₽ отправлена!", reply_markup=main_kb)
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число больше 0")

# --- 👨‍💼 АДМИН-ПАНЕЛЬ ---

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("🔐 <b>Панель Администратора</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Ожидающие заявки", callback_data="admin_pending")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
    ]))

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    stats = await get_statistics()
    await call.message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: {stats['users']}\n"
        f"💰 Всего на балансах: {stats['balance']} ₽\n"
        f"🔥 Заявок в ожидании: {stats['pending']}",
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_pending")
async def admin_show_pending(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    requests = await get_pending_requests()
    if not requests:
        await call.answer("Заявок пока нет!", show_alert=True)
        return

    text = "📋 <b>Заявки на выгул:</b>\n\n"
    keyboard = []
    
    for req in requests:
        text += f"🆔 #{req['id']} | 📅 {req['walk_date']} {req['walk_time']}\n"
        text += f"   ⏱ {req['duration_min']} мин | 💰 {req['price']} ₽\n"
        text += f"   👤 User ID: <code>{req['user_id']}</code>\n\n"
        keyboard.append([
            InlineKeyboardButton(text=f"✅ Заявка #{req['id']}", callback_data=f"approve_{req['id']}"),
            InlineKeyboardButton(text=f"❌ Заявка #{req['id']}", callback_data=f"reject_{req['id']}")
        ])

    await call.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

# 🔥 ЛОГИКА ОДОБРЕНИЯ (со списанием баланса)
@dp.callback_query(F.data.startswith("approve_"))
async def admin_approve(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    
    req_id = int(call.data.split("_")[1])
    
    # 1. Получаем детали заявки
    details = await get_request_details(req_id)
    if not details:
        await call.answer("Заявка не найдена!", show_alert=True)
        return
    
    user_id = details['user_id']
    price = details['price']
    
    # 2. Пытаемся списать баланс
    success = await deduct_balance(user_id, price)
    
    if success:
        # 3. Если списалось успешно — меняем статус
        await update_request_status(req_id, "approved")
        await call.answer("Заявка одобрена и оплата проведена!", show_alert=True)
        await call.message.edit_text(call.message.text.replace(f"✅ Заявка #{req_id}", f"✅ Заявка #{req_id} [ОПЛАЧЕНО]"))
        
        try:
            await call.bot.send_message(user_id, f"✅ Заявка #{req_id} одобрена!\n💰 С вашего счёта списано {price}₽.")
        except: pass
    else:
        # 4. Если денег нет
        await call.answer("Ошибка: У клиента недостаточно средств!", show_alert=True)
        try:
            await call.bot.send_message(user_id, f"❌ Заявка #{req_id} отклонена: Недостаточно средств на счёте.")
        except: pass

@dp.callback_query(F.data.startswith("reject_"))
async def admin_reject(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    req_id = int(call.data.split("_")[1])
    await update_request_status(req_id, "rejected")
    await call.answer("Заявка отклонена", show_alert=True)
    await call.message.edit_text(call.message.text.replace(f"❌ Заявка #{req_id}", f"❌ Заявка #{req_id} [ОТКЛОНЕНО]"))
    
    details = await get_request_details(req_id)
    if details:
        try: await call.bot.send_message(details['user_id'], f"❌ Ваша заявка #{req_id} отклонена администратором.")
        except: pass

# --- 🐕 ЛОГИКА ЗАЯВОК ---

@dp.message(WalkState.date)
async def process_walk_date(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_kb)
        return
    try:
        datetime.strptime(message.text, "%d.%m.%Y")
        await state.update_data(walk_date=message.text)
        await message.answer("⏰ Время (ЧЧ:ММ):")
        await state.set_state(WalkState.time)
    except ValueError:
        await message.answer("❌ Формат: ДД.ММ.ГГГГ")

@dp.message(WalkState.time)
async def process_walk_time(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%H:%M")
        await state.update_data(walk_time=message.text)
        await message.answer("⏱ Длительность:", reply_markup=get_duration_kb())
    except ValueError:
        await message.answer("❌ Формат: ЧЧ:ММ")

@dp.callback_query(F.data.startswith("walk_"))
async def process_duration_click(call: CallbackQuery, state: FSMContext):
    await call.answer()
    try:
        duration = int(call.data.split("_")[1])
        price = (duration // 10) * 50
        data = await state.get_data()
        
        # ✅ ИСПРАВЛЕНИЕ СИНТАКСИСА
        if 'walk_date' not in data or 'walk_time' not in 
            await call.message.answer("❌ Данные потеряны. Попробуйте снова.")
            await state.clear()
            return

        # 🔥 ПРОВЕРКА БАЛАНСА ПЕРЕД СОЗДАНИЕМ
        balance = await get_balance(call.from_user.id)
        if balance < price:
            await call.message.answer(
                f"❌ Недостаточно средств!\n"
                f"На счёте: {balance}₽, Нужно: {price}₽\n"
                f"Пополните баланс: /topup",
                reply_markup=main_kb
            )
            await state.clear()
            return

        # Создаем заявку
        await create_walk_request(call.from_user.id, data['walk_date'], data['walk_time'], duration, price)
        await call.message.edit_text(f"✅ Заявка создана!\n📅 {data['walk_date']} {data['walk_time']}\n💰 Стоимость: {price} ₽ (Будет списано при одобрении)")
        await state.clear()
        await call.message.answer("Главное меню:", reply_markup=main_kb)
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        await call.message.answer("❌ Ошибка при сохранении заявки.")

@dp.callback_query(F.data == "cancel_walk")
async def cancel_walk_click(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    await call.message.edit_text("❌ Отменено.")
    await call.message.answer("Главное меню:", reply_markup=main_kb)

@dp.message(F.text == "❌ Отмена")
async def cmd_cancel_text(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=main_kb)

@dp.message(Command("addbalance"))
async def cmd_add_balance(message: Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID: return
    try:
        if not command.args:
            await message.answer("❌ Использование: /addbalance ID СУММА")
            return
        clean_args = command.args.replace('"', '').replace("'", "").split()
        if len(clean_args) != 2:
            await message.answer("❌ Нужно указать ID и сумму через пробел.")
            return
        user_id = int(clean_args[0])
        amount = float(clean_args[1])
        
        await update_balance(user_id, amount)
        new_balance = await get_balance(user_id)
        
        await message.answer(f"✅ Зачислено {amount}₽ пользователю {user_id}\n💳 Баланс: {new_balance}₽")
        try: await message.bot.send_message(user_id, f"💰 Админ зачислил {amount}₽. Баланс: {new_balance}₽")
        except: pass
    except ValueError: await message.answer("❌ Ошибка формата.")

async def main():
    token = os.getenv("BOT_TOKEN")
    if not token: return
    await init_db()
    bot = Bot(token=token)
    print("✅ Бот с автосписанием запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
