"""Integración API Teamwork v3, homologación de catálogos e importador de tiempos (spec 042)

Revision ID: 054
Revises: 053
Create Date: 2026-08-09

Crea `teamwork_integration_configs` (fila única, credenciales cifradas), `teamwork_entity_mappings`
(homologación Teamwork↔SYTIX de Empresas/Proyectos/Personal/Listas de Tareas) y
`time_import_batches` (auditoría agregada por carga de tiempos confirmada — ver data-model.md).
Agrega `external_time_id` a `work_sessions` con índice único parcial para el upsert idempotente
(FR-013). Crea los permisos `teamwork_integration:manage` (Admin) y `teamwork_integration:operate`
(Admin, Coordinador) — mismo patrón SQL crudo que las migraciones 048/051/052/053. No toca ninguna
tabla ni permiso de spec 041 (`ticket_imports`).
"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "054"
down_revision = "053"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = {
    ("teamwork_integration", "manage"): ["Admin"],
    ("teamwork_integration", "operate"): ["Admin", "Coordinador"],
}


def upgrade() -> None:
    op.create_table(
        "teamwork_integration_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("site_url", sa.Text(), nullable=False),
        sa.Column("api_token", sa.LargeBinary(), nullable=True),
        sa.Column("environment", sa.Text(), nullable=False, server_default="test"),
        sa.Column("last_test_status", sa.Text(), nullable=True),
        sa.Column("last_test_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_test_message", sa.Text(), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "teamwork_entity_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("teamwork_id", sa.Text(), nullable=False),
        sa.Column("teamwork_name", sa.Text(), nullable=True),
        sa.Column("sytix_entity_type", sa.Text(), nullable=True),
        sa.Column("sytix_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("match_method", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("entity_type", "teamwork_id", name="uq_teamwork_entity_mappings_key"),
    )

    op.create_table(
        "time_import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("imported_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("imported_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolved_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_rows", sa.Integer(), nullable=False, server_default="0"),
    )

    op.add_column("work_sessions", sa.Column("external_time_id", sa.Text(), nullable=True))
    op.create_index(
        "ix_work_sessions_external_time_id", "work_sessions", ["external_time_id"],
        unique=True, postgresql_where=sa.text("external_time_id IS NOT NULL"),
    )

    bind = op.get_bind()
    roles = {r.name: r.id for r in bind.execute(sa.text("SELECT id, name FROM roles")).fetchall()}
    for (module, action), role_names in NEW_PERMISSIONS.items():
        perm_id = uuid.uuid4()
        bind.execute(
            sa.text("INSERT INTO permissions (id, module, action) VALUES (:id, :module, :action)"),
            {"id": str(perm_id), "module": module, "action": action},
        )
        for role_name in role_names:
            if role_name in roles:
                bind.execute(
                    sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"),
                    {"r": str(roles[role_name]), "p": str(perm_id)},
                )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE module = 'teamwork_integration')"
    ))
    bind.execute(sa.text("DELETE FROM permissions WHERE module = 'teamwork_integration'"))

    op.drop_index("ix_work_sessions_external_time_id", table_name="work_sessions")
    op.drop_column("work_sessions", "external_time_id")

    op.drop_table("time_import_batches")
    op.drop_table("teamwork_entity_mappings")
    op.drop_table("teamwork_integration_configs")
