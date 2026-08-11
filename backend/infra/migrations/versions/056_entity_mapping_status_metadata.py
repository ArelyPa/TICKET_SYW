"""Estado Inactivo y metadatos ampliados en la homologación de Teamwork (spec 045)

Revision ID: 056
Revises: 055
Create Date: 2026-08-11

Agrega 2 columnas a `teamwork_entity_mappings` (ya creada en 054): `is_discarded` (marca persistente
del estado "Inactivo" de la matriz de 4 estados, independiente de `sytix_id`/`match_method` — ver
research.md Decisión 1 de spec 045) y `teamwork_metadata` (JSONB libre con los campos ampliados de
la API v3 por tipo de entidad: País/Dirección/Dominio/Teléfono en Empresas, Cargo/Zona horaria en
Personal, descripción/estado en Proyectos y Listas — ver research.md Decisión 5). Sin tabla nueva,
sin backfill.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "056"
down_revision = "055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teamwork_entity_mappings",
        sa.Column("is_discarded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "teamwork_entity_mappings",
        sa.Column("teamwork_metadata", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("teamwork_entity_mappings", "teamwork_metadata")
    op.drop_column("teamwork_entity_mappings", "is_discarded")
