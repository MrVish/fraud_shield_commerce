def generate_risk_summary(risk_score: int, risk_level: str, signal_contributions: list[dict]) -> str:
    """Generate a plain-language summary of why an order was flagged (SEON-style)."""
    if not signal_contributions or risk_level == "low":
        return "This order appears safe. No significant risk signals were detected."

    top_signals = signal_contributions[:3]
    signal_descriptions = []
    for s in top_signals:
        name = s.get("signal_name", "").replace("_", " ")
        explanation = s.get("explanation", "")
        points = s.get("points_added", 0)
        if points > 0:
            signal_descriptions.append(explanation)

    if not signal_descriptions:
        return "This order has a moderate risk profile but no individual signal stands out."

    # Build the summary
    if risk_level == "critical":
        opener = "This order is very high risk and should be carefully reviewed."
    elif risk_level == "high":
        opener = "This order shows multiple risk indicators."
    else:
        opener = "This order has some risk factors worth noting."

    reasons = " Additionally, ".join(signal_descriptions[:2])
    if len(signal_descriptions) > 2:
        reasons += f", and {signal_descriptions[2].lower()}"

    return f"{opener} {reasons}."
