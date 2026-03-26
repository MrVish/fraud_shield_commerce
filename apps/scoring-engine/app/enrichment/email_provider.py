import re
from app.enrichment.base import EmailProvider, EmailResult

DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwaway.email",
    "yopmail.com", "sharklasers.com", "guerrillamailblock.com", "grr.la",
    "dispostable.com", "maildrop.cc", "trashmail.com", "tempail.com",
    "10minutemail.com", "temp-mail.org", "fakeinbox.com", "mohmal.com",
    "getnada.com", "emailondeck.com", "burnermail.io", "mailnesia.com",
    "harakirimail.com", "tmail.ws", "tempinbox.com", "mytemp.email",
    "mintemail.com", "filzmail.com", "mailcatch.com", "tempr.email",
    "discard.email", "tmpmail.net", "tmpmail.org", "bupmail.com",
    "guerrillamail.info", "mailexpire.com", "tempmailaddress.com",
}

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "protonmail.com", "mail.com", "zoho.com", "yandex.com",
    "live.com", "msn.com", "me.com", "gmx.com", "inbox.com",
}

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class DisposableListEmailProvider(EmailProvider):
    def __init__(self, extra_domains_file: str | None = None):
        self.disposable_domains = DISPOSABLE_DOMAINS.copy()
        if extra_domains_file:
            try:
                with open(extra_domains_file) as f:
                    for line in f:
                        domain = line.strip().lower()
                        if domain:
                            self.disposable_domains.add(domain)
            except FileNotFoundError:
                pass

    def validate(self, email: str) -> EmailResult:
        email = email.lower().strip()
        domain = email.split("@")[-1] if "@" in email else ""
        is_valid = bool(EMAIL_PATTERN.match(email))
        return EmailResult(
            email=email, is_disposable=domain in self.disposable_domains,
            is_free_provider=domain in FREE_EMAIL_DOMAINS, domain=domain,
            is_valid_format=is_valid, risk_score=self._calculate_risk(domain, is_valid),
        )

    def _calculate_risk(self, domain: str, is_valid: bool) -> int:
        score = 0
        if not is_valid: score += 30
        if domain in self.disposable_domains: score += 40
        if domain in FREE_EMAIL_DOMAINS: score += 5
        return min(score, 100)
