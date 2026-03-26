from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "ShieldCommerce Scoring Engine"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql://shield:localdev@localhost:5432/shieldcommerce"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Internal API key for Remix -> FastAPI auth
    internal_api_key: str = "dev-key"

    # CORS allowed origins (comma-separated, used when debug=False)
    allowed_origins: str = "https://shieldcommerce.app"

    # Encryption
    encryption_key: str = "change-me-in-production-32-bytes!"

    # SendGrid
    sendgrid_api_key: str = ""
    alert_from_email: str = "alerts@shieldcommerce.app"

    # Scoring
    rule_weight: float = 0.5
    ml_weight: float = 0.5

    # MaxMind
    maxmind_db_path: str = "data/GeoLite2-City.mmdb"

    model_config = {"env_file": ".env", "env_prefix": "SC_"}


settings = Settings()
