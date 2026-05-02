from __future__ import annotations

import asyncio

from aiogram import Bot

from kbju_bot.bot import build_dispatcher
from kbju_bot.config import load_config
from kbju_bot.storage import Storage


async def main() -> None:
    config = load_config()
    db = Storage(config.database_path)
    db.init_schema()

    bot = Bot(token=config.bot_token)
    dispatcher = build_dispatcher()
    try:
        await dispatcher.start_polling(bot, db=db, app_config=config)
    finally:
        db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

