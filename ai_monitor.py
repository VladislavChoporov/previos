import asyncio
import logging
import os
import requests
import time
from config import CONFIG, NEWS_API_KEY

logger = logging.getLogger("ai_monitor")
API_KEY = os.getenv("OPENAI_API_KEY")

async def monitor_logs_and_collect_news():
    if not os.path.exists("trades.log"):
        with open("trades.log", "w", encoding="utf-8") as f:
            f.write("")
    while True:
        try:
            with open("trades.log", "r", encoding="utf-8") as f:
                logs = f.read()
            if len(logs) >= 1000 and "ERROR" in logs[-1000:]:
                recommendation = await get_ai_recommendation(logs)
                logger.info(f"AI Recommendation: {recommendation}")
            news = await get_market_news()
            analytics = f"Найдено новостей: {len(news)}. Последняя новость: {news[0] if news else 'Нет новостей'}"
            logger.info(analytics)
        except Exception as e:
            logger.error(f"Ошибка мониторинга: {e}")
        await asyncio.sleep(300)

async def get_ai_recommendation(logs: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {
                "role": "user",
                "content": f"Проанализируй следующий лог и дай рекомендации для улучшения торговой системы:\n{logs}"
            }
        ],
        "max_tokens": 150
    }
    retries = 3
    for attempt in range(retries):
        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                logger.warning(f"Получен 429: Too Many Requests. Ожидание {retry_after} сек. (Попытка {attempt+1}/{retries})")
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            result = response.json()
            recommendation = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            return recommendation
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ошибка API ({attempt+1}/{retries}): {e}")
            time.sleep(2)
    return "Не удалось получить рекомендации от AI"

async def get_market_news() -> list:
    if not NEWS_API_KEY:
        return ["Тестовая новость: рынок стабилен."]
    retries = 3
    url = f"https://newsapi.org/v2/top-headlines?country=ru&apiKey={NEWS_API_KEY}"
    headers = {}
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            articles = data.get("articles", [])
            headlines = [article["title"] for article in articles]
            return headlines
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ошибка API ({attempt+1}/{retries}): {e}")
            time.sleep(2)
    return []
