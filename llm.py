"""Тонкая обёртка над OpenAI-совместимым клиентом (DeepSeek/OpenAI/...)."""
import httpx
from openai import OpenAI

import config


def client() -> OpenAI:
    http_client = None
    if config.LLM_PROXY_URL:
        http_client = httpx.Client(proxy=config.LLM_PROXY_URL)
    return OpenAI(
        api_key=config.LLM_API_KEY,
        base_url=config.LLM_BASE_URL,
        http_client=http_client,
    )


def complete(prompt: str, max_tokens: int = 4000, attempts: int = 2) -> str:
    """Запрос с повтором: модель иногда возвращает пустой ответ."""
    c = client()
    text = ""
    for attempt in range(attempts):
        resp = c.chat.completions.create(
            model=config.GEN_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (resp.choices[0].message.content or "").strip()
        if text:
            return text
        print(f"LLM: пустой ответ, попытка {attempt + 1}")
    return text
