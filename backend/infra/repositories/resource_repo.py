from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from backend.infra.models.resource_model import (
    ResourceModel, SkillModel, ResourceCompensationModel, resource_skills_table,
)
from backend.domain.entities.resource import Resource, Skill
from backend.domain.entities.compensation import ResourceCompensation
import uuid


class SkillRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_all(self, active: bool | None = True) -> list[Skill]:
        q = self._db.query(SkillModel)
        if active is not None:
            q = q.filter(SkillModel.active == active)
        return [m.to_entity() for m in q.order_by(SkillModel.code).all()]

    def list_all_with_catalogs(self, active: bool | None = True) -> list[dict]:
        """Skills con nombre de herramienta/proceso resueltos (spec 010, contracts/skills.md)."""
        from backend.infra.models.catalog_model import ToolCatalogModel, ProcessCatalogModel
        q = (
            self._db.query(SkillModel, ToolCatalogModel.name, ProcessCatalogModel.name)
            .outerjoin(ToolCatalogModel, ToolCatalogModel.id == SkillModel.tool_id)
            .outerjoin(ProcessCatalogModel, ProcessCatalogModel.id == SkillModel.process_id)
        )
        if active is not None:
            q = q.filter(SkillModel.active == active)
        rows = q.order_by(SkillModel.code).all()
        return [
            {
                "id": str(m.id),
                "code": m.code,
                "label": m.label,
                "active": m.active,
                "skill_type": m.skill_type,
                "tool_id": str(m.tool_id) if m.tool_id else None,
                "tool_name": tool_name,
                "process_id": str(m.process_id) if m.process_id else None,
                "process_name": process_name,
            }
            for m, tool_name, process_name in rows
        ]

    def get_by_id(self, skill_id: uuid.UUID) -> Optional[Skill]:
        model = self._db.get(SkillModel, skill_id)
        return model.to_entity() if model else None

    def get_by_code(self, code: str) -> Optional[Skill]:
        model = self._db.query(SkillModel).filter(SkillModel.code == code).first()
        return model.to_entity() if model else None

    def create(self, skill: Skill) -> Skill:
        model = SkillModel(id=skill.id, code=skill.code, label=skill.label, active=skill.active,
                           skill_type=skill.skill_type, tool_id=skill.tool_id,
                           process_id=skill.process_id)
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity()

    def update(self, skill_id: uuid.UUID, data: dict) -> Optional[Skill]:
        """PATCH parcial de label/skill_type/tool_id/process_id (spec 010)."""
        model = self._db.get(SkillModel, skill_id)
        if not model:
            return None
        for field in ("label", "skill_type", "tool_id", "process_id"):
            if field in data:
                setattr(model, field, data[field])
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity()

    def delete(self, skill_id: uuid.UUID) -> bool:
        model = self._db.get(SkillModel, skill_id)
        if not model:
            return False
        self._db.delete(model)
        self._db.commit()
        return True

    def count_active_resources_with_skill(self, skill_id: uuid.UUID) -> int:
        return (
            self._db.query(ResourceModel)
            .join(resource_skills_table, ResourceModel.id == resource_skills_table.c.resource_id)
            .filter(resource_skills_table.c.skill_id == skill_id, ResourceModel.active == True)
            .count()
        )


class ResourceRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, resource_id: uuid.UUID) -> Optional[Resource]:
        model = self._db.get(ResourceModel, resource_id)
        return model.to_entity() if model else None

    def get_by_user_id(self, user_id: uuid.UUID) -> Optional[Resource]:
        model = self._db.query(ResourceModel).filter(ResourceModel.user_id == user_id).first()
        return model.to_entity() if model else None

    def get_or_create_for_user(self, user) -> Resource:
        """OBS-0052/0053: provisiona un `Resource` mínimo (sin skills/calendario) para un
        usuario sin perfil de recurso —hoy los QM— al momento de asignarle un ticket a
        Pre-Análisis. `tickets.assignee_id` es un FK obligatorio a `resources.id`; esto evita
        exigirle a un Admin dar de alta manualmente un recurso completo solo para poder asignar
        tickets a QM (decisión de producto: candidatos QM se listan por rol, no por la tabla de
        recursos)."""
        existing = self.get_by_user_id(user.id)
        if existing:
            return existing
        resource = Resource(id=uuid.uuid4(), user_id=user.id, full_name=user.username, email=user.email)
        return self.create(resource)

    def get_by_email(self, email: str) -> Optional[Resource]:
        model = self._db.query(ResourceModel).filter(ResourceModel.email == email).first()
        return model.to_entity() if model else None

    def get_by_full_name(self, full_name: str) -> Optional[Resource]:
        """Usado por la importación de Teamwork (spec 041, research.md Decisión 7) para
        resolver `Assigned to` cuando no hay coincidencia de correo."""
        model = self._db.query(ResourceModel).filter(ResourceModel.full_name == full_name).first()
        return model.to_entity() if model else None

    def list_paginated(self, page: int = 1, page_size: int = 20, search: str | None = None, skill_code: str | None = None, active: bool | None = None) -> tuple[list[Resource], int]:
        q = self._db.query(ResourceModel)
        if skill_code:
            q = q.join(resource_skills_table, ResourceModel.id == resource_skills_table.c.resource_id)\
                 .join(SkillModel, resource_skills_table.c.skill_id == SkillModel.id)\
                 .filter(SkillModel.code == skill_code)
        if search:
            q = q.filter(ResourceModel.full_name.ilike(f"%{search}%"))
        if active is not None:
            q = q.filter(ResourceModel.active == active)
        total = q.count()
        models = q.order_by(ResourceModel.full_name).offset((page - 1) * page_size).limit(page_size).all()
        return [m.to_entity() for m in models], total

    def create(self, resource: Resource) -> Resource:
        model = ResourceModel(
            id=resource.id,
            user_id=resource.user_id,
            full_name=resource.full_name,
            email=resource.email,
            active=resource.active,
            notes=resource.notes,
            identification=resource.identification,
            nationality=resource.nationality,
            birth_date=resource.birth_date,
            marital_status=resource.marital_status,
            contract_type=resource.contract_type,
            calendar_country=resource.calendar_country,
            education_level=resource.education_level,
            specialty=resource.specialty,
            seniority=resource.seniority,
            certifications=resource.certifications,
            team=resource.team,
            manager_id=resource.manager_id,
            timezone=resource.timezone,
        )
        if resource.skills:
            skill_models = [self._db.get(SkillModel, s.id) for s in resource.skills]
            model.skills = [s for s in skill_models if s]
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity()

    def update_skills(self, resource_id: uuid.UUID, skill_ids: list[uuid.UUID]) -> Optional[Resource]:
        model = self._db.get(ResourceModel, resource_id)
        if not model:
            return None
        model.skills = [self._db.get(SkillModel, sid) for sid in skill_ids if self._db.get(SkillModel, sid)]
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity()

    def update(self, resource_id: uuid.UUID, **fields) -> Optional[Resource]:
        model = self._db.get(ResourceModel, resource_id)
        if not model:
            return None
        for k, v in fields.items():
            if hasattr(model, k):
                setattr(model, k, v)
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity()

    def deactivate(self, resource_id: uuid.UUID) -> Optional[Resource]:
        return self.set_active(resource_id, False)

    def set_active(self, resource_id: uuid.UUID, active: bool) -> Optional[Resource]:
        return self.update(resource_id, active=active)

    def list_by_schedule_mode(self, mode: str) -> list[Resource]:
        """Recursos por `schedule_mode` (`"heredado"` | `"personalizado"`, spec 022, FR-005) —
        usado por la pantalla de RRHH para listar Personalizados y por la propagación de una
        Franja Horaria (quiénes la heredan)."""
        models = (
            self._db.query(ResourceModel)
            .filter(ResourceModel.schedule_mode == mode)
            .order_by(ResourceModel.full_name)
            .all()
        )
        return [m.to_entity() for m in models]


class CompensationRepository:
    """Acceso al area protegida de compensacion (FR-032/FR-033, SDD V3)."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, resource_id: uuid.UUID) -> Optional[ResourceCompensation]:
        model = self._db.get(ResourceCompensationModel, resource_id)
        return model.to_entity() if model else None

    def upsert(self, comp: ResourceCompensation) -> ResourceCompensation:
        model = self._db.get(ResourceCompensationModel, comp.resource_id)
        new_model = ResourceCompensationModel.from_entity(comp)
        if model:
            for f in ("base_salary", "total_salary", "overhead", "hourly_cost", "currency"):
                setattr(model, f, getattr(new_model, f))
        else:
            model = new_model
            self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity()
