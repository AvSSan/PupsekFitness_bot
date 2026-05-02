from __future__ import annotations

from kbju_bot.calculations import DailySummary
from kbju_bot.models import MealEntry, Nutrition, UserSettings


def format_number(value: float | int) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.1f}".rstrip("0").rstrip(".")


def format_nutrition(value: Nutrition) -> str:
    return (
        f"🔥 К {format_number(value.calories)}, "
        f"🥩 Б {format_number(value.protein)}, "
        f"🥑 Ж {format_number(value.fat)}, "
        f"🍚 У {format_number(value.carbs)}"
    )


def format_summary(summary: DailySummary) -> str:
    lines = [f"📊 За активный день ({summary.day.isoformat()}) уже набралось:\n{format_nutrition(summary.total)}"]
    if summary.target is None or summary.remaining is None:
        lines.append("⚙️ Чтобы я считал остаток на день, заполните нормы через кнопку Настройки.")
        return "\n".join(lines)

    lines.append(f"🎯 Дневная цель:\n{format_nutrition(summary.target)}")
    lines.append(f"✅ Осталось на этот день:\n{format_nutrition(summary.remaining)}")
    return "\n".join(lines)


def format_entry(entry: MealEntry) -> str:
    compact_description = " / ".join(line.strip() for line in entry.description.splitlines() if line.strip())
    description = f" — {compact_description}" if compact_description else ""
    return (
        f"🍽️ #{entry.id} {entry.meal_name_raw}{description}: "
        f"🔥 К {format_number(entry.calories)}, "
        f"🥩 Б {format_number(entry.protein)}, "
        f"🥑 Ж {format_number(entry.fat)}, "
        f"🍚 У {format_number(entry.carbs)}"
    )


def format_settings(settings: UserSettings | None) -> str:
    if settings is None:
        return "⚙️ Настройки пока не заполнены. Давайте добавим рост, вес и дневные нормы КБЖУ."
    return (
        "⚙️ Вот текущие настройки:\n"
        f"📏 Рост: {format_number(settings.height_cm)}\n"
        f"⚖️ Вес: {format_number(settings.weight_kg)}\n"
        f"🔥 К: {format_number(settings.target_calories)}\n"
        f"🥩 Б: {format_number(settings.target_protein)}\n"
        f"🥑 Ж: {format_number(settings.target_fat)}\n"
        f"🍚 У: {format_number(settings.target_carbs)}"
    )


def settings_template() -> str:
    return (
        "📝 Отправьте настройки одним сообщением. Можно просто скопировать шаблон и заменить числа:\n\n"
        "📏 Рост 170\n"
        "⚖️ Вес 65\n"
        "🔥 К 1800\n"
        "🥩 Б 120\n"
        "🥑 Ж 60\n"
        "🍚 У 190"
    )
