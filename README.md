# threads-automation

Автономный пайплайн: генерация хуков → генерация тредов → публикация в
Threads через браузер (Playwright). Работает на твоём сервере через cron,
без ручной модерации.

```
hooks (SQLite)
  <= HOOKS_LOW_WATERMARK (по умолчанию 5) → генерится пачка 100-200 хуков
  ↓
threads (SQLite)
  раз в день → 8 хуков разворачиваются в треды (якорь + reply-цепочка)
  ↓
poster.py (Playwright)
  8 запусков в день с разбросом → публикация одного треда за запуск
  ↓
post_log (SQLite) — что и когда ушло, лимит DAILY_POST_LIMIT
```

## Важно понимать перед запуском

- **Это не официальный API Threads.** Постинг идёт через Playwright с
  сохранённой сессией браузера, "как человек". Meta умеет детектить
  автоматизацию: возможен повторный запрос логина, капча или временное
  ограничение аккаунта. Риск снижен рандомизацией таймингов и посимвольным
  набором текста, но не убран полностью.
- **Селекторы в `poster.py` — best-effort.** У Threads нет официального API
  под этот сценарий, вёрстка меняется без предупреждения. Перед первым боевым
  запуском обязательно прогони:
  ```bash
  PWDEBUG=1 python poster.py --dry-run
  ```
  и сверь, что скрипт реально попадает в поле композера и находит кнопку
  публикации. Если нет — поправь селекторы в `_find_composer_field`,
  `_find_reply_field`, `_click_post_button`.
- **Первый батч хуков стоит проверить глазами.** Модерации нет, но одна
  системная ошибка в промпте размножится на 100-200 хуков сразу.

## Установка на сервере (один шаг)

Подключись по SSH к серверу и выполни:

```bash
curl -fsSL https://raw.githubusercontent.com/Ranlaurel/threads-automation/main/deploy/deploy.sh | bash
```

Скрипт поставит зависимости, склонирует репозиторий в `/opt/threads-automation`,
создаст venv, поставит Playwright/Chromium и инициализирует БД. После него
останется вручную: заполнить `.env`, залогиниться в Threads локально
(`login_once.py`) и прописать cron — скрипт в конце сам подскажет команды.

## Установка вручную

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# заполни LLM_API_KEY (DeepSeek/OpenAI/любой OpenAI-совместимый провайдер)

python db.py  # создаст data/threads.db
```

## Логин в Threads (обязательно локально, не на сервере)

```bash
python login_once.py
```

Откроется окно браузера — залогинься сам (включая 2FA), вернись в терминал и
нажми Enter. Скрипт сохранит сессию в `storage_state.json`. Логин и пароль
скрипт никогда не запрашивает и не хранит.

Скопируй `storage_state.json` на сервер рядом с `poster.py`:

```bash
scp storage_state.json user@server:/opt/threads-automation/
```

Логиниться лучше локально (на машине с браузером и окном), а не прямо с
сервера — так безопаснее с точки зрения детекта автоматизации.

## Ручной прогон пайплайна

```bash
python hooks_generator.py     # генерит пачку, если хуков <= HOOKS_LOW_WATERMARK
python thread_generator.py    # генерит до 8 тредов из свежих хуков
python poster.py --dry-run    # проверка селекторов без публикации (нужен PWDEBUG=1)
python poster.py              # публикует один тред из очереди
```

## Деплой на сервер (cron)

```bash
mkdir -p logs
crontab deploy/crontab.example  # поправь пути внутри файла под свой сервер
```

`hooks_generator.py` запускается каждые 30 минут (дешёвая операция при полной
очереди — реальная генерация случается только когда хуков мало).
`thread_generator.py` — раз в сутки. `poster.py` — 8 раз в день с рандомным
разбросом внутри окна `POSTING_WINDOW_START_HOUR`-`POSTING_WINDOW_END_HOUR`.

## Настройка под свою нишу

Весь контекст (кто говорит, ЦА, боли, стоп-слова, стиль) — в
`prompts/tov.md`. Формулы хуков — в `prompts/hooks_library.md`. Правь оба
файла под свою нишу, промпты в `hooks_generator.py`/`thread_generator.py`
их просто подставляют.

## Структура

- `config.py` — все настраиваемые параметры (лимиты, окна постинга, модель).
- `db.py` — SQLite-схема: `hooks`, `threads`, `post_log`.
- `textutils.py` — очистка ответов LLM, парсинг JSON, валидация постов
  (длина, стоп-слова, запрещённые конструкции).
- `llm.py` — обёртка над OpenAI-совместимым клиентом.
- `hooks_generator.py` — генерация пачки хуков.
- `thread_generator.py` — разворачивание хуков в треды.
- `poster.py` — публикация через Playwright.
- `login_once.py` — разовый ручной логин, сохранение сессии.
- `deploy/crontab.example` — пример расписания.
