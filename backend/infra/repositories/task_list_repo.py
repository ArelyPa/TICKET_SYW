from typing import Optional
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.domain.entities.task_list import TaskList
from backend.infra.models.task_list_model import TaskListModel
from backend.infra.models.ticket_model import TicketModel


class TaskListRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, task_list_id: uuid.UUID) -> Optional[TaskList]:
        model = self._db.get(TaskListModel, task_list_id)
        return model.to_entity() if model else None

    def get_by_project_and_name(self, project_id: uuid.UUID, name: str) -> Optional[TaskList]:
        """OBS-0010: para rechazar nombres de Lista duplicados dentro del mismo Proyecto."""
        model = (self._db.query(TaskListModel)
                  .filter(TaskListModel.project_id == project_id, TaskListModel.name == name)
                  .first())
        return model.to_entity() if model else None

    def list_by_project(self, project_id: uuid.UUID) -> list[dict]:
        """Listas de un Proyecto ordenadas por posición, con `task_count` (Tareas de Nivel 4
        asociadas — una Subtarea no cuenta aparte, ya cuenta dentro de su Tarea padre)."""
        counts = dict(
            self._db.query(TicketModel.list_id, func.count(TicketModel.id))
            .filter(TicketModel.list_id.isnot(None), TicketModel.parent_task_id.is_(None))
            .group_by(TicketModel.list_id)
            .all()
        )
        models = (self._db.query(TaskListModel)
                  .filter(TaskListModel.project_id == project_id)
                  .order_by(TaskListModel.position, TaskListModel.created_at)
                  .all())
        return [{
            "id": str(m.id), "project_id": str(m.project_id), "name": m.name,
            "position": m.position, "task_count": counts.get(m.id, 0),
        } for m in models]

    def get_or_create_by_name(self, project_id: uuid.UUID, name: str) -> TaskList:
        """Usado por la importación de Teamwork (spec 041, FR-005): reutiliza la Lista de Tareas
        si ya existe una con ese nombre en el Proyecto, o la crea al final del orden actual."""
        existing = self.get_by_project_and_name(project_id, name)
        if existing:
            return existing
        return self.create(TaskList(
            id=uuid.uuid4(), project_id=project_id, name=name,
            position=self.next_position(project_id),
        ))

    def create(self, task_list: TaskList) -> TaskList:
        model = TaskListModel(
            id=task_list.id, project_id=task_list.project_id,
            name=task_list.name, position=task_list.position,
        )
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity()

    def next_position(self, project_id: uuid.UUID) -> int:
        max_position = (self._db.query(func.max(TaskListModel.position))
                        .filter(TaskListModel.project_id == project_id).scalar())
        return (max_position + 1) if max_position is not None else 0

    def update(self, task_list_id: uuid.UUID, **fields) -> Optional[TaskList]:
        model = self._db.get(TaskListModel, task_list_id)
        if not model:
            return None
        for k, v in fields.items():
            if hasattr(model, k):
                setattr(model, k, v)
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity()
