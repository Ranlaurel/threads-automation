"""Постер: публикует один тред (якорь + reply-цепочка) в Threads через
Playwright с сохранённой сессией (storage_state.json из login_once.py).

Threads не даёт официального API под этот сценарий, а разметка меняется без
предупреждения — селекторы ниже best-effort, проверяй перед боевым запуском.

По умолчанию всегда headless (на сервере обычно нет X-дисплея). Если нужно
увидеть окно браузера вживую (только на машине с экраном, для отладки
селекторов), запускай с HEADED=1:

    HEADED=1 PWDEBUG=1 python poster.py --dry-run

Логика поста:
- Открыть Threads, кликнуть "Новый тред" (композер).
- Ввести текст якоря посимвольно с рандомной задержкой (человекоподобно).
- Опубликовать.
- Открыть свой профиль, найти только что опубликованный якорь, открыть его.
- Для каждого следующего поста: кликнуть "Ответить", ввести текст, опубликовать.
- Между постами - случайная пауза (INTRA_THREAD_DELAY_*).

Запуск (публикует один тред за вызов, для cron):
    python poster.py
    python poster.py --dry-run   # только навигация и поиск полей, без публикации
"""
import json
import os
import random
import sys
import time

from playwright.sync_api import Page, sync_playwright

import config
import db
import proxyutils


def _human_type(page: Page, locator, text: str):
    locator.click()
    for ch in text:
        page.keyboard.type(ch)
        time.sleep(
            random.uniform(
                config.TYPE_CHAR_DELAY_MIN_MS, config.TYPE_CHAR_DELAY_MAX_MS
            )
            / 1000
        )


def _intra_thread_pause():
    time.sleep(
        random.uniform(
            config.INTRA_THREAD_DELAY_MIN_SEC, config.INTRA_THREAD_DELAY_MAX_SEC
        )
    )


def _dialog_scope(page: Page):
    """Модалка "New Thread" почти наверняка имеет role="dialog". Если она
    открыта - все дальнейшие поиски (поле, кнопка Post) должны идти внутри
    неё, иначе легко попасть в одноимённый, но неактивный элемент фоновой
    домашней ленты (там тоже есть своё пустое поле "What's new?" и своя
    кнопка "Post")."""
    dialog = page.locator("div[role='dialog']")
    try:
        if dialog.count() > 0:
            return dialog.last
    except Exception:  # noqa: BLE001
        pass
    return page


def _find_composer_field(scope):
    """Best-effort поиск поля ввода текста нового треда.
    ПРОВЕРЬ через PWDEBUG=1 перед боевым запуском - вёрстка Threads меняется."""
    candidates = [
        ("role What's new?", scope.get_by_role("textbox", name="What's new?")),
        ("role Начните тред...", scope.get_by_role("textbox", name="Начните тред...")),
        ("role Start a thread...", scope.get_by_role("textbox", name="Start a thread...")),
        ("aria-label What's new?", scope.locator("[aria-label=\"What's new?\"]")),
        ("placeholder What's new?", scope.get_by_placeholder("What's new?")),
        ("fallback: первый видимый contenteditable в области",
         scope.locator("div[contenteditable='true']:visible").first),
    ]
    for label, c in candidates:
        try:
            if c.count() > 0:
                print(f"  композер найден по стратегии: {label}")
                return c
        except Exception:  # noqa: BLE001
            continue
    return None


def _find_reply_field(scope):
    candidates = [
        scope.get_by_role("textbox", name="Ответить..."),
        scope.get_by_role("textbox", name="Reply..."),
        scope.locator("div[contenteditable='true']:visible").last,
    ]
    for c in candidates:
        try:
            if c.count() > 0:
                return c
        except Exception:  # noqa: BLE001
            continue
    return None


def _click_post_button(scope):
    for name in ("Опубликовать", "Post", "Отправить"):
        btn = scope.get_by_role("button", name=name)
        try:
            if btn.count() > 0:
                btn.first.click()
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def post_thread(posts: list, dry_run: bool = False) -> bool:
    # По умолчанию всегда headless (сервер без X-дисплея). Headed-режим —
    # только если явно попросили через HEADED=1 (для локальной отладки
    # с PWDEBUG=1, где есть настоящий экран).
    headless = os.getenv("HEADED") != "1"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, proxy=proxyutils.playwright_proxy())
        context = browser.new_context(storage_state=config.STORAGE_STATE_PATH)
        page = context.new_page()
        try:
            return _run_post_thread(page, posts, dry_run)
        except Exception:
            page.screenshot(path="error_screenshot.png", full_page=True)
            print("Ошибка во время постинга, скриншот сохранён: error_screenshot.png")
            raise
        finally:
            browser.close()


def _run_post_thread(page: Page, posts: list, dry_run: bool) -> bool:
    page.goto(config.THREADS_BASE_URL)
    page.wait_for_timeout(2000)

    # ── Якорный пост ────────────────────────────────────────────
    new_thread_btn = page.get_by_role("button", name="Создать")
    if new_thread_btn.count() == 0:
        new_thread_btn = page.get_by_role("button", name="Create")
    if new_thread_btn.count() > 0:
        new_thread_btn.first.click()
        page.wait_for_timeout(1000)

    scope = _dialog_scope(page)
    composer = _find_composer_field(scope)
    if composer is None:
        print("Не нашёл поле композера. Прогони PWDEBUG=1 python poster.py --dry-run")
        return False

    _human_type(page, composer, posts[0])
    # Ввод текста мог открыть модалку "New Thread" (если её не было раньше) -
    # пересчитываем область поиска после набора текста.
    scope = _dialog_scope(page)

    if dry_run:
        print("[dry-run] Якорь набран, публикацию и reply-цепочку пропускаю.")
        print(f"[dry-run] Всего постов в треде: {len(posts)}")
        shot_path = "dry_run_screenshot.png"
        page.screenshot(path=shot_path, full_page=True)
        print(f"[dry-run] Скриншот сохранён: {shot_path}")
        page.wait_for_timeout(2000)
        return True

    if not _click_post_button(scope):
        print("Не нашёл кнопку публикации якоря.")
        return False

    page.wait_for_timeout(3000)

    # ── Reply-цепочка ───────────────────────────────────────────
    for i, post_text in enumerate(posts[1:], start=2):
        _intra_thread_pause()
        scope = _dialog_scope(page)
        reply_field = _find_reply_field(scope)
        if reply_field is None:
            print(f"Не нашёл поле ответа для поста {i}. Останавливаюсь на этом посте.")
            return False
        _human_type(page, reply_field, post_text)
        scope = _dialog_scope(page)
        if not _click_post_button(scope):
            print(f"Не нашёл кнопку публикации для поста {i}.")
            return False
        page.wait_for_timeout(2000)

    return True


def main():
    dry_run = "--dry-run" in sys.argv

    with db.get_conn() as conn:
        posted_today = db.posted_today(conn)
        if posted_today >= config.DAILY_POST_LIMIT and not dry_run:
            print(f"Лимит {config.DAILY_POST_LIMIT} тредов в день уже достигнут ({posted_today})")
            return
        thread = db.next_queued_thread(conn)

    if not thread:
        print("Очередь тредов пуста. Запусти thread_generator.py")
        return

    posts = json.loads(thread["posts_json"])
    print(f"Публикую тред #{thread['id']} ({len(posts)} постов){' [dry-run]' if dry_run else ''}")

    ok = post_thread(posts, dry_run=dry_run)

    if dry_run:
        return

    with db.get_conn() as conn:
        if ok:
            db.mark_thread_posted(conn, thread["id"])
            print(f"Тред #{thread['id']} опубликован")
        else:
            db.set_thread_status(conn, thread["id"], "failed", error="poster: см. логи")
            print(f"Тред #{thread['id']} НЕ опубликован, статус -> failed")


if __name__ == "__main__":
    db.init_db()
    main()
