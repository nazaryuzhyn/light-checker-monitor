import asyncio
import logging

from telegram import Bot
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter, TelegramError

from app.database import async_session
from app.models import Notice
from app.services.subscriber import get_all_subscribers, remove_subscribers

log = logging.getLogger(__name__)

ATTEMPTS = 3
NETWORK_BACKOFF = (2, 5)  # seconds before the second and the third attempt

# Kept so an alert still goes out while the database is unreachable.
_last_known_recipients: dict[Notice | None, list[int]] = {}


async def _send(bot: Bot, chat_id: int, text: str) -> bool:
    """Deliver one message. False only when the chat is gone for good."""
    for attempt in range(ATTEMPTS):
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
            return True
        except RetryAfter as error:
            await asyncio.sleep(error.retry_after)
        except Forbidden:
            return False
        except BadRequest as error:  # a NetworkError subclass, so it goes first
            if "chat not found" in error.message.lower():
                return False
            log.warning("Could not send to %s: %s", chat_id, error)
            return True
        except NetworkError as error:
            # A blip at the moment of an alert must not lose it; a retried timeout
            # can, rarely, deliver the message twice.
            log.warning("Could not send to %s (attempt %d): %s", chat_id, attempt + 1, error)
            if attempt < len(NETWORK_BACKOFF):
                await asyncio.sleep(NETWORK_BACKOFF[attempt])
        except TelegramError as error:
            log.warning("Could not send to %s: %s", chat_id, error)
            return True
    log.warning("Gave up sending to %s", chat_id)
    return True


async def notify_all(bot: Bot, text: str, notice: Notice | None = None) -> None:
    """Send a message to subscribers, removing those who blocked the bot.

    `notice` marks an optional broadcast that skips chats which switched it off;
    without it the message goes to everyone.
    """
    try:
        async with async_session() as session:
            _last_known_recipients[notice] = await get_all_subscribers(session, notice)
    except Exception:
        log.exception("Could not read subscribers; using the last known list")
    chat_ids = _last_known_recipients.get(notice, [])

    gone = [chat_id for chat_id in chat_ids if not await _send(bot, chat_id, text)]
    if gone:
        try:
            async with async_session() as session:
                await remove_subscribers(session, gone)
        except Exception:
            log.exception("Could not remove subscribers %s", gone)
