"""Tests for cached enrichment providers (without Redis - passthrough mode)."""
import pytest
from unittest.mock import MagicMock
from app.enrichment.base import IPResult, EmailResult, PhoneResult
from app.enrichment.cached_provider import CachedIPProvider, CachedEmailProvider, CachedPhoneProvider


class TestCachedIPProvider:
    def test_passthrough_without_redis(self):
        """Without Redis, calls go directly to inner provider."""
        inner = MagicMock()
        inner.lookup.return_value = IPResult(ip="1.2.3.4", country="US", city="NYC")
        cached = CachedIPProvider(inner, redis=None)

        result = cached.lookup("1.2.3.4")
        assert result.ip == "1.2.3.4"
        assert result.country == "US"
        inner.lookup.assert_called_once_with("1.2.3.4")

    def test_cache_hit(self):
        """With Redis and cached data, inner provider is not called."""
        inner = MagicMock()
        redis = MagicMock()
        redis.get_cache.return_value = {"ip": "1.2.3.4", "country": "US", "city": "NYC",
                                         "latitude": 0.0, "longitude": 0.0, "is_vpn": False,
                                         "is_proxy": False, "is_tor": False, "isp": "test", "risk_score": 0}
        cached = CachedIPProvider(inner, redis=redis)

        result = cached.lookup("1.2.3.4")
        assert result.ip == "1.2.3.4"
        inner.lookup.assert_not_called()

    def test_cache_miss_stores_result(self):
        """On cache miss, result is stored in Redis."""
        inner = MagicMock()
        inner.lookup.return_value = IPResult(ip="1.2.3.4", country="US")
        redis = MagicMock()
        redis.get_cache.return_value = None
        cached = CachedIPProvider(inner, redis=redis)

        result = cached.lookup("1.2.3.4")
        assert result.country == "US"
        redis.set_cache.assert_called_once()
        args = redis.set_cache.call_args
        assert args[0][0] == "ip:1.2.3.4"
        assert args[1]["ttl"] == 86400


class TestCachedEmailProvider:
    def test_passthrough_without_redis(self):
        inner = MagicMock()
        inner.validate.return_value = EmailResult(email="a@b.com", is_disposable=False)
        cached = CachedEmailProvider(inner, redis=None)

        result = cached.validate("a@b.com")
        assert result.email == "a@b.com"
        inner.validate.assert_called_once()

    def test_cache_hit(self):
        inner = MagicMock()
        redis = MagicMock()
        redis.get_cache.return_value = {"email": "a@b.com", "is_disposable": False,
                                         "is_free_provider": True, "domain": "b.com",
                                         "domain_age_days": None, "is_valid_format": True, "risk_score": 0}
        cached = CachedEmailProvider(inner, redis=redis)

        result = cached.validate("A@B.com")
        assert result.email == "a@b.com"
        inner.validate.assert_not_called()
        redis.get_cache.assert_called_with("email:a@b.com")


class TestCachedPhoneProvider:
    def test_passthrough_without_redis(self):
        inner = MagicMock()
        inner.validate.return_value = PhoneResult(phone="+1234", is_valid=True)
        cached = CachedPhoneProvider(inner, redis=None)

        result = cached.validate("+1234", "US")
        assert result.phone == "+1234"
        inner.validate.assert_called_once_with("+1234", "US")

    def test_cache_miss_stores_with_country_key(self):
        inner = MagicMock()
        inner.validate.return_value = PhoneResult(phone="+1234", is_valid=True)
        redis = MagicMock()
        redis.get_cache.return_value = None
        cached = CachedPhoneProvider(inner, redis=redis)

        cached.validate("+1234", "GB")
        redis.set_cache.assert_called_once()
        assert redis.set_cache.call_args[0][0] == "phone:+1234:GB"
