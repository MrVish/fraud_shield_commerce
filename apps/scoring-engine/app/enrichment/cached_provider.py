import json
from app.redis_client import RedisClient
from app.enrichment.base import IPProvider, EmailProvider, PhoneProvider, IPResult, EmailResult, PhoneResult
from app.config import settings
from dataclasses import asdict


class CachedIPProvider(IPProvider):
    def __init__(self, inner: IPProvider, redis: RedisClient | None = None):
        self.inner = inner
        self.redis = redis

    def lookup(self, ip: str) -> IPResult:
        if self.redis:
            cached = self.redis.get_cache(f"ip:{ip}")
            if cached:
                return IPResult(**cached)
        result = self.inner.lookup(ip)
        if self.redis:
            self.redis.set_cache(f"ip:{ip}", asdict(result), ttl=86400)  # 24hr
        return result


class CachedEmailProvider(EmailProvider):
    def __init__(self, inner: EmailProvider, redis: RedisClient | None = None):
        self.inner = inner
        self.redis = redis

    def validate(self, email: str) -> EmailResult:
        if self.redis:
            cached = self.redis.get_cache(f"email:{email.lower()}")
            if cached:
                return EmailResult(**cached)
        result = self.inner.validate(email)
        if self.redis:
            self.redis.set_cache(f"email:{email.lower()}", asdict(result), ttl=604800)  # 7 days
        return result


class CachedPhoneProvider(PhoneProvider):
    def __init__(self, inner: PhoneProvider, redis: RedisClient | None = None):
        self.inner = inner
        self.redis = redis

    def validate(self, phone: str, country: str = "US") -> PhoneResult:
        cache_key = f"phone:{phone}:{country}"
        if self.redis:
            cached = self.redis.get_cache(cache_key)
            if cached:
                return PhoneResult(**cached)
        result = self.inner.validate(phone, country)
        if self.redis:
            self.redis.set_cache(cache_key, asdict(result), ttl=604800)  # 7 days
        return result
