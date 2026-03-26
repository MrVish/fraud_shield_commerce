from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.merchant import Merchant, DEFAULT_SETTINGS, DEFAULT_THRESHOLDS

router = APIRouter(prefix="/api/v1")


class MerchantCreate(BaseModel):
    shop_domain: str
    access_token_encrypted: str
    plan_tier: str = "starter"
    settings: Optional[dict] = None
    thresholds: Optional[dict] = None


class MerchantResponse(BaseModel):
    id: int
    shop_domain: str
    plan_tier: str
    settings: dict
    thresholds: dict


@router.post("/merchants", response_model=MerchantResponse, status_code=201)
def register_merchant(body: MerchantCreate, db: Session = Depends(get_db)):
    """Register or upsert a merchant (called during Shopify app install)."""
    existing = db.query(Merchant).filter(Merchant.shop_domain == body.shop_domain).first()

    if existing:
        # Upsert: update token and plan
        existing.access_token_encrypted = body.access_token_encrypted
        existing.plan_tier = body.plan_tier
        if body.settings:
            current = existing.settings_json or {}
            current.update(body.settings)
            existing.settings_json = current
        if body.thresholds:
            current = existing.thresholds_json or {}
            current.update(body.thresholds)
            existing.thresholds_json = current
        db.commit()
        db.refresh(existing)
        merchant = existing
    else:
        merchant = Merchant(
            shop_domain=body.shop_domain,
            access_token_encrypted=body.access_token_encrypted,
            plan_tier=body.plan_tier,
            settings_json=body.settings or DEFAULT_SETTINGS.copy(),
            thresholds_json=body.thresholds or DEFAULT_THRESHOLDS.copy(),
        )
        db.add(merchant)
        db.commit()
        db.refresh(merchant)

    return MerchantResponse(
        id=merchant.id,
        shop_domain=merchant.shop_domain,
        plan_tier=merchant.plan_tier,
        settings=merchant.settings_json or {},
        thresholds=merchant.thresholds_json or {},
    )
