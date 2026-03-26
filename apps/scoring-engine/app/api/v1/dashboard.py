from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.database import get_db
from app.models.merchant import Merchant
from app.models.order_score import OrderScore, ScoringSignal
from app.models.chargeback import Chargeback
from app.models.rules import MerchantOverride, WhitelistBlacklist
from app.services.risk_summary import generate_risk_summary

router = APIRouter(prefix="/api/v1/merchants")


# ── Schemas ──────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_orders: int
    flagged_orders: int
    avg_score: float
    chargeback_count: int
    chargeback_amount: float
    score_distribution: list[dict]
    trend_data: list[dict]
    revenue_protected: float = 0.0
    chargeback_rate: float = 0.0
    chargeback_health: str = "good"


class OrderSummary(BaseModel):
    id: int
    shopify_order_id: str
    risk_score: int
    risk_level: str
    recommendation: str
    created_at: Optional[str] = None


class PaginatedOrders(BaseModel):
    page: int
    limit: int
    total: int
    orders: list[OrderSummary]


class OrderDetail(BaseModel):
    id: int
    shopify_order_id: str
    risk_score: int
    risk_level: str
    recommendation: str
    rule_score: Optional[float] = None
    ml_score: Optional[float] = None
    signals_json: Optional[dict] = None
    signals: list[dict]
    override: Optional[dict] = None
    created_at: Optional[str] = None
    risk_summary: str = ""


class OverrideRequest(BaseModel):
    action: str
    reason: str = ""


class OverrideResponse(BaseModel):
    id: int
    order_score_id: int
    original_recommendation: str
    override_action: str
    reason: Optional[str] = None


class SettingsResponse(BaseModel):
    settings: dict
    thresholds: dict


class SettingsUpdate(BaseModel):
    settings: Optional[dict] = None
    thresholds: Optional[dict] = None


# ── Helpers ──────────────────────────────────────────────────────────

def _get_merchant_or_404(db: Session, merchant_id: int) -> Merchant:
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return merchant


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/{merchant_id}/dashboard", response_model=DashboardStats)
def get_dashboard(merchant_id: int, days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)):
    _get_merchant_or_404(db, merchant_id)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # All orders in period
    orders = db.query(OrderScore).filter(
        OrderScore.merchant_id == merchant_id,
        OrderScore.created_at >= cutoff,
    ).all()

    total_orders = len(orders)
    flagged_orders = sum(1 for o in orders if o.risk_level in ("high", "critical"))
    avg_score = round(sum(o.risk_score for o in orders) / total_orders, 1) if total_orders else 0.0

    # Chargebacks
    chargebacks = db.query(Chargeback).filter(
        Chargeback.merchant_id == merchant_id,
        Chargeback.filed_at >= cutoff,
    ).all()
    chargeback_count = len(chargebacks)
    chargeback_amount = round(sum(c.amount for c in chargebacks), 2)

    # Score distribution (buckets: 0-20, 21-40, 41-60, 61-80, 81-100)
    buckets = [
        {"label": "0-20", "min": 0, "max": 20, "count": 0},
        {"label": "21-40", "min": 21, "max": 40, "count": 0},
        {"label": "41-60", "min": 41, "max": 60, "count": 0},
        {"label": "61-80", "min": 61, "max": 80, "count": 0},
        {"label": "81-100", "min": 81, "max": 100, "count": 0},
    ]
    for order in orders:
        for bucket in buckets:
            if bucket["min"] <= order.risk_score <= bucket["max"]:
                bucket["count"] += 1
                break
    score_distribution = [{"label": b["label"], "count": b["count"]} for b in buckets]

    # Trend data: daily averages
    daily: dict[str, list[int]] = {}
    for order in orders:
        if order.created_at:
            day_str = order.created_at.strftime("%Y-%m-%d")
        else:
            day_str = "unknown"
        daily.setdefault(day_str, []).append(order.risk_score)

    trend_data = sorted([
        {"date": day, "avg_score": round(sum(scores) / len(scores), 1), "count": len(scores)}
        for day, scores in daily.items()
    ], key=lambda x: x["date"])

    # Revenue protected: sum of order_total for high/critical risk orders
    revenue_protected = round(
        sum(o.order_total for o in orders if o.risk_level in ("high", "critical") and o.order_total), 2
    )

    # Chargeback rate and health
    chargeback_rate = round((chargeback_count / total_orders * 100), 2) if total_orders > 0 else 0.0
    if chargeback_rate < 0.4:
        chargeback_health = "good"
    elif chargeback_rate <= 0.6:
        chargeback_health = "at_risk"
    else:
        chargeback_health = "elevated"

    return DashboardStats(
        total_orders=total_orders,
        flagged_orders=flagged_orders,
        avg_score=avg_score,
        chargeback_count=chargeback_count,
        chargeback_amount=chargeback_amount,
        score_distribution=score_distribution,
        trend_data=trend_data,
        revenue_protected=revenue_protected,
        chargeback_rate=chargeback_rate,
        chargeback_health=chargeback_health,
    )


@router.get("/{merchant_id}/orders", response_model=PaginatedOrders)
def list_orders(
    merchant_id: int,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    risk_level: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    _get_merchant_or_404(db, merchant_id)

    query = db.query(OrderScore).filter(OrderScore.merchant_id == merchant_id)
    if risk_level:
        query = query.filter(OrderScore.risk_level == risk_level)

    total = query.count()
    orders = query.order_by(OrderScore.id.desc()).offset((page - 1) * limit).limit(limit).all()

    return PaginatedOrders(
        page=page,
        limit=limit,
        total=total,
        orders=[
            OrderSummary(
                id=o.id,
                shopify_order_id=o.shopify_order_id,
                risk_score=o.risk_score,
                risk_level=o.risk_level,
                recommendation=o.recommendation,
                created_at=o.created_at.isoformat() if o.created_at else None,
            )
            for o in orders
        ],
    )


@router.get("/{merchant_id}/orders/{order_id}", response_model=OrderDetail)
def get_order_detail(merchant_id: int, order_id: int, db: Session = Depends(get_db)):
    _get_merchant_or_404(db, merchant_id)

    order = db.query(OrderScore).filter(
        OrderScore.id == order_id,
        OrderScore.merchant_id == merchant_id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    signals = db.query(ScoringSignal).filter(ScoringSignal.order_score_id == order.id).all()

    override_data = None
    if order.override:
        override_data = {
            "id": order.override.id,
            "override_action": order.override.override_action,
            "original_recommendation": order.override.original_recommendation,
            "reason": order.override.reason,
        }

    # Generate risk summary from stored value or compute on the fly
    risk_summary = order.risk_summary or ""
    if not risk_summary:
        signal_contributions = [
            {"signal_name": s.signal_name, "explanation": (s.raw_data_json or {}).get("explanation", ""), "points_added": s.signal_weight}
            for s in signals if s.signal_weight > 0
        ]
        risk_summary = generate_risk_summary(order.risk_score, order.risk_level, signal_contributions)

    return OrderDetail(
        id=order.id,
        shopify_order_id=order.shopify_order_id,
        risk_score=order.risk_score,
        risk_level=order.risk_level,
        recommendation=order.recommendation,
        rule_score=order.rule_score,
        ml_score=order.ml_score,
        signals_json=order.signals_json,
        signals=[
            {
                "name": s.signal_name,
                "value": s.signal_value,
                "weight": s.signal_weight,
                "raw_data": s.raw_data_json,
            }
            for s in signals
        ],
        override=override_data,
        created_at=order.created_at.isoformat() if order.created_at else None,
        risk_summary=risk_summary,
    )


@router.post("/{merchant_id}/orders/{order_score_id}/override", response_model=OverrideResponse)
def override_order(
    merchant_id: int,
    order_score_id: int,
    body: OverrideRequest,
    db: Session = Depends(get_db),
):
    _get_merchant_or_404(db, merchant_id)

    order = db.query(OrderScore).filter(
        OrderScore.id == order_score_id,
        OrderScore.merchant_id == merchant_id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    existing = db.query(MerchantOverride).filter(
        MerchantOverride.order_score_id == order_score_id
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Override already exists for this order")

    override = MerchantOverride(
        merchant_id=merchant_id,
        order_score_id=order_score_id,
        original_recommendation=order.recommendation,
        override_action=body.action,
        reason=body.reason,
    )
    db.add(override)

    # Update the order recommendation to reflect the override
    order.recommendation = body.action
    db.commit()
    db.refresh(override)

    return OverrideResponse(
        id=override.id,
        order_score_id=override.order_score_id,
        original_recommendation=override.original_recommendation,
        override_action=override.override_action,
        reason=override.reason,
    )


@router.get("/{merchant_id}/settings", response_model=SettingsResponse)
def get_settings(merchant_id: int, db: Session = Depends(get_db)):
    merchant = _get_merchant_or_404(db, merchant_id)
    return SettingsResponse(
        settings=merchant.settings_json or {},
        thresholds=merchant.thresholds_json or {},
    )


@router.patch("/{merchant_id}/settings", response_model=SettingsResponse)
def update_settings(merchant_id: int, body: SettingsUpdate, db: Session = Depends(get_db)):
    merchant = _get_merchant_or_404(db, merchant_id)

    if body.settings is not None:
        current = dict(merchant.settings_json or {})
        current.update(body.settings)
        merchant.settings_json = current

    if body.thresholds is not None:
        current = dict(merchant.thresholds_json or {})
        current.update(body.thresholds)
        merchant.thresholds_json = current

    db.commit()
    db.refresh(merchant)

    return SettingsResponse(
        settings=merchant.settings_json or {},
        thresholds=merchant.thresholds_json or {},
    )


# ── Whitelist / Blacklist ────────────────────────────────────────────

class WBLEntry(BaseModel):
    entry_type: str  # email, ip, bin
    value: str
    list_type: str  # allow, block


class WBLResponse(BaseModel):
    id: int
    entry_type: str
    value: str
    list_type: str


@router.get("/{merchant_id}/lists", response_model=list[WBLResponse])
def get_lists(merchant_id: int, db: Session = Depends(get_db)):
    _get_merchant_or_404(db, merchant_id)
    entries = db.query(WhitelistBlacklist).filter(
        WhitelistBlacklist.merchant_id == merchant_id
    ).all()
    return [
        WBLResponse(id=e.id, entry_type=e.entry_type, value=e.value, list_type=e.list_type)
        for e in entries
    ]


@router.post("/{merchant_id}/lists", response_model=WBLResponse, status_code=201)
def add_list_entry(merchant_id: int, body: WBLEntry, db: Session = Depends(get_db)):
    _get_merchant_or_404(db, merchant_id)
    entry = WhitelistBlacklist(
        merchant_id=merchant_id,
        entry_type=body.entry_type,
        value=body.value,
        list_type=body.list_type,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return WBLResponse(id=entry.id, entry_type=entry.entry_type, value=entry.value, list_type=entry.list_type)


@router.delete("/{merchant_id}/lists/{entry_id}", status_code=204)
def delete_list_entry(merchant_id: int, entry_id: int, db: Session = Depends(get_db)):
    _get_merchant_or_404(db, merchant_id)
    entry = db.query(WhitelistBlacklist).filter(
        WhitelistBlacklist.id == entry_id,
        WhitelistBlacklist.merchant_id == merchant_id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()
    return None
