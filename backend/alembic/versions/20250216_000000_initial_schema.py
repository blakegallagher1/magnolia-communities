"""Initial database schema."""

from __future__ import annotations

from alembic import op

from app.core.database import Base

import app.models  # noqa: F401

revision = "20250216_000000"
down_revision = None
branch_labels = None
depends_on = None

GIST_INDEXES = [
    ("ix_service_requests_311_geometry_gist", "service_requests_311"),
    ("ix_parcels_geometry_gist", "parcels"),
    ("ix_zoning_districts_geometry_gist", "zoning_districts"),
    ("ix_city_limits_geometry_gist", "city_limits"),
    ("ix_adjudicated_parcels_geometry_gist", "adjudicated_parcels"),
]


def upgrade() -> None:
    """Create schema and spatial indexes."""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    for index_name, table_name in GIST_INDEXES:
        op.create_index(
            index_name,
            table_name,
            ["geometry"],
            postgresql_using="gist",
        )


def downgrade() -> None:
    """Drop spatial indexes and schema."""
    for index_name, table_name in GIST_INDEXES:
        op.drop_index(index_name, table_name=table_name)

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
    op.execute("DROP EXTENSION IF EXISTS postgis")
