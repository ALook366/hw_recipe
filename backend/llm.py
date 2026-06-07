"""OpenRouter API клиент с автоматическим переключением между моделями"""

import os
import time
import asyncio
import httpx
from typing import Optional, Dict, List, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class OpenRouterClient:
    """Клиент для работы с OpenRouter API с автоматическим выбором моделей"""

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.models_url = "https://openrouter.ai/api/v1/models"
        self.site_url = os.getenv("OPENROUTER_SITE_URL", "http://localhost:8000")
        self.app_name = os.getenv("OPENROUTER_APP_NAME", "ShoppingListAPI")
        self.mock_mode = os.getenv("MOCK_MODE", "false").lower() == "true"

        self.available_models: List[Dict] = []
        self.failed_models: Dict[str, float] = {}
        self.model_rate_limits: Dict[str, List[float]] = {}

    async def _fetch_models(self) -> List[Dict]:
        """Загружает список моделей из OpenRouter и фильтрует по поддерживаемым типам"""
        SKIP_KEYWORDS = [
            "safety", "content-safety",
            "image", "vision", "multimodal", "omni", "-vl-", "-vl:",
        ]
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                response = await client.get(self.models_url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    models = [
                        {"name": m["id"], "display": m.get("name", m["id"])}
                        for m in data.get("data", [])
                        if ":free" in m.get("id", "")
                        and not any(k in m.get("id", "").lower() for k in SKIP_KEYWORDS)
                        and not any(k in m.get("name", "").lower() for k in SKIP_KEYWORDS)
                    ]
                    return models
        except Exception:
            pass
        return []

    async def initialize(self):
        """Инициализация: загрузка доступных моделей"""
        if self.mock_mode or not self.api_key or self.api_key == "your_api_key_here":
            return

        self.available_models = await self._fetch_models()
        if self.available_models:
            print(f"Загружено {len(self.available_models)} бесплатных моделей из OpenRouter")
        else:
            print("Не удалось загрузить модели из OpenRouter, будет использован пустой пул")

    def _is_model_available(self, model_name: str) -> bool:
        """Проверяет доступность модели"""
        if model_name in self.failed_models:
            if time.time() - self.failed_models[model_name] < 60:
                return False
            del self.failed_models[model_name]

        if model_name in self.model_rate_limits:
            now = time.time()
            self.model_rate_limits[model_name] = [
                ts for ts in self.model_rate_limits[model_name]
                if now - ts < 60
            ]

        return True

    def _mark_model_failed(self, model_name: str):
        """Отмечает модель как временно недоступную"""
        self.failed_models[model_name] = time.time()

    def _mark_model_request(self, model_name: str):
        """Отмечает запрос к модели для rate limiting"""
        if model_name not in self.model_rate_limits:
            self.model_rate_limits[model_name] = []
        self.model_rate_limits[model_name].append(time.time())

    async def _try_model(self, model: Dict, prompt: str, timeout: int = 30) -> Optional[str]:
        async with httpx.AsyncClient(timeout=timeout) as client:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": self.site_url,
                "X-Title": self.app_name,
                "User-Agent": "ShoppingListApp/1.0"
            }
            payload = {
                "model": model["name"],
                "messages": [
                    {"role": "system", "content": "Ты — помощник для составления списка покупок. Отвечай только по делу, каждый пункт с новой строки. Без лишних пояснений."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1000,
                "top_p": 0.9
            }
            try:
                response = await client.post(self.base_url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    if not data.get("choices"):
                        return None
                    content = data["choices"][0].get("message", {}).get("content", "").strip()
                    if content and len(content) > 10:
                        self._mark_model_request(model["name"])
                        return content
                self._mark_model_failed(model["name"])
                return None
            except Exception:
                self._mark_model_failed(model["name"])
                return None

            except httpx.TimeoutException:
                self._mark_model_failed(model["name"])
                return None
            except httpx.ConnectError:
                self._mark_model_failed(model["name"])
                return None
            except Exception:
                self._mark_model_failed(model["name"])
                return None

    def _get_available_models(self) -> List[Dict]:
        """Возвращает список доступных моделей из кэша"""
        available = []
        for model in self.available_models:
            if self._is_model_available(model["name"]):
                available.append(model)
        return available

    def _build_prompt(self, dish: str, people: str, output_format: str) -> str:
        """Формирует промпт для модели"""
        people_num = int(people) if people.isdigit() else 2

        if output_format == "Список продуктов":
            return f"""Составь список покупок для приготовления блюда: {dish}

Количество персон: {people_num}

Требования:
1. Только список продуктов, каждый на новой строке
2. Указывай количество с учётом количества персон
3. Формат: "Продукт — количество"
4. Без лишних слов и пояснений

Пример:
Молоко — {people_num * 200} мл
Яйца — {people_num * 2} шт
Мука — {people_num * 150} г
Соль — по вкусу
Сахар — {people_num * 20} г

Твой ответ:"""

        else:
            return f"""Составь список покупок и инструкцию приготовления для блюда: {dish}

Количество персон: {people_num}

Формат ответа:
=== СПИСОК ПРОДУКТОВ ===
(каждый продукт с количеством на новой строке, с учётом персон)

=== ШАГИ ПРИГОТОВЛЕНИЯ ===
(ровно 6-8 шагов, каждый на новой строке, коротко и понятно)

Требования:
- Только список и шаги, без лишних слов
- Шаги должны быть чёткими и выполнимыми
- Учитывай количество персон в количестве продуктов

Твой ответ:"""

    def _mock_response(self, dish: str, people: str, output_format: str) -> str:
        """Мок-ответ для тестирования без API ключа"""
        people_num = int(people) if people.isdigit() else 2

        if output_format == "Список продуктов":
            return f"""Список продуктов для {dish} ({people_num} чел.):

🥛 Молоко — {people_num * 200} мл
🥚 Яйца — {people_num * 2} шт
🌾 Мука — {people_num * 150} г
🧂 Соль — 1 ч.л.
🍬 Сахар — {people_num * 20} г
🧈 Масло сливочное — {people_num * 30} г"""

        else:
            return f"""=== СПИСОК ПРОДУКТОВ для {dish} ({people_num} чел.) ===
🥛 Молоко — {people_num * 200} мл
🥚 Яйца — {people_num * 2} шт
🌾 Мука — {people_num * 150} г
🧂 Соль — 1 ч.л.
🍬 Сахар — {people_num * 20} г
🧈 Масло сливочное — {people_num * 30} г

=== ШАГИ ПРИГОТОВЛЕНИЯ ===
1. Достать все ингредиенты из холодильника, дать им нагреться до комнатной температуры
2. В большой миске смешать сухие ингредиенты: муку, соль, сахар
3. В отдельной посуде взбить яйца с молоком до однородности
4. Постепенно влить жидкую смесь в сухую, постоянно помешивая
5. Разогреть сковороду на среднем огне, растопить сливочное масло
6. Вылить тесто на сковороду, жарить 2-3 минуты до золотистой корочки
7. Перевернуть и жарить ещё 1-2 минуты с другой стороны
8. Подавать горячим с мёдом, вареньем или сметаной"""

    async def generate_shopping_list(
            self,
            dish: str,
            people: str,
            output_format: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Генерация списка покупок с автоматическим выбором модели

        Returns:
            Tuple[Optional[str], Optional[str]]: (результат, название_модели_или_ошибка)
        """

        if self.mock_mode or not self.api_key or self.api_key == "your_api_key_here":
            return self._mock_response(dish, people, output_format), "mock_mode"

        if not self.available_models:
            return None, "Список моделей не загружен. Попробуйте позже."

        prompt = self._build_prompt(dish, people, output_format)

        available_models = self._get_available_models()
        if not available_models:
            return None, "Все модели временно недоступны. Попробуйте позже."

        for model in available_models:
            result = await self._try_model(model, prompt)
            if result:
                return result, model["display"]

            self._mark_model_failed(model["name"])

        return None, "Не удалось получить ответ от доступных моделей"
