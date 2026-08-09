"""Тонкая обёртка над OpenAI-совместимым клиентом (DeepSeek/OpenAI/...)."""
import httpx
from openai import BadRequestError, OpenAI

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


def _create(c: OpenAI, prompt: str, max_tokens: int, use_max_completion_tokens: bool):
    kwargs = {"max_completion_tokens" if use_max_completion_tokens else "max_tokens": max_tokens}
    return c.chat.completions.create(
        model=config.GEN_MODEL,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )


def complete(prompt: str, max_tokens: int = 4000, attempts: int = 2) -> str:
    """Запрос с повтором: модель иногда возвращает пустой ответ.

    Новые модели (gpt-5.x, o1-family, ...) требуют max_completion_tokens
    вместо max_tokens; DeepSeek и старые OpenAI-модели понимают только
    max_tokens. Пробуем max_tokens, при этой конкретной ошибке переключаемся
    на max_completion_tokens и переиспользуем выбор дальше по функции.
    """
    c = client()
    use_max_completion_tokens = False
    text = ""
    for attempt in range(attempts):
        try:
            resp = _create(c, prompt, max_tokens, use_max_completion_tokens)
        except BadRequestError as e:
            if not use_max_completion_tokens and "max_completion_tokens" in str(e):
                use_max_completion_tokens = True
                resp = _create(c, prompt, max_tokens, use_max_completion_tokens)
            else:
                raise
        text = (resp.choices[0].message.content or "").strip()
        if text:
            return text
        print(f"LLM: пустой ответ, попытка {attempt + 1}")
    return text
