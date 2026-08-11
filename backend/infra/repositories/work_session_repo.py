from datetime import date
from typing import Optional
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.domain.entities.work_session import WorkSession
from backend.infra.models.work_session_model import WorkSessionModel, WorkSessionEditModel

_TRACKED_FIELDS = ("ticket_id", "work_date", "duration_minutes", "note", "started_at", "ended_at")


def _snapshot(model: WorkSessionModel) -> dict:
    return {
        "ticket_id": str(model.ticket_id),
        "work_date": model.work_date.isoformat(),
        "duration_minutes": model.duration_minutes,
        "note": model.note,
        "started_at": model.started_at.isoformat() if model.started_at else None,
        "ended_at": model.ended_at.isoformat() if model.ended_at else None,
    }


class WorkSessionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, work_session_id: uuid.UUID) -> Optional[WorkSession]:
        model = (self._db.query(WorkSessionModel)
                 .filter(WorkSessionModel.id == work_session_id,
                         WorkSessionModel.deleted_at.is_(None))
                 .first())
        return model.to_entity() if model else None

    def create(self, work_session: WorkSession) -> WorkSession:
        model = WorkSessionModel.from_entity(work_session)
        self._db.add(model)
        self._db.flush()
        self._db.add(WorkSessionEditModel(
            work_session_id=model.id,
            action="created",
            previous_values=None,
            new_values=_snapshot(model),
            edited_by=work_session.created_by,
        ))
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity()

    def get_by_external_time_id(self, external_time_id: str) -> Optional[WorkSession]:
        model = (self._db.query(WorkSessionModel)
                 .filter(WorkSessionModel.external_time_id == external_time_id,
                         WorkSessionModel.deleted_at.is_(None))
                 .first())
        return model.to_entity() if model else None

    def upsert_from_import(self, work_session: WorkSession) -> tuple[WorkSession, bool]:
        """FR-013 (spec 042): reimportar el mismo `external_time_id` actualiza en vez de
        duplicar. Devuelve `(work_session, is_new)`."""
        if not work_session.external_time_id:
            return self.create(work_session), True
        model = (self._db.query(WorkSessionModel)
                 .filter(WorkSessionModel.external_time_id == work_session.external_time_id,
                         WorkSessionModel.deleted_at.is_(None))
                 .first())
        if model is None:
            return self.create(work_session), True

        previous = _snapshot(model)
        for f in _TRACKED_FIELDS:
            setattr(model, f, getattr(work_session, f))
        model.off_hours = work_session.off_hours
        model.updated_by = work_session.created_by
        self._db.flush()
        self._db.add(WorkSessionEditModel(
            work_session_id=model.id,
            action="updated",
            previous_values=previous,
            new_values=_snapshot(model),
            edited_by=work_session.created_by,
        ))
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity(), False

    def update(self, work_session_id: uuid.UUID, actor_id: uuid.UUID, **fields) -> Optional[WorkSession]:
        model = (self._db.query(WorkSessionModel)
                 .filter(WorkSessionModel.id == work_session_id,
                         WorkSessionModel.deleted_at.is_(None))
                 .first())
        if not model:
            return None
        previous = _snapshot(model)
        for key, value in fields.items():
            if key in _TRACKED_FIELDS and value is not None:
                setattr(model, key, value)
        model.updated_by = actor_id
        self._db.flush()
        self._db.add(WorkSessionEditModel(
            work_session_id=model.id,
            action="updated",
            previous_values=previous,
            new_values=_snapshot(model),
            edited_by=actor_id,
        ))
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity()

    def soft_delete(self, work_session_id: uuid.UUID, actor_id: uuid.UUID) -> bool:
        model = (self._db.query(WorkSessionModel)
                 .filter(WorkSessionModel.id == work_session_id,
                         WorkSessionModel.deleted_at.is_(None))
                 .first())
        if not model:
            return False
        previous = _snapshot(model)
        model.deleted_at = func.now()
        model.updated_by = actor_id
        self._db.flush()
        self._db.add(WorkSessionEditModel(
            work_session_id=model.id,
            action="deleted",
            previous_values=previous,
            new_values=None,
            edited_by=actor_id,
        ))
        self._db.commit()
        return True

    def list_by_filters(self, resource_id: uuid.UUID | None = None, ticket_id: uuid.UUID | None = None,
                        date_from: date | None = None, date_to: date | None = None,
                        page: int = 1, page_size: int = 20) -> tuple[list[WorkSession], int]:
        q = self._db.query(WorkSessionModel).filter(WorkSessionModel.deleted_at.is_(None))
        if resource_id:
            q = q.filter(WorkSessionModel.resource_id == resource_id)
        if ticket_id:
            q = q.filter(WorkSessionModel.ticket_id == ticket_id)
        if date_from:
            q = q.filter(WorkSessionModel.work_date >= date_from)
        if date_to:
            q = q.filter(WorkSessionModel.work_date <= date_to)
        total = q.count()
        models = (q.order_by(WorkSessionModel.work_date.desc(), WorkSessionModel.created_at.desc())
                  .offset((page - 1) * page_size).limit(page_size).all())
        return [m.to_entity() for m in models], total

    def sum_minutes_for_day(self, resource_id: uuid.UUID, work_date: date,
                            exclude_id: uuid.UUID | None = None) -> int:
        q = (self._db.query(func.coalesce(func.sum(WorkSessionModel.duration_minutes), 0))
             .filter(WorkSessionModel.resource_id == resource_id,
                     WorkSessionModel.work_date == work_date,
                     WorkSessionModel.deleted_at.is_(None)))
        if exclude_id:
            q = q.filter(WorkSessionModel.id != exclude_id)
        return int(q.scalar() or 0)

    def sum_minutes_for_ticket(self, ticket_id: uuid.UUID) -> int:
        """OBS-0026: tiempo total registrado en un ticket, para validar el cierre."""
        q = (self._db.query(func.coalesce(func.sum(WorkSessionModel.duration_minutes), 0))
             .filter(WorkSessionModel.ticket_id == ticket_id, WorkSessionModel.deleted_at.is_(None)))
        return int(q.scalar() or 0)

    def aggregate_by_resource_and_day(self, resource_id: uuid.UUID | None, date_from: date,
                                      date_to: date) -> list[dict]:
        q = (self._db.query(WorkSessionModel.resource_id, WorkSessionModel.work_date,
                            func.sum(WorkSessionModel.duration_minutes))
             .filter(WorkSessionModel.work_date >= date_from,
                     WorkSessionModel.work_date <= date_to,
                     WorkSessionModel.deleted_at.is_(None)))
        if resource_id:
            q = q.filter(WorkSessionModel.resource_id == resource_id)
        q = q.group_by(WorkSessionModel.resource_id, WorkSessionModel.work_date)
        return [{"resource_id": row[0], "work_date": row[1], "total_minutes": int(row[2])} for row in q.all()]
