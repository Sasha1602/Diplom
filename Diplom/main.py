import logging
from aiogram import Bot, Dispatcher
import asyncio
from bot_handlers import router  # Импортируйте роутер
from config import TOKEN

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
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
