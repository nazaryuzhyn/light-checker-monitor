from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Pre-ping: pooled connections die when the db container restarts. Short timeouts:
# asyncpg waits indefinitely by default, and the alert path must not hang on it.
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_timeout=5,
    connect_args={"timeout": 5, "command_timeout": 5},
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
