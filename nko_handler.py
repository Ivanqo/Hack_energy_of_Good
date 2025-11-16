import telebot
from supabase import create_client, Client
from typing import Optional, Dict, Any
import telebot.apihelper as apihelper
from requests.exceptions import ConnectionError as RequestsConnectionError
from telebot import types

# ==========================
# НАСТРОЙКИ
# ==========================



SUPABASE_URL = "https://dvzttqaknxirlwltsnfq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR2enR0cWFrbnhpcmx3bHRzbmZxIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzIzMDc3OCwiZXhwIjoyMDc4ODA2Nzc4fQ.HFM0RSqwACoN5MiSOClc-eXCM_BE4P7A3DlA3KwgazM"
SUPABASE_TABLE = "users"


class NKOAuthService:
    QUESTIONS = [
        ("name_NKO", "Полное или сокращённое название НКО"),
        ("about_NKO", "Чем занимается Ваше НКО"),
        ("v1", "Какие основные проблемы вы решаете"),
        ("v2", "В чём уникальность вашей работы"),
        ("v3", "Какие доказательства успеха есть"),
        ("v4", "Какая миссия или главная цель вашей НКО"),
        ("v5", "Какая целевая аудитория контента вам важнее всего"),
        ("v6", "Каким тоном нужно говорить от лица НКО"),
    ]

    def __init__(self, supabase_url: str, supabase_key: str, table_name: str = SUPABASE_TABLE):
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.table_name = table_name

        self.state: Dict[int, Dict[str, Any]] = {}

    def _safe_send_message(self, bot: telebot.TeleBot, chat_id: int, text: str, **kwargs):
        """
        Обёртка над bot.send_message с отловом сетевых ошибок.
        Возвращает объект Message или None, если отправка не удалась.
        """
        try:
            msg = bot.send_message(chat_id, text, **kwargs)
            return msg
        except RequestsConnectionError as e:
            print(f"[Telegram] Connection error on send_message (chat_id={chat_id}): {e}")
            try:
                bot.send_message(chat_id, "⚠️ Ошибка соединения с Telegram. Попробуйте ещё раз чуть позже.")
            except Exception as e2:
                print(f"[Telegram] Retry send failed: {e2}")
            return None
        except apihelper.ApiTelegramException as e:
            print(f"[Telegram] Api error on send_message (chat_id={chat_id}): {e}")
            return None
        except Exception as e:
            print(f"[Telegram] Unexpected error on send_message (chat_id={chat_id}): {e}")
            return None
        
    def _send_long_message(self, bot: telebot.TeleBot, chat_id: int, lines, chunk_size: int = 3500):
        """
        Отправляет список строк, аккуратно разбивая их на несколько сообщений,
        чтобы не превышать лимит по длине.
        """
        if isinstance(lines, str):
            lines = lines.split("\n")

        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 1 > chunk_size:
                if chunk:
                    self._safe_send_message(bot, chat_id, chunk)
                    chunk = ""
            if chunk:
                chunk += "\n" + line
            else:
                chunk = line

        if chunk:
            self._safe_send_message(bot, chat_id, chunk)

    def _show_main_menu(self, bot: telebot.TeleBot, chat_id: int):
        """
        Локальная версия главного меню, чтобы не импортировать menu_handler
        и не создавать круговой импорт.
        """
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

        self._safe_send_message(
            bot,
            chat_id,
            "<b>Главное меню</b>\nВыберите действие:",
            reply_markup=markup
        )

    # ==========================
    # Публичные методы
    # ==========================

    def process_nko_auth_stub(self, bot: telebot.TeleBot, call):
        """
        Точка входа из хэндлера бота.
        1. Проверяем, есть ли пользователь в базе по tg_id.
        2. Если есть — показываем данные и спрашиваем, актуальны ли.
        3. Если нет — запускаем регистрацию.
        """
        bot.answer_callback_query(call.id)
        tg_id = call.from_user.id
        chat_id = call.message.chat.id if call.message else tg_id

        user_row = self._get_user_by_tg_id(tg_id)

        if user_row:
            summary_lines = ["Я нашёл ваши данные НКО:\n"]
            for idx, (key, question) in enumerate(self.QUESTIONS, start=1):
                val = user_row.get(key) or "—"
                summary_lines.append(f"{idx}. {question}:\n{val}\n")

            instructions_text = (
                "Актуальны ли эти данные?\n"
                "Напишите «да», если всё актуально.\n"
                "Напишите «обновить», чтобы пройти регистрацию заново."
            )

            self._send_long_message(bot, chat_id, summary_lines)

            self.state[tg_id] = {
                "mode": "check_existing",
                "data": user_row
            }

            msg = self._safe_send_message(bot, chat_id, instructions_text)
            if msg is not None:
                bot.register_next_step_handler(msg, lambda m: self._handle_check_existing(bot, m))
            return

        else:
            intro = (
                "Похоже, у меня пока нет данных о вашем НКО.\n"
                "Давайте пройдём короткую регистрацию.\n\n"
                "Вы можете в любой момент отправить /cancel, чтобы отменить регистрацию."
            )
            bot.send_message(chat_id, intro)

            self.state[tg_id] = {
                "mode": "registration",
                "step": 0,
                "data": {},
                "confirming": False,
                "edit_index": None,
            }
            self._ask_next_question(bot, chat_id, tg_id)

    def get_nko_data(self, bot: telebot.TeleBot, tg_id: int) -> Optional[Dict[str, Any]]:
        """
        Проверяем в Supabase, есть ли такой пользователь.
        Если есть — возвращаем словарь вида:
        {
            "name_NKO": "...",
            "about_NKO": "...",
            ...
        }
        Если нет — пишем пользователю сообщение и возвращаем None.
        """
        user_row = self._get_user_by_tg_id(tg_id)
        if user_row:
            result = {key: user_row.get(key) for key, _ in self.QUESTIONS}
            return result

        text = (
            "У меня пока нет данных о вашем НКО.\n"
            "Хотите пройти регистрацию сейчас или остаться в обезличенном режиме?\n\n"
            "Напишите «регистрация», чтобы ввести данные, или «обезличенно», чтобы продолжить без НКО."
        )
        msg = bot.send_message(tg_id, text)
        bot.register_next_step_handler(msg, lambda m: self._handle_no_data_choice(bot, m))
        return None

    # ==========================
    # Внутренние методы (работа с Supabase)
    # ==========================

    def _get_user_by_tg_id(self, tg_id: int) -> Optional[Dict[str, Any]]:
        """
        Получаем строку из Supabase по tg_id.
        """
        try:
            resp = (
                self.supabase
                .table(self.table_name)
                .select("*")
                .eq("tg_id", tg_id)
                .execute()
            )
            data = resp.data
            if data:
                return data[0]
            return None
        except Exception as e:
            print(f"[Supabase] Ошибка при запросе пользователя tg_id={tg_id}: {e}")
            return None

    def _upsert_user(self, tg_id: int, data: Dict[str, Any]) -> bool:
        """
        Сохраняем / обновляем данные пользователя в Supabase.
        Используем upsert по tg_id.
        """
        row = {"tg_id": tg_id}
        row.update(data)

        row.setdefault("mode", 1)

        try:
            resp = (
                self.supabase
                .table(self.table_name)
                .upsert(row, on_conflict="tg_id")
                .execute()
            )
            return True
        except Exception as e:
            print(f"[Supabase] Ошибка при upsert tg_id={tg_id}: {e}")
            return False

    # ==========================
    # Работа с режимом (mode)
    # ==========================

    def get_mode_and_data_for_generation(self, tg_id: int) -> tuple[int, Optional[Dict[str, Any]]]:
        row = self._get_user_by_tg_id(tg_id)
        if not row:
            return 2, None

        mode = row.get("mode") or 1

        if mode == 1:
            data = {key: row.get(key) for key, _ in self.QUESTIONS}
            return 1, data
        else:
            return 2, None

    # ==========================
    # Сброс состояния регистрации НКО
    # ==========================

    def reset_state(self, tg_id: int):
        """
        Полностью сбрасывает состояние регистрации / проверки НКО
        для пользователя tg_id. После этого любые next_step_handler'ы
        просто выйдут по проверке state.
        """
        if tg_id in self.state:
            print(f"[NKO] reset_state for tg_id={tg_id}")
            self.state.pop(tg_id, None)

    def set_mode(self, tg_id: int, mode: int) -> bool:
        """
        Устанавливает режим (1 - НКО, 2 - обезличенный) для пользователя.
        """
        try:
            resp = (
                self.supabase
                .table(self.table_name)
                .upsert({"tg_id": tg_id, "mode": mode}, on_conflict="tg_id")
                .execute()
            )
            return True
        except Exception as e:
            print(f"[Supabase] Ошибка при set_mode tg_id={tg_id}, mode={mode}: {e}")
            return False

    # ==========================
    # Внутренние методы (диалог)
    # ==========================

    def _handle_check_existing(self, bot: telebot.TeleBot, message):
        tg_id = message.from_user.id
        chat_id = message.chat.id
        text = (message.text or "").strip().lower()

        state = self.state.get(tg_id)
        if not state or state.get("mode") != "check_existing":
            return

        if text in ("да", "актуально", "всё актуально", "все актуально"):
            self.set_mode(tg_id, 1)
            bot.send_message(chat_id, "Отлично, будем использовать уже сохранённые данные НКО ✅")
            self.state.pop(tg_id, None)
            self._show_main_menu(bot, chat_id)
            return

        if text in ("обновить", "изменить", "редактировать", "перезаписать"):
            bot.send_message(
                chat_id,
                "Хорошо, давайте обновим данные.\n"
                "Вы можете в любой момент отправить /cancel, чтобы отменить регистрацию."
            )

            self.state[tg_id] = {
                "mode": "registration",
                "step": 0,
                "data": {},
                "confirming": False,
                "edit_index": None,
            }

            self._ask_next_question(bot, chat_id, tg_id)
            return

        msg = bot.send_message(
            chat_id,
            "Пожалуйста, ответьте «да», если данные актуальны, или «обновить», чтобы пройти регистрацию заново."
        )
        bot.register_next_step_handler(msg, lambda m: self._handle_check_existing(bot, m))

    def _handle_no_data_choice(self, bot: telebot.TeleBot, message):
        """
        Обработка ответа на предложение:
        «регистрация» или «обезличенно»
        из метода get_nko_data.
        """
        tg_id = message.from_user.id
        chat_id = message.chat.id
        text = (message.text or "").strip().lower()

        if text.startswith("рег"):
            bot.send_message(
                chat_id,
                "Запускаем регистрацию НКО.\n"
                "Вы можете в любой момент отправить /cancel, чтобы отменить регистрацию."
            )
            self.state[tg_id] = {
                "mode": "registration",
                "step": 0,
                "data": {},
                "confirming": False,
                "edit_index": None,
            }
            self._ask_next_question(bot, chat_id, tg_id)

        else:
            bot.send_message(chat_id, "Ок, продолжим в обезличенном режиме без данных НКО.")

    def _ask_next_question(self, bot: telebot.TeleBot, chat_id: int, tg_id: int):
        """
        Задаём следующий вопрос из списка QUESTIONS.
        """
        state = self.state.get(tg_id)
        if not state:
            return

        step = state.get("step", 0)
        if step < 0 or step >= len(self.QUESTIONS):
            return

        key, question = self.QUESTIONS[step]
        text = f"{step + 1}. {question}\n\n(Для отмены регистрации отправьте /cancel)"
        msg = bot.send_message(chat_id, text)
        bot.register_next_step_handler(msg, lambda m: self._handle_registration_answer(bot, m))

    def _handle_registration_answer(self, bot: telebot.TeleBot, message):
        tg_id = message.from_user.id
        chat_id = message.chat.id
        text_raw = message.text or ""
        text = text_raw.strip()

        state = self.state.get(tg_id)
        if not state or state.get("mode") != "registration":
            return

        # --- Обработка отмены регистрации ---
        if text.startswith("/cancel"):
            bot.send_message(chat_id, "Регистрация НКО отменена. Вы можете пройти её позже, когда будет удобно.")
            self.state.pop(tg_id, None)
            self._show_main_menu(bot, chat_id)
            return

        if state.get("confirming", False):
            lower = text.lower()

            if lower.startswith("исправить"):
                parts = lower.split()
                if len(parts) == 2 and parts[1].isdigit():
                    num = int(parts[1])
                    idx = num - 1
                    if 0 <= idx < len(self.QUESTIONS):
                        state["confirming"] = False
                        state["edit_index"] = idx
                        state["step"] = idx

                        key, question = self.QUESTIONS[idx]
                        msg_text = (
                            f"Окей, исправим пункт {num}.\n"
                            f"{num}. {question}\n\n"
                            "(Для отмены регистрации отправьте /cancel)"
                        )
                        msg = bot.send_message(chat_id, msg_text)
                        bot.register_next_step_handler(msg, lambda m: self._handle_registration_answer(bot, m))
                        return

                msg = bot.send_message(
                    chat_id,
                    "Пожалуйста, укажите номер вопроса в формате «исправить 3»."
                )
                bot.register_next_step_handler(msg, lambda m: self._handle_registration_answer(bot, m))
                return

            if lower in ("да", "верно", "всё верно", "все верно", "ок", "okay", "ага"):
                ok = self._upsert_user(tg_id, state["data"])
                if ok:
                    bot.send_message(chat_id, "✅ Регистрация НКО успешно завершена. Данные сохранены.")
                else:
                    bot.send_message(chat_id, "⚠️ Произошла ошибка при сохранении данных. Попробуйте позже.")
                self._show_main_menu(bot, chat_id)
                self.state.pop(tg_id, None)
                return

            msg = bot.send_message(
                chat_id,
                "Если всё верно — напишите «да».\n"
                "Если хотите что-то изменить — напишите, например, «исправить 2».\n"
                "Для отмены регистрации отправьте /cancel."
            )
            bot.register_next_step_handler(msg, lambda m: self._handle_registration_answer(bot, m))
            return

        # --- Обычный ответ на вопрос регистрации (не этап подтверждения) ---

        step = state.get("step", 0)

        edit_index = state.get("edit_index")
        if edit_index is not None and edit_index == step:
            key, _ = self.QUESTIONS[edit_index]
            state["data"][key] = text

            state["edit_index"] = None

            self._send_summary_and_confirm(bot, chat_id, tg_id)
            return

        if 0 <= step < len(self.QUESTIONS):
            key, _ = self.QUESTIONS[step]
            state["data"][key] = text
            state["step"] = step + 1

        if state["step"] < len(self.QUESTIONS):
            self._ask_next_question(bot, chat_id, tg_id)
        else:
            self._send_summary_and_confirm(bot, chat_id, tg_id)

    def _send_summary_and_confirm(self, bot: telebot.TeleBot, chat_id: int, tg_id: int):
        """
        Показываем пользователю все введённые данные и просим подтвердить
        или исправить конкретный пункт.
        """
        state = self.state.get(tg_id)
        if not state:
            return

        state["confirming"] = True

        summary_lines = ["Проверьте, пожалуйста, ваши ответы:\n"]
        for idx, (key, question) in enumerate(self.QUESTIONS, start=1):
            val = state["data"].get(key, "—")
            summary_lines.append(f"{idx}. {question}:\n{val}\n")

        instructions_text = (
            "Если всё верно — напишите «да».\n"
            f"Если хотите изменить какой-то ответ — напишите: «исправить N», где N — номер вопроса (1–{len(self.QUESTIONS)}).\n"
            "Для отмены регистрации отправьте /cancel."
        )

        self._send_long_message(bot, chat_id, summary_lines)

        msg = self._safe_send_message(bot, chat_id, instructions_text)
        if msg is not None:
            bot.register_next_step_handler(msg, lambda m: self._handle_registration_answer(bot, m))

nko_auth_service = NKOAuthService(SUPABASE_URL, SUPABASE_KEY, SUPABASE_TABLE)

