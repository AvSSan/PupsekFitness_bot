from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from kbju_bot.models import MealEntry, Nutrition, UserSettings


@dataclass(frozen=True)
class DailySummary:
    day: date
    total: Nutrition
    target: Nutrition | None
    remaining: Nutrition | None


def sum_entries(entries: Iterable[MealEntry]) -> Nutrition:
    calories = protein = fat = carbs = 0.0
    for entry in entries:
        calories += entry.calories
        protein += entry.protein
        fat += entry.fat
        carbs += entry.carbs
    return Nutrition(calories=calories, protein=protein, fat=fat, carbs=carbs)


def targets_from_settings(settings: UserSettings | None) -> Nutrition | None:
    if settings is None:
        return None
    return Nutrition(
        calories=settings.target_calories,
        protein=settings.target_protein,
        fat=settings.target_fat,
        carbs=settings.target_carbs,
    )


def subtract(left: Nutrition, right: Nutrition) -> Nutrition:
    return Nutrition(
        calories=left.calories - right.calories,
        protein=left.protein - right.protein,
        fat=left.fat - right.fat,
        carbs=left.carbs - right.carbs,
    )


def build_daily_summary(
    day: date,
    entries: Iterable[MealEntry],
    settings: UserSettings | None,
) -> DailySummary:
    total = sum_entries(entries)
    target = targets_from_settings(settings)
    remaining = subtract(target, total) if target is not None else None
    return DailySummary(day=day, total=total, target=target, remaining=remaining)

