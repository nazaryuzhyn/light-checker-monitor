from sqlalchemy import delete, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MutedNotice, Notice, Subscriber


async def count_subscribers(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(Subscriber))


async def get_all_subscribers(session: AsyncSession, notice: Notice | None = None) -> list[int]:
    """Every subscriber, or, for an optional notice, those who have not switched it off."""
    query = select(Subscriber.chat_id)
    if notice is not None:
        muted = exists().where(
            MutedNotice.chat_id == Subscriber.chat_id, MutedNotice.notice == notice
        )
        query = query.where(~muted)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_muted(session: AsyncSession, chat_id: int) -> set[Notice]:
    result = await session.execute(
        select(MutedNotice.notice).where(MutedNotice.chat_id == chat_id)
    )
    return {Notice(value) for value in result.scalars()}


async def toggle_notice(session: AsyncSession, chat_id: int, notice: Notice) -> bool:
    """Flip one notice for a chat. Returns True when it is now on."""
    removed = await session.execute(
        delete(MutedNotice)
        .where(MutedNotice.chat_id == chat_id, MutedNotice.notice == notice)
        .returning(MutedNotice.chat_id)
    )
    now_on = removed.scalar_one_or_none() is not None
    if not now_on:
        await session.execute(
            insert(MutedNotice).values(chat_id=chat_id, notice=notice).on_conflict_do_nothing()
        )
    await session.commit()
    return now_on


async def add_subscriber(session: AsyncSession, chat_id: int) -> bool:
    """Add subscriber. Returns True if new, False if already existed."""
    # One statement, so two quick /start taps handled concurrently cannot collide.
    result = await session.execute(
        insert(Subscriber)
        .values(chat_id=chat_id)
        .on_conflict_do_nothing()
        .returning(Subscriber.chat_id)
    )
    await session.commit()
    return result.scalar_one_or_none() is not None


async def remove_subscriber(session: AsyncSession, chat_id: int) -> None:
    await session.execute(delete(Subscriber).where(Subscriber.chat_id == chat_id))
    await session.commit()


async def remove_subscribers(session: AsyncSession, chat_ids: list[int]) -> None:
    if not chat_ids:
        return
    await session.execute(delete(Subscriber).where(Subscriber.chat_id.in_(chat_ids)))
    await session.commit()
