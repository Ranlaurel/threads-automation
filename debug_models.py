"""Печатает список моделей, доступных текущему LLM_API_KEY/LLM_BASE_URL.
Запуск: .venv/bin/python debug_models.py
"""
import llm as llm_module

client = llm_module.client()
models = client.models.list()
ids = sorted(m.id for m in models.data)
print(f"Доступно моделей: {len(ids)}")
for i in ids:
    print(" ", i)
