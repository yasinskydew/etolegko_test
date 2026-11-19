from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Geo(Base):
    __tablename__ = "geo"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
