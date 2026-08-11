from typing import Optional
import uuid

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from backend.domain.entities.ticket import Ticket
from backend.infra.models.ticket_model import (
    TicketModel, StatusTransitionModel, AssignmentModel, ReassignmentModel, ticket_skills_table,
)
from backend.infra.models.resource_model import SkillModel, ResourceModel

# OBS-0028: `priority` es texto (critical/high/medium/low) que NO debe ordenarse
# alfabéticamente — un `CASE` mapea cada valor a su urgencia real (0 = más urgente).
_PRIORITY_URGENCY = case(
    (TicketModel.priority == "critical", 0),
    (TicketModel.priority == "high", 1),
    (TicketModel.priority == "medium", 2),
    (TicketModel.priority == "low", 3),
    else_=4,
)

_SORTS = {
    "created_at": (TicketModel.created_at.asc(),),
    "-created_at": (TicketModel.created_at.desc(),),
    "priority": (_PRIORITY_URGENCY.asc(),),
    "-priority": (_PRIORITY_URGENCY.desc(),),
    "status": (TicketModel.status.asc(),),
    "-status": (TicketModel.status.desc(),),
    # spec 035 (FR-008): ordenamiento explícito por código de ticket/tarea.
    "code": (TicketModel.ticket_number.asc(),),
    "-code": (TicketModel.ticket_number.desc(),),
    # OBS-0028: default sugerido — urgencia real de prioridad, luego severidad
    # (s1..s4 ya ordena correctamente en alfabético), luego más antiguo primero.
    "urgency": (_PRIORITY_URGENCY.asc(), TicketModel.severity.asc(), TicketModel.created_at.asc()),
}


class TicketRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, ticket_id: uuid.UUID) -> Optional[Ticket]:
        model = self._db.get(TicketModel, ticket_id)
        return model.to_entity() if model else None

    def get_by_external_reference_id(self, external_reference_id: str) -> Optional[Ticket]:
        """Lookup usado por el upsert de importación de Teamwork (spec 041, FR-009)."""
        model = (self._db.query(TicketModel)
                 .filter(TicketModel.external_reference_id == external_reference_id)
                 .first())
        return model.to_entity() if model else None

    def list_paginated(self, page: int = 1, page_size: int = 20, search: str | None = None,
                       client_id: uuid.UUID | None = None, project_id: uuid.UUID | None = None,
                       statuses: list[str] | None = None, priority: str | None = None,
                       severity: str | None = None, ticket_type: str | None = None,
                       assignee_id: uuid.UUID | None = None, escalation_level: str | None = None,
                       sort: str = "urgency",
                       created_by: uuid.UUID | None = None,
                       sla_status: str | None = None,
                       sla_expiring_within_hours: int | None = None) -> tuple[list[Ticket], int]:
        q = self._db.query(TicketModel)
        if created_by:
            q = q.filter(TicketModel.created_by == created_by)
        if search:
            like = f"%{search}%"
            filters = [TicketModel.title.ilike(like)]
            digits = "".join(ch for ch in search if ch.isdigit())
            if digits:
                filters.append(TicketModel.ticket_number == int(digits))
            from sqlalchemy import or_
            q = q.filter(or_(*filters))
        if client_id:
            q = q.filter(TicketModel.client_id == client_id)
        if project_id:
            q = q.filter(TicketModel.project_id == project_id)
        if statuses:
            q = q.filter(TicketModel.status.in_(statuses))
        if priority:
            q = q.filter(TicketModel.priority == priority)
        if severity:
            q = q.filter(TicketModel.severity == severity)
        if ticket_type:
            q = q.filter(TicketModel.ticket_type == ticket_type)
        if assignee_id:
            q = q.filter(TicketModel.assignee_id == assignee_id)
        if escalation_level:
            q = q.filter(TicketModel.escalation_level == escalation_level)
        if sla_status:
            q = q.filter(TicketModel.sla_status == sla_status)
        if sla_expiring_within_hours is not None:
            # FR-009: tickets cuya fase de SLA vigente sigue corriendo (no vencida aún) y cuyo
            # tiempo restante (calculado en tiempo real, no el snapshot) cae dentro de la
            # ventana pedida. `remaining` puede dar negativo si ya venció entre lecturas —
            # se excluye explícitamente (ese caso ya lo cubre sla_status=vencido).
            remaining = (
                TicketModel.sla_phase_limit_minutes * 60 - TicketModel.sla_consumed_seconds
                - func.coalesce(func.extract("epoch", func.now() - TicketModel.sla_last_resume_at), 0)
            )
            q = q.filter(
                TicketModel.sla_status == "corriendo",
                TicketModel.sla_phase_limit_minutes.isnot(None),
                remaining <= sla_expiring_within_hours * 3600,
                remaining > 0,
            )
        total = q.count()
        order = _SORTS.get(sort, _SORTS["urgency"])
        models = q.order_by(*order).offset((page - 1) * page_size).limit(page_size).all()
        return [m.to_entity() for m in models], total

    def list_active_sla_running(self) -> list[Ticket]:
        """Tickets con la fase de SLA vigente corriendo (candidatos a evaluar vencimiento,
        usado por la tarea periódica `check_sla_breaches`, spec 014 Historia 3)."""
        models = (self._db.query(TicketModel)
                  .filter(TicketModel.sla_status == "corriendo")
                  .all())
        return [m.to_entity() for m in models]

    def list_active_sla_by_assignee(self, resource_id: uuid.UUID) -> list[Ticket]:
        """Tickets con SLA activo (`corriendo` o `pausado`) asignados a `resource_id` (spec 022,
        endpoint de carga de trabajo `GET /api/resources/{id}/workload`)."""
        models = (
            self._db.query(TicketModel)
            .filter(
                TicketModel.assignee_id == resource_id,
                TicketModel.sla_status.in_(("corriendo", "pausado")),
            )
            .all()
        )
        return [m.to_entity() for m in models]

    def create(self, ticket: Ticket) -> Ticket:
        model = TicketModel(
            id=ticket.id,
            record_type_id=ticket.record_type_id,
            ticket_type=ticket.ticket_type,
            title=ticket.title,
            description=ticket.description,
            status=ticket.status,
            priority=ticket.priority,
            severity=ticket.severity,
            escalation_level=ticket.escalation_level,
            client_id=ticket.client_id,
            project_id=ticket.project_id,
            tool_id=ticket.tool_id,
            process_id=ticket.process_id,
            related_ticket_id=ticket.related_ticket_id,
            list_name=ticket.list_name,
            list_id=ticket.list_id,
            parent_task_id=ticket.parent_task_id,
            assignee_id=ticket.assignee_id,
            created_by=ticket.created_by,
            client_contact_id=ticket.client_contact_id,
            sla_rule_id=ticket.sla_rule_id,
            sla_phase=ticket.sla_phase,
            sla_phase_limit_minutes=ticket.sla_phase_limit_minutes,
            sla_consumed_seconds=ticket.sla_consumed_seconds,
            sla_last_resume_at=ticket.sla_last_resume_at,
            sla_status=ticket.sla_status,
            sla_contact_result=ticket.sla_contact_result,
            sla_contact_consumed_seconds=ticket.sla_contact_consumed_seconds,
            external_reference_id=ticket.external_reference_id,
            external_reference_url=ticket.external_reference_url,
        )
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity()

    def upsert_from_import(self, *, external_reference_id: str, external_reference_url: str,
                           record_type_id: uuid.UUID, title: str, description: str,
                           client_id: uuid.UUID, project_id: Optional[uuid.UUID],
                           list_id: Optional[uuid.UUID], parent_task_id: Optional[uuid.UUID],
                           assignee_id: Optional[uuid.UUID],
                           client_contact_id: Optional[uuid.UUID], created_by: uuid.UUID,
                           estimated_resolution_minutes: Optional[int]) -> tuple[Ticket, bool]:
        """Importación de Teamwork (spec 041, FR-009): busca por `external_reference_id`; si ya
        existe, actualiza sus campos mapeados; si no, crea una Tarea nueva. Devuelve
        `(ticket, created)` — `created=False` en un upsert que actualiza."""
        existing = (self._db.query(TicketModel)
                   .filter(TicketModel.external_reference_id == external_reference_id)
                   .first())
        if existing:
            existing.title = title
            existing.description = description
            existing.client_id = client_id
            existing.project_id = project_id
            existing.list_id = list_id
            existing.parent_task_id = parent_task_id
            existing.assignee_id = assignee_id
            existing.client_contact_id = client_contact_id
            existing.estimated_resolution_minutes = estimated_resolution_minutes
            existing.external_reference_url = external_reference_url
            self._db.commit()
            self._db.refresh(existing)
            return existing.to_entity(), False

        ticket = Ticket(
            id=uuid.uuid4(), ticket_number=0, title=title, description=description,
            ticket_type="incident", priority="medium", severity="s3", status="nuevo",
            client_id=client_id, project_id=project_id, record_type_id=record_type_id,
            list_id=list_id, parent_task_id=parent_task_id, assignee_id=assignee_id,
            client_contact_id=client_contact_id, created_by=created_by,
            estimated_resolution_minutes=estimated_resolution_minutes,
            external_reference_id=external_reference_id, external_reference_url=external_reference_url,
        )
        return self.create(ticket), True

    def update_fields(self, ticket_id: uuid.UUID, **fields) -> Optional[Ticket]:
        model = self._db.get(TicketModel, ticket_id)
        if not model:
            return None
        for k, v in fields.items():
            if hasattr(model, k):
                setattr(model, k, v)
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity()

    def update_skills(self, ticket_id: uuid.UUID, skill_ids: list[uuid.UUID]) -> Optional[Ticket]:
        """Reemplaza el set completo de Skills requeridas del ticket (spec 011, FR-001/FR-003).
        IDs que no correspondan a un Skill existente se ignoran (mismo criterio que
        ResourceRepository.update_skills)."""
        model = self._db.get(TicketModel, ticket_id)
        if not model:
            return None
        unique_ids = dict.fromkeys(skill_ids)  # dedupe preservando orden (FR-003)
        model.skills = [self._db.get(SkillModel, sid) for sid in unique_ids if self._db.get(SkillModel, sid)]
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity()

    def count_tickets_with_skill(self, skill_id: uuid.UUID) -> int:
        """Cuántos tickets (cualquier estado) tienen `skill_id` como Skill requerida (spec 011,
        FR-007 — bloquea el borrado del skill mientras esté en uso, mismo criterio que
        `count_active_resources_with_skill`)."""
        return (
            self._db.query(func.count())
            .select_from(ticket_skills_table)
            .filter(ticket_skills_table.c.skill_id == skill_id)
            .scalar()
        )

    def list_related_from(self, ticket_id: uuid.UUID) -> list[Ticket]:
        """Registros (Ticket o Tarea) que tienen a `ticket_id` como `related_ticket_id`
        (relación inversa, Fase 3 FR-006)."""
        models = (self._db.query(TicketModel)
                  .filter(TicketModel.related_ticket_id == ticket_id)
                  .order_by(TicketModel.created_at).all())
        return [m.to_entity() for m in models]

    def list_subtasks(self, parent_task_id: uuid.UUID) -> list[Ticket]:
        """Subtareas (Nivel 5) de una Tarea (Nivel 4) — spec 009 FR-014."""
        models = (self._db.query(TicketModel)
                  .filter(TicketModel.parent_task_id == parent_task_id)
                  .order_by(TicketModel.created_at).all())
        return [m.to_entity() for m in models]

    # ── historiales (append-only) ───────────────────────────────────────

    def add_transition(self, ticket_id: uuid.UUID, from_status: str, to_status: str,
                       actor_id: uuid.UUID, comment_id: uuid.UUID | None = None,
                       commit: bool = True) -> None:
        self._db.add(StatusTransitionModel(
            ticket_id=ticket_id, from_status=from_status, to_status=to_status,
            actor_id=actor_id, comment_id=comment_id,
        ))
        if commit:
            self._db.commit()

    def list_transitions(self, ticket_id: uuid.UUID) -> list[dict]:
        rows = (self._db.query(StatusTransitionModel)
                .filter(StatusTransitionModel.ticket_id == ticket_id)
                .order_by(StatusTransitionModel.created_at).all())
        return [{
            "id": str(r.id), "from_status": r.from_status, "to_status": r.to_status,
            "actor_id": str(r.actor_id),
            "comment_id": str(r.comment_id) if r.comment_id else None,
            "created_at": r.created_at.isoformat(),
        } for r in rows]

    def add_assignment(self, ticket_id: uuid.UUID, assigner_id: uuid.UUID,
                       assignee_id: uuid.UUID, resulting_status: str, context: dict,
                       commit: bool = True) -> uuid.UUID:
        model = AssignmentModel(
            ticket_id=ticket_id, assigner_id=assigner_id, assignee_id=assignee_id,
            resulting_status=resulting_status, context=context,
        )
        self._db.add(model)
        if commit:
            self._db.commit()
            self._db.refresh(model)
        return model.id

    def add_reassignment(self, ticket_id: uuid.UUID, actor_id: uuid.UUID,
                         previous_assignee_id: uuid.UUID | None, new_assignee_id: uuid.UUID,
                         reason: str | None, commit: bool = True) -> uuid.UUID:
        """Reasignación de resolutor (spec 023) — tabla separada de `ticket_assignments`
        (research.md Decisión 4), no toca el FSM."""
        model = ReassignmentModel(
            ticket_id=ticket_id, actor_id=actor_id, previous_assignee_id=previous_assignee_id,
            new_assignee_id=new_assignee_id, reason=reason,
        )
        self._db.add(model)
        if commit:
            self._db.commit()
            self._db.refresh(model)
        return model.id

    def list_reassignments(self, ticket_id: uuid.UUID) -> list[dict]:
        rows = (self._db.query(ReassignmentModel)
                .filter(ReassignmentModel.ticket_id == ticket_id)
                .order_by(ReassignmentModel.created_at).all())
        resource_ids = {r.new_assignee_id for r in rows} | {r.previous_assignee_id for r in rows if r.previous_assignee_id}
        names = {}
        if resource_ids:
            names = {r.id: r.full_name for r in
                     self._db.query(ResourceModel).filter(ResourceModel.id.in_(resource_ids)).all()}
        return [{
            "id": str(r.id), "actor_id": str(r.actor_id),
            "previous_assignee_id": str(r.previous_assignee_id) if r.previous_assignee_id else None,
            "previous_assignee_name": names.get(r.previous_assignee_id) if r.previous_assignee_id else None,
            "new_assignee_id": str(r.new_assignee_id),
            "new_assignee_name": names.get(r.new_assignee_id),
            "reason": r.reason,
            "created_at": r.created_at.isoformat(),
        } for r in rows]

    def list_assignments(self, ticket_id: uuid.UUID) -> list[dict]:
        rows = (self._db.query(AssignmentModel)
                .filter(AssignmentModel.ticket_id == ticket_id)
                .order_by(AssignmentModel.created_at).all())
        return [{
            "id": str(r.id), "assigner_id": str(r.assigner_id),
            "assignee_id": str(r.assignee_id), "resulting_status": r.resulting_status,
            "context": r.context, "created_at": r.created_at.isoformat(),
        } for r in rows]

    def count_open_by_assignee(self, assignee_id: uuid.UUID) -> int:
        return (self._db.query(TicketModel)
                .filter(TicketModel.assignee_id == assignee_id,
                        TicketModel.status.notin_(("cerrado", "cancelado")))
                .count())

    def panel_matrix(self, statuses: list[str] | None = None) -> list[dict]:
        """Conteo de tickets por (assignee, status) para el Panel de Asignación."""
        q = (self._db.query(TicketModel.assignee_id, TicketModel.status,
                            func.count(TicketModel.id))
             .filter(TicketModel.assignee_id.isnot(None),
                     TicketModel.status.notin_(("cerrado", "cancelado")))
             .group_by(TicketModel.assignee_id, TicketModel.status))
        if statuses:
            q = q.filter(TicketModel.status.in_(statuses))
        return [{"assignee_id": row[0], "status": row[1], "count": row[2]} for row in q.all()]

    def count_using_catalog(self, column: str, catalog_id: uuid.UUID) -> int:
        """Tickets no finales que referencian un valor de catálogo (bloqueo por uso)."""
        return (self._db.query(TicketModel)
                .filter(getattr(TicketModel, column) == catalog_id,
                        TicketModel.status.notin_(("cerrado", "cancelado")))
                .count())
