from app.services.email_service import AlertEmail


def test_alert_email_rendering():
    email = AlertEmail(
        to="merchant@store.com", order_id="1042", risk_score=73, risk_level="high",
        top_signals=[
            {"signal_name": "vpn_detected", "points_added": 18, "explanation": "VPN detected"},
            {"signal_name": "address_mismatch", "points_added": 15, "explanation": "States differ"},
        ],
        shop_domain="cool-store.myshopify.com",
    )
    html = email.render_html()
    assert "1042" in html
    assert "73" in html
    assert "high" in html.lower()
    assert "VPN detected" in html


def test_alert_email_subject():
    email = AlertEmail(
        to="test@test.com", order_id="999", risk_score=92, risk_level="critical",
        top_signals=[], shop_domain="store.myshopify.com",
    )
    subject = email.render_subject()
    assert "CRITICAL" in subject
    assert "999" in subject
    assert "92" in subject
