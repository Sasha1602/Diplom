from datetime import datetime, timedelta
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database import (
    execute_query,
    fetch_user_bookings,
    delete_booking,
    delete_all_user_bookings,
    check_availability,
    save_user_info,
    check_user_in_db,
    register_user,
    get_user_from_db,
    fetch_user_bookings_by_uid,
    delete_all_bookings_by_uid,
    delete_booking_by_id
)
from utils import validate_phone, get_min_max_dates
from config import DB_CONFIG
import logging

logging.basicConfig(level=logging.INFO)

router = Router()

user_data = {}
user_step = {}

max_computers_per_zone = {
    "izi": 8,
    "pro": 13,
    "bootkemp": 5,
    "ps4": 1,
    "ps5": 1,
}

full_zone_names = {
    "izi": "Изи-Лайн",
    "pro": "Про-Лайн",
    "bootkemp": "Буткемп",
    "ps4": "PlayStation 4 зона",
    "ps5": "PlayStation 5 зона",
}

zone_computer_mapping = {
    "izi": range(1, 9),
    "pro": range(9, 22),
    "bootkemp": range(22, 27),
    "ps4": [27],
    "ps5": [28],
}


def validate_computers(zone, computer_numbers):
    """
    Проверяет, что номера компьютеров соответствуют выбранной зоне.
    """
    valid_numbers = zone_computer_mapping.get(zone, [])
    for num in computer_numbers:
        if int(num) not in valid_numbers:
            return False
    return True


async def send_week_calendar(uid, message: Message):
    """
    Отправляет inline-клавиатуру с датами на ближайшую неделю.
    """
    now = datetime.now()
    dates = [(now + timedelta(days=i)).strftime("%d.%m.%Y") for i in range(7)]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for date in dates:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=date, callback_data=f"date:{date}")])
    
    await message.answer("Выберите дату для бронирования:", reply_markup=keyboard)

def choosing_actions(uid):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Забронировать", callback_data="book")],
            [InlineKeyboardButton(text="Отменить бронь", callback_data="cancel_booking")],
            [InlineKeyboardButton(text="Оплатить", callback_data="pay")],
            [InlineKeyboardButton(text="Правила", callback_data="rules")]
        ]
    )
    return keyboard


@router.message(F.text.lower() == "/start")
async def start(message: Message):
    uid = message.from_user.id
    if "nikname" in user_data.get(uid, {}):
        greeting = f"Добро пожаловать обратно, {user_data[uid]['nikname']}!"
        await message.answer(greeting)
        await show_actions(message)
    else:
        greeting = "Здравствуйте! Вы уже пользовались этим ботом?"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Да", callback_data="yes")],
                [InlineKeyboardButton(text="Нет", callback_data="no")]
            ]
        )
        await message.answer(greeting, reply_markup=keyboard)
        user_data[uid] = {}
        user_step[uid] = "awaiting_account"


@router.callback_query(F.data.in_({"yes", "no"}))
async def handle_registration(call: CallbackQuery):
    uid = call.from_user.id
    logging.info(f"User {uid} selected: {call.data}")
    if call.data == "yes":
        user_exists = await check_user_in_db(uid)
        logging.info(f"User {uid} exists in DB: {user_exists}")
        if user_exists:
            await call.message.answer("Добро пожаловать обратно!")
            await show_actions(call.message)
        else:
            await call.message.answer("Вы не зарегистрированы. Пожалуйста, введите ваш номер телефона для регистрации:")
            user_step[uid] = "awaiting_new_phone"
    elif call.data == "no":
        user_exists = await check_user_in_db(uid)
        logging.info(f"User {uid} exists in DB: {user_exists}")
        if user_exists:
            await call.message.answer("Добро пожаловать обратно!")
            await show_actions(call.message)
        else:
            await call.message.answer("Введите ваш номер телефона для регистрации:")
            user_step[uid] = "awaiting_new_phone"
    await call.answer()

@router.message(F.func(lambda m: user_step.get(m.from_user.id) == "awaiting_nickname"))
async def get_nickname(message: Message):
    uid = message.from_user.id
    user_data[uid]["nikname"] = message.text.strip()
    await message.answer("Отлично! Теперь введите номер телефона:")
    user_step[uid] = "awaiting_phone"


@router.message(F.func(lambda m: user_step.get(m.from_user.id) == "awaiting_phone"))
async def get_phone(message: Message):
    uid = message.from_user.id
    phone_text = message.text.strip()
    if validate_phone(phone_text):
        user_data[uid]["telefhone"] = phone_text
        await message.answer("Номер телефона сохранён.")
        await show_actions(message)
    else:
        await message.answer("Пожалуйста, введите корректный номер телефона.")


@router.message(F.func(lambda m: user_step.get(m.from_user.id) == "awaiting_new_phone"))
async def get_new_phone(message: Message):
    uid = message.from_user.id
    phone_text = message.text.strip()
    if validate_phone(phone_text):
        user_data[uid]["telefhone"] = phone_text
        await message.answer("Номер телефона сохранён. Теперь введите ваш никнейм:")
        user_step[uid] = "awaiting_new_nickname"
    else:
        await message.answer("Пожалуйста, введите корректный номер телефона.")


@router.message(F.func(lambda m: user_step.get(m.from_user.id) == "awaiting_new_nickname"))
async def get_new_nickname(message: Message):
    uid = message.from_user.id
    nickname = message.text.strip()
    user_data[uid]["nikname"] = nickname
    phone_number = user_data[uid].get("telefhone", "")
    if not phone_number:
        await message.answer("Ошибка: номер телефона не найден. Пожалуйста, начните регистрацию заново.")
        return
    await register_user(uid, phone_number, nickname)
    await message.answer(f"Никнейм '{nickname}' успешно сохранён!")
    await show_actions(message)
    user_step[uid] = None


@router.callback_query(F.data == "book")
async def handle_book_button(call: CallbackQuery):
    uid = call.from_user.id
    await call.answer()  # Убираем "часики" на кнопке

    user_data[uid]["selected_computers"] = []

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Изи-Лайн", callback_data="izi")],
            [InlineKeyboardButton(text="Про-Лайн", callback_data="pro")],
            [InlineKeyboardButton(text="Буткемп", callback_data="bootkemp")],
            [InlineKeyboardButton(text="PS4", callback_data="ps4")],
            [InlineKeyboardButton(text="PS5", callback_data="ps5")]
        ]
    )
    await call.message.answer("Выберите желаемую зону:", reply_markup=keyboard)
    user_step[uid] = "awaiting_zone"


@router.callback_query(F.data.in_(["izi", "pro", "bootkemp", "ps4", "ps5"]))
async def handle_zone_selection(call: CallbackQuery):
    uid = call.from_user.id
    user_data[uid]["selected_zone"] = call.data
    if call.data in ["ps4", "ps5"]:
        await call.message.answer("Выберите дату для бронирования:")
        await send_week_calendar(uid, call.message)
        user_step[uid] = "awaiting_date"
    else:
        await call.message.answer("Сколько компьютеров хотите забронировать?")
        user_step[uid] = "awaiting_number_of_computers"
    await call.answer()


@router.message(F.func(lambda m: user_step.get(m.from_user.id) == "awaiting_number_of_computers"))
async def ask_for_computer_numbers(message: Message):
    uid = message.from_user.id
    try:
        input_text = message.text.strip()
        if not input_text.isdigit():
            await message.answer("Пожалуйста, введите целое число.")
            return
        count = int(input_text)
        selected_zone = user_data[uid]["selected_zone"]
        max_computers = max_computers_per_zone[selected_zone]
        if count <= 0 or count > max_computers:
            await message.answer(
                f"Число должно быть положительным и не больше максимального количества {max_computers} компьютеров для зоны {selected_zone}."
            )
            return
        user_data[uid]["number_of_computers"] = count

        # Отправляем клавиатуру с выбором компьютеров
        valid_numbers = zone_computer_mapping[selected_zone]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for num in valid_numbers:
            keyboard.inline_keyboard.append([InlineKeyboardButton(text=str(num), callback_data=f"computer:{num}")])
        
        await message.answer("Выберите компьютеры для бронирования:", reply_markup=keyboard)
        user_step[uid] = "awaiting_computer_selection"
    except ValueError:
        await message.answer("Произошла ошибка при обработке ввода.")

@router.callback_query(F.data.startswith("computer:"))
async def handle_computer_selection(call: CallbackQuery):
    uid = call.from_user.id
    computer_number = int(call.data.split(":")[1])

    if "selected_computers" not in user_data[uid]:
        user_data[uid]["selected_computers"] = []

    # Проверяем, был ли уже выбран этот компьютер
    if computer_number in user_data[uid]["selected_computers"]:
        await call.answer(f"⚠️ Компьютер {computer_number} уже выбран!", show_alert=True)
        return

    user_data[uid]["selected_computers"].append(computer_number)
    await call.answer(f"✅ Компьютер {computer_number} выбран.")

    if len(user_data[uid]["selected_computers"]) >= user_data[uid]["number_of_computers"]:
        await call.message.answer("Компьютеры успешно выбраны. Пожалуйста, выберите дату бронирования.")
        await send_week_calendar(uid, call.message)
        user_step[uid] = "awaiting_date"


@router.callback_query(F.data.startswith("date:"))
async def handle_date_selection(call: CallbackQuery):
    uid = call.from_user.id
    try:
        selected_date = call.data.split(":")[1]
        user_data[uid]["booking_date"] = selected_date
        selected_zone = user_data[uid]["selected_zone"]
        
        logging.info(f"User {uid} selected date: {selected_date} for zone: {selected_zone}")
        
        now = datetime.now()
        times_list = []
        start_hour = 0 if datetime.strptime(selected_date, "%d.%m.%Y").date() != now.date() else now.hour + 1
        for hour in range(start_hour, 24):
            for minute in [0, 30]:
                time_string = f"{hour:02}:{minute:02}"  # Форматируем часы и минуты как HH:MM
                callback_data = f"time:{selected_date}:{time_string}"
                times_list.append(
                    InlineKeyboardButton(text=time_string, callback_data=callback_data)
                )
        
        markup = InlineKeyboardMarkup(inline_keyboard=[])
        for i in range(0, len(times_list), 6):
            row = times_list[i : i + 6]
            markup.inline_keyboard.append(row)
        
        if selected_zone not in ["ps4", "ps5"]:
            markup.inline_keyboard.append([InlineKeyboardButton(text="Назад к выбору даты", callback_data="back_to_date")])
        
        await call.message.answer(
            f"Вы выбрали дату: {selected_date}. Выберите время:", reply_markup=markup
        )
        await call.answer()
    except Exception as e:
        logging.error(f"Error handling date selection for user {uid}: {e}")
        await call.message.answer("Произошла ошибка при выборе даты. Пожалуйста, попробуйте снова.")
        await call.answer()

@router.callback_query(F.data.startswith("time:"))
async def handle_time_selection(call: CallbackQuery):
    uid = call.from_user.id
    try:
        # Разделяем call.data
        parts = call.data.split(":")

        print(parts)  # Отладка

        if len(parts) < 4:  # Должно быть 4 части: ['time', 'дата', 'часы', 'минуты']
            raise ValueError("Некорректный формат данных. Ожидается: time:date:hours:minutes")

        # Получаем дату и время
        _, date, hours, minutes = parts
        time = f"{hours}:{minutes}"  # Собираем время в "HH:MM"

        # Проверяем корректность формата времени
        try:
            datetime.strptime(time, "%H:%M")
        except ValueError:
            raise ValueError("Некорректный формат времени. Ожидалось HH:MM.")

        # Сохраняем данные
        user_data[uid]["selected_time"] = time
        user_data[uid]["booking_date"] = date

        # Формируем сообщение
        booking_details = f"Вы выбрали время: {time} на {date}. Подтвердите выбор."
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить бронь", callback_data="confirm_booking")],
            [InlineKeyboardButton(text="Отменить бронь", callback_data="cancel_booking")],
        ])

        await call.message.answer(booking_details, reply_markup=markup)
        await call.answer()

    except Exception as e:
        logging.error(f"Ошибка при выборе времени (UID: {uid}): {e}")
        await call.message.answer("❌ Произошла ошибка. Попробуйте снова.")
        await call.answer()

@router.callback_query(F.data == "confirm_booking")
async def confirm_booking(call: CallbackQuery):
    uid = call.from_user.id
    try:
        if uid not in user_data:
            logging.error(f"User {uid} not found in user_data during booking confirmation.")
            await call.message.answer("Произошла ошибка при сохранении данных.")
            return

        data = user_data[uid]

        # Загружаем данные из БД
        user_db_data = await get_user_from_db(uid)
        data["nikname"] = user_db_data.get("nickname")
        data["telefhone"] = user_db_data.get("phone")

        required_fields = (
            ["nikname", "telefhone", "selected_zone", "selected_time", "booking_date"]
            if data["selected_zone"] in ["ps4", "ps5"]
            else [
                "nikname",
                "telefhone",
                "selected_zone",
                "number_of_computers",
                "selected_time",
                "booking_date",
                "selected_computers",
            ]
        )
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            missing_fields_str = ", ".join(missing_fields)
            logging.warning(f"User {uid} is missing required fields: {missing_fields_str}")
            await call.message.answer(
                f"Не удалось сохранить бронирование, так как отсутствуют следующие данные: {missing_fields_str}. Пожалуйста, введите их."
            )
            return
        
        if data["selected_zone"] not in ["ps4", "ps5"]:
            computer_ids = data.get("selected_computers", [])
            booking_date = data.get("booking_date")
            booking_time = data.get("selected_time")
            if not await check_availability(computer_ids, booking_date, booking_time):
                logging.warning(f"User {uid} tried to book unavailable computers: {computer_ids}")
                await call.message.answer(
                    "Один или несколько выбранных компьютеров уже забронированы. Пожалуйста, выберите другие."
                )
                return
        
        await save_user_info(uid, data)
        logging.info(f"User {uid} successfully booked: {data}")
        await call.message.answer("✅ Ваша бронь успешно сохранена!")
        await show_actions(call.message)
    
    except Exception as e:
        logging.error(f"Error confirming booking for user {uid}: {e}")
        await call.message.answer("❌ Произошла ошибка при подтверждении бронирования. Пожалуйста, попробуйте снова.")
    
    await call.answer()

# @router.callback_query(F.data == "cancel_booking")
# async def cancel_booking(call: CallbackQuery):
#     uid = call.from_user.id
#     keys_to_clear = ["computer_count", "zone", "booking_date", "computers"]
#     for key in keys_to_clear:
#         if key in user_data[uid]:
#             user_data[uid][key] = None
#     await call.message.answer("Ваше бронирование было отменено.")
#     await show_actions(call.message)
#     await call.answer()


@router.callback_query(F.data == "cancellation")
async def handle_cancellation(call: CallbackQuery):
    uid = call.from_user.id
    phone_number = user_data[uid].get("telefhone", "")
    nickname = user_data[uid].get("nikname", "")
    bookings = await fetch_user_bookings(phone_number, nickname)
    if not bookings:
        await call.message.answer("У вас нет активных броней.")
        return
    markup = InlineKeyboardMarkup()
    for booking in bookings:
        try:
            booking_id, date, time, zone, computers = booking
            if computers is not None:
                button_text = f"{date.strftime('%d.%m.%Y')}, {time}, Зона: {zone},  Компьютеры: {computers}"
            else:
                button_text = f"{date.strftime('%d.%m.%Y')}, {time}, {zone}"
            markup.add(InlineKeyboardButton(text=button_text, callback_data=f"cancel_{booking_id}"))
        except ValueError as e:
            print(f"Ошибка обработки данных бронирования: {e}")
    markup.add(InlineKeyboardButton(text="Отменить все бронирования", callback_data="cancel_all"))
    await call.message.answer(
        "Выберите бронь для отмены или отмените все сразу:", reply_markup=markup
    )
    await call.answer()

async def show_actions(message: Message):
    keyboard = choosing_actions(message.from_user.id)
    await message.answer("Выберите желаемое действие:", reply_markup=keyboard)

@router.callback_query(F.data == "cancel_booking")
async def handle_cancel_booking(call: CallbackQuery):
    uid = call.from_user.id

    bookings = await fetch_user_bookings_by_uid(uid)

    if not bookings:
        await call.message.answer("У вас нет активных броней.")
        return

    markup = InlineKeyboardMarkup(inline_keyboard=[])

    for booking in bookings:
        booking_id, booking_date, booking_time, zone, computers = booking
        button_text = f"{booking_date.strftime('%d.%m.%Y')} {booking_time} | {zone} | ПК: {computers or 'N/A'}"
        markup.inline_keyboard.append([
            InlineKeyboardButton(text=button_text, callback_data=f"cancel:{booking_id}")
        ])

    markup.inline_keyboard.append([
        InlineKeyboardButton(text="Отменить все бронирования", callback_data="cancel_all")
    ])

    markup.inline_keyboard.append([
        InlineKeyboardButton(text="Назад", callback_data="back_to_menu")
    ])

    await call.message.answer("Выберите бронь для отмены:", reply_markup=markup)

# Обработка отмены конкретной брони
@router.callback_query(F.data.startswith("cancel:"))
async def handle_cancel_specific_booking(call: CallbackQuery):
    booking_id = call.data.split(":")[1]
    await delete_booking_by_id(booking_id)
    await call.message.answer("✅ Бронирование успешно отменено.")
    await handle_cancel_booking(call)

# Обработка отмены всех броней
@router.callback_query(F.data == "cancel_all")
async def handle_cancel_all_bookings(call: CallbackQuery):
    uid = call.from_user.id
    await delete_all_bookings_by_uid(uid)
    await call.message.answer("✅ Все ваши бронирования успешно отменены.")
    await show_actions(call.message)

# Возврат в главное меню
@router.callback_query(F.data == "back_to_menu")
async def handle_back_to_menu(call: CallbackQuery):
    await show_actions(call.message)

@router.callback_query(F.data == "back_to_date")
async def handle_back_to_date(call: CallbackQuery):
    uid = call.from_user.id

    # Очищаем ранее выбранное время
    if "selected_time" in user_data[uid]:
        user_data[uid]["selected_time"] = None

    await call.answer()
    await send_week_calendar(uid, call.message)
    user_step[uid] = "awaiting_date"
