from sqlalchemy.orm import Session
from sqlalchemy import func

from app.scoring.signals import SignalExtractor, OrderPayload
from app.scoring.combined_scorer import CombinedScorer
from app.scoring.custom_rules import CustomRuleEngine
from app.enrichment.registry import EnrichmentRegistry
from app.models.merchant import Merchant
from app.models.order_score import OrderScore, ScoringSignal
from app.models.rules import WhitelistBlacklist
from app.services.email_service import EmailService, AlertEmail


class ScoringPipeline:
    def __init__(self, enrichment: EnrichmentRegistry | None = None,
                 email_service: EmailService | None = None):
        self.enrichment = enrichment or EnrichmentRegistry()
        self.extractor = SignalExtractor(self.enrichment)
        self.email_service = email_service or EmailService()

    def score_order(self, db: Session, merchant_id: int, order_payload: OrderPayload) -> dict:
        # 1. Load merchant
        merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if not merchant:
            raise ValueError(f"Merchant {merchant_id} not found")

        # 2. Compute store average order value from recent orders
        avg_result = db.query(func.avg(OrderScore.risk_score)).filter(
            OrderScore.merchant_id == merchant_id
        ).scalar()
        store_avg = float(avg_result) if avg_result else 150.0

        # 3. Extract signals
        signals = self.extractor.extract(order_payload, store_avg_order=store_avg)

        # 4. Score with merchant thresholds
        scorer = CombinedScorer(thresholds=merchant.thresholds_json)
        result = scorer.score(signals)

        # 5. Apply custom rules (whitelist/blacklist from DB)
        rule_engine = CustomRuleEngine()
        wbl_entries = db.query(WhitelistBlacklist).filter(
            WhitelistBlacklist.merchant_id == merchant_id
        ).all()
        for entry in wbl_entries:
            if entry.list_type == "allow":
                rule_engine.add_whitelist(entry.entry_type, entry.value)
            else:
                rule_engine.add_blacklist(entry.entry_type, entry.value)

        custom_action = rule_engine.evaluate(
            email=order_payload.email,
            ip=order_payload.ip_address,
            card_bin=order_payload.card_bin,
        )

        if custom_action == "approve":
            result.final_score = 0
            result.risk_level = "low"
            result.recommendation = "approve"
            result.custom_rule_action = "approve"
        elif custom_action == "block":
            result.final_score = 100
            result.risk_level = "critical"
            result.recommendation = "cancel"
            result.custom_rule_action = "block"

        # 6. Persist OrderScore to DB
        order_score = OrderScore(
            merchant_id=merchant_id,
            shopify_order_id=order_payload.order_id,
            risk_score=result.final_score,
            risk_level=result.risk_level,
            signals_json={
                s.name: {"value": str(s.value), "weight": s.weight, "explanation": s.explanation}
                for s in signals.all_signals()
            },
            recommendation=result.recommendation,
            rule_score=result.rule_score,
            ml_score=result.ml_score,
        )
        db.add(order_score)
        db.commit()
        db.refresh(order_score)

        # Persist individual signals
        for signal in signals.all_signals():
            db.add(ScoringSignal(
                order_score_id=order_score.id,
                signal_name=signal.name,
                signal_value=str(signal.value),
                signal_weight=signal.weight,
                raw_data_json={"explanation": signal.explanation, "category": signal.category},
            ))
        db.commit()

        # 7. Email alert if needed
        settings = merchant.settings_json or {}
        if settings.get("email_alerts_enabled") and result.risk_level in settings.get("alert_on_risk_levels", []):
            digest_email = settings.get("digest_email", "")
            if digest_email:
                self.email_service.send_alert(AlertEmail(
                    to=digest_email,
                    order_id=order_payload.order_id,
                    risk_score=result.final_score,
                    risk_level=result.risk_level,
                    top_signals=result.signal_contributions[:5],
                    shop_domain=merchant.shop_domain,
                ))

        return {
            "order_score_id": order_score.id,
            "order_id": order_payload.order_id,
            "risk_score": result.final_score,
            "risk_level": result.risk_level,
            "recommendation": result.recommendation,
            "rule_score": result.rule_score,
            "ml_score": result.ml_score,
            "signal_contributions": result.signal_contributions,
            "custom_rule_action": result.custom_rule_action,
        }
