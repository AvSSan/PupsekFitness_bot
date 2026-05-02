import unittest

from kbju_bot.parser import ParseError, normalize_meal_name, parse_meal_message, parse_settings_message


class MealParserTest(unittest.TestCase):
    def test_parses_case_insensitive_fields_in_any_order(self):
        parsed = parse_meal_message(
            """
            Завтрак
            у 55
            Ж: 18
            калории 520
            Б 32
            """
        )

        self.assertEqual(parsed.meal_name_normalized, "завтрак")
        self.assertEqual(parsed.nutrition.calories, 520)
        self.assertEqual(parsed.nutrition.protein, 32)
        self.assertEqual(parsed.nutrition.fat, 18)
        self.assertEqual(parsed.nutrition.carbs, 55)

    def test_accepts_comma_decimal_separator(self):
        parsed = parse_meal_message(
            """
            Полдник
            К 250,5
            Б 20,25
            Ж 10
            У 15
            """
        )

        self.assertEqual(parsed.nutrition.calories, 250.5)
        self.assertEqual(parsed.nutrition.protein, 20.25)

    def test_ignores_free_text_description_lines(self):
        parsed = parse_meal_message(
            """
            завтрак
            яишница
            к 100
            б 90
            ж 80
            у 70
            """
        )

        self.assertEqual(parsed.meal_name_normalized, "завтрак")
        self.assertEqual(parsed.description, "яишница")
        self.assertEqual(parsed.nutrition.calories, 100)
        self.assertEqual(parsed.nutrition.protein, 90)
        self.assertEqual(parsed.nutrition.fat, 80)
        self.assertEqual(parsed.nutrition.carbs, 70)

    def test_preserves_multiline_description(self):
        parsed = parse_meal_message(
            """
            завтрак
            яичница
            два яйца и сыр
            к 100
            б 90
            ж 80
            у 70
            """
        )

        self.assertEqual(parsed.description, "яичница\nдва яйца и сыр")

    def test_accepts_emoji_prefixes_before_fields(self):
        parsed = parse_meal_message(
            """
            завтрак
            омлет
            🔥 к 100
            🥩 б 90
            🥑 ж 80
            🍚 у 70
            """
        )

        self.assertEqual(parsed.description, "омлет")
        self.assertEqual(parsed.nutrition.calories, 100)
        self.assertEqual(parsed.nutrition.protein, 90)
        self.assertEqual(parsed.nutrition.fat, 80)
        self.assertEqual(parsed.nutrition.carbs, 70)

    def test_normalizes_lunch_typo(self):
        self.assertEqual(normalize_meal_name("Одеб"), "обед")

    def test_requires_all_nutrition_fields(self):
        with self.assertRaises(ParseError):
            parse_meal_message(
                """
                Ужин
                К 500
                Б 30
                Ж 20
                """
            )


class SettingsParserTest(unittest.TestCase):
    def test_parses_settings(self):
        parsed = parse_settings_message(
            """
            📏 Рост 170
            ⚖️ Вес 65
            🔥 К 1800
            🥩 Б 120
            🥑 Ж 60
            🍚 У 190
            """
        )

        self.assertEqual(parsed.height_cm, 170)
        self.assertEqual(parsed.weight_kg, 65)
        self.assertEqual(parsed.target_calories, 1800)
        self.assertEqual(parsed.target_protein, 120)
        self.assertEqual(parsed.target_fat, 60)
        self.assertEqual(parsed.target_carbs, 190)


if __name__ == "__main__":
    unittest.main()
