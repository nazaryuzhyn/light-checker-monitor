import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.bot.setup import setup_bot, shutdown_bot
from app.database import Base, engine
from app.logging_config import configure_logging
from app.routes import esp, status
from app.services.monitor import monitor_power
from app.services.schedule_watch import watch_schedule
from app.state import power_state

configure_logging()
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await power_state.load_from_db()

    application = await setup_bot()
    tasks = [
        asyncio.create_task(monitor_power(application.bot)),
        asyncio.create_task(watch_schedule(application.bot)),
    ]
    log.info("Started: bot polling, power monitor and schedule watch are running")

    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        try:
            await power_state.save_to_db()
        finally:
            await shutdown_bot()


# No interactive API docs: the endpoints are for the ESP and uptime-kuma only.
app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

app.include_router(esp.router)
app.include_router(status.router)
