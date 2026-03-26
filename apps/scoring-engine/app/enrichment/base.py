from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class IPResult:
    ip: str
    country: str = "unknown"
    city: str = "unknown"
    latitude: float = 0.0
    longitude: float = 0.0
    is_vpn: bool = False
    is_proxy: bool = False
    is_tor: bool = False
    isp: str = "unknown"
    risk_score: int = 0


@dataclass
class EmailResult:
    email: str
    is_disposable: bool = False
    is_free_provider: bool = False
    domain: str = ""
    domain_age_days: int | None = None
    is_valid_format: bool = True
    risk_score: int = 0


@dataclass
class PhoneResult:
    phone: str
    is_valid: bool = False
    country_code: str = ""
    phone_type: str = "unknown"
    carrier: str = "unknown"
    risk_score: int = 0


class IPProvider(ABC):
    @abstractmethod
    def lookup(self, ip: str) -> IPResult:
        pass


class EmailProvider(ABC):
    @abstractmethod
    def validate(self, email: str) -> EmailResult:
        pass


class PhoneProvider(ABC):
    @abstractmethod
    def validate(self, phone: str, country: str = "US") -> PhoneResult:
        pass
