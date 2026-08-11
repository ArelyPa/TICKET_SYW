"""Entidades de dominio (Capa 1, sin dependencias externas) de la integración Teamwork v3
(spec 042) — ver data-model.md."""
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TeamworkIntegrationConfig:
    id: uuid.UUID
    site_url: str
    api_token: Optional[str]
    environment: str
    last_test_status: Optional[str] = None
    last_test_at: Optional[datetime] = None
    last_test_message: Optional[str] = None


@dataclass
class EntityMapping:
    id: uuid.UUID
    entity_type: str
    teamwork_id: str
    teamwork_name: Optional[str]
    sytix_entity_type: Optional[str] = None
    sytix_id: Optional[uuid.UUID] = None
    match_method: Optional[str] = None
    parent_teamwork_id: Optional[str] = None
    teamwork_email: Optional[str] = None
    is_discarded: bool = False
    teamwork_metadata: Optional[dict] = None
