import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.bot.handlers import BUTTONS, button_handler, cmd_start, cmd_stop, schedule_callback
from app.bot.keyboard import CALLBACK_PREFIX
from app.config import settings

log = logging.getLogger(__name__)

tg_app: Application | None = None


async def _on_error(update: object, context) -> None:
    log.exception("Unhandled error while processing %s", update, exc_info=context.error)


async def setup_bot() -> Application:
    global tg_app

    tg_app = Application.builder().token(settings.BOT_TOKEN).build()

    tg_app.add_handler(CommandHandler("start", cmd_start))
    tg_app.add_handler(CommandHandler("stop", cmd_stop))
    tg_app.add_handler(MessageHandler(filters.Text(list(BUTTONS)), button_handler))
    tg_app.add_handler(
        CallbackQueryHandler(schedule_callback, pattern=f"^{CALLBACK_PREFIX}")
    )
    tg_app.add_error_handler(_on_error)

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

    return tg_app


async def shutdown_bot() -> None:
    global tg_app
    if tg_app is None:
        return
    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()
    tg_app = None
