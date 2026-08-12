"""Generación de notificaciones internas (FR-023/024).

spec 046 (US6, Centro de Notificaciones del Portal): reutilizado sin cambio estructural para
Usuario/cliente — `Notification.user_id` ya acota cada fila a su destinatario, así que
`GET /api/notifications` ya devuelve solo lo propio sin lógica de aislamiento por Cliente
adicional (ver research.md Decisión 6). `user_replied` (ya existente) es el evento relevante que
ahora se genera hacia el resolutor cuando el Usuario/cliente responde una solicitud de
información (US4); los eventos de cambio de estado y comentario público que el Portal muestra al
propio Usuario/cliente reutilizan el mismo mecanismo, sin tabla ni tipo de evento nuevo.
"""
from typing import Optional
import uuid

from backend.domain.entities.notification import Notification
from backend.domain.entities.ticket import STATUS_LABELS, format_ticket_number

_MESSAGES = {
    "assigned": "Se te asignó el ticket {number}: {title}",
    "reassigned": "Se te reasignó el ticket {number}: {title}",
    "user_replied": "El usuario respondió en el ticket {number}",
    "resolution_rejected": "El usuario rechazó la resolución del ticket {number}",
    "closed": "El ticket {number} fue cerrado",
    "close_eligible": "El ticket {number} lleva 3+ días resuelto sin respuesta del usuario; puedes cerrarlo",
    "sla_breached": "El ticket {number} incumplió su tiempo límite de SLA",
}

# Eventos que llevan el detalle adicional del ticket (OBS-0062, FR-008): cliente, prioridad,
# estado y quién realizó la (re)asignación — el resto de eventos no lo necesita.
_ASSIGNMENT_EVENTS = ("assigned", "reassigned")


class NotificationService:
    def build(self, user_id: uuid.UUID, event_type: str, ticket_id: uuid.UUID,
              ticket_number: int, title: str = "", *, client_name: Optional[str] = None,
              priority: Optional[str] = None, status: Optional[str] = None,
              assigned_by: Optional[str] = None) -> Notification:
        template = _MESSAGES[event_type]
        message = template.format(number=format_ticket_number(ticket_number), title=title)
        if event_type in _ASSIGNMENT_EVENTS and (client_name or priority or status or assigned_by):
            status_label = STATUS_LABELS.get(status, status) if status else None
            details = " · ".join(
                part for part in (
                    f"Cliente: {client_name}" if client_name else None,
                    f"Prioridad: {priority}" if priority else None,
                    f"Estado: {status_label}" if status_label else None,
                    f"Asignado por: {assigned_by}" if assigned_by else None,
                ) if part
            )
            message = f"{message} — {details}"
        return Notification.create(user_id=user_id, event_type=event_type,
                                   ticket_id=ticket_id, message=message)
