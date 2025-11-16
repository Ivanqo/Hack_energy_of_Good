import json
import time
import base64
import requests

class FusionBrainAPI:
    def __init__(self, url, api_key, secret_key):
        self.URL = url
        self.AUTH_HEADERS = {
            'X-Key': f'Key {api_key}',
            'X-Secret': f'Secret {secret_key}',
        }

    def get_pipeline(self):
        response = requests.get(self.URL + 'key/api/v1/pipelines', headers=self.AUTH_HEADERS)
        data = response.json()
        return data[0]['id']

    def generate(self, prompt, pipeline_id, style=None, images=1, width=1024, height=1024):
        """
        Генерация изображения по тексту.
        style: str - стиль изображения, например "ANIME", "PAINTING", "REALISTIC"
        width, height: размеры изображения (оптимально кратные 64)
        """
        params = {
            "type": "GENERATE",
            "numImages": images,
            "width": width,
            "height": height,
            "generateParams": {
                "query": f"{prompt}"
            }
        }
        if style:
            params["style"] = style

        data = {
            'pipeline_id': (None, pipeline_id),
            'params': (None, json.dumps(params), 'application/json')
        }

        response = requests.post(self.URL + 'key/api/v1/pipeline/run', headers=self.AUTH_HEADERS, files=data)
        response_data = response.json()
        if "uuid" in response_data:
            return response_data["uuid"]
        else:
            raise RuntimeError(f"[!] Ошибка генерации: {response_data}")

    def check_generation(self, request_id, attempts=10, delay=10):
        """
        Проверка статуса генерации изображения.
        Возвращает список base64 изображений после завершения.
        """
        while attempts > 0:
            response = requests.get(self.URL + f'key/api/v1/pipeline/status/{request_id}', headers=self.AUTH_HEADERS)
            data = response.json()
            status = data.get("status", "")
            if status == "DONE":
                return data['result']['files']
            elif status == "FAIL":
                raise RuntimeError(f"[!] Генерация не удалась: {data.get('errorDescription', 'Нет описания ошибки')}")
            attempts -= 1
            time.sleep(delay)
        raise TimeoutError("[!] Время ожидания генерации истекло")


class GenerateImage:
    def __init__(self, post_text: str, style: str = None):
        self.api = FusionBrainAPI('https://api-key.fusionbrain.ai/', '2CAAB357D6B545FF6875AA07B610FB53', '14D64D6E22AF0019606CB9E46CC0D246')
        self.post_text = post_text
        self.style = style

    def run(self, file_path="out_img.png", width=1024, height=1024):
        print("🔄 Запрос pipeline...")
        pipeline_id = self.api.get_pipeline()

        print("🖼 Генерация изображения...")
        uuid = self.api.generate(
            prompt=self.post_text,
            pipeline_id=pipeline_id,
            style=self.style,
            width=width,
            height=height
        )

        print("⏳ Ожидание результата...")
        files = self.api.check_generation(uuid)

        if not files:
            print("[!] Ошибка: файлы не получены")
            return False

        img_base64 = files[0]
        img_bytes = base64.b64decode(img_base64)

        with open(file_path, "wb") as f:
            f.write(img_bytes)

        print(f"✅ Картинка успешно сохранена как {file_path}")
        return True



