import random, sqlite3
from settings import DATABASE_NAME

def generate_booking_number():
    """Generates a unique 6-digit booking number."""
    conn = sqlite3.connect(DATABASE_NAME)  # Подключение к базе данных
    cursor = conn.cursor()

    while True:
        booking_number = str(random.randint(100000, 999999))  # Генерация случайного 6-значного числа
        cursor.execute("SELECT * FROM bookings WHERE booking_number = ?", (booking_number,))
        result = cursor.fetchone()
        if not result:  # Проверка, что номер бронирования уникален
            break

    conn.close()  # Закрытие соединения с базой данных
    return booking_number