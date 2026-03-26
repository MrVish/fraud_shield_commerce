"""initial schema - all core tables

Revision ID: a89934ef1e73
Revises: 
Create Date: 2026-03-26 13:45:19.544876

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a89934ef1e73'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    NOTE: This is a placeholder migration. Run `alembic revision --autogenerate`
    against a real PostgreSQL database to generate the full DDL for all 10 core
    tables: merchants, order_scores, scoring_signals, chargebacks, custom_rules,
    whitelist_blacklists, merchant_overrides, enrichment_caches, model_versions,
    and daily_digests.

    The autogenerate command will diff the SQLAlchemy models (app/models/) against
    the connected database and produce the correct CREATE TABLE / ALTER TABLE ops.
    """
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
