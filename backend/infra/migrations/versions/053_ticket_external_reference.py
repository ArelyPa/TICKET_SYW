"""Campos de referencia externa Teamwork + permiso ticket_imports:run (spec 041)

Revision ID: 053
Revises: 052
Create Date: 2026-08-09

Agrega `external_reference_id`/`external_reference_url` a `tickets` (aplican a Tickets y Tareas,
misma tabla — ver data-model.md) para la trazabilidad hacia la tarea original de Teamwork tras
una importación, con índice sobre `external_reference_id` (lookup de upsert, FR-009). Crea el
permiso `ticket_imports:run` (Admin, Coordinador) que gatea la pantalla/endpoints de importación
— mismo patrón de permiso de único-uso ya usado en 048/052.
"""
import uuid

from alembic import op
import sqlalchemy as sa

revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = {
    ("ticket_imports", "run"): ["Admin", "Coordinador"],
}


def upgrade() -> None:
    op.add_column("tickets", sa.Column("external_reference_id", sa.Text(), nullable=True))
    op.add_column("tickets", sa.Column("external_reference_url", sa.Text(), nullable=True))
    op.create_index(
        "ix_tickets_external_reference_id", "tickets", ["external_reference_id"],
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
        "(SELECT id FROM permissions WHERE module = 'ticket_imports' AND action = 'run')"
    ))
    bind.execute(sa.text("DELETE FROM permissions WHERE module = 'ticket_imports' AND action = 'run'"))
    op.drop_index("ix_tickets_external_reference_id", table_name="tickets")
    op.drop_column("tickets", "external_reference_url")
    op.drop_column("tickets", "external_reference_id")
