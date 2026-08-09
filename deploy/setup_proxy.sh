#!/usr/bin/env bash
# Поднимает простой авторизованный HTTP-прокси (tinyproxy) на этом сервере.
# Запускать ПРЯМО НА ПРОКСИ-СЕРВЕРЕ (не на сервере с ботом).
#
#   curl -fsSL https://raw.githubusercontent.com/Ranlaurel/threads-automation/main/deploy/setup_proxy.sh | bash
#
# После установки скрипт выведет готовую строку LLM_PROXY_URL —
# её нужно вписать в .env на сервере с ботом.
set -euo pipefail

PROXY_PORT="${PROXY_PORT:-8899}"
PROXY_USER="${PROXY_USER:-llmproxy}"
PROXY_PASS="${PROXY_PASS:-$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20)}"

echo "== 1/4 Установка tinyproxy =="
if command -v apt-get >/dev/null; then
    apt-get update -y
    apt-get install -y tinyproxy
else
    echo "Неизвестный пакетный менеджер, поставь tinyproxy вручную." >&2
    exit 1
fi

echo "== 2/4 Конфиг с базовой авторизацией =="
CONF=/etc/tinyproxy/tinyproxy.conf
cp "$CONF" "$CONF.bak.$(date +%s)"

# Слушать на всех интерфейсах на заданном порту.
sed -i "s/^Port .*/Port ${PROXY_PORT}/" "$CONF"

# Basic-auth логин/пароль (tinyproxy: директива BasicAuth).
if grep -q '^BasicAuth' "$CONF"; then
    sed -i "s/^BasicAuth.*/BasicAuth ${PROXY_USER} ${PROXY_PASS}/" "$CONF"
else
    echo "BasicAuth ${PROXY_USER} ${PROXY_PASS}" >> "$CONF"
fi

# Разрешить подключения отовсюду (авторизация закрывает доступ чужим).
if grep -q '^Allow 127.0.0.1' "$CONF"; then
    sed -i "s/^Allow 127.0.0.1/#Allow 127.0.0.1/" "$CONF"
fi

echo "== 3/4 Firewall (если ufw активен) =="
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
    ufw allow "${PROXY_PORT}/tcp"
fi

echo "== 4/4 Запуск =="
systemctl enable tinyproxy
systemctl restart tinyproxy
sleep 1
systemctl status tinyproxy --no-pager | head -5

echo
echo "Готово. Строка для LLM_PROXY_URL (вставить в .env на сервере с ботом):"
echo
SERVER_IP=$(curl -fsS -4 ifconfig.me || hostname -I | awk '{print $1}')
echo "LLM_PROXY_URL=http://${PROXY_USER}:${PROXY_PASS}@${SERVER_IP}:${PROXY_PORT}"
echo
echo "Логин: ${PROXY_USER}"
echo "Пароль: ${PROXY_PASS}"
echo "(сохранены только в выводе выше и в ${CONF} — больше нигде)"
