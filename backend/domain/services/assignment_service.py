"""Triage Push (US2): asignación de tickets con Gold Standard Dataset (FR-018/019)."""
import uuid

from backend.domain.entities.ticket import Ticket
from backend.domain.errors import DomainError
from backend.domain.fsm import ticket_fsm


class AssignmentError(DomainError):
    default_status_code = 400


ASSIGN_MODES = {
    "resolver": ("assign_resolver", "asignado"),
    "pre_analysis": ("assign_qm", "pre_analisis"),
}

# OBS-0053: rol de negocio exigido al usuario vinculado al recurso asignado, según el modo.
# spec 041 (FR-013): el modo "resolver" ahora admite además usuarios con rol Coordinador, para
# poder asignar Tickets/Tareas migrados desde Teamwork cuyo "Assigned to" original corresponde a
# alguien con ese rol en SYTIX — mismo patrón de asignación que un Resolutor, sin transición ni
# tipo de comentario distintos (research.md Decisión 6).
ASSIGN_MODE_REQUIRED_ROLE = {
    "resolver": {"Resolutor", "Coordinador"},
    "pre_analysis": {"QM"},
}


class AssignmentService:
    def validate(self, ticket: Ticket, assignee, mode: str,
                assignee_role_name: str | None = None) -> tuple[str, str]:
        """Devuelve (trigger FSM, tipo de comentario automático)."""
        if mode not in ASSIGN_MODES:
            raise AssignmentError("validation_error", "mode debe ser 'resolver' o 'pre_analysis'")
        if assignee is None:
            raise AssignmentError("not_found", "Recurso no encontrado", status_code=404)
        if not assignee.active:
            raise AssignmentError("resource_inactive", "No se puede asignar a un recurso inactivo")
        # OBS-0063: un recurso puede seguir "activo" como recurso de RRHH mientras su cuenta de
        # acceso (`User`) fue desactivada por separado — sin acceso al sistema, no puede atender
        # tickets nuevos.
        if assignee.user_id is not None and assignee.user_active is False:
            raise AssignmentError("resource_inactive", "No se puede asignar a un recurso inactivo")
        # OBS-0052/0053: el modo decide el estado destino (resolver→contacto, pre_analysis→
        # pre_analisis) — antes no se validaba que el usuario asignado tuviera el rol de negocio
        # correspondiente, permitiendo enviar un Resolutor a Pre-Análisis (estado propio de QM).
        required_roles = ASSIGN_MODE_REQUIRED_ROLE[mode]
        if assignee_role_name is not None and assignee_role_name not in required_roles:
            expected = " o ".join(sorted(required_roles))
            raise AssignmentError(
                "assignee_role_mismatch",
                f"El usuario seleccionado no tiene rol {expected}, requerido para este modo de asignación")
        trigger, comment_type = ASSIGN_MODES[mode]
        if not ticket_fsm.can_transition(ticket.status, trigger):
            # deja que apply() genere el 409 con las acciones válidas en español
            ticket_fsm.apply(ticket.status, trigger)
        return trigger, comment_type

    def build_context(self, assignee, open_tickets_count: int, ticket: Ticket) -> dict:
        """Snapshot inmutable de la decisión (Gold Standard Dataset, FR-019)."""
        return {
            "assignee_skills": sorted(s.code for s in (assignee.skills or [])),
            "assignee_open_tickets": open_tickets_count,
            "ticket_priority": ticket.priority,
            "ticket_severity": ticket.severity,
        }
