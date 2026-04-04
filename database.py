# database.py — ИСПРАВЛЕННАЯ ВЕРСИЯ (типы date/time)
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
        
        # Используем нативные типы DATE и TIME
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS walk_requests (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                walk_date DATE,
                walk_time TIME,
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

async def create_walk_request(user_id: int, date_str: str, time_str: str, duration: int, price: float):
    # ✅ КОНВЕРТАЦИЯ: строки -> объекты date/time для asyncpg
    date_obj = datetime.strptime(date_str, "%d.%m.%Y").date()
    time_obj = datetime.strptime(time_str, "%H:%M").time()
    
    async with pool.acquire() as conn:
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
        # ✅ КОНВЕРТАЦИЯ ОБРАТНО: объекты date/time -> строки для вывода в Telegram
        result = []
        for row in rows:
            result.append({
                'id': row['id'],
                'walk_date': row['walk_date'].strftime("%d.%m.%Y"),
                'walk_time': row['walk_time'].strftime("%H:%M"),
                'duration_min': row['duration_min'],
                'price': float(row['price']),
                'status': row['status']
            })
        return result
