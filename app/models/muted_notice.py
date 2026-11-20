from enum import StrEnum

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Notice(StrEnum):
    """Optional broadcasts a subscriber can switch off. Power alerts are not among them."""

    SCHEDULE_CHANGES = "schedule_changes"
    REMINDERS = "reminders"


class MutedNotice(Base):
    """A row means the chat switched that notice off; no row means it is on.

    A table of its own rather than columns on subscribers: create_all() adds new
    tables at start-up but never alters existing ones.
    """

    __tablename__ = "muted_notices"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    notice: Mapped[str] = mapped_column(String(32), primary_key=True)
