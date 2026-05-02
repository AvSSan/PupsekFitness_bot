from __future__ import annotations

from datetime import date, datetime, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from kbju_bot.calculations import build_daily_summary
from kbju_bot.config import Config
from kbju_bot.exporter import build_excel_export, export_caption, export_filename
from kbju_bot.formatting import format_entry, format_settings, format_summary, settings_template
from kbju_bot.parser import ParseError, parse_meal_message, parse_settings_message
from kbju_bot.storage import Storage


router = Router()

MENU_TODAY = "📅 Текущий день"
MENU_NEW_DAY = "🌅 Новый день"
MENU_SETTINGS = "⚙️ Настройки"
MENU_EXPORT = "📤 Выгрузить Excel"
LEGACY_MENU_CURRENT_DAY = "Текущий день"
LEGACY_MENU_TODAY = "Сегодня"
LEGACY_MENU_TODAY_EMOJI = "📅 Сегодня"
LEGACY_MENU_NEW_DAY = "Новый день"
LEGACY_MENU_SETTINGS = "Настройки"
LEGACY_MENU_EXPORT = "Выгрузить Excel"


class SettingsState(StatesGroup):
    waiting_for_settings = State()


class EditEntryState(StatesGroup):
    waiting_for_entry_text = State()


def build_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher


@router.message(Command("start"))
async def command_start(message: Message, state: FSMContext, db: Storage, app_config: Config) -> None:
    if not await ensure_allowed_message(message, app_config):
        return
    await state.clear()
    register_user(db, message, app_config)
    await message.answer(
        "👋 Привет! Я помогу спокойно вести дневник КБЖУ и показывать, сколько осталось до дневной нормы.\n\n"
        "🍽️ Можно сразу отправить прием пищи текстом.\n"
        "Первая строка — название приема пищи, дальше можно добавить описание и КБЖУ в любом порядке.\n\n"
        "📝 Пример:\n"
        "Завтрак\n"
        "омлет с сыром\n"
        "К 520\n"
        "Б 32\n"
        "Ж 18\n"
        "У 55\n\n"
        "👇 Кнопки снизу помогут посмотреть текущий день, начать новый день, заполнить настройки или выгрузить таблицу.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("settings"))
async def command_settings(message: Message, state: FSMContext, db: Storage, app_config: Config) -> None:
    if not await ensure_allowed_message(message, app_config):
        return
    register_user(db, message, app_config)
    await state.set_state(SettingsState.waiting_for_settings)
    await message.answer(format_settings(db.get_settings(message.from_user.id)), reply_markup=main_menu_keyboard())
    await message.answer(settings_template(), reply_markup=main_menu_keyboard())


@router.message(Command("today"))
async def command_today(message: Message, state: FSMContext, db: Storage, app_config: Config) -> None:
    if not await ensure_allowed_message(message, app_config):
        return
    await state.clear()
    register_user(db, message, app_config)
    await send_today(message, db, app_config, message.from_user.id)


@router.message(Command("newday"))
async def command_new_day(message: Message, state: FSMContext, db: Storage, app_config: Config) -> None:
    if not await ensure_allowed_message(message, app_config):
        return
    await state.clear()
    register_user(db, message, app_config)
    await advance_to_new_day(message, db, app_config, message.from_user.id)


@router.message(Command("export"))
async def command_export(message: Message, state: FSMContext, db: Storage, app_config: Config) -> None:
    if not await ensure_allowed_message(message, app_config):
        return
    await state.clear()
    register_user(db, message, app_config)
    await message.answer("📤 За какой период подготовить Excel-таблицу?", reply_markup=export_period_keyboard())


@router.message(F.text.in_({MENU_TODAY, LEGACY_MENU_CURRENT_DAY, LEGACY_MENU_TODAY, LEGACY_MENU_TODAY_EMOJI}))
async def menu_today(message: Message, state: FSMContext, db: Storage, app_config: Config) -> None:
    if not await ensure_allowed_message(message, app_config):
        return
    await state.clear()
    register_user(db, message, app_config)
    await send_today(message, db, app_config, message.from_user.id)


@router.message(F.text.in_({MENU_NEW_DAY, LEGACY_MENU_NEW_DAY}))
async def menu_new_day(message: Message, state: FSMContext, db: Storage, app_config: Config) -> None:
    if not await ensure_allowed_message(message, app_config):
        return
    await state.clear()
    register_user(db, message, app_config)
    await advance_to_new_day(message, db, app_config, message.from_user.id)


@router.message(F.text.in_({MENU_SETTINGS, LEGACY_MENU_SETTINGS}))
async def menu_settings(message: Message, state: FSMContext, db: Storage, app_config: Config) -> None:
    if not await ensure_allowed_message(message, app_config):
        return
    register_user(db, message, app_config)
    await state.set_state(SettingsState.waiting_for_settings)
    await message.answer(format_settings(db.get_settings(message.from_user.id)), reply_markup=main_menu_keyboard())
    await message.answer(settings_template(), reply_markup=main_menu_keyboard())


@router.message(F.text.in_({MENU_EXPORT, LEGACY_MENU_EXPORT}))
async def menu_export(message: Message, state: FSMContext, db: Storage, app_config: Config) -> None:
    if not await ensure_allowed_message(message, app_config):
        return
    await state.clear()
    register_user(db, message, app_config)
    await message.answer("📤 За какой период подготовить Excel-таблицу?", reply_markup=export_period_keyboard())


@router.callback_query(F.data.startswith("export:"))
async def callback_export(callback: CallbackQuery, db: Storage, app_config: Config) -> None:
    if not await ensure_allowed_callback(callback, app_config):
        return
    await callback.answer("📄 Готовлю файл...")
    active_day = get_active_day(db, app_config, callback.from_user.id)
    start_date = export_start_date(callback.data.removeprefix("export:"), active_day)
    entries = db.list_entries_for_period(callback.from_user.id, start_date, active_day)
    settings = db.get_settings(callback.from_user.id)
    output = build_excel_export(entries, settings)
    filename = export_filename(start_date, active_day)
    await callback.message.answer_document(
        BufferedInputFile(output.getvalue(), filename=filename),
        caption=export_caption(len(entries)),
    )


@router.callback_query(F.data.startswith("entry:delete:"))
async def callback_delete_entry(callback: CallbackQuery, db: Storage, app_config: Config) -> None:
    if not await ensure_allowed_callback(callback, app_config):
        return
    entry_id = int(callback.data.rsplit(":", 1)[1])
    deleted = db.delete_meal_entry(entry_id, callback.from_user.id)
    await callback.answer("🗑️ Удалено" if deleted else "Запись не найдена")
    await callback.message.answer("🗑️ Запись удалена." if deleted else "Не нашел эту запись.")
    await send_today(callback.message, db, app_config, callback.from_user.id)


@router.callback_query(F.data.startswith("entry:edit:"))
async def callback_edit_entry(callback: CallbackQuery, state: FSMContext, db: Storage, app_config: Config) -> None:
    if not await ensure_allowed_callback(callback, app_config):
        return
    entry_id = int(callback.data.rsplit(":", 1)[1])
    entry = db.get_meal_entry(entry_id, callback.from_user.id)
    if entry is None:
        await callback.answer("Запись не найдена")
        return
    await callback.answer()
    await state.set_state(EditEntryState.waiting_for_entry_text)
    await state.update_data(entry_id=entry_id)
    await callback.message.answer(
        "✏️ Отправьте новый полный текст записи в том же формате.\n\n"
        f"Сейчас:\n{format_entry(entry)}"
    )


@router.message(SettingsState.waiting_for_settings)
async def save_settings(message: Message, state: FSMContext, db: Storage, app_config: Config) -> None:
    if not await ensure_allowed_message(message, app_config):
        return
    register_user(db, message, app_config)
    try:
        settings = parse_settings_message(message_body(message))
    except ParseError as error:
        await message.answer(f"⚠️ Не удалось сохранить настройки: {error}\n\n{settings_template()}")
        return

    db.upsert_settings(message.from_user.id, settings, local_now(app_config))
    await state.clear()
    await message.answer(
        "✅ Настройки сохранены. Теперь после каждой записи я буду показывать остаток КБЖУ на день.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(EditEntryState.waiting_for_entry_text)
async def save_edited_entry(message: Message, state: FSMContext, db: Storage, app_config: Config) -> None:
    if not await ensure_allowed_message(message, app_config):
        return
    data = await state.get_data()
    entry_id = int(data["entry_id"])
    try:
        parsed = parse_meal_message(message_body(message))
    except ParseError as error:
        await message.answer(f"⚠️ Не удалось обновить запись: {error}")
        return

    updated = db.update_meal_entry(entry_id, message.from_user.id, parsed, local_now(app_config))
    await state.clear()
    await message.answer(
        "✅ Готово, запись обновлена." if updated else "Не нашел эту запись.",
        reply_markup=main_menu_keyboard(),
    )
    await send_today(message, db, app_config, message.from_user.id)


@router.message(F.text | F.caption)
async def save_meal_entry(message: Message, db: Storage, app_config: Config) -> None:
    if not await ensure_allowed_message(message, app_config):
        return
    register_user(db, message, app_config)
    try:
        parsed = parse_meal_message(message_body(message))
    except ParseError as error:
        await message.answer(f"⚠️ Не удалось разобрать запись: {error}")
        return

    active_day = get_active_day(db, app_config, message.from_user.id)
    entry_id = db.add_meal_entry(message.from_user.id, active_day, parsed, local_now(app_config))
    entries = db.list_entries_for_day(message.from_user.id, active_day)
    summary = build_daily_summary(active_day, entries, db.get_settings(message.from_user.id))
    await message.answer(
        f"✅ Записал прием пищи #{entry_id}.\n\n{format_summary(summary)}",
        reply_markup=main_menu_keyboard(),
    )


async def send_today(message: Message, db: Storage, app_config: Config, user_id: int) -> None:
    active_day = get_active_day(db, app_config, user_id)
    entries = db.list_entries_for_day(user_id, active_day)
    summary = build_daily_summary(active_day, entries, db.get_settings(user_id))
    if not entries:
        await message.answer(
            f"📭 В текущем дне пока нет записей.\n\n{format_summary(summary)}",
            reply_markup=main_menu_keyboard(),
        )
        return

    lines = [
        f"📅 Текущий день: {active_day.isoformat()}",
        "Вот что уже записано:",
        *[format_entry(entry) for entry in entries],
        "",
        format_summary(summary),
    ]
    await message.answer("\n".join(lines), reply_markup=today_entries_keyboard(entries))


async def advance_to_new_day(message: Message, db: Storage, app_config: Config, user_id: int) -> None:
    new_active_day = db.advance_active_date(user_id, local_today(app_config), local_now(app_config))
    await message.answer(
        f"🌅 Новый день начат: {new_active_day.isoformat()}.\n"
        "Все следующие записи будут попадать в этот день.",
        reply_markup=main_menu_keyboard(),
    )
    await send_today(message, db, app_config, user_id)


def register_user(db: Storage, message: Message, app_config: Config) -> None:
    if message.from_user is None:
        return
    db.upsert_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        now=local_now(app_config),
    )


def message_body(message: Message) -> str:
    return message.text or message.caption or ""


async def ensure_allowed_message(message: Message, app_config: Config) -> bool:
    if message.from_user is not None and message.from_user.id in app_config.allowed_user_ids:
        return True
    await message.answer("⛔ У вас нет доступа к этому боту.")
    return False


async def ensure_allowed_callback(callback: CallbackQuery, app_config: Config) -> bool:
    if callback.from_user.id in app_config.allowed_user_ids:
        return True
    await callback.answer("У вас нет доступа к этому боту.", show_alert=True)
    return False


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_TODAY), KeyboardButton(text=MENU_NEW_DAY)],
            [KeyboardButton(text=MENU_SETTINGS)],
            [KeyboardButton(text=MENU_EXPORT)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Введите прием пищи или выберите действие",
    )


def export_period_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 Текущий день", callback_data="export:today"),
                InlineKeyboardButton(text="🗓️ 7 дней", callback_data="export:7"),
            ],
            [
                InlineKeyboardButton(text="🗓️ 30 дней", callback_data="export:30"),
                InlineKeyboardButton(text="📚 Весь период", callback_data="export:all"),
            ],
        ]
    )


def today_entries_keyboard(entries: list) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for entry in entries:
        rows.append(
            [
                InlineKeyboardButton(text=f"✏️ Изменить #{entry.id}", callback_data=f"entry:edit:{entry.id}"),
                InlineKeyboardButton(text=f"🗑️ Удалить #{entry.id}", callback_data=f"entry:delete:{entry.id}"),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def export_start_date(period: str, today: date) -> date | None:
    if period == "today":
        return today
    if period == "7":
        return today - timedelta(days=6)
    if period == "30":
        return today - timedelta(days=29)
    if period == "all":
        return None
    return today


def local_now(app_config: Config) -> datetime:
    return datetime.now(app_config.timezone)


def local_today(app_config: Config) -> date:
    return local_now(app_config).date()


def get_active_day(db: Storage, app_config: Config, user_id: int) -> date:
    return db.get_active_date(user_id, local_today(app_config), local_now(app_config))
