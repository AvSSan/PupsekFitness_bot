from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

from kbju_bot.models import MealEntry, UserSettings
from kbju_bot.parser import ParsedMeal, ParsedSettings


class Storage:
    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)
        if self.database_path.parent != Path("."):
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database_path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self._connection.close()

    def init_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
                height_cm REAL NOT NULL,
                weight_kg REAL NOT NULL,
                target_calories REAL NOT NULL,
                target_protein REAL NOT NULL,
                target_fat REAL NOT NULL,
                target_carbs REAL NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS meal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
                entry_date TEXT NOT NULL,
                meal_name_raw TEXT NOT NULL,
                meal_name_normalized TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                calories REAL NOT NULL,
                protein REAL NOT NULL,
                fat REAL NOT NULL,
                carbs REAL NOT NULL,
                source_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_day_state (
                user_id INTEGER PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
                active_date TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_meal_entries_user_date
                ON meal_entries(user_id, entry_date);
            """
        )
        self._ensure_column("meal_entries", "description", "TEXT NOT NULL DEFAULT ''")
        self._connection.commit()

    def get_active_date(self, user_id: int, default_date: date, now: datetime) -> date:
        row = self._connection.execute(
            "SELECT active_date FROM user_day_state WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is not None:
            return date.fromisoformat(str(row["active_date"]))

        active_date = self._initial_active_date(user_id, default_date)
        self._connection.execute(
            """
            INSERT INTO user_day_state (user_id, active_date, updated_at)
            VALUES (?, ?, ?)
            """,
            (user_id, active_date.isoformat(), to_iso(now)),
        )
        self._connection.commit()
        return active_date

    def advance_active_date(self, user_id: int, default_date: date, now: datetime) -> date:
        current_date = self.get_active_date(user_id, default_date, now)
        next_date = current_date + timedelta(days=1)
        self._connection.execute(
            """
            INSERT INTO user_day_state (user_id, active_date, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                active_date = excluded.active_date,
                updated_at = excluded.updated_at
            """,
            (user_id, next_date.isoformat(), to_iso(now)),
        )
        self._connection.commit()
        return next_date

    def _initial_active_date(self, user_id: int, default_date: date) -> date:
        row = self._connection.execute(
            "SELECT MAX(entry_date) AS latest_entry_date FROM meal_entries WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is not None and row["latest_entry_date"]:
            return date.fromisoformat(str(row["latest_entry_date"]))
        return default_date

    def _ensure_column(self, table_name: str, column_name: str, definition: str) -> None:
        rows = self._connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing_columns = {str(row["name"]) for row in rows}
        if column_name not in existing_columns:
            self._connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def upsert_user(self, telegram_id: int, username: str | None, full_name: str, now: datetime) -> None:
        now_value = to_iso(now)
        self._connection.execute(
            """
            INSERT INTO users (telegram_id, username, full_name, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                last_seen_at = excluded.last_seen_at
            """,
            (telegram_id, username, full_name, now_value, now_value),
        )
        self._connection.commit()

    def upsert_settings(self, user_id: int, settings: ParsedSettings, now: datetime) -> None:
        self._connection.execute(
            """
            INSERT INTO user_settings (
                user_id, height_cm, weight_kg, target_calories, target_protein,
                target_fat, target_carbs, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                height_cm = excluded.height_cm,
                weight_kg = excluded.weight_kg,
                target_calories = excluded.target_calories,
                target_protein = excluded.target_protein,
                target_fat = excluded.target_fat,
                target_carbs = excluded.target_carbs,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                settings.height_cm,
                settings.weight_kg,
                settings.target_calories,
                settings.target_protein,
                settings.target_fat,
                settings.target_carbs,
                to_iso(now),
            ),
        )
        self._connection.commit()

    def get_settings(self, user_id: int) -> UserSettings | None:
        row = self._connection.execute(
            "SELECT * FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return settings_from_row(row) if row else None

    def add_meal_entry(self, user_id: int, entry_date: date, parsed: ParsedMeal, now: datetime) -> int:
        cursor = self._connection.execute(
            """
            INSERT INTO meal_entries (
                user_id, entry_date, meal_name_raw, meal_name_normalized, description, calories,
                protein, fat, carbs, source_text, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                entry_date.isoformat(),
                parsed.meal_name_raw,
                parsed.meal_name_normalized,
                parsed.description,
                parsed.nutrition.calories,
                parsed.nutrition.protein,
                parsed.nutrition.fat,
                parsed.nutrition.carbs,
                parsed.source_text,
                to_iso(now),
                to_iso(now),
            ),
        )
        self._connection.commit()
        return int(cursor.lastrowid)

    def update_meal_entry(self, entry_id: int, user_id: int, parsed: ParsedMeal, now: datetime) -> bool:
        cursor = self._connection.execute(
            """
            UPDATE meal_entries
            SET meal_name_raw = ?,
                meal_name_normalized = ?,
                description = ?,
                calories = ?,
                protein = ?,
                fat = ?,
                carbs = ?,
                source_text = ?,
                updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                parsed.meal_name_raw,
                parsed.meal_name_normalized,
                parsed.description,
                parsed.nutrition.calories,
                parsed.nutrition.protein,
                parsed.nutrition.fat,
                parsed.nutrition.carbs,
                parsed.source_text,
                to_iso(now),
                entry_id,
                user_id,
            ),
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def delete_meal_entry(self, entry_id: int, user_id: int) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM meal_entries WHERE id = ? AND user_id = ?",
            (entry_id, user_id),
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def get_meal_entry(self, entry_id: int, user_id: int) -> MealEntry | None:
        row = self._connection.execute(
            "SELECT * FROM meal_entries WHERE id = ? AND user_id = ?",
            (entry_id, user_id),
        ).fetchone()
        return meal_entry_from_row(row) if row else None

    def list_entries_for_day(self, user_id: int, day: date) -> list[MealEntry]:
        rows = self._connection.execute(
            """
            SELECT * FROM meal_entries
            WHERE user_id = ? AND entry_date = ?
            ORDER BY created_at, id
            """,
            (user_id, day.isoformat()),
        ).fetchall()
        return [meal_entry_from_row(row) for row in rows]

    def list_entries_for_period(self, user_id: int, start_date: date | None, end_date: date | None) -> list[MealEntry]:
        query = "SELECT * FROM meal_entries WHERE user_id = ?"
        params: list[object] = [user_id]
        if start_date is not None:
            query += " AND entry_date >= ?"
            params.append(start_date.isoformat())
        if end_date is not None:
            query += " AND entry_date <= ?"
            params.append(end_date.isoformat())
        query += " ORDER BY entry_date, created_at, id"

        rows = self._connection.execute(query, params).fetchall()
        return [meal_entry_from_row(row) for row in rows]

    def list_distinct_dates(self, entries: Iterable[MealEntry]) -> list[date]:
        return sorted({entry.entry_date for entry in entries})


def meal_entry_from_row(row: sqlite3.Row) -> MealEntry:
    return MealEntry(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        entry_date=date.fromisoformat(row["entry_date"]),
        meal_name_raw=str(row["meal_name_raw"]),
        meal_name_normalized=str(row["meal_name_normalized"]),
        description=str(row["description"]),
        calories=float(row["calories"]),
        protein=float(row["protein"]),
        fat=float(row["fat"]),
        carbs=float(row["carbs"]),
        source_text=str(row["source_text"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def settings_from_row(row: sqlite3.Row) -> UserSettings:
    return UserSettings(
        user_id=int(row["user_id"]),
        height_cm=float(row["height_cm"]),
        weight_kg=float(row["weight_kg"]),
        target_calories=float(row["target_calories"]),
        target_protein=float(row["target_protein"]),
        target_fat=float(row["target_fat"]),
        target_carbs=float(row["target_carbs"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def to_iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()
