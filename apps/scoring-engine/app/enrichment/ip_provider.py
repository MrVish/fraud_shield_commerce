import os
from app.enrichment.base import IPProvider, IPResult


class MaxMindGeoLiteProvider(IPProvider):
    def __init__(self, db_path: str | None = None):
        self.reader = None
        if db_path and os.path.exists(db_path):
            try:
                import maxminddb
                self.reader = maxminddb.open_database(db_path)
            except Exception:
                pass

    def lookup(self, ip: str) -> IPResult:
        if not self.reader:
            return IPResult(ip=ip)
        try:
            data = self.reader.get(ip)
            if not data:
                return IPResult(ip=ip)
            country = data.get("country", {}).get("iso_code", "unknown")
            city_data = data.get("city", {}).get("names", {})
            city = city_data.get("en", "unknown")
            location = data.get("location", {})
            return IPResult(
                ip=ip, country=country, city=city,
                latitude=location.get("latitude", 0.0),
                longitude=location.get("longitude", 0.0),
            )
        except Exception:
            return IPResult(ip=ip)

    def __del__(self):
        if self.reader:
            self.reader.close()
