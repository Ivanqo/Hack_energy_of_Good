import g4f
import inspect
import time
from datetime import datetime, timedelta


MODEL = "gpt-4"


class ContentPlanGenerator:
    """
    Генератор контент-плана для НКО через g4f.
    Поддерживает: период, частоту, стиль, данные НКО.
    """

    def __init__(
        self,
        model: str = MODEL,
        nko_name: str | None = None,
        nko_description: str | None = None,
        nko_activity: str | None = None,
        nko_audience: str | None = None,
        tone: str = "разговорный",
    ):
        self.model = model
        self.nko_name = nko_name
        self.nko_description = nko_description
        self.nko_activity = nko_activity
        self.nko_audience = nko_audience
        self.tone = tone

    # ---------------------------------------------------------------------
    #                   СЛУЖЕБНЫЕ МЕТОДЫ
    # ---------------------------------------------------------------------

    def _get_all_providers(self):
        """Получить список всех доступных провайдеров g4f."""
        providers = []
        for name, obj in inspect.getmembers(g4f.Provider):
            if inspect.isclass(obj):
                providers.append(obj)
        return providers

    def _format_nko_info(self):
        """Собрать удобный для LLM текст о НКО."""
        parts = []

        if self.nko_name:
            parts.append(f"Название НКО: {self.nko_name}")
        if self.nko_description:
            parts.append(f"Описание: {self.nko_description}")
        if self.nko_activity:
            parts.append(f"Деятельность: {self.nko_activity}")
        if self.nko_audience:
            parts.append(f"Целевая аудитория: {self.nko_audience}")
        if self.tone:
            parts.append(f"Предпочитаемый стиль: {self.tone}")

        if not parts:
            return "Информация об НКО: отсутствует. Контент-план должен быть универсальным."

        return "Информация об НКО:\n" + "\n".join(parts)

    def _build_system_prompt(self):
        """
        Системный промпт — регулирует манеру генерации.
        """
        return (
            "Ты — профессиональный контент-маркетолог, который создает "
            "структурированные, понятные и полезные контент-планы для социальных сетей НКО. "
            "Пиши строго в удобном для Telegram формате. "
            "Не используй воду, будь конкретным. "
            "Все посты должны быть социально значимыми и полезными."
        )

    def _build_user_prompt(self, start_date: str, end_date: str, frequency: str):
        """
        Формируем user_prompt: ввод от пользователя + данные НКО.
        """

        nko_info = self._format_nko_info()

        return f"""
Создай подробный контент-план для НКО.

{nko_info}

Период: {start_date} — {end_date}
Регулярность публикаций: {frequency}

ТРЕБОВАНИЯ К ФОРМАТУ ОТВЕТА (ОБЯЗАТЕЛЬНО):

1) Структура выдачи:
Дата — Категория поста
• Суть поста (одно предложение)
• Формат (текст / фото / видео)
• Пример заголовка
• Хештег

2) Категории постов должны быть разнообразными:
- истории подопечных / кейсы
- анонсы мероприятий
- отчеты
- просветительский контент
- волонтерские обращения
- соц. проблемы и полезные советы
- благодарности партнерам
- цитаты / мотивационные материалы

3) Учитывай особенности НКО, её стиль, аудиторию и деятельность.

4) Все даты должны входить в указанный период.

Сделай план максимально практичным и удобным для реальной работы SMM-щика.
""".strip()

    # ---------------------------------------------------------------------
    #                  ОСНОВНОЙ МЕТОД ГЕНЕРАЦИИ
    # ---------------------------------------------------------------------

    def generate_content_plan(self, start_date: str, end_date: str, frequency: str) -> str:
        """
        Генерация полного контент-плана.
        Возвращает структурированный текст.
        """

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(start_date, end_date, frequency)

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
                        {"role": "user", "content": user_prompt},
                    ]
                )

                if response and response.strip():
                    print(f"✅ Успех: {provider.__name__}")
                    return response.strip()

            except Exception as e:
                print(f"[!] Провайдер {provider.__name__} упал: {e}")
                time.sleep(1)

        return "[!] Не удалось подключиться ни к одному провайдеру. Попробуйте позже."



"""
ПРИМЕР

generator = ContentPlanGenerator(
    nko_name="Фонд Помощи Животным 'Лапа Рядом'",
    nko_description="Помогаем бездомным животным найти новый дом",
    nko_activity="приюты, лечение, поиск хозяев, волонтерство",
    nko_audience="волонтеры, люди 20–45 лет, любящие животных",
    tone="дружелюбный"
)

plan = generator.generate_content_plan(
    start_date="01.02.2025",
    end_date="14.02.2025",
    frequency="3 раза в неделю"
)

print(plan)

"""