from app.enrichment.base import IPProvider, EmailProvider, PhoneProvider
from app.enrichment.ip_provider import MaxMindGeoLiteProvider
from app.enrichment.email_provider import DisposableListEmailProvider
from app.enrichment.phone_provider import LibPhoneProvider
from app.config import settings


class EnrichmentRegistry:
    def __init__(self):
        self._ip_provider: IPProvider = MaxMindGeoLiteProvider(db_path=settings.maxmind_db_path)
        self._email_provider: EmailProvider = DisposableListEmailProvider()
        self._phone_provider: PhoneProvider = LibPhoneProvider()

    @property
    def ip_provider(self) -> IPProvider:
        return self._ip_provider

    @property
    def email_provider(self) -> EmailProvider:
        return self._email_provider

    @property
    def phone_provider(self) -> PhoneProvider:
        return self._phone_provider
