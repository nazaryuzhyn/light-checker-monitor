from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subscriber


async def get_all_subscribers(session: AsyncSession) -> list[int]:
    result = await session.execute(select(Subscriber.chat_id))
    return list(result.scalars().all())


async def add_subscriber(session: AsyncSession, chat_id: int) -> bool:
    """Add subscriber. Returns True if new, False if already existed."""
    existing = await session.execute(
        select(Subscriber).where(Subscriber.chat_id == chat_id)
    )
    if existing.scalar_one_or_none() is not None:
        return False

    session.add(Subscriber(chat_id=chat_id))
    await session.commit()
    return True


async def remove_subscriber(session: AsyncSession, chat_id: int) -> None:
    await session.execute(delete(Subscriber).where(Subscriber.chat_id == chat_id))
    await session.commit()


async def remove_subscribers(session: AsyncSession, chat_ids: list[int]) -> None:
    if not chat_ids:
        return
    await session.execute(delete(Subscriber).where(Subscriber.chat_id.in_(chat_ids)))
    await session.commit()
