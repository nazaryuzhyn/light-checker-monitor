import time
from datetime import datetime, timezone

from app.database import async_session
from app.services.power import get_power_state, upsert_power_state


class PowerStateManager:
    def __init__(self) -> None:
        self.last_ping: float = time.time()
        self.power_is_on: bool = True
        self.power_off_time: float | None = None
        self.power_on_time: float | None = None

    async def load_from_db(self) -> None:
        """Restore state from DB after restart."""
        async with async_session() as session:
            row = await get_power_state(session)

        if row is None:
            # First ever launch — save defaults
            await self.save_to_db()
            return

        self.power_is_on = row.power_is_on
        self.power_off_time = row.power_off_at.timestamp() if row.power_off_at else None
        self.power_on_time = row.power_on_at.timestamp() if row.power_on_at else None

        if row.power_is_on:
            # Power was ON — give ESP 60s to reconnect
            self.last_ping = time.time()
        else:
            # Power was OFF — keep the old last_ping so monitor stays in "off" state
            self.last_ping = row.last_ping_at.timestamp()

    async def save_to_db(self) -> None:
        """Persist current in-memory state to DB."""
        async with async_session() as session:
            await upsert_power_state(
                session,
                power_is_on=self.power_is_on,
                last_ping_at=datetime.fromtimestamp(self.last_ping, tz=timezone.utc),
                power_off_at=(
                    datetime.fromtimestamp(self.power_off_time, tz=timezone.utc)
                    if self.power_off_time
                    else None
                ),
                power_on_at=(
                    datetime.fromtimestamp(self.power_on_time, tz=timezone.utc)
                    if self.power_on_time
                    else None
                ),
            )

    def record_ping(self) -> None:
        self.last_ping = time.time()

    async def record_ping_and_save(self) -> None:
        self.record_ping()
        await self.save_to_db()


power_state = PowerStateManager()
