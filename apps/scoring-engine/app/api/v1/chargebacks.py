from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.models.merchant import Merchant
from app.models.order_score import OrderScore
from app.models.chargeback import Chargeback

router = APIRouter(prefix="/api/v1")


class ChargebackCreate(BaseModel):
    merchant_id: int
    shopify_order_id: str
    dispute_type: str
    amount: float
    filed_at: Optional[str] = None


class ChargebackResponse(BaseModel):
    id: int
    merchant_id: int
    shopify_order_id: str
    order_score_id: Optional[int] = None
    dispute_type: str
    amount: float
    predicted_correctly: Optional[bool] = None
    filed_at: str


@router.post("/chargebacks", response_model=ChargebackResponse, status_code=201)
def record_chargeback(body: ChargebackCreate, db: Session = Depends(get_db)):
    # Validate merchant exists
    merchant = db.query(Merchant).filter(Merchant.id == body.merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    # Try to link to an existing order score
    order_score = db.query(OrderScore).filter(
        OrderScore.merchant_id == body.merchant_id,
        OrderScore.shopify_order_id == body.shopify_order_id,
    ).first()

    # Determine if the fraud was predicted correctly
    predicted_correctly = None
    order_score_id = None
    if order_score:
        order_score_id = order_score.id
        predicted_correctly = order_score.risk_level in ("high", "critical")

    filed_at = datetime.now(timezone.utc)
    if body.filed_at:
        try:
            filed_at = datetime.fromisoformat(body.filed_at)
        except ValueError:
            pass

    chargeback = Chargeback(
        merchant_id=body.merchant_id,
        shopify_order_id=body.shopify_order_id,
        order_score_id=order_score_id,
        dispute_type=body.dispute_type,
        amount=body.amount,
        predicted_correctly=predicted_correctly,
        filed_at=filed_at,
    )
    db.add(chargeback)
    db.commit()
    db.refresh(chargeback)

    return ChargebackResponse(
        id=chargeback.id,
        merchant_id=chargeback.merchant_id,
        shopify_order_id=chargeback.shopify_order_id,
        order_score_id=chargeback.order_score_id,
        dispute_type=chargeback.dispute_type,
        amount=chargeback.amount,
        predicted_correctly=chargeback.predicted_correctly,
        filed_at=chargeback.filed_at.isoformat(),
    )
