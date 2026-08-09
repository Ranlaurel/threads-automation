"""Генератор хуков. Пока в очереди >HOOKS_LOW_WATERMARK неиспользованных
хуков — ничего не делает. Как только их <= HOOKS_LOW_WATERMARK, генерит новую
пачку размером [HOOKS_BATCH_MIN, HOOKS_BATCH_MAX] через LLM, по формулам из
prompts/hooks_library.md.

Запуск: python hooks_generator.py [--force N]
"""
import random
import sys

import config
import db
import llm
import textutils


def _load(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _build_prompt(n: int, tov: str, hooks_lib: str) -> str:
    return f"""Ты помогаешь вести Threads-аккаунт эксперта по маркетингу и
ИИ-автоматизациям для малого и среднего бизнеса.

Сгенерируй {n} РАЗНЫХ хуков (первых строк будущих тредов) строго по формулам
из библиотеки ниже. Равномерно распредели по всем 10 категориям (примерно
поровну, допустимо +-20%). Не повторяй тему и заход дважды.

=== БИБЛИОТЕКА ФОРМУЛ ХУКОВ ===
{hooks_lib}
=== /БИБЛИОТЕКА ===

=== TONE OF VOICE ===
{tov}
=== /TONE OF VOICE ===

Верни ТОЛЬКО валидный JSON-массив без markdown-обёртки, без пояснений, вида:
[{{"text": "...", "category": "numbers"}}, {{"text": "...", "category": "pain"}}, ...]

category — один из: numbers, provocation, curiosity, story, pain, authority,
beforeafter, paradox, question, list.
Ровно {n} элементов."""


def generate_batch(n: int) -> int:
    tov = _load(config.TOV_PATH)
    hooks_lib = _load(config.HOOKS_LIBRARY_PATH)
    prompt = _build_prompt(n, tov, hooks_lib)

    raw = llm.complete(prompt, max_tokens=16000)
    if not raw.strip():
        print("Генератор хуков: пустой ответ модели, пропускаю")
        return 0

    try:
        items = textutils.parse_json_response(raw)
    except Exception as e:  # noqa: BLE001
        print(f"Генератор хуков: не удалось распарсить JSON ({e})")
        return 0

    cleaned = []
    for item in items:
        text = textutils.dedash((item.get("text") or "").strip())
        category = (item.get("category") or "").strip() or "list"
        if not text:
            continue
        issues = textutils.validate_post(text, char_limit=200)
        if issues:
            continue
        cleaned.append((text, category))

    if not cleaned:
        print("Генератор хуков: после валидации не осталось валидных хуков")
        return 0

    with db.get_conn() as conn:
        db.insert_hooks(conn, cleaned)

    print(f"Добавлено {len(cleaned)} хуков (запрошено {n})")
    return len(cleaned)


def ensure_hooks():
    with db.get_conn() as conn:
        remaining = db.unused_hooks_count(conn)
    if remaining > config.HOOKS_LOW_WATERMARK:
        print(f"Хуков в очереди: {remaining}, генерация не нужна")
        return
    n = random.randint(config.HOOKS_BATCH_MIN, config.HOOKS_BATCH_MAX)
    print(f"Хуков в очереди: {remaining} (<= {config.HOOKS_LOW_WATERMARK}), генерю {n}")
    generate_batch(n)


if __name__ == "__main__":
    db.init_db()
    if len(sys.argv) > 2 and sys.argv[1] == "--force":
        generate_batch(int(sys.argv[2]))
    else:
        ensure_hooks()
