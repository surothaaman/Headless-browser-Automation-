
from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="received",
        nullable=False
    )

    provider: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    customer: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    order_details: Mapped[dict] = mapped_column(
        JSON,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
