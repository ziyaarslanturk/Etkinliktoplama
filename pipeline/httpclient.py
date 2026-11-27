"""
Robust HTTP client for fetching event feeds and web scraping.
Includes custom User-Agent, SSL fallback, and timeout management.
"""

import logging
import urllib.request
import urllib.error
import ssl
import json
from typing import Optional, Dict, Any

logger = logging.getLogger("pipeline.httpclient")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

def fetch_url(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 15) -> Optional[str]:
    """
    Fetches raw text content from given URL with fallback SSL handling.
    """
    req_headers = DEFAULT_HEADERS.copy()
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, headers=req_headers)

    # Context 1: Strict SSL
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        logger.debug(f"Default SSL fetch failed for {url}: {e}")

    # Context 2: Fallback unverified SSL (for municipal/forum servers with self-signed SSL)
    try:
        ctx_unverified = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx_unverified) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None

def fetch_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 15) -> Optional[Any]:
    """
    Fetches and parses JSON from given URL.
    """
    content = fetch_url(url, headers=headers, timeout=timeout)
    if not content:
        return None
    try:
        return json.loads(content)
    except Exception as e:
        logger.warning(f"Failed to parse JSON from {url}: {e}")
        return None
