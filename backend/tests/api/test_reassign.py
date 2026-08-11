"""Reasignación de resolutor (spec 023) — endpoint independiente de /assign."""


def _second_resource(client, unique_name):
    response = client.post("/api/resources", json={
        "full_name": f"Segundo Resolutor {unique_name}",
        "email": f"segundo.tk.{unique_name}@sywork.net",
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def _reassign(client, ticket_id, assignee_id, reason=None):
    payload = {"assignee_id": assignee_id}
    if reason is not None:
        payload["reason"] = reason
    return client.post(f"/api/tickets/{ticket_id}/reassign", json=payload)


def test_reassign_success_updates_assignee_and_history(client, make_ticket, ticket_resource, unique_name):
    ticket = make_ticket()
    client.post(f"/api/tickets/{ticket['id']}/assign",
               json={"assignee_id": ticket_resource["id"], "mode": "resolver"})
    second = _second_resource(client, unique_name)

    response = _reassign(client, ticket["id"], second["id"], reason="Escalamiento por complejidad")
    assert response.status_code == 200, response.get_json()
    data = response.get_json()
    assert data["ticket"]["assignee"]["id"] == second["id"]
    assert data["ticket"]["status"] == "contacto"  # no toca el FSM

    reassignment = data["reassignment"]
    assert reassignment["previous_assignee_id"] == ticket_resource["id"]
    assert reassignment["previous_assignee_name"] == ticket_resource["full_name"]
    assert reassignment["new_assignee_id"] == second["id"]
    assert reassignment["reason"] == "Escalamiento por complejidad"

    detail = client.get(f"/api/tickets/{ticket['id']}").get_json()
    assert len(detail["reassignments"]) == 1


def test_reassign_same_assignee_is_rejected(client, make_ticket, ticket_resource):
    ticket = make_ticket()
    client.post(f"/api/tickets/{ticket['id']}/assign",
               json={"assignee_id": ticket_resource["id"], "mode": "resolver"})
    response = _reassign(client, ticket["id"], ticket_resource["id"])
    assert response.status_code == 400
    detail = client.get(f"/api/tickets/{ticket['id']}").get_json()
    assert len(detail["reassignments"]) == 0


def test_reassign_to_coordinador_user_id_provisions_resource(client, make_ticket, ticket_resource,
                                                              coordinador_user):
    """spec 041 (FR-013): reasignar a un Coordinador sin Recurso propio funciona igual que entre
    Resolutores — se aprovisiona su Recurso perezosamente."""
    ticket = make_ticket()
    client.post(f"/api/tickets/{ticket['id']}/assign",
               json={"assignee_id": ticket_resource["id"], "mode": "resolver"})

    response = _reassign(client, ticket["id"], str(coordinador_user.id))
    assert response.status_code == 200, response.get_json()
    data = response.get_json()
    assert data["ticket"]["assignee"]["full_name"] == coordinador_user.username
    assert data["reassignment"]["previous_assignee_id"] == ticket_resource["id"]


def test_reassign_terminal_ticket_is_rejected(client, make_ticket, ticket_resource):
    ticket = make_ticket()
    client.post(f"/api/tickets/{ticket['id']}/cancel", json={"body": "Duplicado"})
    response = _reassign(client, ticket["id"], ticket_resource["id"])
    assert response.status_code == 409
    assert response.get_json()["error"] == "ticket_closed"


def test_reassign_without_permission_is_403(client, make_ticket, ticket_resource,
                                            resolver_auth, anon_client):
    ticket = make_ticket()
    client.post(f"/api/tickets/{ticket['id']}/assign",
               json={"assignee_id": ticket_resource["id"], "mode": "resolver"})
    response = anon_client.post(f"/api/tickets/{ticket['id']}/reassign",
                                json={"assignee_id": ticket_resource["id"]},
                                headers=resolver_auth)
    assert response.status_code == 403


def _second_resource_with_user(client, unique_name, db_session):
    """Segundo resolutor CON cuenta de usuario vinculada (a diferencia de `_second_resource`),
    necesario para probar notificaciones (OBS-0062) y bloqueo por cuenta inactiva (OBS-0063)."""
    import uuid as _uuid
    from backend.domain.entities.user import User
    from backend.infra.repositories.role_repo import RoleRepository
    from backend.infra.repositories.user_repo import UserRepository
    resolutor_role = RoleRepository(db_session).get_by_name("Resolutor")
    user = User(id=_uuid.uuid4(), email=f"segundo.notif.{unique_name}@sywork.net",
               username=f"segundo_notif_{unique_name}", role=resolutor_role, active=True)
    created_user = UserRepository(db_session).create(user)
    response = client.post("/api/resources", json={
        "full_name": f"Segundo Resolutor Notif {unique_name}",
        "email": f"segundo.notif.res.{unique_name}@sywork.net",
        "user_id": str(created_user.id),
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json(), created_user


def test_reassign_notifies_new_assignee(client, make_ticket, ticket_resource, unique_name,
                                        db_session):
    """OBS-0062: reasignar dispara una notificación 'reassigned' para el nuevo resolutor."""
    ticket = make_ticket()
    client.post(f"/api/tickets/{ticket['id']}/assign",
               json={"assignee_id": ticket_resource["id"], "mode": "resolver"})
    second, second_user = _second_resource_with_user(client, unique_name, db_session)

    response = _reassign(client, ticket["id"], second["id"])
    assert response.status_code == 200, response.get_json()

    from flask_jwt_extended import create_access_token
    with client.application.app_context():
        token = create_access_token(identity=str(second_user.id))
    notifs = client.get("/api/notifications", headers={"Authorization": f"Bearer {token}"})
    assert notifs.status_code == 200, notifs.get_json()
    items = notifs.get_json()["items"]
    assert any(n["event_type"] == "reassigned" and n["ticket"]["id"] == ticket["id"]
              for n in items)


def test_reassign_to_resource_with_inactive_user_account_is_rejected(
        client, make_ticket, ticket_resource, unique_name, db_session):
    """OBS-0063: Resource.active=True pero su cuenta de usuario está desactivada."""
    ticket = make_ticket()
    client.post(f"/api/tickets/{ticket['id']}/assign",
               json={"assignee_id": ticket_resource["id"], "mode": "resolver"})
    second, second_user = _second_resource_with_user(client, unique_name, db_session)

    deactivate = client.patch(f"/api/users/{second_user.id}/deactivate")
    assert deactivate.status_code == 200, deactivate.get_json()

    response = _reassign(client, ticket["id"], second["id"])
    assert response.status_code == 400
    assert response.get_json()["error"] == "resource_inactive"
