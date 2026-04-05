# database.py — Версия с автосписанием и проверками
import asyncpg
import os
from datetime import datetime

pool = None

async def init_db():
    global pool
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL не найден!")
        return
    
    pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
    
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                balance DECIMAL(10, 2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS walk_requests (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                walk_date TEXT,
                walk_time TEXT,
                duration_min INTEGER,
                status TEXT DEFAULT 'pending',
                price DECIMAL(10, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    print("✅ База данных инициализирована!")

async def add_user(user_id: int, username: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, username, balance) VALUES ($1, $2, 0) "
            "ON CONFLICT (user_id) DO UPDATE SET username = $2",
            user_id, username
        )

async def get_balance(user_id: int) -> float:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1", user_id)
        return float(row['balance']) if row else 0.0

async def update_balance(user_id: int, amount: float):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
            amount, user_id
        )

# 🔥 НОВАЯ ФУНКЦИЯ: Списание средств (возвращает True если успешно)
async def deduct_balance(user_id: int, amount: float) -> bool:
    async with pool.acquire() as conn:
        # Списываем только если баланс >= суммы
        result = await conn.execute(
            "UPDATE users SET balance = balance - $1 WHERE user_id = $2 AND balance >= $1",
            amount, user_id
        )
        # Если обновилась 1 строка — значит деньги были.
        return "UPDATE 1" in result

async def create_walk_request(user_id: int, date: str, time: str, duration: int, price: float):
    # Преобразуем строки из Telegram в нативные объекты Python
    date_obj = datetime.strptime(date, "%d.%m.%Y").date()
    time_obj = datetime.strptime(time, "%H:%M").time()
    
    async with pool.acquire() as conn:
        # asyncpg сам корректно преобразует date/time объекты в SQL типы
        await conn.execute(
            """INSERT INTO walk_requests 
               (user_id, walk_date, walk_time, duration_min, price, status) 
               VALUES ($1, $2, $3, $4, $5, 'pending')""",
            user_id, date_obj, time_obj, duration, price
        )

async def get_user_requests(user_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM walk_requests WHERE user_id = $1 ORDER BY created_at DESC",
            user_id
        )
        result = []
        for row in rows:
            result.append({
                'id': row['id'],
                'walk_date': row['walk_date'],
                'walk_time': row['walk_time'],
                'duration_min': row['duration_min'],
                'price': float(row['price']),
                'status': row['status']
            })
        return result

async def get_pending_requests():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM walk_requests WHERE status = 'pending' ORDER BY id DESC")

async def update_request_status(req_id: int, status: str):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE walk_requests SET status = $1 WHERE id = $2", status, req_id)

# 🔥 НОВАЯ ФУНКЦИЯ: Получить детали заявки по ID
async def get_request_details(req_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM walk_requests WHERE id = $1", req_id)
        if row:
            return {
                'id': row['id'],
                'user_id': row['user_id'],
                'price': float(row['price'])
            }
        return None

async def get_statistics():
    async with pool.acquire() as conn:
        users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        total_balance = await conn.fetchval("SELECT SUM(balance) FROM users")
        pending_count = await conn.fetchval("SELECT COUNT(*) FROM walk_requests WHERE status = 'pending'")
        return {"users": users_count, "balance": float(total_balance) if total_balance else 0, "pending": pending_count}
