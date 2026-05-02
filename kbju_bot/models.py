from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Nutrition:
    calories: float
    protein: float
    fat: float
    carbs: float


@dataclass(frozen=True)
class UserSettings:
    user_id: int
    height_cm: float
    weight_kg: float
    target_calories: float
    target_protein: float
    target_fat: float
    target_carbs: float
    updated_at: datetime


@dataclass(frozen=True)
class MealEntry:
    id: int
    user_id: int
    entry_date: date
    meal_name_raw: str
    meal_name_normalized: str
    description: str
    calories: float
    protein: float
    fat: float
    carbs: float
    source_text: str
    created_at: datetime
    updated_at: datetime
