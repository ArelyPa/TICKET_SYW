"""Modelos SQLAlchemy de la integración Teamwork v3 (spec 042) — configuración de conexión,
homologación de entidades y auditoría de cargas de tiempos. Ver data-model.md.
"""
import uuid
from sqlalchemy import Boolean, Column, ForeignKey, Integer, LargeBinary, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func, text
from backend.infra.models import Base
from backend.infra.models.client_model import _encrypt, _decrypt
from backend.domain.entities.teamwork_integration import TeamworkIntegrationConfig, EntityMapping


class TeamworkIntegrationConfigModel(Base):
    __tablename__ = "teamwork_integration_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    site_url = Column(Text, nullable=False)
    api_token = Column(LargeBinary, nullable=True)
    environment = Column(Text, nullable=False, server_default=text("'test'"))
    last_test_status = Column(Text, nullable=True)
    last_test_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_test_message = Column(Text, nullable=True)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def to_entity(self, *, include_token: bool = False) -> TeamworkIntegrationConfig:
        return TeamworkIntegrationConfig(
            id=self.id,
            site_url=self.site_url,
            api_token=_decrypt(self.api_token) if include_token else None,
            environment=self.environment,
            last_test_status=self.last_test_status,
            last_test_at=self.last_test_at,
            last_test_message=self.last_test_message,
        )

    @classmethod
    def from_entity(cls, config: TeamworkIntegrationConfig) -> "TeamworkIntegrationConfigModel":
        return cls(
            id=config.id,
            site_url=config.site_url,
            api_token=_encrypt(config.api_token) if config.api_token else None,
            environment=config.environment,
            last_test_status=config.last_test_status,
            last_test_at=config.last_test_at,
            last_test_message=config.last_test_message,
        )


class EntityMappingModel(Base):
    __tablename__ = "teamwork_entity_mappings"
    __table_args__ = (UniqueConstraint("entity_type", "teamwork_id", name="uq_teamwork_entity_mappings_key"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    entity_type = Column(Text, nullable=False)
    teamwork_id = Column(Text, nullable=False)
    teamwork_name = Column(Text, nullable=True)
    sytix_entity_type = Column(Text, nullable=True)
    sytix_id = Column(UUID(as_uuid=True), nullable=True)
    match_method = Column(Text, nullable=True)
    parent_teamwork_id = Column(Text, nullable=True)
    teamwork_email = Column(Text, nullable=True)
    is_discarded = Column(Boolean, nullable=False, server_default=text("false"))
    teamwork_metadata = Column(JSONB, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    def to_entity(self) -> EntityMapping:
        return EntityMapping(
            id=self.id,
            entity_type=self.entity_type,
            teamwork_id=self.teamwork_id,
            teamwork_name=self.teamwork_name,
            sytix_entity_type=self.sytix_entity_type,
            sytix_id=self.sytix_id,
            match_method=self.match_method,
            parent_teamwork_id=self.parent_teamwork_id,
            teamwork_email=self.teamwork_email,
            is_discarded=self.is_discarded,
            teamwork_metadata=self.teamwork_metadata,
        )

    @classmethod
    def from_entity(cls, mapping: EntityMapping) -> "EntityMappingModel":
        return cls(
            id=mapping.id,
            entity_type=mapping.entity_type,
            teamwork_id=mapping.teamwork_id,
            teamwork_name=mapping.teamwork_name,
            sytix_entity_type=mapping.sytix_entity_type,
            sytix_id=mapping.sytix_id,
            match_method=mapping.match_method,
            parent_teamwork_id=mapping.parent_teamwork_id,
            teamwork_email=mapping.teamwork_email,
            is_discarded=mapping.is_discarded,
            teamwork_metadata=mapping.teamwork_metadata,
        )


class TimeImportBatchModel(Base):
    """Auditoría agregada de una carga de tiempos confirmada — sin entidad de dominio propia
    (data-model.md), se maneja directamente como registro de infraestructura."""
    __tablename__ = "time_import_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    filename = Column(Text, nullable=False)
    imported_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    imported_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    total_rows = Column(Integer, nullable=False, server_default=text("0"))
    valid_rows = Column(Integer, nullable=False, server_default=text("0"))
    resolved_rows = Column(Integer, nullable=False, server_default=text("0"))
    skipped_rows = Column(Integer, nullable=False, server_default=text("0"))
    error_rows = Column(Integer, nullable=False, server_default=text("0"))
