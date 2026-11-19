from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.company import Company


class CompanyGeo(Base):
    __tablename__ = "company_geo"
    __table_args__ = (
        CheckConstraint("position >= 1", name="company_geo_position_check"),
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("company.id", ondelete="CASCADE"),
        primary_key=True,
    )
    geo_code: Mapped[str] = mapped_column(
        Text,
        ForeignKey("geo.code"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    company: Mapped[Company] = relationship(back_populates="geos")
