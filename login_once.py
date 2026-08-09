"""Разовый ручной логин в Threads. Открывает окно браузера, ты логинишься
сам (включая 2FA), затем скрипт сохраняет сессию в storage_state.json —
дальше poster.py её переиспользует без повторного логина.

ВАЖНО: запускай локально, на машине с браузером/окном, не на headless-сервере.
Логин и пароль скрипт никогда не запрашивает и не хранит — только сохраняет
куки/localStorage уже залогиненной сессии.

Запуск: python login_once.py
"""
from playwright.sync_api import sync_playwright

import config


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"{config.THREADS_BASE_URL}/login")

        print("Залогинься в открывшемся окне браузера (включая 2FA, если есть).")
        input("Когда окажешься в ленте Threads — вернись сюда и нажми Enter... ")

        context.storage_state(path=config.STORAGE_STATE_PATH)
        print(f"Сессия сохранена в {config.STORAGE_STATE_PATH}")
        print("Скопируй этот файл на сервер рядом с poster.py.")

        browser.close()


if __name__ == "__main__":
    main()
