import telebot
from telebot import types
import os
from content_plan import ContentPlanGenerator
from text_gen import PostGenerator
from Yandex_gen import GenerateImageYandex
from nko_handler import nko_auth_service

USER_FLOW = {}  # {chat_id: "plan" | "post" | "image" | None}

def set_user_flow(chat_id: int, flow: str | None):
    USER_FLOW[chat_id] = flow

def get_user_flow(chat_id: int) -> str | None:
    return USER_FLOW.get(chat_id)

# ============================================================
#                     ГЛАВНОЕ МЕНЮ
# ============================================================
def open_main_menu(bot, call_or_message):
    if isinstance(call_or_message, telebot.types.CallbackQuery):
        chat_id = call_or_message.message.chat.id
        bot.answer_callback_query(call_or_message.id)
    else:
        chat_id = call_or_message.chat.id

    set_user_flow(chat_id, None)

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📅 Создать контент-план", callback_data="gen_plan"),
        types.InlineKeyboardButton("✍️ Сгенерировать пост", callback_data="gen_post")
    )
    markup.add(
        types.InlineKeyboardButton("🖼 Сгенерировать изображение", callback_data="gen_image")
    )
    markup.add(
        types.InlineKeyboardButton("⚙ Режимы", callback_data="switch_modes")
    )

    bot.send_message(
        chat_id,
        "<b>Главное меню</b>\nВыберите действие:",
        reply_markup=markup
    )

# ============================================================
#                РОУТЕР КОЛЛБЕКОВ
# ============================================================
def menu_router(bot, call):
    bot.answer_callback_query(call.id)

    if call.data != "go_nko_handler":
        nko_auth_service.reset_state(call.from_user.id)

    routes = {
        "gen_plan": ask_plan_start_date,
        "gen_post": ask_post_idea,
        "gen_image": ask_image_prompt,
        "open_menu": open_main_menu,
        "switch_modes": show_modes,
        "go_nko_handler": lambda bot, call: nko_auth_service.process_nko_auth_stub(bot, call),
        "set_mode_anon": set_mode_anon,
        "set_mode_nko": set_mode_nko,
    }

    if call.data in routes:
        routes[call.data](bot, call)
    else:
        bot.send_message(call.message.chat.id, "Неизвестная команда. Вернитесь в меню /start")

def set_mode_anon(bot, call):
    tg_id = call.from_user.id
    nko_auth_service.set_mode(tg_id, 2)
    bot.send_message(call.message.chat.id, "Теперь работаешь в обезличенном режиме.")
    show_modes(bot, call)

def set_mode_nko(bot, call):
    tg_id = call.from_user.id
    chat_id = call.message.chat.id

    user_row = nko_auth_service._get_user_by_tg_id(tg_id)
    if not user_row:
        # нет строки — реально нет никаких данных НКО
        bot.send_message(
            chat_id,
            "У тебя пока нет сохранённых данных НКО. Сначала пройдём регистрацию."
        )
        nko_auth_service.process_nko_auth_stub(bot, call)
        return

    nko_auth_service.set_mode(tg_id, 1)
    bot.send_message(call.message.chat.id, "Теперь работаешь с данными НКО.")
    show_modes(bot, call)

# ============================================================
#                     РЕЖИМЫ РАБОТЫ
# ============================================================
def show_modes(bot, call):
    chat_id = call.message.chat.id
    tg_id = call.from_user.id

    mode, _ = nko_auth_service.get_mode_and_data_for_generation(tg_id)

    if mode == 1:
        text_nko = "🟢 Работать с данными НКО"
        text_anon = "🔴 Работать обезличенно"
    else:
        text_nko = "🔴 Работать с данными НКО"
        text_anon = "🟢 Работать обезличенно"

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(text_anon, callback_data="set_mode_anon"),
        types.InlineKeyboardButton(text_nko, callback_data="set_mode_nko")
    )
    markup.add(types.InlineKeyboardButton("⬅ Назад", callback_data="open_menu"))

    bot.send_message(
        chat_id,
        "Выберите режим работы:",
        reply_markup=markup
    )

# ============================================================
#              ====== ГЕНЕРАЦИЯ КОНТЕНТ-ПЛАНА ======
# ============================================================
def ask_plan_start_date(bot, call):
    chat_id = call.message.chat.id
    set_user_flow(chat_id, "plan")
    msg = bot.send_message(call.message.chat.id, "📅 Введите стартовую дату (дд.мм.гггг):")
    bot.register_next_step_handler(msg, ask_plan_end_date, bot)

def ask_plan_end_date(message, bot):
    if get_user_flow(message.chat.id) != "plan":
        return
    start_date = message.text
    msg = bot.send_message(message.chat.id, "📅 Теперь конечную дату:")
    bot.register_next_step_handler(msg, ask_plan_frequency, bot, start_date)

def ask_plan_frequency(message, bot, start_date):
    if get_user_flow(message.chat.id) != "plan":
        return
    end_date = message.text
    msg = bot.send_message(message.chat.id, "📌 Укажите частоту ('3 раза в неделю'):")
    bot.register_next_step_handler(msg, generate_content_plan, bot, start_date, end_date)

def generate_content_plan(message, bot, start_date, end_date):
    if get_user_flow(message.chat.id) != "plan":
        return
    frequency = message.text
    user_id = message.chat.id

    mode, nko = nko_auth_service.get_mode_and_data_for_generation(user_id)

    if mode == 1 and nko:
        generator = ContentPlanGenerator(
            nko_name=nko.get("name_NKO"),
            nko_description=nko.get("about_NKO"),
            nko_activity=(
                f"{nko.get('v1', '')}\n"
                f"Проблемы: {nko.get('v2', '')}\n"
                f"Уникальность: {nko.get('v3', '')}\n"
                f"Доказательства успеха: {nko.get('v4', '')}\n"
                f"Миссия: {nko.get('v5', '')}"
            ),
            nko_audience=nko.get("v6"),
            tone=nko.get("v6", "разговорный"),
        )
    else:
        generator = ContentPlanGenerator()

    bot.send_message(user_id, "⏳ Генерирую контент-план...")
    result = generator.generate_content_plan(start_date, end_date, frequency)

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔄 Сгенерировать снова", callback_data="gen_plan"),
        types.InlineKeyboardButton("🏠 В меню", callback_data="open_menu")
    )

    bot.send_message(user_id, f"<b>Готовый план:</b>\n\n{result}", reply_markup=markup)

# ============================================================
#                     ====== ПОСТЫ ======
# ============================================================
def ask_post_idea(bot, call):
    chat_id = call.message.chat.id
    set_user_flow(chat_id, "post")
    msg = bot.send_message(call.message.chat.id, "✍️ Опишите идею поста:")
    bot.register_next_step_handler(msg, ask_post_topic, bot)

def ask_post_topic(message, bot):
    if get_user_flow(message.chat.id) != "post":
        return
    user_idea = message.text
    msg = bot.send_message(message.chat.id, "🏷 Укажите тему:")
    bot.register_next_step_handler(msg, ask_post_style, bot, user_idea)

def ask_post_style(message, bot, user_idea):
    if get_user_flow(message.chat.id) != "post":
        return
    topic = message.text
    msg = bot.send_message(message.chat.id, "🎨 Укажите стиль:")
    bot.register_next_step_handler(msg, generate_post, bot, user_idea, topic)

def generate_post(message, bot, user_idea, topic):
    if get_user_flow(message.chat.id) != "post":
        return
    style = message.text
    user_id = message.chat.id

    mode, nko = nko_auth_service.get_mode_and_data_for_generation(user_id)

    generator = PostGenerator()
    bot.send_message(user_id, "⏳ Генерирую текст поста...")

    if mode == 1 and nko:
        nko_info = {
            "Название": nko.get("name_NKO"),
            "Описание": nko.get("about_NKO"),
            "Проблемы": nko.get("v1"),
            "Уникальность": nko.get("v2"),
            "Доказательства успеха": nko.get("v3"),
            "Миссия": nko.get("v4"),
            "Целевая аудитория": nko.get("v5"),
            "Тон": nko.get("v6"),
        }
    else:
        nko_info = None

    result = generator.generate_post(
        user_idea=user_idea,
        topic=topic,
        nko_info=nko_info,
        style=style
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔄 Новый пост", callback_data="gen_post"),
        types.InlineKeyboardButton("🏠 В меню", callback_data="open_menu")
    )

    bot.send_message(user_id, f"<b>Ваш пост:</b>\n\n{result}", reply_markup=markup)

# ============================================================
#             ====== ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ ======
# ============================================================
def ask_image_prompt(bot, call):
    chat_id = call.message.chat.id
    set_user_flow(chat_id, "image")
    msg = bot.send_message(call.message.chat.id, "🖼 Опишите изображение:")
    bot.register_next_step_handler(msg, ask_image_style, bot)

def ask_image_style(message, bot):
    if get_user_flow(message.chat.id) != "image":
        return
    prompt = message.text
    msg = bot.send_message(message.chat.id, "🎨 Укажите стиль:")
    bot.register_next_step_handler(msg, generate_image, bot, prompt)

def generate_image(message, bot, prompt):
    if get_user_flow(message.chat.id) != "image":
        return
    style = message.text
    user_id = message.chat.id

    bot.send_message(user_id, "⏳ Генерирую изображение...")

    output_path = f"generated_{message.from_user.id}.png"
    gen = GenerateImageYandex(prompt, style)
    gen.run(output_path)

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔄 Новое изображение", callback_data="gen_image"),
        types.InlineKeyboardButton("🏠 В меню", callback_data="open_menu")
    )

    try:
        with open(output_path, "rb") as f:
            bot.send_photo(user_id, f, caption="Готово!", reply_markup=markup)
    finally:
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except OSError as e:
            print(f"[IMAGE] Не удалось удалить файл {output_path}: {e}")

