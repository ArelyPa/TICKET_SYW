"""Repositorios de Capa 2 (spec 042) de la integración Teamwork v3: configuración de conexión
(patrón singleton), homologación de entidades y auditoría de cargas de tiempos."""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.infra.models.teamwork_integration_model import (
    TeamworkIntegrationConfigModel, EntityMappingModel, TimeImportBatchModel,
)
from backend.domain.entities.teamwork_integration import TeamworkIntegrationConfig, EntityMapping


class TeamworkIntegrationConfigRepository:
    """Fila única (research.md Decisión — el repositorio siempre actualiza la fila existente o
    crea la primera si no hay ninguna; no hay UI para más de una configuración activa a la vez)."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, *, include_token: bool = False) -> Optional[TeamworkIntegrationConfig]:
        model = self._db.query(TeamworkIntegrationConfigModel).first()
        return model.to_entity(include_token=include_token) if model else None

    def upsert(self, site_url: str, environment: str, api_token: Optional[str],
               updated_by: uuid.UUID) -> TeamworkIntegrationConfig:
        """`api_token=None` conserva el token ya guardado (contrato `PUT /config`, contracts/api.md)."""
        model = self._db.query(TeamworkIntegrationConfigModel).first()
        if model is None:
            model = TeamworkIntegrationConfigModel.from_entity(
                TeamworkIntegrationConfig(id=uuid.uuid4(), site_url=site_url, api_token=api_token,
                                          environment=environment)
            )
            self._db.add(model)
        else:
            model.site_url = site_url
            model.environment = environment
            if api_token:
                from backend.infra.models.client_model import _encrypt
                model.api_token = _encrypt(api_token)
            # Cualquier cambio de configuración invalida el último resultado de "Probar
            # Conexión" — evita que una sincronización se ejecute contra credenciales/URL
            # nuevas asumiendo que siguen siendo las ya probadas (Edge Cases, spec.md).
            model.last_test_status = None
            model.last_test_at = None
            model.last_test_message = None
        model.updated_by = updated_by
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity(include_token=False)

    def record_test_result(self, status: str, message: Optional[str]) -> Optional[TeamworkIntegrationConfig]:
        model = self._db.query(TeamworkIntegrationConfigModel).first()
        if model is None:
            return None
        model.last_test_status = status
        model.last_test_message = message
        model.last_test_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity(include_token=False)


class EntityMappingRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list(self, entity_type: Optional[str] = None,
             unresolved_only: bool = False) -> list[EntityMapping]:
        q = self._db.query(EntityMappingModel)
        if entity_type:
            q = q.filter(EntityMappingModel.entity_type == entity_type)
        if unresolved_only:
            q = q.filter(EntityMappingModel.sytix_id.is_(None))
        models = q.order_by(EntityMappingModel.teamwork_name).all()
        return [m.to_entity() for m in models]

    def get_by_id(self, mapping_id: uuid.UUID) -> Optional[EntityMapping]:
        model = self._db.get(EntityMappingModel, mapping_id)
        return model.to_entity() if model else None

    def get_by_teamwork_key(self, entity_type: str, teamwork_id: str) -> Optional[EntityMapping]:
        model = self._db.query(EntityMappingModel).filter(
            EntityMappingModel.entity_type == entity_type,
            EntityMappingModel.teamwork_id == teamwork_id,
        ).first()
        return model.to_entity() if model else None

    def get_by_name(self, entity_type: str, teamwork_name: str) -> Optional[EntityMapping]:
        """Usado por el importador de tiempos (FR-007): resuelve `Who`/`Company`/`Project` de una
        fila contra una homologación ya guardada, por nombre exacto tal como vino de Teamwork."""
        model = self._db.query(EntityMappingModel).filter(
            EntityMappingModel.entity_type == entity_type,
            EntityMappingModel.teamwork_name == teamwork_name,
            EntityMappingModel.sytix_id.isnot(None),
        ).first()
        return model.to_entity() if model else None

    def upsert_from_sync(self, entity_type: str, teamwork_id: str, teamwork_name: str,
                         suggested_match: Optional[dict] = None,
                         parent_teamwork_id: Optional[str] = None,
                         teamwork_email: Optional[str] = None,
                         metadata: Optional[dict] = None) -> tuple[EntityMapping, bool]:
        """Inserta/actualiza una fila sincronizada sin tocar `sytix_id` de una ya homologada
        manualmente, salvo que `suggested_match` traiga una sugerencia nueva y la fila siga sin
        resolver. `parent_teamwork_id`/`teamwork_email`/`metadata` (spec 043/045) se refrescan en
        cada sincronización, ya que reflejan el estado actual de Teamwork, no una decisión del
        usuario — a diferencia de `is_discarded` (spec 045), que nunca se toca acá (preserva el
        estado Inactivo entre resincronizaciones, FR-007). Devuelve `(mapping, is_new)`."""
        model = self._db.query(EntityMappingModel).filter(
            EntityMappingModel.entity_type == entity_type,
            EntityMappingModel.teamwork_id == teamwork_id,
        ).first()
        is_new = model is None
        if model is None:
            model = EntityMappingModel(id=uuid.uuid4(), entity_type=entity_type, teamwork_id=teamwork_id)
            self._db.add(model)
        model.teamwork_name = teamwork_name
        model.parent_teamwork_id = parent_teamwork_id
        model.teamwork_email = teamwork_email
        model.teamwork_metadata = metadata or None
        if model.sytix_id is None and suggested_match:
            model.sytix_entity_type = suggested_match.get("sytix_entity_type")
            model.sytix_id = suggested_match.get("sytix_id")
            model.match_method = suggested_match.get("match_method")
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity(), is_new

    def set_manual_mapping(self, mapping_id: uuid.UUID,
                           sytix_id: Optional[uuid.UUID], sytix_entity_type: str,
                           updated_by: uuid.UUID) -> Optional[EntityMapping]:
        model = self._db.get(EntityMappingModel, mapping_id)
        if model is None:
            return None
        model.sytix_id = sytix_id
        model.sytix_entity_type = sytix_entity_type if sytix_id else None
        model.match_method = "manual" if sytix_id else None
        model.updated_by = updated_by
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity()

    def set_discarded(self, mapping_id: uuid.UUID, discarded: bool,
                      updated_by: uuid.UUID) -> Optional[EntityMapping]:
        """spec 045 US2 (FR-010/FR-006): marca/revierte el estado Inactivo de la matriz de 4
        estados — no toca `sytix_id`/`match_method`, así que una fila reactivada conserva
        cualquier homologación previa que hubiera tenido antes de descartarse."""
        model = self._db.get(EntityMappingModel, mapping_id)
        if model is None:
            return None
        model.is_discarded = discarded
        model.updated_by = updated_by
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity()

    def get_teamwork_ids_for_sytix(self, entity_type: str,
                                   sytix_ids: "list[uuid.UUID]") -> dict:
        """spec 045 US4 (research.md Decisión 7): reverse lookup SYTIX→Teamwork usado por el
        Importador de Tareas para acotar `fetch_tasks()` a los Proyectos ya elegidos por el
        usuario en el selector SYTIX-side. Devuelve `{sytix_id: teamwork_id}` — omite los `id`
        que no tengan homologación."""
        if not sytix_ids:
            return {}
        rows = self._db.query(EntityMappingModel.sytix_id, EntityMappingModel.teamwork_id).filter(
            EntityMappingModel.entity_type == entity_type,
            EntityMappingModel.sytix_id.in_(sytix_ids),
        ).all()
        return {row[0]: row[1] for row in rows}

    def list_sytix_ids_by_type(self, sytix_entity_type: str) -> List[uuid.UUID]:
        """spec 044 US5/research.md Decisión 7: distintivo de trazabilidad para las 5 pantallas
        principales de SYTIX — `sytix_id` es la condición canónica (siempre se escribe junto a
        `match_method` en los tres paths de escritura existentes: `upsert_from_sync` con
        sugerencia, `set_manual_mapping`, `set_created_new_mapping`)."""
        rows = self._db.query(EntityMappingModel.sytix_id).filter(
            EntityMappingModel.sytix_entity_type == sytix_entity_type,
            EntityMappingModel.sytix_id.isnot(None),
        ).all()
        return [r[0] for r in rows]

    def set_created_new_mapping(self, mapping_id: uuid.UUID, sytix_id: uuid.UUID,
                                sytix_entity_type: str,
                                updated_by: uuid.UUID) -> Optional[EntityMapping]:
        """Vincula la fila al registro recién creado por "Migrar como Nuevo" (spec 043 FR-003),
        distinto de `set_manual_mapping` para que la UI pueda distinguir el badge "Migrado" del
        "Homologado" (`match_method="created_new"` vs. `"manual"`)."""
        model = self._db.get(EntityMappingModel, mapping_id)
        if model is None:
            return None
        model.sytix_id = sytix_id
        model.sytix_entity_type = sytix_entity_type
        model.match_method = "created_new"
        model.updated_by = updated_by
        self._db.commit()
        self._db.refresh(model)
        return model.to_entity()


class TimeImportBatchRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, filename: str, imported_by: uuid.UUID, total_rows: int, valid_rows: int,
              resolved_rows: int, skipped_rows: int, error_rows: int) -> uuid.UUID:
        model = TimeImportBatchModel(
            id=uuid.uuid4(), filename=filename, imported_by=imported_by, total_rows=total_rows,
            valid_rows=valid_rows, resolved_rows=resolved_rows, skipped_rows=skipped_rows,
            error_rows=error_rows,
        )
        self._db.add(model)
        self._db.commit()
        return model.id
