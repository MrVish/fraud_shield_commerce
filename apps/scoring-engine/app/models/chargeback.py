from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
from datetime import datetime


class Chargeback(Base):
    __tablename__ = "chargebacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    shopify_order_id: Mapped[str] = mapped_column(String(50), index=True)
    order_score_id: Mapped[int | None] = mapped_column(ForeignKey("order_scores.id"), nullable=True)
    dispute_type: Mapped[str] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column(Float)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    predicted_correctly: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    filed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    merchant = relationship("Merchant")
    order_score = relationship("OrderScore")
