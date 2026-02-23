import logging

from fastapi import APIRouter, Request

from app.bot import setup as bot_setup

log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook")
async def webhook(request: Request):
    try:
        from telegram import Update

        data = await request.json()
        update = Update.de_json(data, bot_setup.tg_app.bot)
        await bot_setup.tg_app.process_update(update)
    except Exception:
        log.exception("webhook error")
    return {"ok": True}
