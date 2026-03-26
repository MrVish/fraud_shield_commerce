from sqlalchemy import String, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base
from datetime import datetime


class EnrichmentCache(Base):
    __tablename__ = "enrichment_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    lookup_type: Mapped[str] = mapped_column(String(50), index=True)
    lookup_key: Mapped[str] = mapped_column(String(500), index=True)
    result_json: Mapped[dict] = mapped_column(JSON)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
