import datetime

_today = datetime.date.today().isoformat()


def test_encargado_create_ticket_uses_simplified_payload_and_own_client(client, encargado_auth, ticket_client):
    resp = client.post("/api/tickets", json={
        "title": "No puedo acceder al portal",
        "description": "Me sale error 500 al iniciar sesión",
    }, headers=encargado_auth)
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["client"]["id"] == ticket_client["id"]
    assert body["ticket_type"] == "incident"
    assert body["priority"] == "medium"
    assert body["severity"] == "s3"
    assert body["requester"]["is_encargado"] is True


def test_encargado_create_ticket_ignores_extra_fields(client, encargado_auth):
    resp = client.post("/api/tickets", json={
        "title": "Otro problema", "description": "Detalle del problema",
        "ticket_type": "evolutive", "priority": "critical", "severity": "s1",
        "client_id": "00000000-0000-0000-0000-000000000000",
    }, headers=encargado_auth)
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["ticket_type"] == "incident"
    assert body["priority"] == "medium"
    assert body["severity"] == "s3"


def test_encargado_create_ticket_requires_title_and_description(client, encargado_auth):
    resp = client.post("/api/tickets", json={"title": "Solo título"}, headers=encargado_auth)
    assert resp.status_code == 400


def test_encargado_sees_company_tickets_from_other_contacts_in_list(client, encargado_auth, make_ticket):
    """spec 046 US2: el aislamiento por Cliente se amplía a 'empresa completa' — un Usuario/
    cliente ya no se limita a lo que él mismo creó, ve todo lo de su propio Cliente."""
    company_ticket = make_ticket()  # creado por Admin, mismo Cliente que encargado_auth
    own = client.post("/api/tickets", json={
        "title": "Mi propio ticket", "description": "Descripción de mi ticket",
    }, headers=encargado_auth)
    assert own.status_code == 201, own.get_json()
    own_id = own.get_json()["id"]

    listing = client.get("/api/tickets", headers=encargado_auth)
    assert listing.status_code == 200
    ids = {item["id"] for item in listing.get_json()["items"]}
    assert own_id in ids
    assert company_ticket["id"] in ids


def test_encargado_does_not_see_other_client_tickets_in_list(client, encargado_auth, unique_name):
    """spec 046 US2: el aislamiento sigue siendo estricto entre Clientes distintos."""
    other_client = client.post("/api/clients", json={"name": f"Otro Cliente {unique_name}"}).get_json()
    other_project = client.post("/api/projects", json={
        "client_id": other_client["id"], "name": f"Otro Proyecto {unique_name}",
        "start_date": _today,
    }).get_json()
    other_ticket = client.post("/api/tickets", json={
        "title": "Ticket de otro cliente", "description": "No debe ser visible",
        "client_id": other_client["id"], "project_id": other_project["id"],
        "ticket_type": "incident", "priority": "high", "severity": "s2",
    }).get_json()

    listing = client.get("/api/tickets", headers=encargado_auth)
    assert listing.status_code == 200
    ids = {item["id"] for item in listing.get_json()["items"]}
    assert other_ticket["id"] not in ids

    # Forzar client_id de otro Cliente por query tampoco filtra fuera del propio (se ignora).
    forced = client.get(f"/api/tickets?client_id={other_client['id']}", headers=encargado_auth)
    assert forced.status_code == 200
    assert other_ticket["id"] not in {item["id"] for item in forced.get_json()["items"]}


def test_encargado_detail_of_company_ticket_returns_200(client, encargado_auth, make_ticket):
    """spec 046 US2: un ticket del mismo Cliente creado por otro contacto ya no es 404."""
    company_ticket = make_ticket()
    resp = client.get(f"/api/tickets/{company_ticket['id']}", headers=encargado_auth)
    assert resp.status_code == 200


def test_encargado_detail_of_other_client_ticket_returns_404(client, encargado_auth, unique_name):
    other_client = client.post("/api/clients", json={"name": f"Otro Cliente Detalle {unique_name}"}).get_json()
    other_project = client.post("/api/projects", json={
        "client_id": other_client["id"], "name": f"Otro Proyecto Detalle {unique_name}",
        "start_date": _today,
    }).get_json()
    other_ticket = client.post("/api/tickets", json={
        "title": "Ticket ajeno", "description": "No debe ser visible",
        "client_id": other_client["id"], "project_id": other_project["id"],
        "ticket_type": "incident", "priority": "high", "severity": "s2",
    }).get_json()

    resp = client.get(f"/api/tickets/{other_ticket['id']}", headers=encargado_auth)
    assert resp.status_code == 404


def test_encargado_detail_of_own_ticket_returns_200_with_requester(client, encargado_auth):
    created = client.post("/api/tickets", json={
        "title": "Ticket propio detalle", "description": "Descripción",
    }, headers=encargado_auth)
    ticket_id = created.get_json()["id"]

    resp = client.get(f"/api/tickets/{ticket_id}", headers=encargado_auth)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["requester"]["is_encargado"] is True


def test_admin_still_sees_all_tickets_including_encargado_ones(client, encargado_auth, make_ticket, ticket_client):
    other_ticket = make_ticket()
    own = client.post("/api/tickets", json={
        "title": "Ticket de encargado visible para admin", "description": "Descripción",
    }, headers=encargado_auth)
    own_id = own.get_json()["id"]

    # Filtra por el Cliente único de este test para no depender del volumen acumulado de
    # tickets de otras pruebas al paginar sin filtro (spec 038, mismo ajuste que
    # test_tickets_view_assigned.py — la paginación por defecto puede dejar tickets recientes
    # fuera de la página 1 según `sort=urgency` a medida que crece la base de datos de prueba).
    listing = client.get(f"/api/tickets?client_id={ticket_client['id']}")  # `client` fixture = Admin
    ids = {item["id"] for item in listing.get_json()["items"]}
    assert other_ticket["id"] in ids
    assert own_id in ids

    detail = client.get(f"/api/tickets/{own_id}")
    assert detail.status_code == 200
    assert detail.get_json()["requester"]["is_encargado"] is True


def test_encargado_does_not_see_internal_comments_in_detail(client, encargado_auth, make_ticket):
    """spec 046 US3 (FR-006): comentarios `visibility=internal` excluidos a nivel de API para
    `tickets:view_own` — Coordinador/Admin siguen viendo el historial completo (no-regresión)."""
    ticket = make_ticket()
    comment = client.post(f"/api/tickets/{ticket['id']}/comments", json={
        "comment_type": "comentario_interno", "body": "Nota interna de diagnóstico",
    }).get_json()

    admin_view = client.get(f"/api/tickets/{ticket['id']}")
    admin_comment_ids = {c["id"] for c in admin_view.get_json()["comments"]}
    assert comment["comment"]["id"] in admin_comment_ids

    encargado_view = client.get(f"/api/tickets/{ticket['id']}", headers=encargado_auth)
    assert encargado_view.status_code == 200
    encargado_comment_ids = {c["id"] for c in encargado_view.get_json()["comments"]}
    assert comment["comment"]["id"] not in encargado_comment_ids


def test_encargado_can_respond_to_solicitud_informacion(client, encargado_auth, make_ticket,
                                                         ticket_resource, resolver_auth):
    """spec 046 US4: el Usuario/cliente puede responder una 'Solicitud de información' de un
    ticket de su empresa — reutiliza sin cambios la transición pendiente_usuario->en_ejecucion
    y la notificación user_replied al resolutor asignado, ambas ya implementadas."""
    ticket = make_ticket()
    client.post(f"/api/tickets/{ticket['id']}/assign",
                json={"assignee_id": ticket_resource["id"], "mode": "resolver"})
    client.post(f"/api/tickets/{ticket['id']}/comments",
                json={"comment_type": "confirmacion_atencion", "body": "Contacto"})
    r = client.post(f"/api/tickets/{ticket['id']}/comments",
                    json={"comment_type": "solicitud_informacion", "body": "Necesito más datos"})
    assert r.get_json()["ticket"]["status"] == "pendiente_usuario"

    resp = client.post(f"/api/tickets/{ticket['id']}/comments",
                       json={"comment_type": "respuesta_usuario", "body": "Aquí está la información"},
                       headers=encargado_auth)
    assert resp.status_code == 201, resp.get_json()
    assert resp.get_json()["ticket"]["status"] == "en_ejecucion"

    notifications = client.get("/api/notifications?unread=false&page=1&page_size=10",
                               headers=resolver_auth)
    messages = [n["message"] for n in notifications.get_json()["items"]]
    assert any("respondió" in m for m in messages)


def test_encargado_cannot_post_other_comment_types(client, encargado_auth, make_ticket):
    ticket = make_ticket()
    resp = client.post(f"/api/tickets/{ticket['id']}/comments",
                       json={"comment_type": "comentario_interno", "body": "intento"},
                       headers=encargado_auth)
    assert resp.status_code == 403


def test_encargado_cannot_respond_to_other_client_ticket(client, encargado_auth, unique_name):
    other_client = client.post("/api/clients", json={"name": f"Otro Cliente Resp {unique_name}"}).get_json()
    other_project = client.post("/api/projects", json={
        "client_id": other_client["id"], "name": f"Otro Proyecto Resp {unique_name}",
        "start_date": _today,
    }).get_json()
    other_ticket = client.post("/api/tickets", json={
        "title": "Ticket ajeno", "description": "No debe poder responder",
        "client_id": other_client["id"], "project_id": other_project["id"],
        "ticket_type": "incident", "priority": "high", "severity": "s2",
    }).get_json()
    resp = client.post(f"/api/tickets/{other_ticket['id']}/comments",
                       json={"comment_type": "respuesta_usuario", "body": "intento"},
                       headers=encargado_auth)
    assert resp.status_code == 404


def test_encargado_can_list_own_notifications(client, encargado_auth):
    """Regression: notifications.py gated on tickets:view only, which Encargado never has
    (only tickets:view_own) — broke the notification bell for this role with a 403."""
    resp = client.get("/api/notifications?unread=false&page=1&page_size=10", headers=encargado_auth)
    assert resp.status_code == 200
    assert resp.get_json()["items"] == []


def test_encargado_mine_filter_narrows_to_own_and_requested(client, encargado_auth, make_ticket):
    """spec 046 US6 (FR-014): 'Asignado a mí' acota a lo creado o solicitado por el propio
    Usuario/cliente, dentro del mismo Cliente ya forzado por US2 (no lo reemplaza)."""
    company_ticket = make_ticket()  # de otro contacto de la misma empresa — visible sin `mine`
    own = client.post("/api/tickets", json={
        "title": "Mío para el filtro", "description": "Descripción",
    }, headers=encargado_auth).get_json()

    without_filter = client.get("/api/tickets", headers=encargado_auth)
    ids_without = {i["id"] for i in without_filter.get_json()["items"]}
    assert company_ticket["id"] in ids_without and own["id"] in ids_without

    with_filter = client.get("/api/tickets?mine=true", headers=encargado_auth)
    ids_with = {i["id"] for i in with_filter.get_json()["items"]}
    assert own["id"] in ids_with
    assert company_ticket["id"] not in ids_with


def test_encargado_cannot_force_tarea_record_type(client, encargado_auth):
    """spec 046 US5/FR-008: aunque se envíe `record_type_id` de Tarea en el payload directo, el
    autoservicio de Usuario/cliente lo ignora por completo (ver tickets.py `is_encargado`) — se
    conserva el alta simplificada de Ticket ya existente, sin exponer creación de Tareas."""
    record_types = client.get("/api/catalogs/record-types").get_json()["items"]
    tarea_id = next(rt["id"] for rt in record_types if rt["name"] == "Tarea")

    resp = client.post("/api/tickets", json={
        "title": "Intento de crear Tarea", "description": "No debería convertirse en Tarea",
        "record_type_id": tarea_id,
    }, headers=encargado_auth)
    assert resp.status_code == 201, resp.get_json()
    assert resp.get_json()["record_type"] == "Ticket"


def test_encargado_without_client_contact_gets_409(client, unique_name):
    from flask_jwt_extended import create_access_token
    from backend.domain.entities.user import User
    from backend.infra.database import get_db
    from backend.infra.repositories.role_repo import RoleRepository
    from backend.infra.repositories.user_repo import UserRepository
    import uuid

    app = client.application
    with app.app_context():
        role = RoleRepository(get_db()).get_by_name("Usuario/cliente")
        orphan = UserRepository(get_db()).create(User(
            id=uuid.uuid4(), email=f"orphan.{unique_name}@clienteexterno.com",
            username=f"orphan_{unique_name}", role=role,
        ))
        token = create_access_token(identity=str(orphan.id))

    resp = client.post("/api/tickets", json={
        "title": "Sin cliente asociado", "description": "Descripción",
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "no_client_contact"
