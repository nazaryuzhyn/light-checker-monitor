from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from app.bot.handlers import button_handler, cmd_start, cmd_stop, schedule_callback
from app.bot.keyboard import BTN_CHECK, BTN_DETAILS, BTN_SCHEDULE
from app.config import settings

tg_app: Application | None = None


async def setup_bot() -> Application:
    global tg_app

    tg_app = Application.builder().token(settings.BOT_TOKEN).build()

    tg_app.add_handler(CommandHandler("start", cmd_start))
    tg_app.add_handler(CommandHandler("stop", cmd_stop))
    tg_app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(f"^({BTN_CHECK}|{BTN_DETAILS}|{BTN_SCHEDULE})$"),
            button_handler,
        )
    )
    tg_app.add_handler(CallbackQueryHandler(schedule_callback, pattern="^schedule_"))

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

    return tg_app
