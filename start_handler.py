import telebot
from telebot import types
from menu_handler import menu_router

from nko_handler import nko_auth_service

API_TOKEN = "8476224067:AAFU_ZomwjKytUJ9BdMKGP6feIpBO2IgdBw"

bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")


# ================================
#   START COMMAND
# ================================
@bot.message_handler(commands=['start'])
def cmd_start(message: types.Message):
    """
    Первый шаг пайплайна из ТЗ:
    1) Приветствие
    2) Создание простого UX
    3) Переход в модуль авторизации НКО
    """

    user = message.from_user
    greeting = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я — бот для генерации контента для НКО.\n"
        "Помогу создавать контент-планы, посты, тексты и многое другое.\n\n"
        "<b>Чтобы начать, авторизуйтесь как НКО.</b>"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("Указываем данные НКО", callback_data="auth_nko"),
        types.InlineKeyboardButton("Работаем обезличенно", callback_data="open_menu")
    )

    bot.send_message(message.chat.id, greeting, reply_markup=markup)


# ================================
#   CALLBACK ROUTER
# ================================
@bot.callback_query_handler(func=lambda call: True)
def callback_router(call: types.CallbackQuery):
    if call.data == "auth_nko":
        nko_auth_service.process_nko_auth_stub(bot, call)
    else:
        menu_router(bot, call)

# ================================
#   FALLBACK HANDLER
# ================================
@bot.message_handler(func=lambda _: True)
def fallback_handler(message: types.Message):
    """
    Всё, что бот не понял — сюда.
    Важно: зачищаем UX и направляем пользователя.
    """
    bot.send_message(
        message.chat.id,
        "Я пока не понял эту команду 🤔\n"
        "Используйте /start, чтобы начать работу."
    )


# ================================
#   RUN BOT
# ================================
if __name__ == "__main__":
    print("Bot started...")
    bot.infinity_polling()
