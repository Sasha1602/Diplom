import asyncio
from datetime import datetime
import aiomysql
from config import DB_CONFIG
import logging

db_pool = None

def set_db_pool(pool):
    global db_pool
    db_pool = pool

async def create_db_connection():
    """Создает асинхронное подключение к базе данных."""
    try:
        conn = await aiomysql.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            db=DB_CONFIG['db'],
            autocommit=True
        )
        return conn
    except Exception as e:
        logging.error(f"Ошибка подключения к базе данных: {e}")
        raise

async def execute_query(query, params=None, fetch=False):
    async with db_pool.acquire() as conn:
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                if fetch:
                    return await cursor.fetchall()
                await conn.commit()
        except Exception as e:
            logging.error(f"Ошибка выполнения запроса: {query} | Ошибка: {e}")
            return None

async def delete_booking(booking_id):
    query = "DELETE FROM UserInfo WHERE id = %s"
    await execute_query(query, (booking_id,))

async def delete_all_user_bookings(phone_number, nickname):
    query = "DELETE FROM UserInfo WHERE phone = %s AND nickname = %s"
    await execute_query(query, (phone_number, nickname))

async def fetch_user_bookings(phone_number, nickname):
    query = """
        SELECT id, booking_date, booking_time, zone, computers 
        FROM UserInfo 
        WHERE phone = %s AND nickname = %s
    """
    return await execute_query(query, (phone_number, nickname), fetch=True)

async def format_date(date_str):
    try:
        return datetime.strptime(date_str, "%d.%m.%Y").strftime("%Y-%m-%d")
    except ValueError as e:
        logging.error(f"Ошибка преобразования даты: {date_str} | {e}")
        return None

async def check_availability(computer_ids, booking_date, booking_time):
    """
    Проверяет доступность компьютеров на определенную дату и время.
    """
    if not computer_ids:
        return True
    
    formatted_date = await format_date(booking_date)

    if not formatted_date:
        logging.error("Некорректная дата, не удалось проверить доступность.")
        return False

    placeholders = ','.join(['%s'] * len(computer_ids))
    query = f"""
        SELECT COUNT(*)
        FROM UserInfo
        WHERE computers IN ({placeholders}) AND booking_date = %s AND booking_time = %s
    """
    params = (*computer_ids, formatted_date, booking_time)
    result = await execute_query(query, params, fetch=True)

    if result:
        (count,) = result[0]
        return count == 0
    return False

async def format_date(date_str):
    """
    Преобразует строку даты из формата 'DD.MM.YYYY' в 'YYYY-MM-DD'
    """
    try:
        return datetime.strptime(date_str, "%d.%m.%Y").strftime("%Y-%m-%d")
    except ValueError:
        logging.error(f"Ошибка преобразования даты: {date_str}")
        return None

async def save_user_info(uid, data):
    """
    Сохраняет информацию о бронировании в базу данных.
    :param uid: ID пользователя в Telegram.
    :param data: Словарь с данными пользователя.
    """

    formatted_date = await format_date(data['booking_date'])

    if not formatted_date:
        logging.error("Некорректная дата бронирования.")
        return

    if data['selected_zone'] in ['ps4', 'ps5']:
        query = """
            INSERT INTO UserInfo (user_id, nickname, phone, zone, booking_date, booking_time)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        params = (
            uid, data['nikname'], data['telefhone'], data['selected_zone'],
            formatted_date, data['selected_time']
        )
    else:
        query = """
            INSERT INTO UserInfo (user_id, nickname, phone, zone, computer_count, booking_date, booking_time, computers)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            uid, data['nikname'], data['telefhone'], data['selected_zone'],
            data['number_of_computers'], formatted_date, data['selected_time'],
            ','.join(map(str, data['selected_computers']))
        )
    await execute_query(query, params)

async def check_user_in_db(uid):
    """
    Проверяет, существует ли пользователь в базе данных по его uid.
    :param uid: ID пользователя в Telegram.
    :return: True, если пользователь существует, иначе False.
    """
    query = "SELECT COUNT(*) FROM Users WHERE user_id = %s"
    result = await execute_query(query, (uid,), fetch=True)
    if result:
        (count,) = result[0]
        return count > 0
    return False

async def register_user(uid, phone_number, nickname):
    """
    Регистрирует нового пользователя в базе данных.
    :param uid: ID пользователя в Telegram.
    :param phone_number: Номер телефона пользователя.
    :param nickname: Никнейм пользователя.
    """
    query = """
        INSERT INTO Users (user_id, phone, nickname, registration_date)
        VALUES (%s, %s, %s, NOW())
    """
    await execute_query(query, (uid, phone_number, nickname))

async def get_user_from_db(uid):
    """
    Загружает данные пользователя из базы данных.
    :param uid: ID пользователя в Telegram.
    :return: Словарь с данными пользователя или None, если не найден.
    """
    query = "SELECT nickname, phone FROM Users WHERE user_id = %s"
    result = await execute_query(query, (uid,), fetch=True)
    if result:
        return {"nickname": result[0][0], "phone": result[0][1]}
    return None

async def fetch_user_bookings_by_uid(uid):
    query = """
        SELECT id, booking_date, booking_time, zone, computers
        FROM UserInfo
        WHERE user_id = %s
    """
    return await execute_query(query, (uid,), fetch=True)

async def delete_booking_by_id(booking_id):
    query = "DELETE FROM UserInfo WHERE id = %s"
    await execute_query(query, (booking_id,))

async def delete_all_bookings_by_uid(uid):
    query = "DELETE FROM UserInfo WHERE user_id = %s"
    await execute_query(query, (uid,))
