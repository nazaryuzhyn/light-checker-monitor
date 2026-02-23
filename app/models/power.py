from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PowerState(Base):
    __tablename__ = "power_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    power_is_on: Mapped[bool] = mapped_column(Boolean, nullable=False)
    last_ping_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    power_off_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    power_on_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
