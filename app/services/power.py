from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PowerState


async def get_power_state(session: AsyncSession) -> PowerState | None:
    result = await session.execute(select(PowerState).where(PowerState.id == 1))
    return result.scalar_one_or_none()


async def upsert_power_state(
    session: AsyncSession,
    *,
    power_is_on: bool,
    last_ping_at: datetime,
    power_off_at: datetime | None = None,
    power_on_at: datetime | None = None,
) -> PowerState:
    row = await get_power_state(session)
    now = datetime.now(timezone.utc)

    if row is None:
        row = PowerState(
            id=1,
            power_is_on=power_is_on,
            last_ping_at=last_ping_at,
            power_off_at=power_off_at,
            power_on_at=power_on_at,
            updated_at=now,
        )
        session.add(row)
    else:
        row.power_is_on = power_is_on
        row.last_ping_at = last_ping_at
        row.power_off_at = power_off_at
        row.power_on_at = power_on_at
        row.updated_at = now

    await session.commit()
    return row
