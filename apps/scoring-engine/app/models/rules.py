from sqlalchemy import String, Integer, JSON, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class CustomRule(Base, TimestampMixin):
    __tablename__ = "custom_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    rule_name: Mapped[str] = mapped_column(String(255))
    conditions_json: Mapped[dict] = mapped_column(JSON)
    action: Mapped[str] = mapped_column(String(50))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    merchant = relationship("Merchant", back_populates="custom_rules")


class WhitelistBlacklist(Base, TimestampMixin):
    __tablename__ = "whitelist_blacklist"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    entry_type: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(500))
    list_type: Mapped[str] = mapped_column(String(10))

    merchant = relationship("Merchant", back_populates="whitelist_blacklist")


class MerchantOverride(Base, TimestampMixin):
    __tablename__ = "merchant_overrides"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    order_score_id: Mapped[int] = mapped_column(ForeignKey("order_scores.id"), unique=True)
    original_recommendation: Mapped[str] = mapped_column(String(50))
    override_action: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    merchant = relationship("Merchant")
    order_score = relationship("OrderScore", back_populates="override")
