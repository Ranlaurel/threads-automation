"""Генератор тредов. Раз в день берёт THREADS_PER_DAY неиспользованных хуков
и разворачивает каждый в тред (7-9 постов: якорь, ставки, пункты, сборка,
CTA), по правилам из threads-viral. Хуки помечаются использованными.

Запуск: python thread_generator.py
"""
import config
import db
import llm
import textutils


def _load(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _build_prompt(hook_text: str, hook_category: str, tov: str) -> str:
    return f"""Разверни хук ниже в тред для Threads: якорный пост + reply-цепочка.

Хук ({hook_category}): {hook_text}

Структура (7-9 постов):
1. Якорь. Хук + обещание. Вся суть интриги здесь.
2. Ставки. Почему это важно сейчас, что теряет тот, кто игнорирует.
3-N. Пункты. Одна мысль = один пост. Конкретика: механика, пример, ориентир.
N+1. Сборка. Принцип, который объединяет пункты.
N+2. CTA. Один мягкий призыв (вопрос по содержанию, приглашение написать
     в комментарии свой опыт, без «продайте», «купите», «пишите в директ
     слово Х», без прямых команд лайкать/репостить).

Требования к каждому посту:
- Длина 280-480 знаков (жёсткий лимит 500).
- Первая строка каждого поста - мини-хук, есть мостик в следующий пост.
- Без эмодзи, хэштегов, длинного тире (только запятая/точка/двоеточие).
- Без «не X, а Y», без цепочек отрицаний, без канцелярита («таким образом»,
  «более того», «давайте разберёмся»).
- Без стоп-слов Meta (продать, купить, заработать, доход, лёгкие деньги,
  гарантированный результат).
- НЕ выдумывай точные цифры результатов от первого лица, если это не
  правдоподобное обобщение из ниши (маркетинг/реклама/автоматизации для
  малого-среднего бизнеса).
- Обращение на «вы», спокойный наставнический тон, живая речь.

=== TONE OF VOICE ===
{tov}
=== /TONE OF VOICE ===

Верни ТОЛЬКО валидный JSON-массив строк без markdown-обёртки и пояснений:
["текст поста 1", "текст поста 2", ...]"""


def _generate_thread_posts(hook_text: str, hook_category: str, tov: str):
    prompt = _build_prompt(hook_text, hook_category, tov)
    for attempt in range(2):
        raw = llm.complete(prompt, max_tokens=4000)
        if not raw.strip():
            continue
        try:
            posts = textutils.parse_json_response(raw)
        except Exception as e:  # noqa: BLE001
            print(f"  попытка {attempt + 1}: JSON не распарсился ({e})")
            continue

        posts = [textutils.dedash((p or "").strip()) for p in posts if (p or "").strip()]
        if not (config.THREAD_MIN_POSTS <= len(posts) <= config.THREAD_MAX_POSTS):
            print(f"  попытка {attempt + 1}: {len(posts)} постов, ожидалось 7-9")
            continue

        bad = [(i, textutils.validate_post(p, config.POST_CHAR_LIMIT))
               for i, p in enumerate(posts, 1)]
        bad = [(i, issues) for i, issues in bad if issues]
        if bad:
            for i, issues in bad:
                print(f"  попытка {attempt + 1}: пост {i}: {issues}")
            continue

        return posts
    return None


def generate_daily_threads():
    with db.get_conn() as conn:
        already_today = db.threads_created_today(conn)
        need = config.THREADS_PER_DAY - already_today
        if need <= 0:
            print(f"Уже сгенерировано {already_today} тредов сегодня, хватит")
            return []
        hooks = db.pick_unused_hooks(conn, need)

    if len(hooks) < need:
        print(
            f"Недостаточно хуков в очереди ({len(hooks)} из {need} нужных). "
            f"Запусти hooks_generator.py."
        )

    tov = _load(config.TOV_PATH)
    created = []
    for hook in hooks:
        print(f"Тред по хуку #{hook['id']} [{hook['category']}]: {hook['text'][:60]}...")
        posts = _generate_thread_posts(hook["text"], hook["category"], tov)
        if not posts:
            print(f"  пропускаю хук #{hook['id']}: не удалось сгенерить валидный тред")
            continue
        with db.get_conn() as conn:
            thread_id = db.save_thread(conn, hook["id"], posts)
            db.mark_hook_used(conn, hook["id"])
        print(f"  тред #{thread_id} сохранён, {len(posts)} постов")
        created.append(thread_id)

    return created


if __name__ == "__main__":
    db.init_db()
    generate_daily_threads()
