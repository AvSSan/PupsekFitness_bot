from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    allowed_user_ids: set[int]
    database_path: Path
    timezone: ZoneInfo


def load_config() -> Config:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required")

    raw_ids = os.getenv("ALLOWED_USER_IDS", "").strip()
    allowed_user_ids = parse_allowed_user_ids(raw_ids)
    if not allowed_user_ids:
        raise RuntimeError("ALLOWED_USER_IDS must contain at least one Telegram user id")

    database_path = Path(os.getenv("DATABASE_PATH", "data/kbju.sqlite3"))
    tz_name = os.getenv("TZ", "Asia/Vladivostok")

    try:
        timezone = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as error:
        raise RuntimeError(
            f"Timezone {tz_name!r} is not available. "
            "Install dependencies with `pip install -r requirements.txt`; "
            "on Windows this requires the `tzdata` package."
        ) from error

    return Config(
        bot_token=bot_token,
        allowed_user_ids=allowed_user_ids,
        database_path=database_path,
        timezone=timezone,
    )


def parse_allowed_user_ids(value: str) -> set[int]:
    result: set[int] = set()
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        result.add(int(chunk))
    return result
