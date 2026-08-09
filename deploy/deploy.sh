#!/usr/bin/env bash
# Разворачивает threads-automation на сервере. Запускать ПРЯМО НА СЕРВЕРЕ
# (по SSH, из-под root или sudo).
#
#   curl -fsSL https://raw.githubusercontent.com/Ranlaurel/threads-automation/main/deploy/deploy.sh | bash
#
# либо после git clone:
#   bash deploy/deploy.sh
set -euo pipefail

REPO_URL="https://github.com/Ranlaurel/threads-automation.git"
PROJECT_DIR="/opt/threads-automation"

echo "== 1/6 Системные зависимости =="
if command -v apt-get >/dev/null; then
    apt-get update -y
    apt-get install -y python3 python3-venv python3-pip git \
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
        libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
        libgbm1 libasound2t64 libasound2 2>/dev/null || \
        apt-get install -y libasound2 2>/dev/null || true
else
    echo "Неизвестный пакетный менеджер, поставь python3/venv/git вручную." >&2
fi

echo "== 2/6 Код проекта =="
if [ -d "$PROJECT_DIR/.git" ]; then
    echo "Репозиторий уже есть в $PROJECT_DIR, обновляю..."
    git -C "$PROJECT_DIR" pull
else
    git clone "$REPO_URL" "$PROJECT_DIR"
fi
cd "$PROJECT_DIR"
mkdir -p logs data

echo "== 3/6 Python venv + зависимости =="
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "== 4/6 Playwright + Chromium =="
.venv/bin/playwright install --with-deps chromium

echo "== 5/6 Конфиг =="
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Создан .env из шаблона. ОБЯЗАТЕЛЬНО заполни LLM_API_KEY:"
    echo "  nano $PROJECT_DIR/.env"
else
    echo ".env уже существует, не трогаю"
fi

echo "== 6/6 БД =="
.venv/bin/python db.py

echo
echo "Готово. Дальше вручную:"
echo "1. nano $PROJECT_DIR/.env               # заполнить LLM_API_KEY"
echo "2. Залогинься в Threads ЛОКАЛЬНО (не на сервере): python login_once.py"
echo "3. Скопируй storage_state.json на сервер:"
echo "   scp storage_state.json root@<сервер>:$PROJECT_DIR/"
echo "4. Проверь селекторы постера (лучше через VNC/X11-форвардинг, poster.py"
echo "   открывает окно браузера в dry-run):"
echo "   cd $PROJECT_DIR && .venv/bin/python poster.py --dry-run"
echo "5. Пропиши cron (поправь пути на .venv/bin/python в deploy/crontab.example):"
echo "   crontab $PROJECT_DIR/deploy/crontab.example"
