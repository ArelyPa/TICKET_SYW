"""Triage Push (US2) — dominio puro, sin DB. OBS-0063: cuenta de usuario vinculada inactiva."""
import uuid

import pytest

from backend.domain.entities.resource import Resource
from backend.domain.entities.ticket import Ticket
from backend.domain.services.assignment_service import AssignmentError, AssignmentService


def _ticket(**overrides) -> Ticket:
    defaults = dict(
        id=uuid.uuid4(), ticket_number=1, title="t", description="d",
        ticket_type="incident", priority="high", severity="s2",
        client_id=uuid.uuid4(), created_by=uuid.uuid4(), status="nuevo",
    )
    defaults.update(overrides)
    return Ticket(**defaults)


def _resource(**overrides) -> Resource:
    defaults = dict(id=uuid.uuid4(), full_name="Resolutor", email="r@sywork.net")
    defaults.update(overrides)
    return Resource(**defaults)


def test_validate_rejects_inactive_resource():
    ticket = _ticket()
    with pytest.raises(AssignmentError) as exc:
        AssignmentService().validate(ticket, _resource(active=False), "resolver")
    assert exc.value.code == "resource_inactive"


def test_validate_rejects_resource_with_inactive_linked_user_account():
    """OBS-0063: Resource.active=True pero la cuenta de usuario vinculada está inactiva."""
    ticket = _ticket()
    with pytest.raises(AssignmentError) as exc:
        AssignmentService().validate(
            ticket, _resource(user_id=uuid.uuid4(), user_active=False), "resolver")
    assert exc.value.code == "resource_inactive"


def test_validate_accepts_active_resource_with_active_linked_user():
    ticket = _ticket()
    trigger, comment_type = AssignmentService().validate(
        ticket, _resource(user_id=uuid.uuid4(), user_active=True), "resolver")
    assert trigger == "assign_resolver"
    assert comment_type == "asignado"


def test_validate_accepts_coordinador_role_in_resolver_mode():
    """spec 041 (FR-013): modo 'resolver' ahora también admite rol Coordinador, no solo
    Resolutor — mismo trigger/tipo de comentario que un Resolutor."""
    ticket = _ticket()
    trigger, comment_type = AssignmentService().validate(
        ticket, _resource(user_id=uuid.uuid4(), user_active=True), "resolver",
        assignee_role_name="Coordinador")
    assert trigger == "assign_resolver"
    assert comment_type == "asignado"


def test_validate_rejects_role_outside_resolver_or_coordinador_in_resolver_mode():
    ticket = _ticket()
    with pytest.raises(AssignmentError) as exc:
        AssignmentService().validate(
            ticket, _resource(user_id=uuid.uuid4(), user_active=True), "resolver",
            assignee_role_name="QM")
    assert exc.value.code == "assignee_role_mismatch"
