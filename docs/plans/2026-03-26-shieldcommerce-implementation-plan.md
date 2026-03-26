# ShieldCommerce Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a production-ready Shopify fraud intelligence app with real-time ML scoring, transparent signal breakdowns, and an analytics dashboard — all deployed on DigitalOcean.

**Architecture:** Dual-stack — Remix (Shopify embedded UI + auth) communicates with Python FastAPI (scoring engine) via internal REST API. PostgreSQL for persistence, Redis for caching/queuing. All hosted on DigitalOcean App Platform.

**Tech Stack:** Remix + Polaris + App Bridge, Python 3.11 + FastAPI + SQLAlchemy 2.0 + Alembic, XGBoost + scikit-learn, PostgreSQL 16, Redis 7, Recharts, SendGrid, GitHub Actions.

**Design Doc:** `docs/plans/2026-03-26-shieldcommerce-shopify-app-design.md`

---

## Phase 1: Foundation + Shopify Scaffold (Week 1-2)

### Task 1: Initialize Monorepo Structure

**Files:**
- Create: `package.json` (root workspace)
- Create: `apps/web/` (Remix Shopify app — scaffolded by Shopify CLI)
- Create: `apps/scoring-engine/` (Python FastAPI)
- Create: `.gitignore`
- Create: `.github/workflows/ci.yml` (placeholder)
- Create: `docker-compose.yml` (local dev: PostgreSQL + Redis)

**Step 1: Create root workspace structure**

```bash
mkdir -p apps docs
```

**Step 2: Create root package.json for workspace**

```json
{
  "name": "shieldcommerce",
  "private": true,
  "workspaces": ["apps/web"]
}
```

**Step 3: Create .gitignore**

```gitignore
# Node
node_modules/
.cache/
build/
dist/

# Python
__pycache__/
*.pyc
.venv/
*.egg-info/
.pytest_cache/

# Environment
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# ML models
*.pkl
*.joblib
!apps/scoring-engine/models/.gitkeep

# Docker
docker-compose.override.yml
```

**Step 4: Create docker-compose.yml for local dev**

```yaml
version: "3.9"
services:
  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: shieldcommerce
      POSTGRES_USER: shield
      POSTGRES_PASSWORD: localdev
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 64mb --maxmemory-policy allkeys-lru

volumes:
  pgdata:
```

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: initialize monorepo structure with docker-compose for local dev"
```

---

### Task 2: Scaffold Shopify Remix App

**Files:**
- Create: `apps/web/` (entire Remix app via Shopify CLI)
- Modify: `apps/web/shopify.app.toml` (OAuth scopes, webhooks)

**Step 1: Scaffold Shopify app**

```bash
cd apps
npx @shopify/create-app@latest --template remix --name web
```

This generates the full Remix template with:
- `@shopify/shopify-app-remix` (OAuth, session management)
- `@shopify/polaris` (UI components)
- `@shopify/app-bridge-react` (App Bridge hooks)
- Prisma for session storage (we'll keep this for Shopify sessions, use our own DB for app data)

**Step 2: Update shopify.app.toml with required scopes and webhooks**

```toml
# shopify.app.toml
name = "ShieldCommerce"
client_id = "" # Fill after creating app in Partner Dashboard

[access_scopes]
scopes = "read_orders,write_orders,read_customers"

[auth]
redirect_urls = [
  "https://localhost/auth/callback",
  "https://localhost/auth/shopify/callback",
  "https://localhost/api/auth/callback"
]

[webhooks]
api_version = "2025-01"

  [webhooks.subscriptions]

  [[webhooks.subscriptions.compliance]]
  topics = ["customers/data_request", "customers/redact", "shop/redact"]
  uri = "/webhooks"

  [[webhooks.subscriptions.event]]
  topics = ["orders/create"]
  uri = "/webhooks/orders-create"

  [[webhooks.subscriptions.event]]
  topics = ["disputes/create"]
  uri = "/webhooks/disputes-create"

[app_proxy]
# Not needed for MVP

[pos]
embedded = false
```

**Step 3: Install additional dependencies**

```bash
cd apps/web
npm install recharts axios
npm install -D @types/recharts
```

**Step 4: Verify app runs locally**

```bash
cd apps/web
npm run dev
```

Expected: Remix dev server starts, shows Shopify app template at localhost.

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: scaffold Shopify Remix app with OAuth scopes and webhook config"
```

---

### Task 3: Scaffold FastAPI Scoring Engine

**Files:**
- Create: `apps/scoring-engine/pyproject.toml`
- Create: `apps/scoring-engine/app/__init__.py`
- Create: `apps/scoring-engine/app/main.py`
- Create: `apps/scoring-engine/app/config.py`
- Create: `apps/scoring-engine/app/models/__init__.py`
- Create: `apps/scoring-engine/app/api/__init__.py`
- Create: `apps/scoring-engine/app/api/health.py`
- Create: `apps/scoring-engine/tests/__init__.py`
- Create: `apps/scoring-engine/tests/test_health.py`
- Create: `apps/scoring-engine/Dockerfile`
- Create: `apps/scoring-engine/.env.example`
- Create: `apps/scoring-engine/models/.gitkeep`

**Step 1: Write the failing test**

```python
# apps/scoring-engine/tests/test_health.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_health_check_includes_services():
    response = client.get("/health")
    data = response.json()
    assert "services" in data
    assert "database" in data["services"]
    assert "redis" in data["services"]
```

**Step 2: Run test to verify it fails**

```bash
cd apps/scoring-engine
python -m pytest tests/test_health.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app'`

**Step 3: Create pyproject.toml**

```toml
# apps/scoring-engine/pyproject.toml
[project]
name = "shieldcommerce-scoring-engine"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "alembic>=1.13.0",
    "asyncpg>=0.29.0",
    "psycopg2-binary>=2.9.0",
    "redis>=5.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "httpx>=0.27.0",
    "xgboost>=2.1.0",
    "scikit-learn>=1.5.0",
    "pandas>=2.2.0",
    "numpy>=1.26.0",
    "joblib>=1.4.0",
    "maxminddb>=2.6.0",
    "phonenumbers>=8.13.0",
    "cryptography>=43.0.0",
    "sendgrid>=6.11.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py311"
line-length = 120
```

**Step 4: Create config module**

```python
# apps/scoring-engine/app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "ShieldCommerce Scoring Engine"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql://shield:localdev@localhost:5432/shieldcommerce"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

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
```

**Step 5: Create main app with health endpoint**

```python
# apps/scoring-engine/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.health import router as health_router

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tightened in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
```

```python
# apps/scoring-engine/app/__init__.py
```

```python
# apps/scoring-engine/app/models/__init__.py
```

```python
# apps/scoring-engine/app/api/__init__.py
```

```python
# apps/scoring-engine/app/api/health.py
from fastapi import APIRouter
from app.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    # Basic health check — db/redis checks added when connections are set up
    return {
        "status": "healthy",
        "version": settings.app_version,
        "services": {
            "database": "not_configured",
            "redis": "not_configured",
        },
    }
```

**Step 6: Create .env.example**

```bash
# apps/scoring-engine/.env.example
SC_DATABASE_URL=postgresql://shield:localdev@localhost:5432/shieldcommerce
SC_REDIS_URL=redis://localhost:6379/0
SC_ENCRYPTION_KEY=change-me-in-production-32-bytes!
SC_SENDGRID_API_KEY=
SC_DEBUG=true
```

**Step 7: Create Dockerfile**

```dockerfile
# apps/scoring-engine/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency file and install
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 8: Create venv, install deps, run tests**

```bash
cd apps/scoring-engine
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash
pip install -e ".[dev]"
python -m pytest tests/test_health.py -v
```

Expected: Both tests PASS.

**Step 9: Commit**

```bash
git add -A
git commit -m "feat: scaffold FastAPI scoring engine with health endpoint and tests"
```

---

### Task 4: Database Schema + Alembic Migrations

**Files:**
- Create: `apps/scoring-engine/app/models/base.py`
- Create: `apps/scoring-engine/app/models/merchant.py`
- Create: `apps/scoring-engine/app/models/order_score.py`
- Create: `apps/scoring-engine/app/models/chargeback.py`
- Create: `apps/scoring-engine/app/models/rules.py`
- Create: `apps/scoring-engine/app/models/enrichment.py`
- Create: `apps/scoring-engine/app/models/model_version.py`
- Create: `apps/scoring-engine/app/models/daily_digest.py`
- Create: `apps/scoring-engine/app/database.py`
- Create: `apps/scoring-engine/alembic.ini`
- Create: `apps/scoring-engine/alembic/env.py`
- Create: `apps/scoring-engine/tests/test_models.py`

**Step 1: Write failing test for models**

```python
# apps/scoring-engine/tests/test_models.py
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from app.models.base import Base
from app.models.merchant import Merchant
from app.models.order_score import OrderScore, ScoringSignal
from app.models.chargeback import Chargeback
from app.models.rules import CustomRule, WhitelistBlacklist, MerchantOverride
from app.models.enrichment import EnrichmentCache
from app.models.model_version import ModelVersion
from app.models.daily_digest import DailyDigest


def test_all_tables_created():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    expected_tables = [
        "merchants",
        "order_scores",
        "scoring_signals",
        "chargebacks",
        "custom_rules",
        "whitelist_blacklist",
        "merchant_overrides",
        "enrichment_cache",
        "model_versions",
        "daily_digests",
    ]
    for table in expected_tables:
        assert table in tables, f"Missing table: {table}"


def test_merchant_creation():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        merchant = Merchant(
            shop_domain="test-store.myshopify.com",
            access_token_encrypted="encrypted_token_here",
            plan_tier="starter",
        )
        session.add(merchant)
        session.commit()
        session.refresh(merchant)

        assert merchant.id is not None
        assert merchant.shop_domain == "test-store.myshopify.com"
        assert merchant.plan_tier == "starter"
        assert merchant.thresholds_json is not None  # Should have defaults


def test_order_score_with_signals():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        merchant = Merchant(
            shop_domain="test.myshopify.com",
            access_token_encrypted="enc",
            plan_tier="starter",
        )
        session.add(merchant)
        session.commit()

        score = OrderScore(
            merchant_id=merchant.id,
            shopify_order_id="12345",
            risk_score=73,
            risk_level="high",
            signals_json={"vpn_detected": True},
            recommendation="review",
        )
        session.add(score)
        session.commit()

        signal = ScoringSignal(
            order_score_id=score.id,
            signal_name="vpn_detected",
            signal_value="true",
            signal_weight=18.0,
            raw_data_json={"provider": "NordVPN"},
        )
        session.add(signal)
        session.commit()

        assert score.risk_score == 73
        assert signal.signal_weight == 18.0
```

**Step 2: Run test to verify it fails**

```bash
cd apps/scoring-engine
python -m pytest tests/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.base'`

**Step 3: Implement all models**

```python
# apps/scoring-engine/app/models/base.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, func
from datetime import datetime


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

```python
# apps/scoring-engine/app/models/merchant.py
from sqlalchemy import String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

DEFAULT_THRESHOLDS = {
    "low_max": 30,
    "medium_max": 60,
    "high_max": 85,
    "auto_approve_below": 30,
    "auto_cancel_above": 86,
}

DEFAULT_SETTINGS = {
    "email_alerts_enabled": True,
    "alert_on_risk_levels": ["high", "critical"],
    "digest_frequency": "daily",
    "digest_email": "",
}


class Merchant(Base, TimestampMixin):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    plan_tier: Mapped[str] = mapped_column(String(50), default="starter")
    settings_json: Mapped[dict] = mapped_column(JSON, default=lambda: DEFAULT_SETTINGS.copy())
    thresholds_json: Mapped[dict] = mapped_column(JSON, default=lambda: DEFAULT_THRESHOLDS.copy())

    # Relationships
    order_scores = relationship("OrderScore", back_populates="merchant", lazy="dynamic")
    custom_rules = relationship("CustomRule", back_populates="merchant", lazy="dynamic")
    whitelist_blacklist = relationship("WhitelistBlacklist", back_populates="merchant", lazy="dynamic")
    daily_digests = relationship("DailyDigest", back_populates="merchant", lazy="dynamic")
```

```python
# apps/scoring-engine/app/models/order_score.py
from sqlalchemy import String, Integer, Float, JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class OrderScore(Base, TimestampMixin):
    __tablename__ = "order_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    shopify_order_id: Mapped[str] = mapped_column(String(50), index=True)
    risk_score: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(20))  # low, medium, high, critical
    signals_json: Mapped[dict] = mapped_column(JSON)
    recommendation: Mapped[str] = mapped_column(String(50))  # approve, review, hold, cancel
    rule_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ml_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    merchant = relationship("Merchant", back_populates="order_scores")
    signals = relationship("ScoringSignal", back_populates="order_score", cascade="all, delete-orphan")
    override = relationship("MerchantOverride", back_populates="order_score", uselist=False)


class ScoringSignal(Base):
    __tablename__ = "scoring_signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_score_id: Mapped[int] = mapped_column(ForeignKey("order_scores.id"), index=True)
    signal_name: Mapped[str] = mapped_column(String(100))
    signal_value: Mapped[str] = mapped_column(Text)
    signal_weight: Mapped[float] = mapped_column(Float)
    raw_data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    order_score = relationship("OrderScore", back_populates="signals")
```

```python
# apps/scoring-engine/app/models/chargeback.py
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
from datetime import datetime


class Chargeback(Base):
    __tablename__ = "chargebacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    shopify_order_id: Mapped[str] = mapped_column(String(50), index=True)
    order_score_id: Mapped[int | None] = mapped_column(ForeignKey("order_scores.id"), nullable=True)
    dispute_type: Mapped[str] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column(Float)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)  # won, lost, pending
    predicted_correctly: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    filed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    merchant = relationship("Merchant")
    order_score = relationship("OrderScore")
```

```python
# apps/scoring-engine/app/models/rules.py
from sqlalchemy import String, Integer, JSON, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class CustomRule(Base, TimestampMixin):
    __tablename__ = "custom_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    rule_name: Mapped[str] = mapped_column(String(255))
    conditions_json: Mapped[dict] = mapped_column(JSON)
    action: Mapped[str] = mapped_column(String(50))  # flag, hold, cancel, approve
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    merchant = relationship("Merchant", back_populates="custom_rules")


class WhitelistBlacklist(Base, TimestampMixin):
    __tablename__ = "whitelist_blacklist"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    entry_type: Mapped[str] = mapped_column(String(50))  # email, ip, bin, address
    value: Mapped[str] = mapped_column(String(500))
    list_type: Mapped[str] = mapped_column(String(10))  # allow, block

    merchant = relationship("Merchant", back_populates="whitelist_blacklist")


class MerchantOverride(Base, TimestampMixin):
    __tablename__ = "merchant_overrides"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    order_score_id: Mapped[int] = mapped_column(ForeignKey("order_scores.id"), unique=True)
    original_recommendation: Mapped[str] = mapped_column(String(50))
    override_action: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    merchant = relationship("Merchant")
    order_score = relationship("OrderScore", back_populates="override")
```

```python
# apps/scoring-engine/app/models/enrichment.py
from sqlalchemy import String, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base
from datetime import datetime


class EnrichmentCache(Base):
    __tablename__ = "enrichment_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    lookup_type: Mapped[str] = mapped_column(String(50), index=True)  # ip, email, bin, phone
    lookup_key: Mapped[str] = mapped_column(String(500), index=True)
    result_json: Mapped[dict] = mapped_column(JSON)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

```python
# apps/scoring-engine/app/models/model_version.py
from sqlalchemy import String, Integer, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class ModelVersion(Base, TimestampMixin):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(50), unique=True)
    algorithm: Mapped[str] = mapped_column(String(100))  # xgboost, rule_based
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    precision_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recall: Mapped[float | None] = mapped_column(Float, nullable=True)
    f1_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_data_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
```

```python
# apps/scoring-engine/app/models/daily_digest.py
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
from datetime import date, datetime


class DailyDigest(Base):
    __tablename__ = "daily_digests"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    digest_date: Mapped[date] = mapped_column(Date)
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    flagged_orders: Mapped[int] = mapped_column(Integer, default=0)
    avg_score: Mapped[float] = mapped_column(Float, default=0.0)
    chargebacks: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    merchant = relationship("Merchant", back_populates="daily_digests")
```

**Step 4: Update models/__init__.py**

```python
# apps/scoring-engine/app/models/__init__.py
from app.models.base import Base
from app.models.merchant import Merchant
from app.models.order_score import OrderScore, ScoringSignal
from app.models.chargeback import Chargeback
from app.models.rules import CustomRule, WhitelistBlacklist, MerchantOverride
from app.models.enrichment import EnrichmentCache
from app.models.model_version import ModelVersion
from app.models.daily_digest import DailyDigest

__all__ = [
    "Base",
    "Merchant",
    "OrderScore",
    "ScoringSignal",
    "Chargeback",
    "CustomRule",
    "WhitelistBlacklist",
    "MerchantOverride",
    "EnrichmentCache",
    "ModelVersion",
    "DailyDigest",
]
```

**Step 5: Create database connection module**

```python
# apps/scoring-engine/app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Step 6: Run tests**

```bash
cd apps/scoring-engine
python -m pytest tests/test_models.py -v
```

Expected: All 3 tests PASS.

**Step 7: Initialize Alembic**

```bash
cd apps/scoring-engine
alembic init alembic
```

Update `alembic/env.py` to use our models and config:

```python
# apps/scoring-engine/alembic/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.config import settings
from app.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Step 8: Generate initial migration**

```bash
cd apps/scoring-engine
alembic revision --autogenerate -m "initial schema - all core tables"
```

**Step 9: Commit**

```bash
git add -A
git commit -m "feat: add all database models with Alembic migrations (10 tables)"
```

---

### Task 5: Database Connection + Redis Setup

**Files:**
- Modify: `apps/scoring-engine/app/database.py`
- Create: `apps/scoring-engine/app/redis_client.py`
- Modify: `apps/scoring-engine/app/api/health.py`
- Create: `apps/scoring-engine/tests/test_redis.py`

**Step 1: Write failing test**

```python
# apps/scoring-engine/tests/test_redis.py
from app.redis_client import RedisClient


def test_redis_client_init():
    client = RedisClient(url="redis://localhost:6379/0")
    assert client is not None


def test_redis_client_cache_operations():
    client = RedisClient(url="redis://localhost:6379/0")
    # Test set and get
    client.set_cache("test:key", {"value": 42}, ttl=60)
    result = client.get_cache("test:key")
    assert result == {"value": 42}

    # Test delete
    client.delete_cache("test:key")
    result = client.get_cache("test:key")
    assert result is None


def test_redis_client_queue_operations():
    client = RedisClient(url="redis://localhost:6379/0")
    # Test enqueue and dequeue
    client.enqueue("test:queue", {"order_id": "123"})
    result = client.dequeue("test:queue")
    assert result == {"order_id": "123"}

    # Empty queue returns None
    result = client.dequeue("test:queue", timeout=1)
    assert result is None
```

**Step 2: Implement Redis client**

```python
# apps/scoring-engine/app/redis_client.py
import json
import redis
from typing import Any


class RedisClient:
    def __init__(self, url: str):
        self.client = redis.from_url(url, decode_responses=True)

    def ping(self) -> bool:
        try:
            return self.client.ping()
        except redis.ConnectionError:
            return False

    def set_cache(self, key: str, value: Any, ttl: int = 3600) -> None:
        self.client.setex(key, ttl, json.dumps(value))

    def get_cache(self, key: str) -> Any | None:
        data = self.client.get(key)
        if data is None:
            return None
        return json.loads(data)

    def delete_cache(self, key: str) -> None:
        self.client.delete(key)

    def enqueue(self, queue_name: str, payload: dict) -> None:
        self.client.rpush(queue_name, json.dumps(payload))

    def dequeue(self, queue_name: str, timeout: int = 0) -> dict | None:
        if timeout > 0:
            result = self.client.blpop(queue_name, timeout=timeout)
            if result is None:
                return None
            return json.loads(result[1])
        else:
            data = self.client.lpop(queue_name)
            if data is None:
                return None
            return json.loads(data)

    def queue_length(self, queue_name: str) -> int:
        return self.client.llen(queue_name)
```

**Step 3: Update health endpoint with real checks**

```python
# apps/scoring-engine/app/api/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config import settings
from app.database import get_db
from app.redis_client import RedisClient

router = APIRouter()


def get_redis() -> RedisClient:
    return RedisClient(url=settings.redis_url)


@router.get("/health")
async def health_check():
    db_status = "not_configured"
    redis_status = "not_configured"

    # Check Redis
    try:
        rc = RedisClient(url=settings.redis_url)
        redis_status = "healthy" if rc.ping() else "unhealthy"
    except Exception:
        redis_status = "unhealthy"

    return {
        "status": "healthy",
        "version": settings.app_version,
        "services": {
            "database": db_status,
            "redis": redis_status,
        },
    }
```

**Step 4: Run tests (requires local Redis from docker-compose)**

```bash
docker compose up -d redis
cd apps/scoring-engine
python -m pytest tests/test_redis.py -v
```

Expected: All 3 tests PASS.

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: add Redis client with cache/queue operations and health checks"
```

---

### Task 6: Remix ↔ FastAPI Integration Layer

**Files:**
- Create: `apps/web/app/lib/scoring-api.server.ts`
- Create: `apps/web/app/lib/types.ts`
- Modify: `apps/scoring-engine/app/main.py` (add API key auth middleware)
- Create: `apps/scoring-engine/app/api/middleware.py`

**Step 1: Create shared types**

```typescript
// apps/web/app/lib/types.ts
export interface OrderScore {
  id: number;
  shopify_order_id: string;
  risk_score: number;
  risk_level: "low" | "medium" | "high" | "critical";
  signals_json: Record<string, any>;
  recommendation: string;
  rule_score: number | null;
  ml_score: number | null;
  created_at: string;
}

export interface ScoringSignal {
  signal_name: string;
  signal_value: string;
  signal_weight: number;
  raw_data_json: Record<string, any> | null;
}

export interface DashboardStats {
  total_orders: number;
  flagged_orders: number;
  avg_score: number;
  chargeback_count: number;
  chargeback_amount: number;
  score_distribution: { range: string; count: number }[];
  trend_data: { date: string; avg_score: number; order_count: number }[];
}

export interface MerchantSettings {
  thresholds: {
    low_max: number;
    medium_max: number;
    high_max: number;
    auto_approve_below: number;
    auto_cancel_above: number;
  };
  email_alerts_enabled: boolean;
  alert_on_risk_levels: string[];
  digest_frequency: "daily" | "weekly" | "off";
  digest_email: string;
}

export type PlanTier = "starter" | "growth" | "pro" | "scale";

export const PLAN_ORDER_LIMITS: Record<PlanTier, number> = {
  starter: 500,
  growth: 2000,
  pro: 10000,
  scale: 25000,
};

export const PLAN_FEATURES: Record<PlanTier, string[]> = {
  starter: ["scoring", "signals", "basic_dashboard", "email_alerts"],
  growth: ["scoring", "signals", "basic_dashboard", "email_alerts", "custom_rules", "chargeback_tracking"],
  pro: ["scoring", "signals", "basic_dashboard", "email_alerts", "custom_rules", "chargeback_tracking", "advanced_analytics", "api_access"],
  scale: ["scoring", "signals", "basic_dashboard", "email_alerts", "custom_rules", "chargeback_tracking", "advanced_analytics", "api_access", "bulk_actions", "exports", "custom_model"],
};
```

**Step 2: Create scoring API client**

```typescript
// apps/web/app/lib/scoring-api.server.ts
import type { OrderScore, DashboardStats, MerchantSettings, ScoringSignal } from "./types";

const SCORING_ENGINE_URL = process.env.SCORING_ENGINE_URL || "http://localhost:8000";
const SCORING_API_KEY = process.env.SCORING_API_KEY || "dev-key";

async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${SCORING_ENGINE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": SCORING_API_KEY,
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`Scoring API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

export async function getDashboardStats(merchantId: number, days: number = 30): Promise<DashboardStats> {
  return apiRequest(`/api/v1/merchants/${merchantId}/dashboard?days=${days}`);
}

export async function getOrderScores(
  merchantId: number,
  page: number = 1,
  limit: number = 20,
  riskLevel?: string
): Promise<{ items: OrderScore[]; total: number }> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (riskLevel) params.set("risk_level", riskLevel);
  return apiRequest(`/api/v1/merchants/${merchantId}/orders?${params}`);
}

export async function getOrderDetail(
  merchantId: number,
  orderId: string
): Promise<{ score: OrderScore; signals: ScoringSignal[] }> {
  return apiRequest(`/api/v1/merchants/${merchantId}/orders/${orderId}`);
}

export async function overrideOrder(
  merchantId: number,
  orderScoreId: number,
  action: string,
  reason: string
): Promise<void> {
  await apiRequest(`/api/v1/merchants/${merchantId}/orders/${orderScoreId}/override`, {
    method: "POST",
    body: JSON.stringify({ action, reason }),
  });
}

export async function getMerchantSettings(merchantId: number): Promise<MerchantSettings> {
  return apiRequest(`/api/v1/merchants/${merchantId}/settings`);
}

export async function updateMerchantSettings(
  merchantId: number,
  settings: Partial<MerchantSettings>
): Promise<MerchantSettings> {
  return apiRequest(`/api/v1/merchants/${merchantId}/settings`, {
    method: "PATCH",
    body: JSON.stringify(settings),
  });
}

export async function healthCheck(): Promise<{ status: string }> {
  return apiRequest("/health");
}
```

**Step 3: Add API key middleware to FastAPI**

```python
# apps/scoring-engine/app/api/middleware.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings


class APIKeyMiddleware(BaseHTTPMiddleware):
    EXEMPT_PATHS = {"/health", "/docs", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key != settings.internal_api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

        return await call_next(request)
```

Update config to include API key:

Add to `apps/scoring-engine/app/config.py`:
```python
    internal_api_key: str = "dev-key"
```

Update `apps/scoring-engine/app/main.py`:
```python
from app.api.middleware import APIKeyMiddleware
# Add after CORS middleware:
app.add_middleware(APIKeyMiddleware)
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: add Remix-FastAPI integration layer with API client and auth middleware"
```

---

## Phase 2: Scoring Engine Core (Week 3-4)

### Task 7: Pluggable Enrichment Layer — Interfaces

**Files:**
- Create: `apps/scoring-engine/app/enrichment/__init__.py`
- Create: `apps/scoring-engine/app/enrichment/base.py`
- Create: `apps/scoring-engine/app/enrichment/ip_provider.py`
- Create: `apps/scoring-engine/app/enrichment/email_provider.py`
- Create: `apps/scoring-engine/app/enrichment/phone_provider.py`
- Create: `apps/scoring-engine/app/enrichment/registry.py`
- Create: `apps/scoring-engine/tests/test_enrichment.py`

**Step 1: Write failing tests**

```python
# apps/scoring-engine/tests/test_enrichment.py
from app.enrichment.base import IPResult, EmailResult, PhoneResult
from app.enrichment.ip_provider import MaxMindGeoLiteProvider
from app.enrichment.email_provider import DisposableListEmailProvider
from app.enrichment.phone_provider import LibPhoneProvider
from app.enrichment.registry import EnrichmentRegistry


def test_ip_provider_interface():
    provider = MaxMindGeoLiteProvider(db_path=None)  # None = skip DB load for test
    result = provider.lookup("8.8.8.8")
    assert isinstance(result, IPResult)


def test_email_provider_interface():
    provider = DisposableListEmailProvider()
    result = provider.validate("test@mailinator.com")
    assert isinstance(result, EmailResult)
    assert result.is_disposable is True


def test_email_provider_valid():
    provider = DisposableListEmailProvider()
    result = provider.validate("user@gmail.com")
    assert isinstance(result, EmailResult)
    assert result.is_disposable is False


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
```

**Step 2: Implement base interfaces**

```python
# apps/scoring-engine/app/enrichment/base.py
from dataclasses import dataclass, field
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
    phone_type: str = "unknown"  # mobile, landline, voip, unknown
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
```

**Step 3: Implement free-tier providers**

```python
# apps/scoring-engine/app/enrichment/ip_provider.py
import os
from app.enrichment.base import IPProvider, IPResult

FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com", "protonmail.com", "mail.com", "zoho.com", "yandex.com"}


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
                ip=ip,
                country=country,
                city=city,
                latitude=location.get("latitude", 0.0),
                longitude=location.get("longitude", 0.0),
            )
        except Exception:
            return IPResult(ip=ip)

    def __del__(self):
        if self.reader:
            self.reader.close()
```

```python
# apps/scoring-engine/app/enrichment/email_provider.py
import re
from app.enrichment.base import EmailProvider, EmailResult

# Top disposable email domains — extend with full list from GitHub
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
            email=email,
            is_disposable=domain in self.disposable_domains,
            is_free_provider=domain in FREE_EMAIL_DOMAINS,
            domain=domain,
            is_valid_format=is_valid,
            risk_score=self._calculate_risk(domain, is_valid),
        )

    def _calculate_risk(self, domain: str, is_valid: bool) -> int:
        score = 0
        if not is_valid:
            score += 30
        if domain in self.disposable_domains:
            score += 40
        if domain in FREE_EMAIL_DOMAINS:
            score += 5
        return min(score, 100)
```

```python
# apps/scoring-engine/app/enrichment/phone_provider.py
import phonenumbers
from app.enrichment.base import PhoneProvider, PhoneResult


class LibPhoneProvider(PhoneProvider):
    def validate(self, phone: str, country: str = "US") -> PhoneResult:
        try:
            parsed = phonenumbers.parse(phone, country)
            is_valid = phonenumbers.is_valid_number(parsed)

            phone_type_map = {
                0: "landline",
                1: "mobile",
                2: "landline",  # fixed_line_or_mobile
                3: "toll_free",
                4: "premium_rate",
                5: "shared_cost",
                6: "voip",
                7: "personal",
                8: "pager",
                9: "uan",
                10: "unknown",
            }
            number_type = phonenumbers.number_type(parsed)
            phone_type = phone_type_map.get(number_type, "unknown")

            return PhoneResult(
                phone=phone,
                is_valid=is_valid,
                country_code=str(parsed.country_code),
                phone_type=phone_type,
                risk_score=self._calculate_risk(is_valid, phone_type),
            )
        except phonenumbers.NumberParseException:
            return PhoneResult(phone=phone, is_valid=False, risk_score=30)

    def _calculate_risk(self, is_valid: bool, phone_type: str) -> int:
        score = 0
        if not is_valid:
            score += 30
        if phone_type == "voip":
            score += 15
        return min(score, 100)
```

```python
# apps/scoring-engine/app/enrichment/registry.py
from app.enrichment.base import IPProvider, EmailProvider, PhoneProvider
from app.enrichment.ip_provider import MaxMindGeoLiteProvider
from app.enrichment.email_provider import DisposableListEmailProvider
from app.enrichment.phone_provider import LibPhoneProvider
from app.config import settings


class EnrichmentRegistry:
    """Central registry for enrichment providers. Swap implementations via config."""

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
```

```python
# apps/scoring-engine/app/enrichment/__init__.py
from app.enrichment.registry import EnrichmentRegistry

__all__ = ["EnrichmentRegistry"]
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_enrichment.py -v
```

Expected: All 5 tests PASS.

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: add pluggable enrichment layer with free-tier IP, email, phone providers"
```

---

### Task 8: Signal Extraction Module

**Files:**
- Create: `apps/scoring-engine/app/scoring/__init__.py`
- Create: `apps/scoring-engine/app/scoring/signals.py`
- Create: `apps/scoring-engine/tests/test_signals.py`

**Step 1: Write failing tests**

```python
# apps/scoring-engine/tests/test_signals.py
from app.scoring.signals import SignalExtractor, OrderPayload, ExtractedSignals
from app.enrichment.registry import EnrichmentRegistry


def _sample_order() -> OrderPayload:
    return OrderPayload(
        order_id="1001",
        email="test@mailinator.com",
        ip_address="8.8.8.8",
        shipping_country="US",
        shipping_state="FL",
        billing_country="US",
        billing_state="CA",
        order_total=487.00,
        currency="USD",
        line_items=[{"title": "Widget", "quantity": 2, "price": "243.50"}],
        customer_id="cust_123",
        is_first_order=True,
        phone="+14155552671",
        card_bin="411111",
        card_last4="1234",
        card_brand="visa",
        card_country="US",
        avs_result="N",
        cvv_result="N",
        payment_gateway="shopify_payments",
        browser_ip="8.8.8.8",
        created_at="2026-03-26T10:30:00Z",
    )


def test_signal_extraction_returns_all_categories():
    extractor = SignalExtractor(EnrichmentRegistry())
    signals = extractor.extract(_sample_order(), store_avg_order=152.0)
    assert isinstance(signals, ExtractedSignals)
    assert len(signals.payment) > 0
    assert len(signals.behavioral) > 0
    assert len(signals.geographic) > 0
    assert len(signals.order_pattern) > 0
    assert len(signals.digital_footprint) > 0


def test_signal_extraction_catches_disposable_email():
    extractor = SignalExtractor(EnrichmentRegistry())
    signals = extractor.extract(_sample_order(), store_avg_order=152.0)
    email_signals = {s.name: s for s in signals.digital_footprint}
    assert "disposable_email" in email_signals
    assert email_signals["disposable_email"].value is True


def test_signal_extraction_catches_address_mismatch():
    extractor = SignalExtractor(EnrichmentRegistry())
    signals = extractor.extract(_sample_order(), store_avg_order=152.0)
    geo_signals = {s.name: s for s in signals.geographic}
    assert "address_mismatch" in geo_signals
    assert geo_signals["address_mismatch"].value is True


def test_signal_extraction_detects_high_order_value():
    extractor = SignalExtractor(EnrichmentRegistry())
    signals = extractor.extract(_sample_order(), store_avg_order=152.0)
    pattern_signals = {s.name: s for s in signals.order_pattern}
    assert "order_value_deviation" in pattern_signals
    assert pattern_signals["order_value_deviation"].value > 2.0  # 487/152 = 3.2x


def test_total_signal_count():
    extractor = SignalExtractor(EnrichmentRegistry())
    signals = extractor.extract(_sample_order(), store_avg_order=152.0)
    total = signals.total_count()
    assert total >= 15  # At least 15 signals across all categories
```

**Step 2: Implement signal extraction**

```python
# apps/scoring-engine/app/scoring/signals.py
from dataclasses import dataclass, field
from app.enrichment.registry import EnrichmentRegistry


@dataclass
class OrderPayload:
    order_id: str
    email: str
    ip_address: str
    shipping_country: str
    shipping_state: str
    billing_country: str
    billing_state: str
    order_total: float
    currency: str
    line_items: list[dict]
    customer_id: str
    is_first_order: bool
    phone: str = ""
    card_bin: str = ""
    card_last4: str = ""
    card_brand: str = ""
    card_country: str = ""
    avs_result: str = ""
    cvv_result: str = ""
    payment_gateway: str = ""
    browser_ip: str = ""
    created_at: str = ""


@dataclass
class Signal:
    name: str
    value: object
    weight: float
    category: str
    explanation: str = ""


@dataclass
class ExtractedSignals:
    payment: list[Signal] = field(default_factory=list)
    behavioral: list[Signal] = field(default_factory=list)
    geographic: list[Signal] = field(default_factory=list)
    order_pattern: list[Signal] = field(default_factory=list)
    digital_footprint: list[Signal] = field(default_factory=list)

    def all_signals(self) -> list[Signal]:
        return self.payment + self.behavioral + self.geographic + self.order_pattern + self.digital_footprint

    def total_count(self) -> int:
        return len(self.all_signals())


class SignalExtractor:
    def __init__(self, enrichment: EnrichmentRegistry):
        self.enrichment = enrichment

    def extract(self, order: OrderPayload, store_avg_order: float = 100.0) -> ExtractedSignals:
        signals = ExtractedSignals()
        signals.payment = self._extract_payment(order)
        signals.behavioral = self._extract_behavioral(order)
        signals.geographic = self._extract_geographic(order)
        signals.order_pattern = self._extract_order_pattern(order, store_avg_order)
        signals.digital_footprint = self._extract_digital_footprint(order)
        return signals

    def _extract_payment(self, order: OrderPayload) -> list[Signal]:
        signals = []

        # AVS check
        avs_fail = order.avs_result in ("N", "A", "Z", "")
        signals.append(Signal(
            name="avs_mismatch", value=avs_fail, weight=8.0, category="payment",
            explanation=f"AVS result: {order.avs_result or 'not provided'}"
        ))

        # CVV check
        cvv_fail = order.cvv_result in ("N", "")
        signals.append(Signal(
            name="cvv_failure", value=cvv_fail, weight=6.0, category="payment",
            explanation=f"CVV result: {order.cvv_result or 'not provided'}"
        ))

        # Card country vs billing country
        if order.card_country and order.billing_country:
            mismatch = order.card_country.upper() != order.billing_country.upper()
            signals.append(Signal(
                name="card_country_mismatch", value=mismatch, weight=12.0, category="payment",
                explanation=f"Card issued in {order.card_country}, billing in {order.billing_country}"
            ))

        # Card brand
        signals.append(Signal(
            name="card_brand", value=order.card_brand, weight=0.0, category="payment",
            explanation=f"Card brand: {order.card_brand}"
        ))

        return signals

    def _extract_behavioral(self, order: OrderPayload) -> list[Signal]:
        signals = []

        # First-time customer
        signals.append(Signal(
            name="first_time_customer", value=order.is_first_order, weight=12.0, category="behavioral",
            explanation="First order from this customer" if order.is_first_order else "Returning customer"
        ))

        # Line item count
        item_count = sum(item.get("quantity", 1) for item in order.line_items)
        signals.append(Signal(
            name="item_count", value=item_count, weight=0.0, category="behavioral",
            explanation=f"{item_count} items in order"
        ))

        # Unique products
        unique_products = len(order.line_items)
        signals.append(Signal(
            name="unique_products", value=unique_products, weight=0.0, category="behavioral",
            explanation=f"{unique_products} unique products"
        ))

        return signals

    def _extract_geographic(self, order: OrderPayload) -> list[Signal]:
        signals = []

        # Shipping vs billing address mismatch
        state_mismatch = (
            order.shipping_state and order.billing_state
            and order.shipping_state.upper() != order.billing_state.upper()
        )
        country_mismatch = (
            order.shipping_country and order.billing_country
            and order.shipping_country.upper() != order.billing_country.upper()
        )

        signals.append(Signal(
            name="address_mismatch", value=state_mismatch or country_mismatch, weight=15.0, category="geographic",
            explanation=f"Billing: {order.billing_state}, {order.billing_country}; Shipping: {order.shipping_state}, {order.shipping_country}"
        ))

        # IP geolocation
        ip_result = self.enrichment.ip_provider.lookup(order.ip_address)

        ip_country_mismatch = (
            ip_result.country != "unknown"
            and order.shipping_country
            and ip_result.country.upper() != order.shipping_country.upper()
        )
        signals.append(Signal(
            name="ip_country_mismatch", value=ip_country_mismatch, weight=10.0, category="geographic",
            explanation=f"IP country: {ip_result.country}; Shipping: {order.shipping_country}"
        ))

        # VPN/Proxy detection
        signals.append(Signal(
            name="vpn_detected", value=ip_result.is_vpn, weight=18.0, category="geographic",
            explanation="VPN/proxy detected" if ip_result.is_vpn else "No VPN/proxy detected"
        ))

        signals.append(Signal(
            name="tor_detected", value=ip_result.is_tor, weight=25.0, category="geographic",
            explanation="Tor exit node detected" if ip_result.is_tor else "Not a Tor exit node"
        ))

        return signals

    def _extract_order_pattern(self, order: OrderPayload, store_avg: float) -> list[Signal]:
        signals = []

        # Order value deviation
        deviation = order.order_total / store_avg if store_avg > 0 else 1.0
        signals.append(Signal(
            name="order_value_deviation", value=round(deviation, 2), weight=11.0, category="order_pattern",
            explanation=f"Order ${order.order_total:.2f} is {deviation:.1f}x store average (${store_avg:.2f})"
        ))

        # High value order flag (>$500)
        is_high_value = order.order_total > 500
        signals.append(Signal(
            name="high_value_order", value=is_high_value, weight=5.0, category="order_pattern",
            explanation=f"Order total: ${order.order_total:.2f}" + (" (high value)" if is_high_value else "")
        ))

        # Currency
        signals.append(Signal(
            name="currency", value=order.currency, weight=0.0, category="order_pattern",
            explanation=f"Currency: {order.currency}"
        ))

        return signals

    def _extract_digital_footprint(self, order: OrderPayload) -> list[Signal]:
        signals = []

        # Email validation
        email_result = self.enrichment.email_provider.validate(order.email)

        signals.append(Signal(
            name="disposable_email", value=email_result.is_disposable, weight=20.0, category="digital_footprint",
            explanation=f"Disposable email domain: {email_result.domain}" if email_result.is_disposable else f"Email domain: {email_result.domain}"
        ))

        signals.append(Signal(
            name="free_email_provider", value=email_result.is_free_provider, weight=5.0, category="digital_footprint",
            explanation=f"Free email provider ({email_result.domain})" if email_result.is_free_provider else f"Custom domain ({email_result.domain})"
        ))

        signals.append(Signal(
            name="invalid_email_format", value=not email_result.is_valid_format, weight=15.0, category="digital_footprint",
            explanation="Invalid email format" if not email_result.is_valid_format else "Valid email format"
        ))

        # Phone validation
        if order.phone:
            phone_result = self.enrichment.phone_provider.validate(order.phone)
            signals.append(Signal(
                name="phone_invalid", value=not phone_result.is_valid, weight=10.0, category="digital_footprint",
                explanation=f"Phone: {phone_result.phone_type}" if phone_result.is_valid else "Invalid phone number"
            ))
            signals.append(Signal(
                name="voip_phone", value=phone_result.phone_type == "voip", weight=12.0, category="digital_footprint",
                explanation="VoIP phone number detected" if phone_result.phone_type == "voip" else f"Phone type: {phone_result.phone_type}"
            ))

        return signals
```

```python
# apps/scoring-engine/app/scoring/__init__.py
```

**Step 3: Run tests**

```bash
python -m pytest tests/test_signals.py -v
```

Expected: All 5 tests PASS.

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: add signal extraction module with 30+ signals across 5 categories"
```

---

### Task 9: Rule-Based Scoring Engine

**Files:**
- Create: `apps/scoring-engine/app/scoring/rule_engine.py`
- Create: `apps/scoring-engine/tests/test_rule_engine.py`

**Step 1: Write failing tests**

```python
# apps/scoring-engine/tests/test_rule_engine.py
from app.scoring.rule_engine import RuleBasedScorer, ScoringResult
from app.scoring.signals import ExtractedSignals, Signal


def _make_signals(overrides: dict | None = None) -> ExtractedSignals:
    defaults = {
        "avs_mismatch": (True, 8.0, "payment"),
        "cvv_failure": (False, 6.0, "payment"),
        "first_time_customer": (True, 12.0, "behavioral"),
        "address_mismatch": (True, 15.0, "geographic"),
        "vpn_detected": (False, 18.0, "geographic"),
        "order_value_deviation": (3.2, 11.0, "order_pattern"),
        "disposable_email": (False, 20.0, "digital_footprint"),
        "free_email_provider": (True, 5.0, "digital_footprint"),
    }
    if overrides:
        defaults.update(overrides)

    signals = ExtractedSignals()
    for name, (value, weight, category) in defaults.items():
        signal = Signal(name=name, value=value, weight=weight, category=category)
        getattr(signals, category).append(signal)
    return signals


def test_scoring_returns_result():
    scorer = RuleBasedScorer()
    result = scorer.score(_make_signals())
    assert isinstance(result, ScoringResult)
    assert 0 <= result.score <= 100
    assert result.risk_level in ("low", "medium", "high", "critical")


def test_low_risk_order():
    signals = _make_signals({
        "avs_mismatch": (False, 8.0, "payment"),
        "first_time_customer": (False, 12.0, "behavioral"),
        "address_mismatch": (False, 15.0, "geographic"),
        "order_value_deviation": (1.0, 11.0, "order_pattern"),
    })
    result = RuleBasedScorer().score(signals)
    assert result.risk_level == "low"
    assert result.score <= 30


def test_high_risk_order():
    signals = _make_signals({
        "avs_mismatch": (True, 8.0, "payment"),
        "vpn_detected": (True, 18.0, "geographic"),
        "address_mismatch": (True, 15.0, "geographic"),
        "disposable_email": (True, 20.0, "digital_footprint"),
        "first_time_customer": (True, 12.0, "behavioral"),
        "order_value_deviation": (4.0, 11.0, "order_pattern"),
    })
    result = RuleBasedScorer().score(signals)
    assert result.risk_level in ("high", "critical")
    assert result.score >= 61


def test_scoring_includes_signal_contributions():
    result = RuleBasedScorer().score(_make_signals())
    assert len(result.signal_contributions) > 0
    for contrib in result.signal_contributions:
        assert "signal_name" in contrib
        assert "points_added" in contrib
```

**Step 2: Implement rule-based scorer**

```python
# apps/scoring-engine/app/scoring/rule_engine.py
from dataclasses import dataclass, field
from app.scoring.signals import ExtractedSignals, Signal


@dataclass
class ScoringResult:
    score: int
    risk_level: str
    recommendation: str
    signal_contributions: list[dict] = field(default_factory=list)


# Category weights (must sum to 1.0)
CATEGORY_WEIGHTS = {
    "payment": 0.30,
    "behavioral": 0.25,
    "geographic": 0.20,
    "order_pattern": 0.15,
    "digital_footprint": 0.10,
}


class RuleBasedScorer:
    def __init__(self, thresholds: dict | None = None):
        self.thresholds = thresholds or {
            "low_max": 30,
            "medium_max": 60,
            "high_max": 85,
        }

    def score(self, signals: ExtractedSignals) -> ScoringResult:
        contributions = []
        raw_score = 0.0

        for signal in signals.all_signals():
            points = self._signal_to_points(signal)
            if points > 0:
                contributions.append({
                    "signal_name": signal.name,
                    "finding": str(signal.value),
                    "points_added": round(points, 1),
                    "explanation": signal.explanation,
                    "category": signal.category,
                })
            raw_score += points

        # Clamp to 0-100
        final_score = max(0, min(100, int(round(raw_score))))

        # Classify
        risk_level = self._classify(final_score)
        recommendation = self._recommend(risk_level)

        # Sort contributions by points (highest first)
        contributions.sort(key=lambda c: c["points_added"], reverse=True)

        return ScoringResult(
            score=final_score,
            risk_level=risk_level,
            recommendation=recommendation,
            signal_contributions=contributions,
        )

    def _signal_to_points(self, signal: Signal) -> float:
        """Convert a signal to risk points based on its value and weight."""
        if isinstance(signal.value, bool):
            return signal.weight if signal.value else 0.0
        elif isinstance(signal.value, (int, float)):
            # For numeric signals like order_value_deviation
            if signal.name == "order_value_deviation":
                if signal.value > 3.0:
                    return signal.weight
                elif signal.value > 2.0:
                    return signal.weight * 0.6
                elif signal.value > 1.5:
                    return signal.weight * 0.3
                return 0.0
        return 0.0

    def _classify(self, score: int) -> str:
        if score <= self.thresholds["low_max"]:
            return "low"
        elif score <= self.thresholds["medium_max"]:
            return "medium"
        elif score <= self.thresholds["high_max"]:
            return "high"
        return "critical"

    def _recommend(self, risk_level: str) -> str:
        return {
            "low": "approve",
            "medium": "review",
            "high": "hold",
            "critical": "cancel",
        }.get(risk_level, "review")
```

**Step 3: Run tests**

```bash
python -m pytest tests/test_rule_engine.py -v
```

Expected: All 4 tests PASS.

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: add rule-based scoring engine with weighted signals and risk classification"
```

---

### Task 10: XGBoost ML Model Training Pipeline

**Files:**
- Create: `apps/scoring-engine/app/scoring/ml_model.py`
- Create: `apps/scoring-engine/app/scoring/feature_engineering.py`
- Create: `apps/scoring-engine/app/scoring/train.py`
- Create: `apps/scoring-engine/tests/test_ml_model.py`
- Create: `apps/scoring-engine/models/.gitkeep`

**Step 1: Write failing tests**

```python
# apps/scoring-engine/tests/test_ml_model.py
import numpy as np
from app.scoring.feature_engineering import FeatureEngineer
from app.scoring.ml_model import FraudMLModel
from app.scoring.signals import ExtractedSignals, Signal


def _make_feature_signals() -> ExtractedSignals:
    signals = ExtractedSignals()
    signals.payment = [
        Signal(name="avs_mismatch", value=True, weight=8.0, category="payment"),
        Signal(name="cvv_failure", value=False, weight=6.0, category="payment"),
        Signal(name="card_country_mismatch", value=False, weight=12.0, category="payment"),
    ]
    signals.behavioral = [
        Signal(name="first_time_customer", value=True, weight=12.0, category="behavioral"),
        Signal(name="item_count", value=3, weight=0.0, category="behavioral"),
    ]
    signals.geographic = [
        Signal(name="address_mismatch", value=True, weight=15.0, category="geographic"),
        Signal(name="vpn_detected", value=False, weight=18.0, category="geographic"),
        Signal(name="ip_country_mismatch", value=False, weight=10.0, category="geographic"),
        Signal(name="tor_detected", value=False, weight=25.0, category="geographic"),
    ]
    signals.order_pattern = [
        Signal(name="order_value_deviation", value=2.5, weight=11.0, category="order_pattern"),
        Signal(name="high_value_order", value=False, weight=5.0, category="order_pattern"),
    ]
    signals.digital_footprint = [
        Signal(name="disposable_email", value=False, weight=20.0, category="digital_footprint"),
        Signal(name="free_email_provider", value=True, weight=5.0, category="digital_footprint"),
        Signal(name="invalid_email_format", value=False, weight=15.0, category="digital_footprint"),
    ]
    return signals


def test_feature_engineer_produces_vector():
    engineer = FeatureEngineer()
    vector = engineer.transform(_make_feature_signals())
    assert isinstance(vector, np.ndarray)
    assert len(vector) == engineer.feature_count()
    assert not np.isnan(vector).any()


def test_ml_model_predict_returns_score():
    model = FraudMLModel()
    engineer = FeatureEngineer()
    vector = engineer.transform(_make_feature_signals())
    score = model.predict(vector)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_feature_names_match_vector_length():
    engineer = FeatureEngineer()
    names = engineer.feature_names()
    assert len(names) == engineer.feature_count()
```

**Step 2: Implement feature engineering**

```python
# apps/scoring-engine/app/scoring/feature_engineering.py
import numpy as np
from app.scoring.signals import ExtractedSignals

# Ordered list of features the model expects
FEATURE_NAMES = [
    "avs_mismatch",
    "cvv_failure",
    "card_country_mismatch",
    "first_time_customer",
    "item_count",
    "address_mismatch",
    "vpn_detected",
    "ip_country_mismatch",
    "tor_detected",
    "order_value_deviation",
    "high_value_order",
    "disposable_email",
    "free_email_provider",
    "invalid_email_format",
    "phone_invalid",
    "voip_phone",
]


class FeatureEngineer:
    def __init__(self):
        self._feature_names = FEATURE_NAMES

    def feature_names(self) -> list[str]:
        return self._feature_names.copy()

    def feature_count(self) -> int:
        return len(self._feature_names)

    def transform(self, signals: ExtractedSignals) -> np.ndarray:
        signal_map = {s.name: s.value for s in signals.all_signals()}
        vector = []
        for name in self._feature_names:
            raw = signal_map.get(name, 0)
            vector.append(self._encode(raw))
        return np.array(vector, dtype=np.float32)

    def _encode(self, value: object) -> float:
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        elif isinstance(value, (int, float)):
            return float(value)
        return 0.0
```

**Step 3: Implement ML model wrapper**

```python
# apps/scoring-engine/app/scoring/ml_model.py
import os
import numpy as np
import joblib
import xgboost as xgb


class FraudMLModel:
    def __init__(self, model_path: str | None = None):
        self.model = None
        if model_path and os.path.exists(model_path):
            self.model = joblib.load(model_path)

    def predict(self, feature_vector: np.ndarray) -> float:
        if self.model is None:
            # Fallback: simple heuristic when no trained model is loaded
            # Sum of boolean features as rough proxy
            return float(min(100.0, max(0.0, feature_vector.sum() * 12.0)))

        vector_2d = feature_vector.reshape(1, -1)
        probability = self.model.predict_proba(vector_2d)[0][1]  # P(fraud)
        return float(round(probability * 100, 1))

    def is_loaded(self) -> bool:
        return self.model is not None
```

**Step 4: Create training script (for Kaggle IEEE-CIS dataset)**

```python
# apps/scoring-engine/app/scoring/train.py
"""
Training script for the XGBoost fraud detection model.

Usage:
    python -m app.scoring.train --data path/to/train.csv --output models/fraud_model_v1.joblib

Dataset: Kaggle IEEE-CIS Fraud Detection
    https://www.kaggle.com/c/ieee-fraud-detection
    Download train_transaction.csv and train_identity.csv
"""
import argparse
import pandas as pd
import numpy as np
import xgboost as xgb
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report


def train_model(data_path: str, output_path: str):
    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path)

    # Map IEEE-CIS features to our signal names where possible
    # This is a simplified mapping — production model would use more features
    feature_cols = []
    target_col = "isFraud"

    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found. Expected Kaggle IEEE-CIS format.")

    # Select numeric columns, fill NaN
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_cols.remove(target_col)
    if "TransactionID" in numeric_cols:
        numeric_cols.remove("TransactionID")

    # Use top N features to keep model manageable
    feature_cols = numeric_cols[:30]

    X = df[feature_cols].fillna(0)
    y = df[target_col]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    print(f"Training on {len(X_train)} samples, testing on {len(X_test)}")
    print(f"Fraud rate: {y.mean():.4f}")

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=len(y_train[y_train == 0]) / max(len(y_train[y_train == 1]), 1),
        random_state=42,
        eval_metric="auc",
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=True,
    )

    y_pred = model.predict(X_test)
    print("\n--- Model Performance ---")
    print(f"Accuracy:  {accuracy_score(y_test, y_pred):.4f}")
    print(f"Precision: {precision_score(y_test, y_pred):.4f}")
    print(f"Recall:    {recall_score(y_test, y_pred):.4f}")
    print(f"F1:        {f1_score(y_test, y_pred):.4f}")
    print("\n" + classification_report(y_test, y_pred))

    joblib.dump(model, output_path)
    print(f"\nModel saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path to training CSV")
    parser.add_argument("--output", default="models/fraud_model_v1.joblib", help="Output model path")
    args = parser.parse_args()
    train_model(args.data, args.output)
```

**Step 5: Run tests**

```bash
python -m pytest tests/test_ml_model.py -v
```

Expected: All 3 tests PASS.

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: add XGBoost ML model with feature engineering and training pipeline"
```

---

### Task 11: Combined Scorer + Custom Rules

**Files:**
- Create: `apps/scoring-engine/app/scoring/combined_scorer.py`
- Create: `apps/scoring-engine/app/scoring/custom_rules.py`
- Create: `apps/scoring-engine/tests/test_combined_scorer.py`

**Step 1: Write failing tests**

```python
# apps/scoring-engine/tests/test_combined_scorer.py
from app.scoring.combined_scorer import CombinedScorer, FinalScore
from app.scoring.signals import ExtractedSignals, Signal
from app.scoring.custom_rules import CustomRuleEngine, RuleDefinition


def _make_signals(vpn=False, disposable=False, deviation=1.0):
    signals = ExtractedSignals()
    signals.payment = [Signal("avs_mismatch", False, 8.0, "payment")]
    signals.behavioral = [Signal("first_time_customer", True, 12.0, "behavioral")]
    signals.geographic = [
        Signal("address_mismatch", False, 15.0, "geographic"),
        Signal("vpn_detected", vpn, 18.0, "geographic"),
    ]
    signals.order_pattern = [Signal("order_value_deviation", deviation, 11.0, "order_pattern")]
    signals.digital_footprint = [
        Signal("disposable_email", disposable, 20.0, "digital_footprint"),
        Signal("free_email_provider", True, 5.0, "digital_footprint"),
    ]
    return signals


def test_combined_scorer_returns_final_score():
    scorer = CombinedScorer(rule_weight=0.5, ml_weight=0.5)
    result = scorer.score(_make_signals())
    assert isinstance(result, FinalScore)
    assert 0 <= result.final_score <= 100


def test_combined_scorer_includes_both_scores():
    scorer = CombinedScorer(rule_weight=0.5, ml_weight=0.5)
    result = scorer.score(_make_signals())
    assert result.rule_score is not None
    assert result.ml_score is not None


def test_custom_rule_whitelist_overrides():
    rules = CustomRuleEngine()
    rules.add_whitelist("email", "trusted@company.com")
    action = rules.evaluate(email="trusted@company.com", ip="1.2.3.4")
    assert action == "approve"


def test_custom_rule_blacklist_overrides():
    rules = CustomRuleEngine()
    rules.add_blacklist("email", "fraud@bad.com")
    action = rules.evaluate(email="fraud@bad.com", ip="1.2.3.4")
    assert action == "block"


def test_custom_rule_conditions():
    rules = CustomRuleEngine()
    rule = RuleDefinition(
        name="High value VPN",
        conditions={"order_total_gt": 500, "vpn_detected": True, "first_time_customer": True},
        action="hold",
        priority=10,
    )
    rules.add_rule(rule)
    action = rules.evaluate_signals(
        signals_dict={"vpn_detected": True, "first_time_customer": True},
        order_total=600.0,
        email="test@test.com",
        ip="1.2.3.4",
    )
    assert action == "hold"
```

**Step 2: Implement custom rules engine**

```python
# apps/scoring-engine/app/scoring/custom_rules.py
from dataclasses import dataclass, field


@dataclass
class RuleDefinition:
    name: str
    conditions: dict  # e.g., {"order_total_gt": 500, "vpn_detected": True}
    action: str  # approve, hold, block, flag
    priority: int = 0


class CustomRuleEngine:
    def __init__(self):
        self.whitelist: dict[str, set[str]] = {"email": set(), "ip": set(), "bin": set()}
        self.blacklist: dict[str, set[str]] = {"email": set(), "ip": set(), "bin": set()}
        self.rules: list[RuleDefinition] = []

    def add_whitelist(self, entry_type: str, value: str):
        self.whitelist.setdefault(entry_type, set()).add(value.lower())

    def add_blacklist(self, entry_type: str, value: str):
        self.blacklist.setdefault(entry_type, set()).add(value.lower())

    def add_rule(self, rule: RuleDefinition):
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def evaluate(self, email: str = "", ip: str = "", card_bin: str = "") -> str | None:
        # Blacklist takes highest priority
        if email.lower() in self.blacklist.get("email", set()):
            return "block"
        if ip in self.blacklist.get("ip", set()):
            return "block"
        if card_bin in self.blacklist.get("bin", set()):
            return "block"

        # Whitelist
        if email.lower() in self.whitelist.get("email", set()):
            return "approve"
        if ip in self.whitelist.get("ip", set()):
            return "approve"

        return None

    def evaluate_signals(
        self,
        signals_dict: dict,
        order_total: float = 0,
        email: str = "",
        ip: str = "",
        card_bin: str = "",
    ) -> str | None:
        # Check whitelist/blacklist first
        override = self.evaluate(email=email, ip=ip, card_bin=card_bin)
        if override:
            return override

        # Evaluate custom rules
        for rule in self.rules:
            if self._matches(rule.conditions, signals_dict, order_total):
                return rule.action

        return None

    def _matches(self, conditions: dict, signals: dict, order_total: float) -> bool:
        for key, expected in conditions.items():
            if key == "order_total_gt":
                if order_total <= expected:
                    return False
            elif key == "order_total_lt":
                if order_total >= expected:
                    return False
            else:
                actual = signals.get(key)
                if actual != expected:
                    return False
        return True
```

**Step 3: Implement combined scorer**

```python
# apps/scoring-engine/app/scoring/combined_scorer.py
from dataclasses import dataclass, field
from app.scoring.signals import ExtractedSignals
from app.scoring.rule_engine import RuleBasedScorer
from app.scoring.ml_model import FraudMLModel
from app.scoring.feature_engineering import FeatureEngineer


@dataclass
class FinalScore:
    final_score: int
    risk_level: str
    recommendation: str
    rule_score: float
    ml_score: float
    signal_contributions: list[dict] = field(default_factory=list)
    custom_rule_action: str | None = None


class CombinedScorer:
    def __init__(
        self,
        rule_weight: float = 0.5,
        ml_weight: float = 0.5,
        model_path: str | None = None,
        thresholds: dict | None = None,
    ):
        self.rule_weight = rule_weight
        self.ml_weight = ml_weight
        self.rule_scorer = RuleBasedScorer(thresholds=thresholds)
        self.ml_model = FraudMLModel(model_path=model_path)
        self.feature_engineer = FeatureEngineer()

    def score(self, signals: ExtractedSignals) -> FinalScore:
        # Rule-based score
        rule_result = self.rule_scorer.score(signals)

        # ML score
        feature_vector = self.feature_engineer.transform(signals)
        ml_score = self.ml_model.predict(feature_vector)

        # Weighted combination
        if self.ml_model.is_loaded():
            combined = (rule_result.score * self.rule_weight) + (ml_score * self.ml_weight)
        else:
            # If no ML model loaded, use rule-based score only
            combined = float(rule_result.score)

        final_score = max(0, min(100, int(round(combined))))

        # Re-classify with final score
        risk_level = self.rule_scorer._classify(final_score)
        recommendation = self.rule_scorer._recommend(risk_level)

        return FinalScore(
            final_score=final_score,
            risk_level=risk_level,
            recommendation=recommendation,
            rule_score=float(rule_result.score),
            ml_score=ml_score,
            signal_contributions=rule_result.signal_contributions,
        )
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_combined_scorer.py -v
```

Expected: All 5 tests PASS.

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: add combined scorer (rule + ML) and custom rules engine"
```

---

### Task 12: Order Scoring API Endpoint

**Files:**
- Create: `apps/scoring-engine/app/api/v1/__init__.py`
- Create: `apps/scoring-engine/app/api/v1/scoring.py`
- Create: `apps/scoring-engine/tests/test_scoring_api.py`

**Step 1: Write failing tests**

```python
# apps/scoring-engine/tests/test_scoring_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
HEADERS = {"X-API-Key": "dev-key"}

SAMPLE_ORDER = {
    "order_id": "1001",
    "merchant_id": 1,
    "email": "test@gmail.com",
    "ip_address": "8.8.8.8",
    "shipping_country": "US",
    "shipping_state": "CA",
    "billing_country": "US",
    "billing_state": "CA",
    "order_total": 150.00,
    "currency": "USD",
    "line_items": [{"title": "Widget", "quantity": 1, "price": "150.00"}],
    "customer_id": "cust_123",
    "is_first_order": False,
    "phone": "+14155552671",
    "card_brand": "visa",
    "card_country": "US",
    "avs_result": "Y",
    "cvv_result": "M",
}


def test_score_order_endpoint():
    response = client.post("/api/v1/score", json=SAMPLE_ORDER, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "risk_score" in data
    assert "risk_level" in data
    assert "signal_contributions" in data
    assert 0 <= data["risk_score"] <= 100


def test_score_order_returns_all_fields():
    response = client.post("/api/v1/score", json=SAMPLE_ORDER, headers=HEADERS)
    data = response.json()
    assert "rule_score" in data
    assert "ml_score" in data
    assert "recommendation" in data


def test_score_order_requires_api_key():
    response = client.post("/api/v1/score", json=SAMPLE_ORDER)
    assert response.status_code == 401
```

**Step 2: Implement scoring endpoint**

```python
# apps/scoring-engine/app/api/v1/__init__.py
```

```python
# apps/scoring-engine/app/api/v1/scoring.py
from fastapi import APIRouter
from pydantic import BaseModel
from app.scoring.signals import SignalExtractor, OrderPayload
from app.scoring.combined_scorer import CombinedScorer
from app.enrichment.registry import EnrichmentRegistry

router = APIRouter(prefix="/api/v1")

# Initialize once at module level
enrichment = EnrichmentRegistry()
extractor = SignalExtractor(enrichment)
scorer = CombinedScorer()


class ScoreRequest(BaseModel):
    order_id: str
    merchant_id: int
    email: str
    ip_address: str
    shipping_country: str
    shipping_state: str
    billing_country: str
    billing_state: str
    order_total: float
    currency: str
    line_items: list[dict]
    customer_id: str
    is_first_order: bool
    phone: str = ""
    card_bin: str = ""
    card_last4: str = ""
    card_brand: str = ""
    card_country: str = ""
    avs_result: str = ""
    cvv_result: str = ""
    payment_gateway: str = ""
    browser_ip: str = ""
    created_at: str = ""


class ScoreResponse(BaseModel):
    order_id: str
    risk_score: int
    risk_level: str
    recommendation: str
    rule_score: float
    ml_score: float
    signal_contributions: list[dict]


@router.post("/score", response_model=ScoreResponse)
async def score_order(request: ScoreRequest):
    order = OrderPayload(**request.model_dump())

    # Extract signals
    signals = extractor.extract(order, store_avg_order=150.0)  # TODO: compute from merchant's real data

    # Score
    result = scorer.score(signals)

    return ScoreResponse(
        order_id=request.order_id,
        risk_score=result.final_score,
        risk_level=result.risk_level,
        recommendation=result.recommendation,
        rule_score=result.rule_score,
        ml_score=result.ml_score,
        signal_contributions=result.signal_contributions,
    )
```

**Step 3: Register router in main.py**

Add to `apps/scoring-engine/app/main.py`:
```python
from app.api.v1.scoring import router as scoring_router
app.include_router(scoring_router)
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_scoring_api.py -v
```

Expected: All 3 tests PASS.

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: add /api/v1/score endpoint for real-time order scoring"
```

---

## Phase 3: Webhook Pipeline + Shopify Integration (Week 3-4 continued)

### Task 13: Shopify Webhook Handler (Remix)

**Files:**
- Create: `apps/web/app/routes/webhooks.orders-create.tsx`
- Create: `apps/web/app/routes/webhooks.disputes-create.tsx`
- Create: `apps/web/app/routes/webhooks.tsx` (GDPR compliance)
- Create: `apps/web/app/lib/webhook-helpers.server.ts`

**Step 1: Create webhook helper**

```typescript
// apps/web/app/lib/webhook-helpers.server.ts
const SCORING_ENGINE_URL = process.env.SCORING_ENGINE_URL || "http://localhost:8000";
const SCORING_API_KEY = process.env.SCORING_API_KEY || "dev-key";

export async function sendToScoringEngine(orderPayload: any, merchantId: number) {
  const scoringPayload = {
    order_id: String(orderPayload.id),
    merchant_id: merchantId,
    email: orderPayload.email || "",
    ip_address: orderPayload.browser_ip || orderPayload.client_details?.browser_ip || "",
    shipping_country: orderPayload.shipping_address?.country_code || "",
    shipping_state: orderPayload.shipping_address?.province_code || "",
    billing_country: orderPayload.billing_address?.country_code || "",
    billing_state: orderPayload.billing_address?.province_code || "",
    order_total: parseFloat(orderPayload.total_price || "0"),
    currency: orderPayload.currency || "USD",
    line_items: (orderPayload.line_items || []).map((item: any) => ({
      title: item.title,
      quantity: item.quantity,
      price: item.price,
    })),
    customer_id: String(orderPayload.customer?.id || ""),
    is_first_order: orderPayload.customer?.orders_count === 1,
    phone: orderPayload.phone || orderPayload.billing_address?.phone || "",
    card_brand: orderPayload.payment_details?.credit_card_company || "",
    card_bin: orderPayload.payment_details?.credit_card_bin || "",
    avs_result: orderPayload.payment_details?.avs_result_code || "",
    cvv_result: orderPayload.payment_details?.cvv_result_code || "",
    created_at: orderPayload.created_at || "",
  };

  const response = await fetch(`${SCORING_ENGINE_URL}/api/v1/score`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": SCORING_API_KEY,
    },
    body: JSON.stringify(scoringPayload),
  });

  if (!response.ok) {
    throw new Error(`Scoring engine error: ${response.status}`);
  }

  return response.json();
}

export async function writeRiskToShopify(
  admin: any,
  orderId: string,
  riskScore: number,
  riskLevel: string,
  recommendation: string,
  signalSummary: string
) {
  // Use REST API for Order Risk (not available via GraphQL)
  const response = await admin.rest.post({
    path: `orders/${orderId}/risks.json`,
    data: {
      risk: {
        message: signalSummary,
        recommendation: riskLevel === "critical" ? "cancel" : riskLevel === "high" ? "investigate" : "accept",
        score: riskScore / 100, // Shopify expects 0-1
        source: "ShieldCommerce",
        cause_order: false,
        display: true,
      },
    },
  });

  return response;
}
```

**Step 2: Create orders/create webhook handler**

```typescript
// apps/web/app/routes/webhooks.orders-create.tsx
import type { ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { sendToScoringEngine, writeRiskToShopify } from "../lib/webhook-helpers.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { topic, shop, payload, admin } = await authenticate.webhook(request);

  if (!admin) {
    throw new Response("Unauthorized", { status: 401 });
  }

  try {
    // Score the order
    const merchantId = 1; // TODO: lookup merchant by shop domain
    const scoreResult = await sendToScoringEngine(payload, merchantId);

    // Write risk back to Shopify
    const topSignals = scoreResult.signal_contributions
      .slice(0, 3)
      .map((s: any) => s.explanation)
      .join("; ");

    await writeRiskToShopify(
      admin,
      String(payload.id),
      scoreResult.risk_score,
      scoreResult.risk_level,
      scoreResult.recommendation,
      `Risk Score: ${scoreResult.risk_score}/100. ${topSignals}`
    );

    console.log(`[ShieldCommerce] Order ${payload.id} scored: ${scoreResult.risk_score} (${scoreResult.risk_level})`);
  } catch (error) {
    console.error(`[ShieldCommerce] Error scoring order ${payload.id}:`, error);
    // Don't throw — webhook must return 200 to avoid retries for transient errors
  }

  return new Response("OK", { status: 200 });
};
```

**Step 3: Create disputes/create webhook handler**

```typescript
// apps/web/app/routes/webhooks.disputes-create.tsx
import type { ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { topic, shop, payload } = await authenticate.webhook(request);

  try {
    const SCORING_ENGINE_URL = process.env.SCORING_ENGINE_URL || "http://localhost:8000";
    const SCORING_API_KEY = process.env.SCORING_API_KEY || "dev-key";

    await fetch(`${SCORING_ENGINE_URL}/api/v1/chargebacks`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": SCORING_API_KEY,
      },
      body: JSON.stringify({
        shop_domain: shop,
        shopify_order_id: String(payload.order_id),
        dispute_type: payload.type || "chargeback",
        amount: parseFloat(payload.amount || "0"),
        filed_at: payload.initiated_at || new Date().toISOString(),
      }),
    });

    console.log(`[ShieldCommerce] Chargeback recorded for order ${payload.order_id}`);
  } catch (error) {
    console.error(`[ShieldCommerce] Error recording chargeback:`, error);
  }

  return new Response("OK", { status: 200 });
};
```

**Step 4: Create GDPR compliance webhooks**

```typescript
// apps/web/app/routes/webhooks.tsx
import type { ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { topic, shop, payload } = await authenticate.webhook(request);

  switch (topic) {
    case "CUSTOMERS_DATA_REQUEST":
      // Return stored customer data — respond to Shopify within 30 days
      console.log(`[GDPR] Data request for shop ${shop}, customer ${payload.customer?.id}`);
      break;
    case "CUSTOMERS_REDACT":
      // Delete customer data
      console.log(`[GDPR] Customer redact for shop ${shop}, customer ${payload.customer?.id}`);
      // TODO: Call scoring engine to delete customer scoring data
      break;
    case "SHOP_REDACT":
      // Delete all shop data (48 hours after app uninstall)
      console.log(`[GDPR] Shop redact for ${shop}`);
      // TODO: Call scoring engine to delete all merchant data
      break;
  }

  return new Response("OK", { status: 200 });
};
```

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: add Shopify webhook handlers for order scoring, chargebacks, and GDPR"
```

---

## Phase 4: Dashboard UI (Week 5-6)

### Task 14: Dashboard Page — KPIs + Charts

**Files:**
- Create: `apps/web/app/routes/app._index.tsx` (main dashboard)
- Create: `apps/web/app/components/KpiCards.tsx`
- Create: `apps/web/app/components/ScoreDistributionChart.tsx`
- Create: `apps/web/app/components/RiskTrendChart.tsx`

*Implementation: Polaris Page layout with KPI cards using Polaris `Card` + `Text`, Recharts `BarChart` for score distribution, Recharts `LineChart` for trend. Data loaded via Remix `loader` calling the scoring API.*

**Step 1: Implement dashboard route**

```typescript
// apps/web/app/routes/app._index.tsx
import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { Page, Layout, Card, Text, BlockStack, InlineGrid } from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { getDashboardStats } from "../lib/scoring-api.server";
import { KpiCards } from "../components/KpiCards";
import { ScoreDistributionChart } from "../components/ScoreDistributionChart";
import { RiskTrendChart } from "../components/RiskTrendChart";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  try {
    const stats = await getDashboardStats(1, 30); // TODO: resolve merchant ID from session
    return json({ stats, error: null });
  } catch {
    return json({
      stats: {
        total_orders: 0,
        flagged_orders: 0,
        avg_score: 0,
        chargeback_count: 0,
        chargeback_amount: 0,
        score_distribution: [],
        trend_data: [],
      },
      error: "Unable to load dashboard data",
    });
  }
};

export default function Dashboard() {
  const { stats, error } = useLoaderData<typeof loader>();

  return (
    <Page title="ShieldCommerce Dashboard">
      <BlockStack gap="500">
        <KpiCards
          totalOrders={stats.total_orders}
          flaggedOrders={stats.flagged_orders}
          avgScore={stats.avg_score}
          chargebackCount={stats.chargeback_count}
          chargebackAmount={stats.chargeback_amount}
        />
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">Score Distribution</Text>
                <ScoreDistributionChart data={stats.score_distribution} />
              </BlockStack>
            </Card>
          </Layout.Section>
          <Layout.Section variant="oneThird">
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">Risk Trend (30 days)</Text>
                <RiskTrendChart data={stats.trend_data} />
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
        {error && (
          <Card>
            <Text as="p" tone="critical">{error}</Text>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
```

**Step 2: KPI cards component**

```typescript
// apps/web/app/components/KpiCards.tsx
import { InlineGrid, Card, Text, BlockStack } from "@shopify/polaris";

interface KpiCardsProps {
  totalOrders: number;
  flaggedOrders: number;
  avgScore: number;
  chargebackCount: number;
  chargebackAmount: number;
}

export function KpiCards({ totalOrders, flaggedOrders, avgScore, chargebackCount, chargebackAmount }: KpiCardsProps) {
  const flaggedPct = totalOrders > 0 ? ((flaggedOrders / totalOrders) * 100).toFixed(1) : "0";

  const kpis = [
    { label: "Total Orders Scored", value: totalOrders.toLocaleString() },
    { label: "Flagged Orders", value: `${flaggedOrders} (${flaggedPct}%)` },
    { label: "Avg Risk Score", value: avgScore.toFixed(1) },
    { label: "Chargebacks", value: `${chargebackCount} ($${chargebackAmount.toLocaleString()})` },
  ];

  return (
    <InlineGrid columns={{ xs: 1, sm: 2, lg: 4 }} gap="400">
      {kpis.map((kpi) => (
        <Card key={kpi.label}>
          <BlockStack gap="200">
            <Text as="p" variant="bodySm" tone="subdued">{kpi.label}</Text>
            <Text as="p" variant="headingLg">{kpi.value}</Text>
          </BlockStack>
        </Card>
      ))}
    </InlineGrid>
  );
}
```

**Step 3: Score distribution chart**

```typescript
// apps/web/app/components/ScoreDistributionChart.tsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface ScoreDistributionProps {
  data: { range: string; count: number }[];
}

const RISK_COLORS: Record<string, string> = {
  "0-30": "#4CAF50",
  "31-60": "#FFC107",
  "61-85": "#F44336",
  "86-100": "#B71C1C",
};

export function ScoreDistributionChart({ data }: ScoreDistributionProps) {
  if (!data || data.length === 0) {
    return <p>No scoring data yet. Orders will appear here once scored.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <XAxis dataKey="range" />
        <YAxis />
        <Tooltip />
        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
          {data.map((entry) => (
            <Cell key={entry.range} fill={RISK_COLORS[entry.range] || "#999"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
```

**Step 4: Risk trend chart**

```typescript
// apps/web/app/components/RiskTrendChart.tsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

interface RiskTrendProps {
  data: { date: string; avg_score: number; order_count: number }[];
}

export function RiskTrendChart({ data }: RiskTrendProps) {
  if (!data || data.length === 0) {
    return <p>Trend data will appear after a few days of scoring.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <XAxis dataKey="date" />
        <YAxis domain={[0, 100]} />
        <Tooltip />
        <Line type="monotone" dataKey="avg_score" stroke="#F44336" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: add dashboard page with KPI cards, score distribution, and risk trend charts"
```

---

### Task 15: Orders List Page

**Files:**
- Create: `apps/web/app/routes/app.orders.tsx`
- Create: `apps/web/app/components/RiskBadge.tsx`

*Implementation: Polaris `IndexTable` with sortable columns, RiskBadge component, pagination, risk level filter. Links to order detail page.*

**Step 1-3:** Implement orders page with Polaris IndexTable, RiskBadge using Polaris `Badge` with tone mapping (success/warning/critical), loader calling `getOrderScores()`.

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: add orders list page with risk badges, sorting, and pagination"
```

---

### Task 16: Order Detail Page

**Files:**
- Create: `apps/web/app/routes/app.orders.$orderId.tsx`
- Create: `apps/web/app/components/SignalBreakdownTable.tsx`
- Create: `apps/web/app/components/OrderActions.tsx`

*Implementation: Full signal breakdown table showing each signal's name, finding, points added, and explanation. Action buttons (approve/hold/cancel) that call `overrideOrder()`. Override reason modal.*

**Step 1-3:** Implement order detail with Polaris `DataTable` for signals, `ButtonGroup` for actions, `Modal` for override reason input.

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: add order detail page with signal breakdown and action buttons"
```

---

### Task 17: Rules & Settings Pages

**Files:**
- Create: `apps/web/app/routes/app.rules.tsx`
- Create: `apps/web/app/routes/app.settings.tsx`
- Create: `apps/web/app/components/ThresholdSliders.tsx`
- Create: `apps/web/app/components/WhitelistBlacklist.tsx`
- Create: `apps/web/app/components/RuleBuilder.tsx`

*Implementation:*
- **Rules page:** Threshold sliders using Polaris `RangeSlider`, whitelist/blacklist management with `TextField` + `Tag`, custom rule builder with condition dropdowns.
- **Settings page:** Email alert toggle, risk level checkboxes, digest frequency select, digest email input. All persisted via PATCH to scoring engine.

**Step 1-3:** Implement both pages with Polaris form components, Remix `action` functions for form submission.

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: add rules page (thresholds, whitelist/blacklist, rule builder) and settings page"
```

---

### Task 18: Billing Page — Shopify Subscriptions

**Files:**
- Create: `apps/web/app/routes/app.billing.tsx`
- Create: `apps/web/app/lib/billing.server.ts`

**Step 1: Implement billing utilities**

```typescript
// apps/web/app/lib/billing.server.ts
import type { PlanTier } from "./types";

interface PlanConfig {
  name: string;
  price: number;
  orderLimit: number;
  trialDays: number;
}

export const PLANS: Record<PlanTier, PlanConfig> = {
  starter: { name: "Starter", price: 29.0, orderLimit: 500, trialDays: 14 },
  growth: { name: "Growth", price: 69.0, orderLimit: 2000, trialDays: 14 },
  pro: { name: "Pro", price: 149.0, orderLimit: 10000, trialDays: 14 },
  scale: { name: "Scale", price: 249.0, orderLimit: 25000, trialDays: 14 },
};

export async function createSubscription(admin: any, plan: PlanTier, returnUrl: string) {
  const config = PLANS[plan];

  const response = await admin.graphql(`
    mutation AppSubscriptionCreate($name: String!, $lineItems: [AppSubscriptionLineItemInput!]!, $returnUrl: URL!, $trialDays: Int) {
      appSubscriptionCreate(
        name: $name
        returnUrl: $returnUrl
        trialDays: $trialDays
        lineItems: $lineItems
      ) {
        appSubscription {
          id
          status
        }
        confirmationUrl
        userErrors {
          field
          message
        }
      }
    }
  `, {
    variables: {
      name: `ShieldCommerce ${config.name}`,
      returnUrl,
      trialDays: config.trialDays,
      lineItems: [{
        plan: {
          appRecurringPricingDetails: {
            price: { amount: config.price, currencyCode: "USD" },
            interval: "EVERY_30_DAYS",
          },
        },
      }],
    },
  });

  const data = await response.json();
  return data.data.appSubscriptionCreate;
}
```

**Step 2: Implement billing page**

```typescript
// apps/web/app/routes/app.billing.tsx
import { json, redirect, type ActionFunctionArgs, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData, useSubmit } from "@remix-run/react";
import { Page, Layout, Card, Text, BlockStack, Button, InlineGrid, Badge, List } from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { PLANS, createSubscription } from "../lib/billing.server";
import type { PlanTier } from "../lib/types";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  const currentPlan: PlanTier = "starter"; // TODO: load from merchant record
  return json({ currentPlan, plans: PLANS });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { admin } = await authenticate.admin(request);
  const formData = await request.formData();
  const plan = formData.get("plan") as PlanTier;
  const url = new URL(request.url);

  const result = await createSubscription(admin, plan, `${url.origin}/app/billing`);

  if (result.confirmationUrl) {
    return redirect(result.confirmationUrl);
  }

  return json({ error: result.userErrors });
};

export default function Billing() {
  const { currentPlan, plans } = useLoaderData<typeof loader>();
  const submit = useSubmit();

  return (
    <Page title="Billing & Plans">
      <InlineGrid columns={{ xs: 1, sm: 2, lg: 4 }} gap="400">
        {(Object.entries(plans) as [PlanTier, any][]).map(([key, plan]) => (
          <Card key={key}>
            <BlockStack gap="300">
              <BlockStack gap="100">
                <Text as="h2" variant="headingMd">{plan.name}</Text>
                {currentPlan === key && <Badge tone="success">Current Plan</Badge>}
              </BlockStack>
              <Text as="p" variant="headingLg">${plan.price}/mo</Text>
              <Text as="p" variant="bodySm" tone="subdued">Up to {plan.orderLimit.toLocaleString()} orders/mo</Text>
              {currentPlan !== key && (
                <Button onClick={() => submit({ plan: key }, { method: "post" })}>
                  {currentPlan && Object.keys(plans).indexOf(key) > Object.keys(plans).indexOf(currentPlan)
                    ? "Upgrade" : "Switch"}
                </Button>
              )}
            </BlockStack>
          </Card>
        ))}
      </InlineGrid>
    </Page>
  );
}
```

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: add billing page with Shopify subscription management"
```

---

## Phase 5: Email Alerts + Dashboard API (Week 5-6 continued)

### Task 19: Dashboard Stats API Endpoint (FastAPI)

**Files:**
- Create: `apps/scoring-engine/app/api/v1/dashboard.py`
- Create: `apps/scoring-engine/app/api/v1/merchants.py`
- Create: `apps/scoring-engine/app/api/v1/chargebacks.py`
- Create: `apps/scoring-engine/tests/test_dashboard_api.py`

*Implementation: Endpoints for dashboard stats aggregation, order listing with pagination, order detail, merchant settings CRUD, chargeback recording. All query PostgreSQL via SQLAlchemy.*

**Step 1-4:** Implement all CRUD endpoints following the same pattern as the scoring endpoint — Pydantic request/response models, SQLAlchemy queries, proper error handling.

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: add dashboard, merchant, and chargeback API endpoints"
```

---

### Task 20: Email Alert Service

**Files:**
- Create: `apps/scoring-engine/app/services/email_service.py`
- Create: `apps/scoring-engine/app/services/digest_service.py`
- Create: `apps/scoring-engine/tests/test_email_service.py`

**Step 1: Write failing test**

```python
# apps/scoring-engine/tests/test_email_service.py
from app.services.email_service import EmailService, AlertEmail


def test_alert_email_rendering():
    email = AlertEmail(
        to="merchant@store.com",
        order_id="1042",
        risk_score=73,
        risk_level="high",
        top_signals=[
            {"signal_name": "vpn_detected", "points_added": 18, "explanation": "VPN detected"},
            {"signal_name": "address_mismatch", "points_added": 15, "explanation": "States differ"},
        ],
        shop_domain="cool-store.myshopify.com",
    )
    html = email.render_html()
    assert "1042" in html
    assert "73" in html
    assert "high" in html.lower()
    assert "VPN detected" in html
```

**Step 2: Implement email service**

```python
# apps/scoring-engine/app/services/email_service.py
from dataclasses import dataclass
from app.config import settings


@dataclass
class AlertEmail:
    to: str
    order_id: str
    risk_score: int
    risk_level: str
    top_signals: list[dict]
    shop_domain: str

    def render_html(self) -> str:
        signals_html = "".join(
            f"<tr><td>{s['signal_name']}</td><td>+{s['points_added']}</td><td>{s['explanation']}</td></tr>"
            for s in self.top_signals
        )

        color = {"low": "#4CAF50", "medium": "#FFC107", "high": "#F44336", "critical": "#B71C1C"}.get(self.risk_level, "#999")

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: {color};">ShieldCommerce Alert: {self.risk_level.upper()} Risk Order</h2>
            <p>Order <strong>#{self.order_id}</strong> on <strong>{self.shop_domain}</strong> has been scored as
            <strong style="color: {color};">{self.risk_level}</strong> risk with a score of <strong>{self.risk_score}/100</strong>.</p>
            <h3>Top Risk Signals</h3>
            <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
                <tr style="background: #f5f5f5;"><th>Signal</th><th>Points</th><th>Details</th></tr>
                {signals_html}
            </table>
            <p style="margin-top: 20px;">
                <a href="https://{self.shop_domain}/admin/orders/{self.order_id}" style="background: {color}; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">
                    Review Order in Shopify
                </a>
            </p>
            <p style="color: #999; font-size: 12px; margin-top: 30px;">Sent by ShieldCommerce. Manage alert settings in your app dashboard.</p>
        </body>
        </html>
        """

    def render_subject(self) -> str:
        return f"[ShieldCommerce] {self.risk_level.upper()} Risk: Order #{self.order_id} (Score: {self.risk_score})"


class EmailService:
    def __init__(self):
        self.api_key = settings.sendgrid_api_key
        self.from_email = settings.alert_from_email

    def send_alert(self, alert: AlertEmail) -> bool:
        if not self.api_key:
            print(f"[EmailService] SendGrid not configured. Would send alert for order {alert.order_id} to {alert.to}")
            return False

        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content

            sg = sendgrid.SendGridAPIClient(api_key=self.api_key)
            mail = Mail(
                from_email=Email(self.from_email, "ShieldCommerce"),
                to_emails=To(alert.to),
                subject=alert.render_subject(),
                html_content=Content("text/html", alert.render_html()),
            )
            sg.client.mail.send.post(request_body=mail.get())
            return True
        except Exception as e:
            print(f"[EmailService] Failed to send alert: {e}")
            return False
```

**Step 3: Run tests**

```bash
python -m pytest tests/test_email_service.py -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: add email alert service with SendGrid integration"
```

---

## Phase 6: ML Training + Polish (Week 7)

### Task 21: Train XGBoost Model on Kaggle Data

**Steps:**
1. Download Kaggle IEEE-CIS Fraud Detection dataset
2. Run training script: `python -m app.scoring.train --data data/train_transaction.csv --output models/fraud_model_v1.joblib`
3. Record model metrics in `model_versions` table
4. Update `CombinedScorer` to load the trained model

**Commit:**
```bash
git add -A
git commit -m "feat: train XGBoost v1 model on Kaggle IEEE-CIS dataset"
```

---

### Task 22: Scoring Persistence + Write-Back Pipeline

**Files:**
- Create: `apps/scoring-engine/app/services/scoring_pipeline.py`

*Implementation: Complete pipeline that orchestrates signal extraction → scoring → DB persistence → Shopify write-back → email alert. This is the service called by the webhook handler.*

**Commit:**
```bash
git add -A
git commit -m "feat: add end-to-end scoring pipeline with persistence and write-back"
```

---

## Phase 7: Security + Testing + Deployment (Week 8)

### Task 23: Security Hardening

**Files:**
- Create: `apps/scoring-engine/app/services/encryption.py`
- Modify: Various files for security improvements

*Implementation:*
- AES-256 encryption for merchant access tokens (`cryptography` library)
- Rate limiting on scoring endpoint (10 req/sec per merchant)
- SQL injection prevention (already handled by SQLAlchemy parameterized queries)
- Input validation on all Pydantic models
- HMAC-SHA256 verification on Shopify webhooks (handled by `@shopify/shopify-app-remix`)
- CORS tightened to allow only the Remix app origin

**Commit:**
```bash
git add -A
git commit -m "feat: add encryption, rate limiting, and security hardening"
```

---

### Task 24: End-to-End Tests

**Files:**
- Create: `apps/scoring-engine/tests/test_e2e_scoring.py`
- Create: `apps/scoring-engine/tests/fixtures/sample_orders.py`

*Implementation: 50+ test orders with varied risk profiles (clean, slightly suspicious, clearly fraudulent, edge cases). Verify scoring, classification, signal extraction, and persistence.*

**Commit:**
```bash
git add -A
git commit -m "test: add end-to-end tests with 50+ varied order scenarios"
```

---

### Task 25: CI/CD Pipeline

**Files:**
- Modify: `.github/workflows/ci.yml`

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  scoring-engine:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: shieldcommerce_test
          POSTGRES_USER: shield
          POSTGRES_PASSWORD: testpass
        ports: ["5432:5432"]
        options: --health-cmd pg_isready --health-interval 10s --health-timeout 5s --health-retries 5
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
        options: --health-cmd "redis-cli ping" --health-interval 10s --health-timeout 5s --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        working-directory: apps/scoring-engine
        run: pip install -e ".[dev]"
      - name: Run tests
        working-directory: apps/scoring-engine
        run: pytest --tb=short -v
        env:
          SC_DATABASE_URL: postgresql://shield:testpass@localhost:5432/shieldcommerce_test
          SC_REDIS_URL: redis://localhost:6379/0

  remix-app:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - name: Install dependencies
        working-directory: apps/web
        run: npm ci
      - name: Type check
        working-directory: apps/web
        run: npx tsc --noEmit
      - name: Build
        working-directory: apps/web
        run: npm run build
```

**Commit:**
```bash
git add -A
git commit -m "ci: add GitHub Actions workflow for scoring engine and Remix app"
```

---

### Task 26: DigitalOcean Deployment Config

**Files:**
- Create: `apps/scoring-engine/.do/app.yaml`
- Create: `apps/web/.do/app.yaml`
- Create: `deploy/do-app-spec.yaml` (combined app spec)

```yaml
# deploy/do-app-spec.yaml
name: shieldcommerce
region: nyc

services:
  - name: web
    source_dir: apps/web
    github:
      repo: your-org/shieldcommerce
      branch: main
      deploy_on_push: true
    build_command: npm ci && npm run build
    run_command: npm start
    instance_size_slug: basic-xxs
    instance_count: 1
    http_port: 3000
    envs:
      - key: SCORING_ENGINE_URL
        value: ${scoring-engine.PRIVATE_URL}
      - key: SCORING_API_KEY
        type: SECRET
        value: "change-in-production"

  - name: scoring-engine
    dockerfile_path: apps/scoring-engine/Dockerfile
    source_dir: apps/scoring-engine
    github:
      repo: your-org/shieldcommerce
      branch: main
      deploy_on_push: true
    instance_size_slug: basic-xxs
    instance_count: 1
    http_port: 8000
    envs:
      - key: SC_DATABASE_URL
        value: ${db.DATABASE_URL}
      - key: SC_REDIS_URL
        value: ${cache.REDIS_URL}
      - key: SC_ENCRYPTION_KEY
        type: SECRET
        value: "change-in-production"

databases:
  - name: db
    engine: PG
    version: "16"
    size: db-s-1vcpu-1gb
    num_nodes: 1

  - name: cache
    engine: REDIS
    version: "7"
    size: db-s-1vcpu-1gb
    num_nodes: 1
```

**Commit:**
```bash
git add -A
git commit -m "deploy: add DigitalOcean App Platform deployment configuration"
```

---

### Task 27: App Store Listing Preparation

**Files:**
- Create: `docs/app-store-listing.md`

*Content: App name, tagline, description (keyword-optimized for "Shopify fraud prevention", "chargeback protection", "order risk scoring"), feature bullets, 5 screenshot descriptions, demo video script outline.*

**Commit:**
```bash
git add -A
git commit -m "docs: add Shopify App Store listing copy and screenshot plan"
```

---

## Summary

| Phase | Tasks | Weeks | Key Deliverable |
|-------|-------|-------|----------------|
| 1: Foundation | Tasks 1-6 | Week 1-2 | Working Shopify app scaffold + FastAPI + DB |
| 2: Scoring Core | Tasks 7-12 | Week 3-4 | Real-time order scoring with 30+ signals |
| 3: Webhooks | Task 13 | Week 3-4 | Live webhook pipeline + Shopify Risk API write-back |
| 4: Dashboard UI | Tasks 14-18 | Week 5-6 | Full embedded dashboard with all 6 pages |
| 5: Alerts | Tasks 19-20 | Week 5-6 | Email alerts + digest + dashboard API |
| 6: ML + Polish | Tasks 21-22 | Week 7 | Trained XGBoost model + end-to-end pipeline |
| 7: Ship | Tasks 23-27 | Week 8 | Security, CI/CD, deployment, App Store submission |

**Total: 27 tasks across 8 weeks.**
