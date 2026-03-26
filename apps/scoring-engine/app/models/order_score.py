from sqlalchemy import String, Integer, Float, JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class OrderScore(Base, TimestampMixin):
    __tablename__ = "order_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    shopify_order_id: Mapped[str] = mapped_column(String(50), index=True)
    risk_score: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(20))
    signals_json: Mapped[dict] = mapped_column(JSON)
    recommendation: Mapped[str] = mapped_column(String(50))
    order_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    rule_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ml_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    merchant = relationship("Merchant", back_populates="order_scores")
    signals = relationship("ScoringSignal", back_populates="order_score", cascade="all, delete-orphan")
    override = relationship("MerchantOverride", back_populates="order_score", uselist=False)


class ScoringSignal(Base):
    __tablename__ = "scoring_signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_score_id: Mapped[int] = mapped_column(ForeignKey("order_scores.id"), index=True)
    signal_name: Mapped[str] = mapped_column(String(100))
    signal_value: Mapped[str] = mapped_column(Text)
    signal_weight: Mapped[float] = mapped_column(Float)
    raw_data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    order_score = relationship("OrderScore", back_populates="signals")
