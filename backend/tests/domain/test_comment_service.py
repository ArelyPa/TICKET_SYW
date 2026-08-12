"""spec 046, US4 (FR-009/010): un Usuario/cliente (`actor_is_client=True`) solo puede registrar
`respuesta_usuario`, nunca otro tipo — la restricción vive en `CommentService.validate`
(Capa 1), no en el permiso de ruta. Tests puros de dominio, sin base de datos."""
import uuid

import pytest

from backend.domain.entities.ticket import Ticket
from backend.domain.errors import DomainError
from backend.domain.services.comment_service import CommentService, CommentError


def _make_ticket(status="pendiente_usuario"):
    return Ticket(
        id=uuid.uuid4(), ticket_number=1, title="t", description="d",
        ticket_type="incident", priority="medium", severity="s3",
        client_id=uuid.uuid4(), created_by=uuid.uuid4(), status=status,
    )


def test_client_actor_can_respond_when_pending_user():
    ticket = _make_ticket(status="pendiente_usuario")
    trigger = CommentService().validate(
        ticket, "respuesta_usuario", "Aquí está la información solicitada",
        actor_user_id=uuid.uuid4(), actor_can_manage=False, actor_resource_id=None,
        actor_is_client=True,
    )
    assert trigger == "respuesta_usuario"


def test_client_actor_cannot_post_other_comment_types():
    ticket = _make_ticket(status="pendiente_usuario")
    with pytest.raises(CommentError) as exc:
        CommentService().validate(
            ticket, "comentario_interno", "Intento de nota interna",
            actor_user_id=uuid.uuid4(), actor_can_manage=False, actor_resource_id=None,
            actor_is_client=True,
        )
    assert exc.value.status_code == 403


def test_client_actor_cannot_respond_outside_pending_user():
    """El comment_type es válido (`respuesta_usuario`) pero el estado no admite esa transición
    (409, `InvalidTransitionError` — un `DomainError` distinto de `CommentError`)."""
    ticket = _make_ticket(status="en_analisis")
    with pytest.raises(DomainError):
        CommentService().validate(
            ticket, "respuesta_usuario", "Respuesta fuera de lugar",
            actor_user_id=uuid.uuid4(), actor_can_manage=False, actor_resource_id=None,
            actor_is_client=True,
        )


def test_staff_behavior_unaffected_by_actor_is_client_default():
    """No-regresión: `actor_is_client=False` (default) preserva el comportamiento existente."""
    ticket = _make_ticket(status="pendiente_usuario")
    with pytest.raises(CommentError) as exc:
        CommentService().validate(
            ticket, "respuesta_usuario", "x",
            actor_user_id=uuid.uuid4(), actor_can_manage=False, actor_resource_id=None,
        )
    assert exc.value.status_code == 403
