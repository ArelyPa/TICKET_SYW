"""Automapeo puro de homologación de entidades (spec 042, US5, Capa 1 — sin imports de Flask/
SQLAlchemy/`requests`). FR-006: sugiere una coincidencia por correo, luego ID externo, luego
nombre exacto; la Capa 3 arma las listas de `teamwork_entity`/`sytix_candidates` consultando la
API v3 y los repositorios correspondientes."""
from typing import Literal

SyncStatus = Literal["pending", "linked", "created", "inactive"]


def suggest_match(teamwork_entity: dict, sytix_candidates: list[dict]) -> dict | None:
    """`teamwork_entity`: `{"id", "name", "email"?}`. `sytix_candidates`:
    `[{"id", "name", "email"?, "external_id"?}, ...]`. Devuelve
    `{"sytix_id", "match_method"}` o `None` si no hay coincidencia."""
    email = (teamwork_entity.get("email") or "").strip().lower()
    if email:
        for candidate in sytix_candidates:
            if (candidate.get("email") or "").strip().lower() == email:
                return {"sytix_id": candidate["id"], "match_method": "email"}

    teamwork_id = str(teamwork_entity.get("id") or "").strip()
    if teamwork_id:
        for candidate in sytix_candidates:
            if str(candidate.get("external_id") or "").strip() == teamwork_id:
                return {"sytix_id": candidate["id"], "match_method": "external_id"}

    name = (teamwork_entity.get("name") or "").strip()
    if name:
        for candidate in sytix_candidates:
            if (candidate.get("name") or "").strip() == name:
                return {"sytix_id": candidate["id"], "match_method": "name"}

    return None


def derive_sync_status(mapping) -> SyncStatus:
    """Deriva el estado de la matriz de 4 valores (spec 045, FR-001/002) de una fila de
    homologación. `is_discarded` se evalúa primero — un registro descartado explícitamente por el
    usuario es "inactive" sin importar si alguna vez tuvo (o tiene) un `sytix_id`/`match_method`
    asociado. Reemplaza a `_migration_status`, que vivía indebidamente en la Capa 3."""
    if getattr(mapping, "is_discarded", False):
        return "inactive"
    if not mapping.sytix_id:
        return "pending"
    if mapping.match_method == "created_new":
        return "created"
    return "linked"
