import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.bot import setup as bot_setup
from app.bot.setup import setup_bot
from app.routes import esp, status, webhook
from app.services.monitor import monitor_power
from app.state import power_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Restore state from DB
    await power_state.load_from_db()

    # Start Telegram bot
    application = await setup_bot()

    # Start background power monitor
    asyncio.create_task(monitor_power(application.bot))

    yield

    # Graceful shutdown: save state, stop bot
    await power_state.save_to_db()
    if bot_setup.tg_app:
        await bot_setup.tg_app.stop()
        await bot_setup.tg_app.shutdown()


app = FastAPI(lifespan=lifespan)

app.include_router(esp.router)
app.include_router(status.router)
app.include_router(webhook.router)
