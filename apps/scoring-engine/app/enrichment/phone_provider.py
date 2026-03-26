import phonenumbers
from app.enrichment.base import PhoneProvider, PhoneResult


class LibPhoneProvider(PhoneProvider):
    def validate(self, phone: str, country: str = "US") -> PhoneResult:
        try:
            parsed = phonenumbers.parse(phone, country)
            is_valid = phonenumbers.is_valid_number(parsed)
            phone_type_map = {
                0: "landline", 1: "mobile", 2: "landline", 3: "toll_free",
                4: "premium_rate", 5: "shared_cost", 6: "voip", 7: "personal",
                8: "pager", 9: "uan", 10: "unknown",
            }
            number_type = phonenumbers.number_type(parsed)
            phone_type = phone_type_map.get(number_type, "unknown")
            return PhoneResult(
                phone=phone, is_valid=is_valid, country_code=str(parsed.country_code),
                phone_type=phone_type, risk_score=self._calculate_risk(is_valid, phone_type),
            )
        except phonenumbers.NumberParseException:
            return PhoneResult(phone=phone, is_valid=False, risk_score=30)

    def _calculate_risk(self, is_valid: bool, phone_type: str) -> int:
        score = 0
        if not is_valid: score += 30
        if phone_type == "voip": score += 15
        return min(score, 100)
