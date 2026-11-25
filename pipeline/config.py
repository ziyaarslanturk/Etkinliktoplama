"""Yol ve zaman sabitleri."""
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMUNITY_DIR = Path(os.environ.get("COMMUNITY_DIR", ROOT / "community_events"))
SITE_DIR = Path(os.environ.get("SITE_DIR", ROOT / "site"))
SOURCES_CONFIG = Path(os.environ.get("SOURCES_CONFIG", ROOT / "config" / "sources.json"))

# Tüm tarama için üst süre sınırı (saniye). Aşılırsa kalan kaynaklar atlanır.
TIME_BUDGET_SECONDS = int(os.environ.get("TIME_BUDGET_SECONDS", str(30 * 60)))


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
