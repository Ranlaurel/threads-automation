"""Диагностика: печатает ответ LLM-провайдера на простой запрос.
Запуск: .venv/bin/python debug_llm.py
"""
import config
import llm

print(f"LLM_BASE_URL={config.LLM_BASE_URL}")
print(f"GEN_MODEL={config.GEN_MODEL}")
print(f"LLM_API_KEY set: {bool(config.LLM_API_KEY)} (len={len(config.LLM_API_KEY)})")
print(f"LLM_PROXY_URL set: {bool(config.LLM_PROXY_URL)}")

text = llm.complete("Скажи одно слово: привет", max_tokens=200, attempts=1)
print("=== ответ модели ===")
print(repr(text))
