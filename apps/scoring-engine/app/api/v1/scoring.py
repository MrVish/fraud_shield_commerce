from fastapi import APIRouter
from pydantic import BaseModel
from app.scoring.signals import SignalExtractor, OrderPayload
from app.scoring.combined_scorer import CombinedScorer
from app.enrichment.registry import EnrichmentRegistry

router = APIRouter(prefix="/api/v1")

enrichment = EnrichmentRegistry()
extractor = SignalExtractor(enrichment)
scorer = CombinedScorer()


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


@router.post("/score", response_model=ScoreResponse)
async def score_order(request: ScoreRequest):
    payload = request.model_dump()
    payload.pop("merchant_id", None)
    order = OrderPayload(**payload)
    signals = extractor.extract(order, store_avg_order=150.0)
    result = scorer.score(signals)
    return ScoreResponse(
        order_id=request.order_id, risk_score=result.final_score,
        risk_level=result.risk_level, recommendation=result.recommendation,
        rule_score=result.rule_score, ml_score=result.ml_score,
        signal_contributions=result.signal_contributions,
    )
