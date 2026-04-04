# database.py — Работа с базой данных
import asyncpg
import os

# Глобальная переменная для подключения
pool = None

async def init_db():
    """Инициализация базы данных"""
    global pool
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ DATABASE_URL не найден!")
        return
    
    # Создаём пул подключений
    pool = await asyncpg.create_pool(
        database_url,
        min_size=2,
        max_size=10
    )
    
    # Создаём таблицу пользователей
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                balance DECIMAL(10, 2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица заявок на выгул
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
    """Добавить пользователя или обновить данные"""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, username, balance) VALUES ($1, $2, 0) "
            "ON CONFLICT (user_id) DO UPDATE SET username = $2",
            user_id, username
        )

async def get_balance(user_id: int) -> float:
    """Получить баланс пользователя"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT balance FROM users WHERE user_id = $1",
            user_id
        )
        return float(row['balance']) if row else 0.0

async def update_balance(user_id: int, amount: float):
    """Изменить баланс (положительно или отрицательно)"""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
            amount, user_id
        )

async def create_walk_request(user_id: int, date: str, time: str, duration: int, price: float):
    """Создать заявку на выгул"""
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO walk_requests 
               (user_id, walk_date, walk_time, duration_min, price, status) 
               VALUES ($1, $2, $3, $4, $5, 'pending')""",
            user_id, date, time, duration, price
        )

async def get_user_requests(user_id: int):
    """Получить все заявки пользователя"""
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM walk_requests WHERE user_id = $1 ORDER BY created_at DESC",
            user_id
        )
