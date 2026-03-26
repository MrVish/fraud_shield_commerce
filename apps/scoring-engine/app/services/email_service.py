from dataclasses import dataclass
from app.config import settings


@dataclass
class AlertEmail:
    to: str
    order_id: str
    risk_score: int
    risk_level: str
    top_signals: list[dict]
    shop_domain: str

    def render_html(self) -> str:
        signals_html = "".join(
            f"<tr><td>{s['signal_name']}</td><td>+{s['points_added']}</td><td>{s['explanation']}</td></tr>"
            for s in self.top_signals
        )
        color = {"low": "#4CAF50", "medium": "#FFC107", "high": "#F44336", "critical": "#B71C1C"}.get(self.risk_level, "#999")
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: {color};">ShieldCommerce Alert: {self.risk_level.upper()} Risk Order</h2>
            <p>Order <strong>#{self.order_id}</strong> on <strong>{self.shop_domain}</strong> scored
            <strong style="color: {color};">{self.risk_level}</strong> risk ({self.risk_score}/100).</p>
            <h3>Top Risk Signals</h3>
            <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
                <tr style="background: #f5f5f5;"><th>Signal</th><th>Points</th><th>Details</th></tr>
                {signals_html}
            </table>
            <p style="margin-top: 20px;">
                <a href="https://{self.shop_domain}/admin/orders/{self.order_id}"
                   style="background: {color}; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">
                    Review Order in Shopify
                </a>
            </p>
            <p style="color: #999; font-size: 12px; margin-top: 30px;">Sent by ShieldCommerce.</p>
        </body>
        </html>
        """

    def render_subject(self) -> str:
        return f"[ShieldCommerce] {self.risk_level.upper()} Risk: Order #{self.order_id} (Score: {self.risk_score})"


class EmailService:
    def __init__(self):
        self.api_key = settings.sendgrid_api_key
        self.from_email = settings.alert_from_email

    def send_alert(self, alert: AlertEmail) -> bool:
        if not self.api_key:
            print(f"[EmailService] SendGrid not configured. Would send alert for order {alert.order_id} to {alert.to}")
            return False
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content
            sg = sendgrid.SendGridAPIClient(api_key=self.api_key)
            mail = Mail(
                from_email=Email(self.from_email, "ShieldCommerce"),
                to_emails=To(alert.to),
                subject=alert.render_subject(),
                html_content=Content("text/html", alert.render_html()),
            )
            sg.client.mail.send.post(request_body=mail.get())
            return True
        except Exception as e:
            print(f"[EmailService] Failed: {e}")
            return False
