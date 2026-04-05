# main.py — ВЕРСИЯ 24/7 + 10 МИНУТ + ТАРИФЫ
import asyncio
import os
import traceback
from datetime import datetime, timedelta
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

# ✅ Ваш ID админа (запомнен)
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

# 💰 ТАРИФЫ (10 мин = 200 руб)
DURATION_PRICES = {
    10: 200,
    20: 400,
    30: 600,
    40: 800,
    50: 1000,
    60: 1200,
    90: 1800
}

def get_duration_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    row = []
    for dur, price in DURATION_PRICES.items():
        row.append(InlineKeyboardButton(text=f"{dur} мин ({price}₽)", callback_data=f"walk_{dur}"))
        if len(row) == 2: # По 2 кнопки в ряд
            kb.inline_keyboard.append(row)
            row = []
    if row:
        kb.inline_keyboard.append(row)
    kb.inline_keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_walk")])
    return kb

def get_calendar_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    today = datetime.now()
    row = []
    for i in range(1, 15):
        day = today + timedelta(days=i)
        date_str = day.strftime("%d.%m.%Y")
        btn_text = f"{day.strftime('%d')} {day.strftime('%a')}"
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"cal_{date_str}"))
        if len(row) == 4:
            kb.inline_keyboard.append(row)
            row = []
    if row:
        kb.inline_keyboard.append(row)
    kb.inline_keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_walk")])
    return kb

def get_hour_kb():
    """Выбор часа (00-23)"""
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    row = []
    for h in range(24):
        row.append(InlineKeyboardButton(text=f"{h:02d}:00", callback_data=f"hour_{h:02d}"))
        if len(row) == 4:
            kb.inline_keyboard.append(row)
            row = []
    if row:
        kb.inline_keyboard.append(row)
    kb.inline_keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_walk")])
    return kb

def get_minute_kb():
    """Выбор минут (00-50 с шагом 10)"""
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    row = []
    for m in range(0, 60, 10):
        row.append(InlineKeyboardButton(text=f"{m:02d}", callback_data=f"min_{m:02d}"))
        if len(row) == 3:
            kb.inline_keyboard.append(row)
            row = []
    if row:
        kb.inline_keyboard.append(row)
    kb.inline_keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_walk")])
    return kb

# --- 🔹 FSM СОСТОЯНИЯ ---
class TopupState(StatesGroup):
    amount = State()

# --- 📝 ХЕНДЛЕРЫ ПОЛЬЗОВАТЕЛЯ ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Друг"
    await add_user(user_id, username)
    await message.answer(f"🐕 Привет, {username}! Круглосуточный выгул! 🌙\nИспользуй меню ниже 👇", reply_markup=main_kb)

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

# --- 👨‍ АДМИН-ПАНЕЛЬ ---
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

@dp.callback_query(F.data.startswith("approve_"))
async def admin_approve(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    req_id = int(call.data.split("_")[1])
    details = await get_request_details(req_id)
    if not details:
        await call.answer("Заявка не найдена!", show_alert=True)
        return
    
    success = await deduct_balance(details['user_id'], details['price'])
    if success:
        await update_request_status(req_id, "approved")
        await call.answer("Заявка одобрена и оплата проведена!", show_alert=True)
        await call.message.edit_text(call.message.text.replace(f"✅ Заявка #{req_id}", f"✅ Заявка #{req_id} [ОПЛАЧЕНО]"))
        try: await call.bot.send_message(details['user_id'], f"✅ Заявка #{req_id} одобрена!\n💰 С вашего счёта списано {details['price']}₽.")
        except: pass
    else:
        await call.answer("Ошибка: У клиента недостаточно средств!", show_alert=True)
        try: await call.bot.send_message(details['user_id'], f"❌ Заявка #{req_id} отклонена: Недостаточно средств на счёте.")
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

# --- 🐕 НОВЫЙ ПОТОК ЗАЯВОК (КАЛЕНДАРЬ -> ЧАС -> МИНУТЫ -> ДЛИТЕЛЬНОСТЬ) ---
@dp.message(F.text == "🐕 Заявка на выгул")
async def cmd_walk_menu(message: Message, state: FSMContext):
    await message.answer("📅 Выберите дату выгула (следующие 14 дней):", reply_markup=get_calendar_kb())
    await state.clear()

@dp.callback_query(F.data.startswith("cal_"))
async def process_date_click(call: CallbackQuery, state: FSMContext):
    await call.answer()
    date_str = call.data.split("_", 1)[1]
    await state.update_data(walk_date=date_str)
    await call.message.answer("🕒 Выберите ЧАС выгула (00-23):", reply_markup=get_hour_kb())

@dp.callback_query(F.data.startswith("hour_"))
async def process_hour_click(call: CallbackQuery, state: FSMContext):
    await call.answer()
    hour = call.data.split("_", 1)[1]
    await state.update_data(walk_hour=hour)
    await call.message.answer("⏱ Выберите МИНУТЫ (шаг 10 мин):", reply_markup=get_minute_kb())

@dp.callback_query(F.data.startswith("min_"))
async def process_minute_click(call: CallbackQuery, state: FSMContext):
    await call.answer()
    minute = call.data.split("_", 1)[1]
    data = await state.get_data()
    
    date_str = data.get('walk_date')
    hour = data.get('walk_hour')
    
    if not date_str or not hour:
        await call.message.answer("❌ Ошибка данных. Начните заново: /walk", reply_markup=main_kb)
        await state.clear()
        return

    # Формируем итоговое время для проверки и сохранения
    time_str = f"{hour}:{minute}"
    selected_dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
    min_dt = datetime.now() + timedelta(hours=4)

    # 🔥 ПРОВЕРКА ПРАВИЛА 4 ЧАСОВ
    if selected_dt <= min_dt:
        await call.message.answer(
            f"❌ Невозможно оформить заявку!\n\n"
            f"📏 Заявку можно сделать минимум за 4 часа до выгула.\n"
            f"🕒 Вы выбрали: {date_str} в {time_str}\n"
            f"⏳ Ближайшее доступное время: {min_dt.strftime('%d.%m.%Y %H:%M')}",
            reply_markup=main_kb
        )
        await state.clear()
        return

    await state.update_data(walk_time=time_str)
    await call.message.answer("⏱ Выберите длительность выгула:", reply_markup=get_duration_kb())

@dp.callback_query(F.data.startswith("walk_"))
async def process_duration_click(call: CallbackQuery, state: FSMContext):
    await call.answer()
    try:
        duration = int(call.data.split("_")[1])
        # 💰 НОВАЯ ФОРМУЛА ЦЕНЫ (10 мин = 200 руб)
        price = DURATION_PRICES.get(duration, (duration // 10) * 200)
        
        data = await state.get_data()
        
        # ✅ ИСПРАВЛЕННЫЙ СИНТАКСИС
        if 'walk_date' not in data or 'walk_time' not in 
            await call.message.answer("❌ Данные потеряны. Попробуйте снова.", reply_markup=main_kb)
            await state.clear()
            return

        # 🔥 ПРОВЕРКА БАЛАНСА
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

        await create_walk_request(call.from_user.id, data['walk_date'], data['walk_time'], duration, price)
        await call.message.edit_text(f"✅ Заявка создана!\n📅 {data['walk_date']} в {data['walk_time']}\n⏱ {duration} мин\n💰 Стоимость: {price} ₽\n\n💡 Средства спишутся автоматически после одобрения админом.")
        await state.clear()
        await call.message.answer("Главное меню:", reply_markup=main_kb)
    except Exception as e:
        print(f"❌ ПОЛНАЯ ОШИБКА СОХРАНЕНИЯ:\n{traceback.format_exc()}")
        await call.message.answer("❌ Ошибка при сохранении заявки. Админ уже видит лог.", reply_markup=main_kb)

@dp.callback_query(F.data == "cancel_walk")
async def cancel_walk_click(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    await call.message.edit_text("❌ Отменено.", reply_markup=None)
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
    print("✅ Бот 24/7 с тарифом 200₽/10мин запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
