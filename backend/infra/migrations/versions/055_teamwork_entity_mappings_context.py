"""Contexto jerárquico y correo en la homologación de Teamwork (spec 043)

Revision ID: 055
Revises: 054
Create Date: 2026-08-10

Agrega 2 columnas nullable a `teamwork_entity_mappings` (ya creada en 054): `parent_teamwork_id`
(ID de Teamwork del padre jerárquico inmediato — Empresa dueña de un Proyecto, Proyecto dueño de
una Lista de Tareas) y `teamwork_email` (correo de Teamwork, solo para `entity_type="person"`).
Sin tabla nueva, sin backfill — ver research.md Decisión 2-4 de spec 043. `match_method` (columna
ya existente) gana el valor de aplicación `"created_new"`, sin cambio de esquema.
"""
from alembic import op
import sqlalchemy as sa

revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teamwork_entity_mappings", sa.Column("parent_teamwork_id", sa.Text(), nullable=True))
    op.add_column("teamwork_entity_mappings", sa.Column("teamwork_email", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("teamwork_entity_mappings", "teamwork_email")
    op.drop_column("teamwork_entity_mappings", "parent_teamwork_id")
