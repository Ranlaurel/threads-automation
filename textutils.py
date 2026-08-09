"""Общие утилиты очистки и валидации текста, генерируемого LLM."""
import json
import re

FORBIDDEN_PATTERNS = [
    re.compile(r"(?i)\bне\s+\S+[.,]\s+не\s+\S+"),          # цепочки отрицаний
    re.compile(r"(?i)это не\s.+\.\s*это\s"),                 # «Это не X. Это Y»
    re.compile(r"[—–]"),                                     # длинное/среднее тире
    re.compile(r"(?i)\bтаким образом\b|\bболее того\b|\bпомимо этого\b"),
    re.compile(r"[\U0001F300-\U0001FAFF☀-➿]"),     # эмодзи
    re.compile(r"#\w+"),                                     # хэштеги
]

STOP_WORDS = [
    "продать", "продавать", "купить", "покупать", "заработать", "заработок",
    "лёгкие деньги", "гарантированный результат",
]


def _extract_json_block(text: str) -> str:
    """Вырезает JSON из ответа модели, если она обернула его в текст/бэктики."""
    t = text.strip().strip("`").strip()
    if t.startswith("json"):
        t = t[4:].strip()
    start = min(
        (i for i in (t.find("["), t.find("{")) if i != -1),
        default=-1,
    )
    if start == -1:
        return t
    end = max(t.rfind("]"), t.rfind("}"))
    return t[start:end + 1] if end != -1 else t


def parse_json_response(text: str):
    """Парсит JSON-ответ модели, снисходительно к обёрткам/преамбулам."""
    block = _extract_json_block(text or "")
    return json.loads(block)


def dedash(text: str) -> str:
    text = re.sub(r"\s*[—–]\s*", ", ", text)
    text = re.sub(r",\s*([.!?,:;])", r"\1", text)
    text = re.sub(r"[ \t]+,", ",", text)
    text = re.sub(r"(?m)^\s*,\s*", "", text)
    return text


def validate_post(text: str, char_limit: int = 500) -> list:
    """Возвращает список нарушений (пустой список = пост валиден)."""
    issues = []
    if len(text) > char_limit:
        issues.append(f"длина {len(text)} > {char_limit}")
    for pat in FORBIDDEN_PATTERNS:
        if pat.search(text):
            issues.append(f"запрещённая конструкция: {pat.pattern}")
    low = text.lower()
    for w in STOP_WORDS:
        if w in low:
            issues.append(f"стоп-слово: {w}")
    return issues
