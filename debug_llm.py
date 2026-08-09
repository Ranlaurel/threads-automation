"""Диагностика: печатает сырой ответ LLM-провайдера на простой запрос.
Запуск: .venv/bin/python debug_llm.py
"""
import llm as llm_module
import config

print(f"LLM_BASE_URL={config.LLM_BASE_URL}")
print(f"GEN_MODEL={config.GEN_MODEL}")
print(f"LLM_API_KEY set: {bool(config.LLM_API_KEY)} (len={len(config.LLM_API_KEY)})")
print(f"LLM_PROXY_URL set: {bool(config.LLM_PROXY_URL)}")

client = llm_module.client()
resp = client.chat.completions.create(
    model=config.GEN_MODEL,
    max_tokens=200,
    messages=[{"role": "user", "content": "Скажи одно слово: привет"}],
)
print("=== RAW RESPONSE ===")
print(resp)
print("=== message.content ===")
print(repr(resp.choices[0].message.content))
