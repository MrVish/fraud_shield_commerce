from app.enrichment.base import IPProvider, EmailProvider, PhoneProvider
from app.enrichment.ip_provider import MaxMindGeoLiteProvider
from app.enrichment.email_provider import DisposableListEmailProvider
from app.enrichment.phone_provider import LibPhoneProvider
from app.enrichment.cached_provider import CachedIPProvider, CachedEmailProvider, CachedPhoneProvider
from app.config import settings


class EnrichmentRegistry:
    def __init__(self, enable_cache: bool = True):
        redis = None
        if enable_cache:
            try:
                from app.redis_client import RedisClient
                rc = RedisClient(url=settings.redis_url)
                if rc.ping():
                    redis = rc
            except Exception:
                pass

        ip_base = MaxMindGeoLiteProvider(db_path=settings.maxmind_db_path)
        email_base = DisposableListEmailProvider()
        phone_base = LibPhoneProvider()

        self._ip_provider: IPProvider = CachedIPProvider(ip_base, redis) if redis else ip_base
        self._email_provider: EmailProvider = CachedEmailProvider(email_base, redis) if redis else email_base
        self._phone_provider: PhoneProvider = CachedPhoneProvider(phone_base, redis) if redis else phone_base

    @property
    def ip_provider(self) -> IPProvider:
        return self._ip_provider

    @property
    def email_provider(self) -> EmailProvider:
        return self._email_provider

    @property
    def phone_provider(self) -> PhoneProvider:
        return self._phone_provider
