import tempfile
import unittest
from datetime import date, datetime
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


if __name__ == "__main__":
    unittest.main()
