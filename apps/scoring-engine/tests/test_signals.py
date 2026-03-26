from app.scoring.signals import SignalExtractor, OrderPayload, ExtractedSignals
from app.enrichment.registry import EnrichmentRegistry


def _sample_order() -> OrderPayload:
    return OrderPayload(
        order_id="1001", email="test@mailinator.com", ip_address="8.8.8.8",
        shipping_country="US", shipping_state="FL", billing_country="US", billing_state="CA",
        order_total=487.00, currency="USD",
        line_items=[{"title": "Widget", "quantity": 2, "price": "243.50"}],
        customer_id="cust_123", is_first_order=True, phone="+14155552671",
        card_bin="411111", card_last4="1234", card_brand="visa", card_country="US",
        avs_result="N", cvv_result="N", payment_gateway="shopify_payments",
        browser_ip="8.8.8.8", created_at="2026-03-26T10:30:00Z",
    )


def test_signal_extraction_returns_all_categories():
    extractor = SignalExtractor(EnrichmentRegistry())
    signals = extractor.extract(_sample_order(), store_avg_order=152.0)
    assert isinstance(signals, ExtractedSignals)
    assert len(signals.payment) > 0
    assert len(signals.behavioral) > 0
    assert len(signals.geographic) > 0
    assert len(signals.order_pattern) > 0
    assert len(signals.digital_footprint) > 0


def test_signal_extraction_catches_disposable_email():
    extractor = SignalExtractor(EnrichmentRegistry())
    signals = extractor.extract(_sample_order(), store_avg_order=152.0)
    email_signals = {s.name: s for s in signals.digital_footprint}
    assert "disposable_email" in email_signals
    assert email_signals["disposable_email"].value is True


def test_signal_extraction_catches_address_mismatch():
    extractor = SignalExtractor(EnrichmentRegistry())
    signals = extractor.extract(_sample_order(), store_avg_order=152.0)
    geo_signals = {s.name: s for s in signals.geographic}
    assert "address_mismatch" in geo_signals
    assert geo_signals["address_mismatch"].value is True


def test_signal_extraction_detects_high_order_value():
    extractor = SignalExtractor(EnrichmentRegistry())
    signals = extractor.extract(_sample_order(), store_avg_order=152.0)
    pattern_signals = {s.name: s for s in signals.order_pattern}
    assert "order_value_deviation" in pattern_signals
    assert pattern_signals["order_value_deviation"].value > 2.0


def test_total_signal_count():
    extractor = SignalExtractor(EnrichmentRegistry())
    signals = extractor.extract(_sample_order(), store_avg_order=152.0)
    total = signals.total_count()
    assert total >= 15
