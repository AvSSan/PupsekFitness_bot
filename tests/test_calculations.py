import unittest
from datetime import date, datetime

from kbju_bot.calculations import build_daily_summary
from kbju_bot.models import MealEntry, UserSettings


class CalculationTest(unittest.TestCase):
    def test_daily_summary_with_remaining_values(self):
        day = date(2026, 5, 2)
        entries = [
            make_entry(1, day, calories=500, protein=30, fat=20, carbs=50),
            make_entry(2, day, calories=700, protein=40, fat=25, carbs=70),
        ]
        settings = UserSettings(
            user_id=1,
            height_cm=170,
            weight_kg=65,
            target_calories=1800,
            target_protein=120,
            target_fat=60,
            target_carbs=190,
            updated_at=datetime(2026, 5, 2, 10, 0, 0),
        )

        summary = build_daily_summary(day, entries, settings)

        self.assertEqual(summary.total.calories, 1200)
        self.assertEqual(summary.total.protein, 70)
        self.assertEqual(summary.remaining.calories, 600)
        self.assertEqual(summary.remaining.protein, 50)
        self.assertEqual(summary.remaining.fat, 15)
        self.assertEqual(summary.remaining.carbs, 70)


def make_entry(entry_id, day, calories, protein, fat, carbs):
    now = datetime(2026, 5, 2, 10, 0, 0)
    return MealEntry(
        id=entry_id,
        user_id=1,
        entry_date=day,
        meal_name_raw="Завтрак",
        meal_name_normalized="завтрак",
        description="source description",
        calories=calories,
        protein=protein,
        fat=fat,
        carbs=carbs,
        source_text="source",
        created_at=now,
        updated_at=now,
    )


if __name__ == "__main__":
    unittest.main()
