import os
import asyncio
from yandex_cloud_ml_sdk import AsyncYCloudML


class YandexImageAPI:
    def __init__(self, folder_id: str | None = None):
        self.folder_id = folder_id or os.getenv("YC_FOLDER_ID")
        if not self.folder_id:
            raise RuntimeError(
                "Не задан folder_id для Yandex Cloud. "
                "Укажи его либо в конструкторе YandexImageAPI, либо через переменную окружения YC_FOLDER_ID."
            )

        self.sdk = AsyncYCloudML(folder_id=self.folder_id)

    async def generate(self, prompt: str, seed: int = 5, width_ratio=1, height_ratio=1):
        model = self.sdk.models.image_generation("yandex-art")

        configured_model = model.configure(
            height_ratio=height_ratio,
            width_ratio=width_ratio,
            seed=seed
        )

        operation = await configured_model.run_deferred(prompt)
        return operation

    async def check_generation(self, operation):
        """
        Дожидается результата и возвращает image_bytes.
        """
        result = await operation
        return result.image_bytes


class GenerateImageYandex:
    def __init__(
        self,
        prompt: str,
        style: str | None = None,
        seed: int = 5,
        folder_id: str | None = None,
    ):
        """
        prompt  — текст для генерации
        style   — стиль (можно просто подмешать в prompt)
        seed    — сид для детерминированности
        folder_id — ID каталога Yandex Cloud (если None, берём из YC_FOLDER_ID)
        """
        self.prompt = prompt
        self.style = style
        self.seed = seed
        self.api = YandexImageAPI(folder_id=folder_id)

    def run(self, file_path="out_yandex.png", width_ratio=1, height_ratio=1):
        async def _run():
            print("🖼 Генерация изображения в Yandex...")

            full_prompt = self.prompt
            if self.style:
                full_prompt = f"{self.prompt}\nСтиль: {self.style}"

            operation = await self.api.generate(
                prompt=full_prompt,
                seed=self.seed,
                width_ratio=width_ratio,
                height_ratio=height_ratio,
            )

            print("⏳ Ожидание результата...")

            img_bytes = await self.api.check_generation(operation)

            with open(file_path, "wb") as f:
                f.write(img_bytes)

            print(f"✅ Картинка сохранена как {file_path}")
            return True

        return asyncio.run(_run())
