"""Permiso tickets:respond_client para Usuario/cliente (spec 046, US4)

Revision ID: 057
Revises: 056
Create Date: 2026-08-12

Habilita a un Usuario/cliente a registrar el comentario `respuesta_usuario` sobre un ticket de
su propia empresa cuando está en `pendiente_usuario` (comentario "Solicitud de información"),
cerrando el ciclo ya modelado en `ticket_fsm.py` (`solicitud_informacion` -> `pendiente_usuario`
-> `respuesta_usuario` -> `en_ejecucion`) que hasta ahora era inalcanzable para este rol.

Deliberadamente NO se otorga `tickets:transition` (permiso ya existente, usado por roles
internos) porque expondría también `confirmacion_atencion`/`termina_analisis`/
`solicitud_cierre`/`comentario_interno` a este rol externo — la restricción de que solo pueda
usar `respuesta_usuario` vive en `comment_service.validate` (Capa 1), no en el permiso.
"""
from alembic import op
import sqlalchemy as sa

revision = "057"
down_revision = "056"
branch_labels = None
depends_on = None

NEW_PERMISSION = ("tickets", "respond_client")
NEW_PERMISSION_ROLES = ["Usuario/cliente"]


def upgrade() -> None:
    bind = op.get_bind()
    roles = {r.name: r.id for r in bind.execute(sa.text("SELECT id, name FROM roles")).fetchall()}

    permission_id = bind.execute(sa.text(
        "SELECT id FROM permissions WHERE module = :m AND action = :a"
    ), {"m": NEW_PERMISSION[0], "a": NEW_PERMISSION[1]}).scalar()
    if not permission_id:
        permission_id = bind.execute(sa.text(
            "INSERT INTO permissions (id, module, action) VALUES (gen_random_uuid(), :m, :a) "
            "RETURNING id"
        ), {"m": NEW_PERMISSION[0], "a": NEW_PERMISSION[1]}).scalar()

    for role_name in NEW_PERMISSION_ROLES:
        role_id = roles.get(role_name)
        if not role_id:
            continue
        exists = bind.execute(sa.text(
            "SELECT 1 FROM role_permissions WHERE role_id = :r AND permission_id = :p"
        ), {"r": str(role_id), "p": str(permission_id)}).first()
        if not exists:
            bind.execute(
                sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"),
                {"r": str(role_id), "p": str(permission_id)},
            )


def downgrade() -> None:
    bind = op.get_bind()
    permission_id = bind.execute(sa.text(
        "SELECT id FROM permissions WHERE module = :m AND action = :a"
    ), {"m": NEW_PERMISSION[0], "a": NEW_PERMISSION[1]}).scalar()
    if permission_id:
        bind.execute(sa.text(
            "DELETE FROM role_permissions WHERE permission_id = :p"
        ), {"p": str(permission_id)})
        bind.execute(sa.text(
            "DELETE FROM permissions WHERE id = :p"
        ), {"p": str(permission_id)})
