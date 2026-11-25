"""Hata vermeyen HTTP katmanı: yalnızca standart kütüphane, yeniden deneme + geri çekilme.

Hiçbir fonksiyon istisna fırlatmaz; başarısızlıkta None döner.
"""
from __future__ import annotations

import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "OutdoorEventsPipeline/1.0 (GitHub Actions; open data aggregator)"
MAX_BYTES = 20 * 1024 * 1024
_SECRET_RX = re.compile(r"(apikey|api_key|key|token)=[^&\s]+", re.IGNORECASE)


def redact(text: str) -> str:
    return _SECRET_RX.sub(r"\1=***", str(text))


def log(msg: str) -> None:
    text = redact(msg)
    if len(text) > 220:
        text = text[:220] + "…"
    print(text, file=sys.stderr, flush=True)


def fetch_text(url: str, params: dict | None = None, headers: dict | None = None,
               retries: int = 3, timeout: int = 30, pause: float = 0.0) -> str | None:
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    hdrs = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    for attempt in range(retries):
        try:
            if pause:
                time.sleep(pause)
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read(MAX_BYTES)
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 429 or 500 <= e.code < 600:
                wait = 2 ** (attempt + 1)
                try:
                    wait = min(int(e.headers.get("Retry-After", wait)), 60)
                except (TypeError, ValueError):
                    pass
                log(f"HTTP {e.code} (deneme {attempt + 1}/{retries}): {url}")
                time.sleep(wait)
                continue
            log(f"HTTP {e.code}: {url}")
            return None
        except (urllib.error.URLError, TimeoutError, ssl.SSLError, ConnectionError, OSError, ValueError) as e:
            log(f"Ağ hatası (deneme {attempt + 1}/{retries}): {url} -> {type(e).__name__}")
            time.sleep(2 ** (attempt + 1))
        except Exception as e:  # beklenmeyen: yine de çökertme
            log(f"Beklenmeyen HTTP hatası: {url} -> {type(e).__name__}")
            return None
    return None


def fetch_json(url: str, **kw):
    text = fetch_text(url, **kw)
    if text is None:
        return None
    try:
        return json.loads(text)
    except (ValueError, RecursionError):
        log(f"Geçersiz JSON: {url}")
        return None
