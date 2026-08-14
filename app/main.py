import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.bot.setup import setup_bot, shutdown_bot
from app.database import Base, engine
from app.logging_config import configure_logging
from app.routes import esp, status
from app.services.monitor import monitor_power
from app.state import power_state

configure_logging()
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await power_state.load_from_db()

    application = await setup_bot()
    monitor = asyncio.create_task(monitor_power(application.bot))
    log.info("Started: bot polling and power monitor are running")

    try:
        yield
    finally:
        monitor.cancel()
        with suppress(asyncio.CancelledError):
            await monitor
        await power_state.save_to_db()
        await shutdown_bot()


app = FastAPI(lifespan=lifespan)

app.include_router(esp.router)
app.include_router(status.router)
