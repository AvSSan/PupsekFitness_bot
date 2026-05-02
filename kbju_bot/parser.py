from __future__ import annotations

import re
from dataclasses import dataclass

from kbju_bot.models import Nutrition


class ParseError(ValueError):
    """Raised when a user message cannot be converted into a structured entity."""


@dataclass(frozen=True)
class ParsedMeal:
    meal_name_raw: str
    meal_name_normalized: str
    description: str
    nutrition: Nutrition
    source_text: str


@dataclass(frozen=True)
class ParsedSettings:
    height_cm: float
    weight_kg: float
    target_calories: float
    target_protein: float
    target_fat: float
    target_carbs: float


KNOWN_MEALS = {
    "завтрак": "завтрак",
    "обед": "обед",
    "одеб": "обед",
    "полдник": "полдник",
    "ужин": "ужин",
    "перекус": "перекус",
}

FIELD_ALIASES = {
    "calories": ("к", "калории", "калорий", "ккал", "кал"),
    "protein": ("б", "белки", "белок", "протеин"),
    "fat": ("ж", "жиры", "жир"),
    "carbs": ("у", "углеводы", "углевод", "угли"),
}

SETTINGS_ALIASES = {
    "height_cm": ("рост", "height"),
    "weight_kg": ("вес", "weight"),
    "target_calories": ("к", "калории", "ккал", "кал"),
    "target_protein": ("б", "белки", "белок", "протеин"),
    "target_fat": ("ж", "жиры", "жир"),
    "target_carbs": ("у", "углеводы", "углевод", "угли"),
}

NUMBER_RE = re.compile(r"[-+]?\d+(?:[,.]\d+)?")


def parse_meal_message(text: str) -> ParsedMeal:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ParseError("Нужна первая строка с приемом пищи и строки с КБЖУ.")

    meal_name_raw = lines[0]
    values: dict[str, float] = {}
    description_lines: list[str] = []

    for line in lines[1:]:
        field = detect_field(line, FIELD_ALIASES)
        if field is None:
            description_lines.append(line)
            continue
        if field in values:
            raise ParseError(f"Поле {field_label(field)} указано дважды.")
        values[field] = extract_number(line)

    missing = [field_label(field) for field in ("calories", "protein", "fat", "carbs") if field not in values]
    if missing:
        raise ParseError("Не хватает полей: " + ", ".join(missing))

    return ParsedMeal(
        meal_name_raw=meal_name_raw,
        meal_name_normalized=normalize_meal_name(meal_name_raw),
        description="\n".join(description_lines),
        nutrition=Nutrition(
            calories=values["calories"],
            protein=values["protein"],
            fat=values["fat"],
            carbs=values["carbs"],
        ),
        source_text=text.strip(),
    )


def parse_settings_message(text: str) -> ParsedSettings:
    values: dict[str, float] = {}
    for line in [line.strip() for line in text.splitlines() if line.strip()]:
        field = detect_field(line, SETTINGS_ALIASES)
        if field is None:
            raise ParseError(f"Не понял строку настроек: {line}")
        if field in values:
            raise ParseError(f"Поле {settings_field_label(field)} указано дважды.")
        values[field] = extract_number(line)

    required = ("height_cm", "weight_kg", "target_calories", "target_protein", "target_fat", "target_carbs")
    missing = [settings_field_label(field) for field in required if field not in values]
    if missing:
        raise ParseError("Не хватает настроек: " + ", ".join(missing))

    return ParsedSettings(
        height_cm=values["height_cm"],
        weight_kg=values["weight_kg"],
        target_calories=values["target_calories"],
        target_protein=values["target_protein"],
        target_fat=values["target_fat"],
        target_carbs=values["target_carbs"],
    )


def normalize_meal_name(value: str) -> str:
    normalized = " ".join(value.lower().split())
    return KNOWN_MEALS.get(normalized, normalized)


def detect_field(line: str, aliases: dict[str, tuple[str, ...]]) -> str | None:
    lowered = line.casefold().strip()
    for field, field_aliases in aliases.items():
        for alias in field_aliases:
            pattern = rf"^\s*(?:[^\w]+\s*)*{re.escape(alias.casefold())}\b"
            if re.search(pattern, lowered):
                return field
    return None


def extract_number(line: str) -> float:
    match = NUMBER_RE.search(line)
    if match is None:
        raise ParseError(f"Не нашел число в строке: {line}")
    return float(match.group(0).replace(",", "."))


def field_label(field: str) -> str:
    return {
        "calories": "К",
        "protein": "Б",
        "fat": "Ж",
        "carbs": "У",
    }[field]


def settings_field_label(field: str) -> str:
    return {
        "height_cm": "рост",
        "weight_kg": "вес",
        "target_calories": "К",
        "target_protein": "Б",
        "target_fat": "Ж",
        "target_carbs": "У",
    }[field]
