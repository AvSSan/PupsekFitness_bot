import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from kbju_bot.parser import parse_meal_message, parse_settings_message
from kbju_bot.storage import Storage


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Storage(Path(self.temp_dir.name) / "test.sqlite3")
        self.db.init_schema()
        self.now = datetime(2026, 5, 2, 10, 0, 0)
        self.db.upsert_user(1, "user", "Test User", self.now)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_settings_roundtrip(self):
        settings = parse_settings_message(
            """
            Рост 170
            Вес 65
            К 1800
            Б 120
            Ж 60
            У 190
            """
        )

        self.db.upsert_settings(1, settings, self.now)
        saved = self.db.get_settings(1)

        self.assertEqual(saved.height_cm, 170)
        self.assertEqual(saved.target_carbs, 190)

    def test_meal_crud_and_period_selection(self):
        parsed = parse_meal_message(
            """
            Обед
            гречка и курица
            К 600
            Б 35
            Ж 22
            У 70
            """
        )
        day = date(2026, 5, 2)
        entry_id = self.db.add_meal_entry(1, day, parsed, self.now)

        entries = self.db.list_entries_for_day(1, day)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].id, entry_id)
        self.assertEqual(entries[0].meal_name_normalized, "обед")
        self.assertEqual(entries[0].description, "гречка и курица")

        updated = parse_meal_message(
            """
            Одеб
            рис
            тунец
            К 650
            Б 40
            Ж 20
            У 80
            """
        )
        self.assertTrue(self.db.update_meal_entry(entry_id, 1, updated, self.now))
        self.assertEqual(self.db.get_meal_entry(entry_id, 1).calories, 650)
        self.assertEqual(self.db.get_meal_entry(entry_id, 1).meal_name_normalized, "обед")
        self.assertEqual(self.db.get_meal_entry(entry_id, 1).description, "рис\nтунец")

        period_entries = self.db.list_entries_for_period(1, day, day)
        self.assertEqual(len(period_entries), 1)

        self.assertTrue(self.db.delete_meal_entry(entry_id, 1))
        self.assertEqual(self.db.list_entries_for_day(1, day), [])

    def test_active_day_advances_only_by_user_action(self):
        first_day = date(2026, 5, 2)
        active_day = self.db.get_active_date(1, first_day, self.now)
        self.assertEqual(active_day, first_day)

        calendar_next_day = first_day + timedelta(days=1)
        still_active_day = self.db.get_active_date(1, calendar_next_day, self.now + timedelta(days=1))
        self.assertEqual(still_active_day, first_day)

        advanced_day = self.db.advance_active_date(1, calendar_next_day, self.now + timedelta(days=1))
        self.assertEqual(advanced_day, calendar_next_day)
        self.assertEqual(self.db.get_active_date(1, first_day, self.now), calendar_next_day)

    def test_active_day_initializes_from_existing_entries(self):
        self.db.close()
        database_path = Path(self.temp_dir.name) / "legacy.sqlite3"
        connection = sqlite3.connect(database_path)
        connection.executescript(
            """
            CREATE TABLE users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE TABLE meal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                entry_date TEXT NOT NULL,
                meal_name_raw TEXT NOT NULL,
                meal_name_normalized TEXT NOT NULL,
                calories REAL NOT NULL,
                protein REAL NOT NULL,
                fat REAL NOT NULL,
                carbs REAL NOT NULL,
                source_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            """
            INSERT INTO users (telegram_id, username, full_name, first_seen_at, last_seen_at)
            VALUES (1, 'user', 'Test User', '2026-05-02T10:00:00', '2026-05-02T10:00:00')
            """
        )
        connection.execute(
            """
            INSERT INTO meal_entries (
                user_id, entry_date, meal_name_raw, meal_name_normalized, calories,
                protein, fat, carbs, source_text, created_at, updated_at
            )
            VALUES (1, '2026-05-02', 'Ужин', 'ужин', 500, 30, 20, 50, 'source',
                    '2026-05-02T23:30:00', '2026-05-02T23:30:00')
            """
        )
        connection.commit()
        connection.close()

        self.db = Storage(database_path)
        self.db.init_schema()

        active_day = self.db.get_active_date(1, date(2026, 5, 3), self.now)
        self.assertEqual(active_day, date(2026, 5, 2))


if __name__ == "__main__":
    unittest.main()
