import logging
from aiogram import Bot, Dispatcher
import asyncio
from bot_handlers_FIXED import router  # Импортируйте роутер
from config import TOKEN, DB_CONFIG
from aiomysql import create_pool
from database import set_db_pool  # эту функцию мы создадим в database.py

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Включение роутера в диспетчер
dp.include_router(router)

async def main():
    print("Starting the bot...")
    try:
        pool = await create_pool(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            db=DB_CONFIG['db'],
            autocommit=True,
            minsize=1,  # минимальное количество соединений
            maxsize=5   # максимальное количество соединений
        )
        set_db_pool(pool)  # передаём пул в database.py
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
