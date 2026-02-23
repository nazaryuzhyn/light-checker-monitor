import logging

from telegram import Bot

from app.database import async_session
from app.services.subscriber import get_all_subscribers, remove_subscribers

log = logging.getLogger(__name__)


async def notify_all(bot: Bot, text: str) -> None:
    """Send a message to all subscribers, removing those who blocked the bot."""
    async with async_session() as session:
        chat_ids = await get_all_subscribers(session)

    failed: list[int] = []
    for chat_id in chat_ids:
        try:
            await bot.send_message(
                chat_id=chat_id, text=text, parse_mode="Markdown"
            )
        except Exception as e:
            log.warning("Помилка надсилання до %s: %s", chat_id, e)
            failed.append(chat_id)

    if failed:
        async with async_session() as session:
            await remove_subscribers(session, failed)
