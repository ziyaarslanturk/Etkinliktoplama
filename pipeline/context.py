from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import date

from . import config


class SkipSource(Exception):
    """Kaynak bilinçli olarak atlanır (ör. API anahtarı yok)."""


@dataclass
class Context:
    today: date = field(default_factory=config.today_utc)
    started: float = field(default_factory=time.monotonic)
    env: dict = field(default_factory=lambda: dict(os.environ))

    def time_left(self) -> float:
        return config.TIME_BUDGET_SECONDS - (time.monotonic() - self.started)

    def expired(self) -> bool:
        return self.time_left() <= 0

    def secret(self, name: str) -> str | None:
        v = (self.env.get(name) or "").strip()
        return v or None

    def sources_config(self) -> dict:
        try:
            with open(config.SOURCES_CONFIG, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}
