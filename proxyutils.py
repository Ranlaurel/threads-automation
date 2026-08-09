"""Разбор BROWSER_PROXY_URL в формат, который ждёт Playwright."""
from urllib.parse import urlparse

import config


def playwright_proxy():
    """http://user:pass@host:port -> {"server", "username", "password"} или None."""
    if not config.BROWSER_PROXY_URL:
        return None
    parsed = urlparse(config.BROWSER_PROXY_URL)
    proxy = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
    if parsed.username:
        proxy["username"] = parsed.username
    if parsed.password:
        proxy["password"] = parsed.password
    return proxy
