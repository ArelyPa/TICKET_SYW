"""GET /api/tickets/{id} expone external_reference_id/external_reference_url (spec 041, US2).

Ultra-limitado (Principio VII): 2 tickets de prueba (con y sin referencia externa), sin depender
de un flujo de importación real — los campos se fijan directo en el repositorio, como pide la
Independent Test de US2 en spec.md."""
from backend.infra.repositories.ticket_repo import TicketRepository


def test_ticket_with_external_reference_exposes_it_in_detail(client, make_ticket, db_session):
    ticket = make_ticket(title="Tarea migrada desde Teamwork")
    TicketRepository(db_session).update_fields(
        ticket["id"],
        external_reference_id="41972833",
        external_reference_url="https://sywork.teamwork.com/app/tasks/41972833",
    )

    response = client.get(f"/api/tickets/{ticket['id']}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["external_reference_id"] == "41972833"
    assert body["external_reference_url"] == "https://sywork.teamwork.com/app/tasks/41972833"


def test_ticket_without_external_reference_returns_null(client, make_ticket):
    ticket = make_ticket(title="Ticket creado directo en SYTIX")

    response = client.get(f"/api/tickets/{ticket['id']}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["external_reference_id"] is None
    assert body["external_reference_url"] is None
