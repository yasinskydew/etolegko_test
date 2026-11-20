from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import StreamType

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.stream_offer import StreamOffer


class Stream(Base):
    __tablename__ = "stream"
    __table_args__ = (
        CheckConstraint("position >= 1", name="stream_position_check"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("company.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[StreamType] = mapped_column(
        Enum(
            StreamType,
            name="stream_type",
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
    )
    keitaro_stream_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    company: Mapped[Company] = relationship(back_populates="streams")
    offers: Mapped[list[StreamOffer]] = relationship(
        back_populates="stream",
        cascade="all, delete-orphan",
        order_by="StreamOffer.position",
    )
