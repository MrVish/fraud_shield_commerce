from dataclasses import dataclass, field
from app.enrichment.registry import EnrichmentRegistry


@dataclass
class OrderPayload:
    order_id: str
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


@dataclass
class Signal:
    name: str
    value: object
    weight: float
    category: str
    explanation: str = ""


@dataclass
class ExtractedSignals:
    payment: list[Signal] = field(default_factory=list)
    behavioral: list[Signal] = field(default_factory=list)
    geographic: list[Signal] = field(default_factory=list)
    order_pattern: list[Signal] = field(default_factory=list)
    digital_footprint: list[Signal] = field(default_factory=list)

    def all_signals(self) -> list[Signal]:
        return self.payment + self.behavioral + self.geographic + self.order_pattern + self.digital_footprint

    def total_count(self) -> int:
        return len(self.all_signals())


class SignalExtractor:
    def __init__(self, enrichment: EnrichmentRegistry):
        self.enrichment = enrichment

    def extract(self, order: OrderPayload, store_avg_order: float = 100.0) -> ExtractedSignals:
        signals = ExtractedSignals()
        signals.payment = self._extract_payment(order)
        signals.behavioral = self._extract_behavioral(order)
        signals.geographic = self._extract_geographic(order)
        signals.order_pattern = self._extract_order_pattern(order, store_avg_order)
        signals.digital_footprint = self._extract_digital_footprint(order)
        return signals

    def _extract_payment(self, order: OrderPayload) -> list[Signal]:
        signals = []
        avs_fail = order.avs_result in ("N", "A", "Z", "")
        signals.append(Signal(name="avs_mismatch", value=avs_fail, weight=8.0, category="payment",
            explanation=f"AVS result: {order.avs_result or 'not provided'}"))
        cvv_fail = order.cvv_result in ("N", "")
        signals.append(Signal(name="cvv_failure", value=cvv_fail, weight=6.0, category="payment",
            explanation=f"CVV result: {order.cvv_result or 'not provided'}"))
        if order.card_country and order.billing_country:
            mismatch = order.card_country.upper() != order.billing_country.upper()
            signals.append(Signal(name="card_country_mismatch", value=mismatch, weight=12.0, category="payment",
                explanation=f"Card issued in {order.card_country}, billing in {order.billing_country}"))
        signals.append(Signal(name="card_brand", value=order.card_brand, weight=0.0, category="payment",
            explanation=f"Card brand: {order.card_brand}"))
        return signals

    def _extract_behavioral(self, order: OrderPayload) -> list[Signal]:
        signals = []
        signals.append(Signal(name="first_time_customer", value=order.is_first_order, weight=12.0, category="behavioral",
            explanation="First order from this customer" if order.is_first_order else "Returning customer"))
        item_count = sum(item.get("quantity", 1) for item in order.line_items)
        signals.append(Signal(name="item_count", value=item_count, weight=0.0, category="behavioral",
            explanation=f"{item_count} items in order"))
        unique_products = len(order.line_items)
        signals.append(Signal(name="unique_products", value=unique_products, weight=0.0, category="behavioral",
            explanation=f"{unique_products} unique products"))
        return signals

    def _extract_geographic(self, order: OrderPayload) -> list[Signal]:
        signals = []
        state_mismatch = (order.shipping_state and order.billing_state
            and order.shipping_state.upper() != order.billing_state.upper())
        country_mismatch = (order.shipping_country and order.billing_country
            and order.shipping_country.upper() != order.billing_country.upper())
        signals.append(Signal(name="address_mismatch", value=state_mismatch or country_mismatch, weight=15.0,
            category="geographic",
            explanation=f"Billing: {order.billing_state}, {order.billing_country}; Shipping: {order.shipping_state}, {order.shipping_country}"))
        ip_result = self.enrichment.ip_provider.lookup(order.ip_address)
        ip_country_mismatch = (ip_result.country != "unknown" and order.shipping_country
            and ip_result.country.upper() != order.shipping_country.upper())
        signals.append(Signal(name="ip_country_mismatch", value=ip_country_mismatch, weight=10.0, category="geographic",
            explanation=f"IP country: {ip_result.country}; Shipping: {order.shipping_country}"))
        signals.append(Signal(name="vpn_detected", value=ip_result.is_vpn, weight=18.0, category="geographic",
            explanation="VPN/proxy detected" if ip_result.is_vpn else "No VPN/proxy detected"))
        signals.append(Signal(name="tor_detected", value=ip_result.is_tor, weight=25.0, category="geographic",
            explanation="Tor exit node detected" if ip_result.is_tor else "Not a Tor exit node"))
        return signals

    def _extract_order_pattern(self, order: OrderPayload, store_avg: float) -> list[Signal]:
        signals = []
        deviation = order.order_total / store_avg if store_avg > 0 else 1.0
        signals.append(Signal(name="order_value_deviation", value=round(deviation, 2), weight=11.0,
            category="order_pattern",
            explanation=f"Order ${order.order_total:.2f} is {deviation:.1f}x store average (${store_avg:.2f})"))
        is_high_value = order.order_total > 500
        signals.append(Signal(name="high_value_order", value=is_high_value, weight=5.0, category="order_pattern",
            explanation=f"Order total: ${order.order_total:.2f}" + (" (high value)" if is_high_value else "")))
        signals.append(Signal(name="currency", value=order.currency, weight=0.0, category="order_pattern",
            explanation=f"Currency: {order.currency}"))
        return signals

    def _extract_digital_footprint(self, order: OrderPayload) -> list[Signal]:
        signals = []
        email_result = self.enrichment.email_provider.validate(order.email)
        signals.append(Signal(name="disposable_email", value=email_result.is_disposable, weight=20.0,
            category="digital_footprint",
            explanation=f"Disposable email domain: {email_result.domain}" if email_result.is_disposable else f"Email domain: {email_result.domain}"))
        signals.append(Signal(name="free_email_provider", value=email_result.is_free_provider, weight=5.0,
            category="digital_footprint",
            explanation=f"Free email provider ({email_result.domain})" if email_result.is_free_provider else f"Custom domain ({email_result.domain})"))
        signals.append(Signal(name="invalid_email_format", value=not email_result.is_valid_format, weight=15.0,
            category="digital_footprint",
            explanation="Invalid email format" if not email_result.is_valid_format else "Valid email format"))
        if order.phone:
            phone_result = self.enrichment.phone_provider.validate(order.phone)
            signals.append(Signal(name="phone_invalid", value=not phone_result.is_valid, weight=10.0,
                category="digital_footprint",
                explanation=f"Phone: {phone_result.phone_type}" if phone_result.is_valid else "Invalid phone number"))
            signals.append(Signal(name="voip_phone", value=phone_result.phone_type == "voip", weight=12.0,
                category="digital_footprint",
                explanation="VoIP phone number detected" if phone_result.phone_type == "voip" else f"Phone type: {phone_result.phone_type}"))
        return signals
