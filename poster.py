"""Постер: публикует один тред в Threads через Playwright с сохранённой
сессией (storage_state.json из login_once.py).

Threads не даёт официального API под этот сценарий, а разметка меняется без
предупреждения — селекторы ниже best-effort, проверяй перед боевым запуском.

По умолчанию всегда headless (на сервере обычно нет X-дисплея). Если нужно
увидеть окно браузера вживую (только на машине с экраном, для отладки
селекторов), запускай с HEADED=1:

    HEADED=1 PWDEBUG=1 python poster.py --dry-run

Логика поста (важно: Threads строит тред ВНУТРИ ОДНОЙ модалки композера,
кнопкой "Add to thread" добавляются следующие сегменты, и публикуется всё
одним кликом "Post" в конце - это не последовательность отдельных постов
с ручным reply):
- Открыть Threads, кликнуть "Новый тред" (композер).
- Ввести текст первого сегмента посимвольно с рандомной задержкой.
- Для каждого следующего поста: кликнуть "Add to thread" (добавляет пустой
  сегмент в ТОЙ ЖЕ модалке), ввести текст.
- Опубликовать весь тред одним кликом "Post".
- Между сегментами - случайная пауза (INTRA_THREAD_DELAY_*).

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


def _find_add_to_thread(scope):
    """Строка "Add to thread" под уже заполненным сегментом - клик по ней
    добавляет следующий пустой сегмент ВНУТРИ той же модалки (не открывает
    новое окно). Именно так Threads строит тред из нескольких постов:
    один композер, несколько сегментов, один Post в конце."""
    candidates = [
        scope.get_by_role("button", name="Add to thread"),
        scope.get_by_text("Add to thread", exact=False),
        scope.get_by_text("Добавить в тред", exact=False),
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

    # ── Открыть композер явным кликом по пункту меню, НЕ по инлайн-полю
    # "What's new?" на самой ленте ──────────────────────────────────
    # Клик по инлайн-полю дал плавающий баг: он то открывает модалку и
    # переносит туда фокус, то оставляет фоновое поле "живым" и видимым,
    # и следующий клик по нему (например, из-за неточного скоупинга)
    # открывает ВТОРУЮ модалку поверх первой - именно так реальный текст
    # оказывался в фоновой модалке, а финальный Post жал по пустой передней.
    # Явный клик по "New thread" в сайдбаре открывает модалку ровно один раз.
    opened = False
    for name in ("New thread", "Создать"):
        btn = page.get_by_role("link", name=name)
        if btn.count() == 0:
            btn = page.get_by_role("button", name=name)
        try:
            if btn.count() > 0:
                btn.first.click()
                opened = True
                break
        except Exception:  # noqa: BLE001
            continue

    if not opened:
        print("Не нашёл пункт 'New thread' в сайдбаре. Прогони HEADED=1 PWDEBUG=1 python poster.py --dry-run")
        return False

    page.wait_for_timeout(1000)
    dialog_count = page.locator("div[role='dialog']").count()
    print(f"  открыто модалок после клика 'New thread': {dialog_count}")
    if not dry_run:
        page.screenshot(path="debug_0_modal_opened.png", full_page=True)
    scope = _dialog_scope(page)
    composer = _find_composer_field(scope)
    if composer is None:
        print("Не нашёл поле композера внутри модалки. Прогони HEADED=1 PWDEBUG=1 python poster.py --dry-run")
        return False

    _human_type(page, composer, posts[0])
    scope = _dialog_scope(page)

    if dry_run:
        print("[dry-run] Якорь набран, публикацию пропускаю.")
        print(f"[dry-run] Всего сегментов в треде: {len(posts)}")
        shot_path = "dry_run_screenshot.png"
        page.screenshot(path=shot_path, full_page=True)
        print(f"[dry-run] Скриншот сохранён: {shot_path}")
        page.wait_for_timeout(2000)
        return True

    # ── Добавить остальные сегменты кнопкой "Add to thread" ────────
    for i, post_text in enumerate(posts[1:], start=2):
        print(f"  сегмент {i}/{len(posts)}...")
        _intra_thread_pause()
        add_btn = _find_add_to_thread(scope)
        if add_btn is None:
            print(f"Не нашёл 'Add to thread' для сегмента {i}. Прерываюсь без публикации.")
            page.screenshot(path=f"debug_{i}_no_add_button.png", full_page=True)
            return False
        add_btn.first.click()
        page.wait_for_timeout(500)

        scope = _dialog_scope(page)
        seg_field = scope.locator("div[contenteditable='true']:visible").last
        if seg_field.count() == 0:
            print(f"Не нашёл поле для сегмента {i} после клика 'Add to thread'.")
            page.screenshot(path=f"debug_{i}_no_field.png", full_page=True)
            return False

        _human_type(page, seg_field, post_text)
        scope = _dialog_scope(page)

    # ── Публикация всего треда одним кликом ────────────────────────
    page.screenshot(path="debug_before_final_post.png", full_page=True)
    if not _click_post_button(scope):
        print("Не нашёл финальную кнопку Post.")
        return False

    page.wait_for_timeout(4000)
    page.screenshot(path="debug_after_final_post.png", full_page=True)
    print(f"  URL после публикации: {page.url}")

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
