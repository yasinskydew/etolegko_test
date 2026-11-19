from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    SmallInteger,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.stream import Stream


class StreamOffer(Base):
    __tablename__ = "stream_offer"
    __table_args__ = (
        CheckConstraint("percent >= 0 AND percent <= 100", name="stream_offer_percent_check"),
        CheckConstraint("position >= 1", name="stream_offer_position_check"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stream_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("stream.id", ondelete="CASCADE"),
        nullable=False,
    )
    offer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    percent: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    removed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    stream: Mapped[Stream] = relationship(back_populates="offers")
