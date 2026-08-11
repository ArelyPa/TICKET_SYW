from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
import uuid

# Reglas de negocio (FR-004, FR-007) — límites del registro diario de tiempos.
MAX_DAILY_MINUTES = 24 * 60
EDIT_WINDOW_DAYS = 7

EDIT_ACTIONS = ("created", "updated", "deleted")


@dataclass
class WorkSession:
    id: uuid.UUID
    resource_id: uuid.UUID
    ticket_id: uuid.UUID
    work_date: date
    duration_minutes: int
    note: Optional[str]
    created_by: uuid.UUID
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    updated_by: Optional[uuid.UUID] = None
    # spec 028, US6/OBS-0036 (FR-020): True si el registro cae total o parcialmente fuera del
    # horario laboral del recurso — puramente informativo, nunca bloquea la creación.
    off_hours: bool = False
    # spec 042 (FR-013): `ID` del reporte de tiempos de Teamwork — permite reimportar el mismo
    # archivo actualizando en vez de duplicar (WorkSessionRepository.upsert_from_import).
    external_time_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(cls, resource_id: uuid.UUID, ticket_id: uuid.UUID, work_date: date,
               duration_minutes: int, created_by: uuid.UUID, note: Optional[str] = None,
               started_at: Optional[datetime] = None, ended_at: Optional[datetime] = None,
               off_hours: bool = False, external_time_id: Optional[str] = None) -> "WorkSession":
        return cls(
            id=uuid.uuid4(),
            resource_id=resource_id,
            ticket_id=ticket_id,
            work_date=work_date,
            duration_minutes=duration_minutes,
            note=note,
            created_by=created_by,
            started_at=started_at,
            ended_at=ended_at,
            off_hours=off_hours,
            external_time_id=external_time_id,
        )


@dataclass
class WorkSessionEdit:
    id: uuid.UUID
    work_session_id: uuid.UUID
    action: str
    edited_by: uuid.UUID
    previous_values: Optional[dict] = None
    new_values: Optional[dict] = None
    edited_at: datetime = field(default_factory=datetime.utcnow)
