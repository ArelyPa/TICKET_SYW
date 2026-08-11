import uuid
from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func, text
from backend.infra.models import Base
from backend.domain.entities.work_session import WorkSession, WorkSessionEdit


class WorkSessionModel(Base):
    __tablename__ = "work_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id"), nullable=False)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False)
    work_date = Column(Date, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    note = Column(Text, nullable=True)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    ended_at = Column(TIMESTAMP(timezone=True), nullable=True)
    off_hours = Column(Boolean, nullable=False, server_default=text("false"))
    external_time_id = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def to_entity(self) -> WorkSession:
        return WorkSession(
            id=self.id,
            resource_id=self.resource_id,
            ticket_id=self.ticket_id,
            work_date=self.work_date,
            duration_minutes=self.duration_minutes,
            note=self.note,
            created_by=self.created_by,
            started_at=self.started_at,
            ended_at=self.ended_at,
            updated_by=self.updated_by,
            off_hours=self.off_hours,
            external_time_id=self.external_time_id,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, work_session: WorkSession) -> "WorkSessionModel":
        return cls(
            id=work_session.id,
            resource_id=work_session.resource_id,
            ticket_id=work_session.ticket_id,
            work_date=work_session.work_date,
            duration_minutes=work_session.duration_minutes,
            note=work_session.note,
            created_by=work_session.created_by,
            started_at=work_session.started_at,
            ended_at=work_session.ended_at,
            updated_by=work_session.updated_by,
            off_hours=work_session.off_hours,
            external_time_id=work_session.external_time_id,
        )


class WorkSessionEditModel(Base):
    __tablename__ = "work_session_edits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    work_session_id = Column(UUID(as_uuid=True), ForeignKey("work_sessions.id"), nullable=False)
    action = Column(Text, nullable=False)
    previous_values = Column(JSONB(), nullable=True)
    new_values = Column(JSONB(), nullable=True)
    edited_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    edited_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    def to_entity(self) -> WorkSessionEdit:
        return WorkSessionEdit(
            id=self.id,
            work_session_id=self.work_session_id,
            action=self.action,
            edited_by=self.edited_by,
            previous_values=self.previous_values,
            new_values=self.new_values,
            edited_at=self.edited_at,
        )
