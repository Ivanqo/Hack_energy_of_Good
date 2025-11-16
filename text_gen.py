import g4f
import inspect
import time


MODEL = "gpt-4"


class PostGenerator:
    """
    Класс для генерации Telegram-постов для НКО через g4f
    с автоматическим перебором провайдеров.
    """

    def __init__(self, model: str = MODEL):
        self.model = model

    # ---------- Служебные методы ----------
    def _get_all_providers(self):
        """Получить список всех доступных провайдеров g4f."""
        providers = []
        for name, obj in inspect.getmembers(g4f.Provider):
            if inspect.isclass(obj):
                providers.append(obj)
        return providers

    def _build_user_prompt(self, user_idea: str, topic: str, nko_info: dict = None, style: str = "разговорный"):
        """Формирование user_prompt на основе входных параметров."""

        nko_text = ""
        if nko_info:
            nko_parts = []
            for key, value in nko_info.items():
                if value:
                    nko_parts.append(f"{key}: {value}")
            nko_text = "Информация об НКО:\n" + "\n".join(nko_parts) + "\n"

        prompt = f"""
Ты эксперт по созданию контента для НКО.
Задача: создать готовый текст для поста в Telegram на основе идеи пользователя.

{nko_text}
Идея поста: {user_idea}
Стиль: {style}
Хештег по теме: #{topic.replace(' ', '')}

Требования к тексту:
- Грамотность: без ошибок
- Логичность и структурированность
- Подходит под ограничения Telegram
- Можно добавлять рекомендации по визуалу
- Предлагать варианты заголовков / подзаголовков, если уместно
- Текст должен быть социально значимым, креативным и доброжелательным
"""
        return prompt.strip()

    def _build_system_prompt(self, topic: str):
        """Системный промпт, который определяет стиль модели."""
        return (
            "Ты эксперт в создании контента для НКО. "
            "Пиши тексты креативно, структурированно, без ошибок. "
            "Используй лёгкую разметку, аккуратно добавляй смайлики. "
            "Учитывай ограничения Telegram. "
            f"В конце обязательно добавь хештег #{topic.replace(' ', '')}."
        )

    # ---------- Основной метод ----------
    def generate_post(self, user_idea: str, topic: str, nko_info: dict = None, style: str = "разговорный") -> str:
        """
        Генерация поста с автоматическим перебором провайдеров.
        Возвращает готовый текст поста или ошибку.
        """

        system_prompt = self._build_system_prompt(topic)
        user_prompt = self._build_user_prompt(user_idea, topic, nko_info, style)

        providers = self._get_all_providers()
        print(f"[INFO] Найдено провайдеров: {len(providers)}")

        for provider in providers:
            try:
                print(f"➡ Пробуем провайдера: {provider.__name__}")

                response = g4f.ChatCompletion.create(
                    model=self.model,
                    provider=provider,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )

                if response and response.strip():
                    print(f"✅ Успех: {provider.__name__}")
                    return response.strip()

            except Exception as e:
                print(f"[!] Провайдер {provider.__name__} упал: {e}")
                time.sleep(1)

        return "[!] Не удалось подключиться ни к одному провайдеру. Попробуйте позже."
