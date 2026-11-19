from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CompanyLifecycle, TrafficStatus

if TYPE_CHECKING:
    from app.models.company_geo import CompanyGeo
    from app.models.stream import Stream


class Company(Base):
    __tablename__ = "company"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    keitaro_campaign_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    traffic_status: Mapped[TrafficStatus] = mapped_column(
        Enum(
            TrafficStatus,
            name="traffic_status",
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
        server_default=TrafficStatus.active.value,
    )
    lifecycle: Mapped[CompanyLifecycle] = mapped_column(
        Enum(
            CompanyLifecycle,
            name="company_lifecycle",
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    geos: Mapped[list[CompanyGeo]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        order_by="CompanyGeo.position",
    )
    streams: Mapped[list[Stream]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        order_by="Stream.position",
    )
