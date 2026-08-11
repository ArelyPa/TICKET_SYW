"""Automapeo puro de homologación (spec 042, US5) y matriz de estados (spec 045, US1) — sin DB
(Principio VII: ≤10 registros)."""
import uuid
from dataclasses import dataclass
from typing import Optional

from backend.domain.services.entity_mapping_service import suggest_match, derive_sync_status

_CANDIDATES = [
    {"id": "r1", "name": "Juan Pérez", "email": "juan.perez@sywork.net", "external_id": None},
    {"id": "r2", "name": "María Ruiz", "email": "maria.ruiz@sywork.net", "external_id": "556"},
    {"id": "r3", "name": "Aris Ming", "email": None, "external_id": None},
]


def test_matches_by_email_first():
    result = suggest_match({"id": "1", "name": "Distinto Nombre", "email": "juan.perez@sywork.net"},
                           _CANDIDATES)
    assert result == {"sytix_id": "r1", "match_method": "email"}


def test_matches_by_external_id_when_no_email_match():
    result = suggest_match({"id": "556", "name": "Otro Nombre", "email": None}, _CANDIDATES)
    assert result == {"sytix_id": "r2", "match_method": "external_id"}


def test_matches_by_exact_name_as_last_resort():
    result = suggest_match({"id": "999", "name": "Aris Ming", "email": None}, _CANDIDATES)
    assert result == {"sytix_id": "r3", "match_method": "name"}


def test_no_match_returns_none():
    result = suggest_match({"id": "999", "name": "Nadie Coincide", "email": None}, _CANDIDATES)
    assert result is None


def test_email_match_is_case_insensitive():
    result = suggest_match({"id": "1", "name": "x", "email": "JUAN.PEREZ@SYWORK.NET"}, _CANDIDATES)
    assert result == {"sytix_id": "r1", "match_method": "email"}


def test_empty_candidates_returns_none():
    assert suggest_match({"id": "1", "name": "x", "email": "x@sywork.net"}, []) is None


# ── derive_sync_status (spec 045, US1, FR-001/002) ──────────────────────────────────────────

@dataclass
class _FakeMapping:
    sytix_id: Optional[uuid.UUID] = None
    match_method: Optional[str] = None
    is_discarded: bool = False


def test_derive_sync_status_pending_without_sytix_id():
    assert derive_sync_status(_FakeMapping()) == "pending"


def test_derive_sync_status_linked_when_sytix_id_and_not_created_new():
    mapping = _FakeMapping(sytix_id=uuid.uuid4(), match_method="manual")
    assert derive_sync_status(mapping) == "linked"


def test_derive_sync_status_created_when_match_method_created_new():
    mapping = _FakeMapping(sytix_id=uuid.uuid4(), match_method="created_new")
    assert derive_sync_status(mapping) == "created"


def test_derive_sync_status_inactive_when_discarded_without_sytix_id():
    mapping = _FakeMapping(is_discarded=True)
    assert derive_sync_status(mapping) == "inactive"


def test_derive_sync_status_inactive_takes_priority_over_sytix_id():
    mapping = _FakeMapping(sytix_id=uuid.uuid4(), match_method="created_new", is_discarded=True)
    assert derive_sync_status(mapping) == "inactive"
