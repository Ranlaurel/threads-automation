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


def _find_composer_field(page: Page):
    """Best-effort поиск поля ввода текста нового треда.
    ПРОВЕРЬ через PWDEBUG=1 перед боевым запуском - вёрстка Threads меняется."""
    candidates = [
        page.get_by_role("textbox", name="Начните тред..."),
        page.get_by_role("textbox", name="Start a thread..."),
        page.locator("div[contenteditable='true']").first,
    ]
    for c in candidates:
        try:
            if c.count() > 0:
                return c
        except Exception:  # noqa: BLE001
            continue
    return None


def _find_reply_field(page: Page):
    candidates = [
        page.get_by_role("textbox", name="Ответить..."),
        page.get_by_role("textbox", name="Reply..."),
        page.locator("div[contenteditable='true']").last,
    ]
    for c in candidates:
        try:
            if c.count() > 0:
                return c
        except Exception:  # noqa: BLE001
            continue
    return None


def _click_post_button(page: Page):
    for name in ("Опубликовать", "Post", "Отправить"):
        btn = page.get_by_role("button", name=name)
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
        page.goto(config.THREADS_BASE_URL)
        page.wait_for_timeout(2000)

        # ── Якорный пост ────────────────────────────────────────────
        new_thread_btn = page.get_by_role("button", name="Создать")
        if new_thread_btn.count() == 0:
            new_thread_btn = page.get_by_role("button", name="Create")
        if new_thread_btn.count() > 0:
            new_thread_btn.first.click()
            page.wait_for_timeout(1000)

        composer = _find_composer_field(page)
        if composer is None:
            print("Не нашёл поле композера. Прогони PWDEBUG=1 python poster.py --dry-run")
            browser.close()
            return False

        _human_type(page, composer, posts[0])

        if dry_run:
            print("[dry-run] Якорь набран, публикацию и reply-цепочку пропускаю.")
            print(f"[dry-run] Всего постов в треде: {len(posts)}")
            page.wait_for_timeout(5000)
            browser.close()
            return True

        if not _click_post_button(page):
            print("Не нашёл кнопку публикации якоря.")
            browser.close()
            return False

        page.wait_for_timeout(3000)

        # ── Reply-цепочка ───────────────────────────────────────────
        for i, post_text in enumerate(posts[1:], start=2):
            _intra_thread_pause()
            reply_field = _find_reply_field(page)
            if reply_field is None:
                print(f"Не нашёл поле ответа для поста {i}. Останавливаюсь на этом посте.")
                browser.close()
                return False
            _human_type(page, reply_field, post_text)
            if not _click_post_button(page):
                print(f"Не нашёл кнопку публикации для поста {i}.")
                browser.close()
                return False
            page.wait_for_timeout(2000)

        browser.close()
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
