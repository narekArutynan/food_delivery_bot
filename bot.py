import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    PreCheckoutQueryHandler,
    MessageHandler,
    Filters,
)

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Меню ресторана
menu = {
    "Пицца": 500,
    "Суши": 700,
    "Бургер": 300,
    "Салат": 200,
    "Напиток": 100,
}

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect("food_delivery.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item TEXT,
            price INTEGER,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """
    )
    conn.commit()
    conn.close()

# Добавление пользователя
def add_user(user_id, username, first_name, last_name):
    conn = sqlite3.connect("food_delivery.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
        (user_id, username, first_name, last_name),
    )
    conn.commit()
    conn.close()

# Добавление заказа
def add_order(user_id, item, price):
    conn = sqlite3.connect("food_delivery.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (user_id, item, price) VALUES (?, ?, ?)",
        (user_id, item, price),
    )
    conn.commit()
    conn.close()

# Получение заказов пользователя
def get_user_orders(user_id):
    conn = sqlite3.connect("food_delivery.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE user_id = ?", (user_id,))
    orders = cursor.fetchall()
    conn.close()
    return orders

# Команда /start
def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name)
    update.message.reply_text(
        f"Привет, {user.first_name}! Добро пожаловать в наш бот для доставки еды. Используйте /menu чтобы увидеть наше меню."
    )

# Команда /menu
def show_menu(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton(f"{item} - {price} руб.", callback_data=item)]
        for item, price in menu.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Выберите блюдо из меню:", reply_markup=reply_markup)

# Обработка выбора блюда
def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    selected_item = query.data
    price = menu[selected_item]
    add_order(query.from_user.id, selected_item, price)
    query.edit_message_text(text=f"Вы выбрали: {selected_item} за {price} руб. Спасибо за заказ!")

# Оплата
def send_invoice(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    title = "Оплата заказа"
    description = "Оплата заказа через Telegram Payments"
    payload = "Custom-Payload"
    provider_token = "YOUR_PROVIDER_TOKEN"  # Замените на ваш токен
    start_parameter = "test-payment"
    currency = "RUB"
    prices = [LabeledPrice("Пицца", 500 * 100)]  # Цена в копейках

    context.bot.send_invoice(
        chat_id, title, description, payload, provider_token, start_parameter, currency, prices
    )

def precheckout_callback(update: Update, context: CallbackContext) -> None:
    query = update.pre_checkout_query
    if query.invoice_payload != "Custom-Payload":
        query.answer(ok=False, error_message="Ошибка оплаты")
    else:
        query.answer(ok=True)

def successful_payment_callback(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Оплата прошла успешно! Спасибо за заказ.")

# Админка
def admin_orders(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id != ADMIN_USER_ID:  # Замените на ID администратора
        update.message.reply_text("У вас нет доступа к этой команде.")
        return

    conn = sqlite3.connect("food_delivery.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders")
    orders = cursor.fetchall()
    conn.close()

    if not orders:
        update.message.reply_text("Заказов нет.")
    else:
        for order in orders:
            update.message.reply_text(
                f"Заказ #{order[0]}: {order[2]} за {order[3]} руб. (Статус: {order[4]})"
            )

# Геолокация
def ask_location(update: Update, context: CallbackContext) -> None:
    keyboard = [[KeyboardButton("Отправить местоположение", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text(
        "Пожалуйста, отправьте ваше местоположение для доставки.", reply_markup=reply_markup
    )

def handle_location(update: Update, context: CallbackContext) -> None:
    location = update.message.location
    lat = location.latitude
    lon = location.longitude
    update.message.reply_text(f"Ваш адрес доставки: широта {lat}, долгота {lon}.")

# Обработка ошибок
def error(update: Update, context: CallbackContext) -> None:
    logger.warning(f"Update {update} caused error {context.error}")

def main() -> None:
    init_db()
    updater = Updater("YOUR_TELEGRAM_BOT_TOKEN")  # Замените на ваш токен
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("menu", show_menu))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(CommandHandler("pay", send_invoice))
    dp.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    dp.add_handler(MessageHandler(Filters.successful_payment, successful_payment_callback))
    dp.add_handler(CommandHandler("admin_orders", admin_orders, filters=Filters.user(user_id=ADMIN_USER_ID)))
    dp.add_handler(CommandHandler("location", ask_location))
    dp.add_handler(MessageHandler(Filters.location, handle_location))
    dp.add_error_handler(error)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
