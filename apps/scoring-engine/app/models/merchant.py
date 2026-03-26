from sqlalchemy import String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

DEFAULT_THRESHOLDS = {
    "low_max": 30,
    "medium_max": 60,
    "high_max": 85,
    "auto_approve_below": 30,
    "auto_cancel_above": 86,
}

DEFAULT_SETTINGS = {
    "email_alerts_enabled": True,
    "alert_on_risk_levels": ["high", "critical"],
    "digest_frequency": "daily",
    "digest_email": "",
}


class Merchant(Base, TimestampMixin):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    plan_tier: Mapped[str] = mapped_column(String(50), default="starter")
    settings_json: Mapped[dict] = mapped_column(JSON, default=lambda: DEFAULT_SETTINGS.copy())
    thresholds_json: Mapped[dict] = mapped_column(JSON, default=lambda: DEFAULT_THRESHOLDS.copy())

    order_scores = relationship("OrderScore", back_populates="merchant", lazy="dynamic")
    custom_rules = relationship("CustomRule", back_populates="merchant", lazy="dynamic")
    whitelist_blacklist = relationship("WhitelistBlacklist", back_populates="merchant", lazy="dynamic")
    daily_digests = relationship("DailyDigest", back_populates="merchant", lazy="dynamic")
