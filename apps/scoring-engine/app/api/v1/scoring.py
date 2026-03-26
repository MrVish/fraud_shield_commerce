from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.scoring.signals import OrderPayload
from app.services.scoring_pipeline import ScoringPipeline
from app.database import get_db

router = APIRouter(prefix="/api/v1")

pipeline = ScoringPipeline()


class ScoreRequest(BaseModel):
    order_id: str
    merchant_id: int
    email: str
    ip_address: str
    shipping_country: str
    shipping_state: str
    billing_country: str
    billing_state: str
    order_total: float
    currency: str
    line_items: list[dict]
    customer_id: str
    is_first_order: bool
    phone: str = ""
    card_bin: str = ""
    card_last4: str = ""
    card_brand: str = ""
    card_country: str = ""
    avs_result: str = ""
    cvv_result: str = ""
    payment_gateway: str = ""
    browser_ip: str = ""
    created_at: str = ""


class ScoreResponse(BaseModel):
    order_id: str
    risk_score: int
    risk_level: str
    recommendation: str
    rule_score: float
    ml_score: float
    signal_contributions: list[dict]
    custom_rule_action: str | None = None


@router.post("/score", response_model=ScoreResponse)
async def score_order(request: ScoreRequest, db: Session = Depends(get_db)):
    payload = request.model_dump()
    merchant_id = payload.pop("merchant_id")
    order = OrderPayload(**payload)

    result = pipeline.score_order(db, merchant_id, order)

    return ScoreResponse(
        order_id=result["order_id"],
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
        recommendation=result["recommendation"],
        rule_score=result["rule_score"],
        ml_score=result["ml_score"],
        signal_contributions=result["signal_contributions"],
        custom_rule_action=result.get("custom_rule_action"),
    )
