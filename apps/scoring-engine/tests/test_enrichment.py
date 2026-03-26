from app.enrichment.base import IPResult, EmailResult, PhoneResult
from app.enrichment.ip_provider import MaxMindGeoLiteProvider
from app.enrichment.email_provider import DisposableListEmailProvider
from app.enrichment.phone_provider import LibPhoneProvider
from app.enrichment.registry import EnrichmentRegistry


def test_ip_provider_interface():
    provider = MaxMindGeoLiteProvider(db_path=None)
    result = provider.lookup("8.8.8.8")
    assert isinstance(result, IPResult)


def test_email_provider_disposable():
    provider = DisposableListEmailProvider()
    result = provider.validate("test@mailinator.com")
    assert isinstance(result, EmailResult)
    assert result.is_disposable is True


def test_email_provider_valid():
    provider = DisposableListEmailProvider()
    result = provider.validate("user@gmail.com")
    assert isinstance(result, EmailResult)
    assert result.is_disposable is False
    assert result.is_free_provider is True


def test_phone_provider_interface():
    provider = LibPhoneProvider()
    result = provider.validate("+14155552671", "US")
    assert isinstance(result, PhoneResult)
    assert result.is_valid is True


def test_registry_returns_providers():
    registry = EnrichmentRegistry()
    assert registry.ip_provider is not None
    assert registry.email_provider is not None
    assert registry.phone_provider is not None
