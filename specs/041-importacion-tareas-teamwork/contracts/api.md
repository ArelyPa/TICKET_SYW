# Contract: Migración e Importación de Tareas desde Teamwork (spec 041)

Endpoints nuevos, documentados en Swagger vía Flask-RESTX (Principio I) antes de implementarse.

## Importación (`backend/api/routes/ticket_imports.py`, namespace nuevo `ticket_imports`)

Todos los endpoints de este namespace requieren `require_permission("ticket_imports", "run")`
(Admin, Coordinador — Decisión 1 de `research.md`).

### `POST /api/ticket-imports/preview` — generar vista previa

**Body**: `multipart/form-data` con campo `file` (`.xlsx`/`.csv` del reporte estándar de
Teamwork) **o** `application/json` `{"source": "api_v3"}` para consultar
`/projects/api/v3/tasks.json` de Teamwork (US3) usando las credenciales ya configuradas.

**200**:
```json
{
  "rows": [
    {"source_row_number": 2, "external_id": "41972833", "status": "ready",
     "issues": [],
     "resolved": {"client_name": "Aris", "client_id": "uuid", "project_name": "Soporte",
                  "project_id": "uuid", "list_name": "Backlog", "title": "Ajustar reporte X",
                  "description": "...", "start_date": "2026-07-01", "due_date": "2026-07-10",
                  "assignee_name": "Juan Pérez", "assignee_resource_id": "uuid",
                  "requester_name": "María Ruiz", "requester_client_contact_id": "uuid",
                  "estimated_hours": 2.5, "parent_external_id": null}},
    {"source_row_number": 3, "external_id": "41972899", "status": "needs_review",
     "issues": ["assignee_not_found"], "resolved": {"...": "..."}}
  ],
  "summary": {"total": 2, "ready": 1, "needs_review": 1, "error": 0}
}
```

**400** `validation_error`: archivo sin las columnas mínimas esperadas, o `source` inválido.
**502** `teamwork_api_error`: la API v3 de Teamwork no respondió o devolvió error (solo aplica a
`source: "api_v3"`).

### `POST /api/ticket-imports/confirm` — insertar/actualizar las filas revisadas

**Body**: `{"rows": [ /* mismas filas de la preview, ya editadas/filtradas por el usuario */ ]}`
— solo se procesan filas con `status: "ready"` o `"needs_review"` con su campo `resolved`
completado manualmente por el usuario en el navegador; las de `status: "error"` se ignoran.

**200**:
```json
{"created": 8, "updated": 2, "errors": [{"source_row_number": 5, "reason": "client_not_found"}]}
```

**403**: sin permiso `ticket_imports:run`.

## Asignación a Coordinador (`backend/api/routes/tickets.py`, cambios)

### `GET /api/tickets/coordinador-candidates` (nuevo, espejo de `qm-candidates`)

**Permiso**: `require_permission("tickets", "assign")` (igual que `/qm-candidates` y `/assign`).

**200**: `[{"id": "user-uuid", "full_name": "...", "active": true}]` — igual que
`qm-candidates`, `id` es un `user_id` que `/assign`/`/reassign` resuelven a `resource_id`
(aprovisionando el Recurso si hace falta).

### `POST /api/tickets/{id}/assign` (cambio aditivo, modo `resolver`)

Si `assignee_id` no corresponde a un Recurso existente, se intenta resolver como `user_id` de un
usuario con rol Coordinador (mismo mecanismo ya usado para QM en modo `pre_analysis`). Sin cambio
de contrato de request/response.

### `POST /api/tickets/{id}/reassign` (cambio aditivo)

Mismo mecanismo de resolución que `/assign`. Sin cambio de contrato de request/response.

## Detalle del Ticket/Tarea (`backend/api/routes/tickets.py`, `_ticket_detail`)

`GET /api/tickets/{id}` (respuesta existente, cambio aditivo): agrega `external_reference_id` y
`external_reference_url` (ambos `null` si el ticket no tiene origen Teamwork).
