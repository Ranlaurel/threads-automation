"""Настройки пайплайна. Правь под себя — тут всё, что меняется руками."""
import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM: любой OpenAI-совместимый провайдер (DeepSeek, OpenAI, ...) ────────
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
GEN_MODEL = os.getenv("GEN_MODEL", "deepseek-reasoner")

# ── Очередь хуков ────────────────────────────────────────────────────────
# Как только неиспользованных хуков остаётся <= HOOKS_LOW_WATERMARK,
# генерится новая пачка размером в диапазоне [HOOKS_BATCH_MIN, HOOKS_BATCH_MAX].
HOOKS_LOW_WATERMARK = int(os.getenv("HOOKS_LOW_WATERMARK", "5"))
HOOKS_BATCH_MIN = int(os.getenv("HOOKS_BATCH_MIN", "100"))
HOOKS_BATCH_MAX = int(os.getenv("HOOKS_BATCH_MAX", "200"))

# ── Треды ────────────────────────────────────────────────────────────────
THREADS_PER_DAY = int(os.getenv("THREADS_PER_DAY", "8"))
THREAD_MIN_POSTS = 7
THREAD_MAX_POSTS = 9
POST_CHAR_LIMIT = 500
POST_CHAR_TARGET_MIN = 280
POST_CHAR_TARGET_MAX = 480

# ── Постинг (Playwright) ────────────────────────────────────────────────
STORAGE_STATE_PATH = os.getenv("STORAGE_STATE_PATH", "storage_state.json")
DAILY_POST_LIMIT = THREADS_PER_DAY  # предохранитель: не постить больше N тредов в день

# Окно активности и человекоподобные паузы. poster.py спит случайное время
# перед стартом (в пределах джиттера из cron) и между постами внутри треда.
POSTING_WINDOW_START_HOUR = int(os.getenv("POSTING_WINDOW_START_HOUR", "8"))
POSTING_WINDOW_END_HOUR = int(os.getenv("POSTING_WINDOW_END_HOUR", "22"))
INTRA_THREAD_DELAY_MIN_SEC = 8
INTRA_THREAD_DELAY_MAX_SEC = 45
TYPE_CHAR_DELAY_MIN_MS = 25
TYPE_CHAR_DELAY_MAX_MS = 90

THREADS_BASE_URL = "https://www.threads.net"

DB_PATH = os.getenv("DB_PATH", "data/threads.db")
TOV_PATH = os.getenv("TOV_PATH", "prompts/tov.md")
HOOKS_LIBRARY_PATH = os.getenv("HOOKS_LIBRARY_PATH", "prompts/hooks_library.md")
