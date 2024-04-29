import sqlite3
from datetime import datetime, timedelta
from random_book_number_generator import *  # Импорт функции генерации уникального номера бронирования
from settings import *  # Импорт настроек бота

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)  # Создание клавиатуры для ответа пользователю

# Обработчик команды старта бронирования
async def start(update: Update, context) -> int:
    await update.message.reply_text(
        "Привет! 👋 Добро пожаловать в галерею черных кошек. 🐈‍⬛ Что вы хотите сделать?",
        reply_markup=ReplyKeyboardMarkup(main_menu_keyboard, one_time_keyboard=True),
    )
    return CHOOSING  # Переход к выбору действия пользователя

# Обработчик запроса информации о галерее
async def gallery_info(update: Update, context) -> int:
    await update.message.reply_text(
        "Галерея черных кошек - это уникальное место, где можно насладиться красотой и таинственностью черных кошек в искусстве. 🎨🐈‍⬛ Приходите и окунитесь в атмосферу загадочности! ✨",
        reply_markup=ReplyKeyboardMarkup(back_keyboard, one_time_keyboard=True),
    )

    # Отправка местоположения галереи
    await update.message.reply_location(latitude=53.33613, longitude=83.77797)

    return CHOOSING  # Переход к выбору действия пользователя

# Обработчик выбора пользователя
async def choice(update: Update, context) -> int:
    user_choice = update.message.text
    if user_choice == "Забронировать 🗓️":
        conn = sqlite3.connect(DATABASE_NAME)  # Подключение к базе данных
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS bookings (id INTEGER PRIMARY KEY, booking_number TEXT UNIQUE, date TEXT, time TEXT)"
        )
        conn.commit()
        conn.close()

        # Получение доступных дат и времени для бронирования
        available_dates_times = get_available_dates_times()

        # Создание клавиатуры с датами, на которые есть доступные слоты
        reply_keyboard = [[date.strftime("%d.%m.%Y")] for date, times in available_dates_times.items() if times]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

        await update.message.reply_text(
            "Пожалуйста, выберите дату: 🗓️", reply_markup=markup
        )
        return SELECTING_DATE  # Переход к выбору даты

    elif user_choice == "Посмотреть брони 📋":
        bookings = get_all_bookings_sorted()
        if bookings:
            booking_list = "\n".join(
                [f"• {booking[0]} в {booking[1]}" for booking in bookings]
            )  
            await update.message.reply_text(
                f"```\nБронирования:\n{booking_list}\n```",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup(back_keyboard, one_time_keyboard=True),
            )
        else:
            await update.message.reply_text(
                "Нет бронирований. 😔", reply_markup=ReplyKeyboardMarkup(back_keyboard, one_time_keyboard=True)
            )
        return GETTING_BACK  # Переход к главному меню

    elif user_choice == "Отменить бронь ❌":
        await update.message.reply_text(
            "Пожалуйста, введите номер бронирования, которое вы хотите отменить:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return CANCELING  # Переход к отмене бронирования

    elif user_choice == "Узнать больше о галерее 🐈‍⬛":
        await gallery_info(update, context)  # Переход к просмотру информации о галерее
        return GETTING_BACK  # Переход к главному меню

    else:
        await update.message.reply_text("Пожалуйста, выберите одно из предложенных действий.")
        return CHOOSING  # Повторный выбор действия

async def select_date(update: Update, context) -> None:
    selected_date_str = update.message.text
    try:
        selected_date = datetime.strptime(selected_date_str, "%d.%m.%Y").date()
    except ValueError:
        await update.message.reply_text("Неверный формат даты. Пожалуйста, используйте формат ДД.ММ.ГГГГ.")
        return SELECTING_DATE

    # Проверка, что выбранная дата в пределах следующих 7 дней
    today = datetime.today().date()
    if selected_date < today or selected_date > today + timedelta(days=6):
        await update.message.reply_text("Пожалуйста, выберите дату в течение следующих 7 дней.")
        return SELECTING_DATE

    context.user_data["date"] = selected_date

    # Получение доступных времен для выбранной даты
    available_times = get_available_times(selected_date)

    if not available_times:
        await update.message.reply_text(
            f"На {selected_date.strftime('%d.%m.%Y')} нет доступных времен для бронирования."
        )
        return CHOOSING

    # Обновление клавиатуры с доступными временами
    reply_keyboard = [available_times[i : i + 3] for i in range(0, len(available_times), 3)]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    await update.message.reply_text(
        f"Вы выбрали {selected_date.strftime('%d.%m.%Y')}. Теперь выберите удобное время: 🕐",
        reply_markup=markup,
    )
    return SELECTING_TIME

async def select_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_time = update.message.text
    selected_date = context.user_data["date"]

    try:
        booking_time = datetime.strptime(user_time, "%H:%M").time()
        if booking_time < datetime.strptime("10:00", "%H:%M").time() or booking_time > datetime.strptime("17:00", "%H:%M").time():
            raise ValueError() 
    except ValueError:
        await update.message.reply_text("Неверный формат времени или время вне рабочего диапазона (10:00 - 17:00).")
        return SELECTING_TIME

    # Проверка, что выбранное время еще не забронировано
    if is_time_slot_booked(selected_date, user_time):
        await update.message.reply_text(
            f"Время {user_time} на {selected_date.strftime('%d.%m.%Y')} уже занято. 😔 Пожалуйста, выберите другое время."
        )
        return SELECTING_TIME 

    # Генерация уникального номера бронирования
    booking_number = generate_booking_number()

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO bookings (booking_number, date, time) VALUES (?, ?, ?)",
        (booking_number, selected_date.strftime("%Y-%m-%d"), user_time),
    )
    conn.commit()
    conn.close()

    # Отправка анимации
    gif_url = open(GIF_PATH, 'rb')
    await update.message.reply_animation(gif_url) 

    # Отправка сообщения с подтверждением бронирования
    await update.message.reply_text(
        f"Бронирование успешно завершено на {selected_date.strftime('%d.%m.%Y')} в {user_time}. 🎉\n"
        f"Ваш номер бронирования: {booking_number}",
        reply_markup=ReplyKeyboardMarkup(back_keyboard, one_time_keyboard=True),
    )
    return GETTING_BACK

# Функция получения доступных дат и времен для бронирования
def get_available_dates_times():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Получить все забронированные даты и времена
    cursor.execute("SELECT date, time FROM bookings")
    bookings = cursor.fetchall()

    # Словарь для хранения дат и времен
    available_dates_times = {}

    # Можно бронировать на BOOKING_DAYS дней вперед
    for days_ahead in range(BOOKING_DAYS):
        current_date = (datetime.today() + timedelta(days=days_ahead)).date()

        # Все забронированные времена на эту дату
        booked_times = [
            booking[1] for booking in bookings if booking[0] == current_date.strftime("%Y-%m-%d")
        ]

        # Всевозможные времена на такую дату
        all_times = ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"]

        # Получаем свободные промежутки
        available_times = [time for time in all_times if time not in booked_times]

        available_dates_times[current_date] = available_times

    conn.close()
    return available_dates_times

# Функция получения доступных времен для конкретной даты
def get_available_times(selected_date):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT time FROM bookings WHERE date = ?", (selected_date.strftime("%Y-%m-%d"),))
    booked_times = [row[0] for row in cursor.fetchall()]

    all_times = ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"]

    available_times = [time for time in all_times if time not in booked_times]

    conn.close()
    return available_times

# Функция получения всех бронирований, отсортированных по дате и времени
def get_all_bookings_sorted():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT date, time FROM bookings ORDER BY date, time")
    bookings = cursor.fetchall()
    conn.close()

    return bookings

# Функция проверки, забронирован ли уже данный слот времени на выбранную дату
def is_time_slot_booked(selected_date, user_time):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM bookings WHERE date = ? AND time = ?",
        (selected_date.strftime("%Y-%m-%d"), user_time),
    )
    result = cursor.fetchone()
    conn.close()

    return bool(result)

# Обработчик отмены бронирования
async def cancel(update: Update, context) -> int:
    booking_number = update.message.text

    # Проверка формата номера бронирования
    if not booking_number.isdigit() or len(booking_number) != 6:
        await update.message.reply_text("Неверный формат номера бронирования. Пожалуйста, введите 6-значный номер.")
        return CANCELING

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bookings WHERE booking_number = ?", (booking_number,))
    conn.commit()
    conn.close()

    if cursor.rowcount > 0:
        await update.message.reply_text(
            f"Бронирование с номером {booking_number} успешно отменено. ✅",
            reply_markup=ReplyKeyboardMarkup(back_keyboard, one_time_keyboard=True),
        )
    else:
        await update.message.reply_text(
            f"Бронирование с номером {booking_number} не найдено. 😔",
            reply_markup=ReplyKeyboardMarkup(back_keyboard, one_time_keyboard=True),
        )

    return GETTING_BACK  # Переход к главному меню

# Главная функция для запуска бота
def main() -> None:
    application = Application.builder().token(
        MYTOKEN
    ).build()

    application.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("start", start)],  # Обработчик старта бронирования
            states={
                CHOOSING: [
                    MessageHandler(
                        filters.Regex(
                            r"^Забронировать 🗓️$|^Посмотреть брони 📋$|^Отменить бронь ❌$|^Узнать больше о галерее 🐈‍⬛$"
                        ),
                        choice,
                    )
                ],
                SELECTING_DATE: [
                    MessageHandler(
                        filters.Regex(r"^\d{2}\.\d{2}\.\d{4}$"),
                        select_date,
                    )
                ],
                SELECTING_TIME: [
                    MessageHandler(
                        filters.Regex(r"^10:00$|^11:00$|^12:00$|^13:00$|^14:00$|^15:00$|^16:00$|^17:00$"),
                        select_time,
                    )
                ],
                CANCELING: [MessageHandler(filters.Regex(r"\d{6}"), cancel)],
                GETTING_BACK: [MessageHandler(filters.Regex(r"^Назад$"), start)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )
    )

    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()