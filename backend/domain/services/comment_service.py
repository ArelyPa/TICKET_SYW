"""Comentarios tipificados → transiciones (US3, FR-013/014/028)."""
import uuid
from typing import Optional

from backend.domain.entities.comment import COMMENT_TYPES
from backend.domain.entities.ticket import Ticket
from backend.domain.errors import DomainError
from backend.domain.fsm import ticket_fsm
from backend.domain.services.rich_content_service import strip_html


class CommentError(DomainError):
    default_status_code = 400


# Tipos de comentario registrables por el endpoint /comments y su trigger FSM.
# None = comentario sin efecto de estado. Los automáticos (asignado/pre_analisis)
# solo los genera la asignación; cancelacion solo el endpoint /cancel;
# descripcion_solucion solo el endpoint /close.
MANUAL_COMMENT_TRIGGERS: dict[str, Optional[str]] = {
    "confirmacion_atencion": "confirmacion_atencion",
    "solicitud_informacion": "solicitud_informacion",
    "termina_analisis": "termina_analisis",
    "solicitud_cierre": "solicitud_cierre",
    "respuesta_usuario": "respuesta_usuario",
    "comentario_interno": None,
}


class CommentService:
    def validate(self, ticket: Ticket, comment_type: str, body: str,
                 actor_user_id: uuid.UUID, actor_can_manage: bool,
                 actor_resource_id: Optional[uuid.UUID],
                 actor_is_client: bool = False) -> Optional[str]:
        """Valida tipo/autoría y devuelve el trigger FSM a ejecutar (o None).

        `actor_is_client` (spec 046, US4): actor autenticado solo con `tickets:respond_client`
        (Usuario/cliente) — únicamente puede registrar `respuesta_usuario`, nunca otro tipo
        (evita que este rol externo dispare `comentario_interno` u otras transiciones de staff
        por este mismo endpoint compartido)."""
        if comment_type not in COMMENT_TYPES:
            raise CommentError("validation_error", "Tipo de comentario desconocido")
        if comment_type not in MANUAL_COMMENT_TRIGGERS:
            raise CommentError(
                "validation_error",
                f"El tipo '{comment_type}' no se registra por esta vía")
        if actor_is_client and comment_type != "respuesta_usuario":
            raise CommentError(
                "forbidden", "Solo puedes responder a una solicitud de información",
                status_code=403)
        if not strip_html(body or "").strip():
            raise CommentError("validation_error", "El comentario no puede estar vacío")

        trigger = MANUAL_COMMENT_TRIGGERS[comment_type]
        if trigger is not None:
            # FR-028: un Resolutor solo transiciona tickets asignados a él;
            # Coordinador/QM/Admin (actor_can_manage) pueden sobre cualquiera; un Usuario/
            # cliente (actor_is_client) puede responder sin estar "asignado" (no tiene Recurso).
            if not actor_can_manage and not actor_is_client:
                if actor_resource_id is None or ticket.assignee_id != actor_resource_id:
                    raise CommentError(
                        "forbidden", "Solo puedes avanzar tickets asignados a ti",
                        status_code=403)
            # valida la transición (levanta 409 con acciones válidas si no aplica)
            if not ticket_fsm.can_transition(ticket.status, trigger):
                ticket_fsm.apply(ticket.status, trigger)
        return trigger
