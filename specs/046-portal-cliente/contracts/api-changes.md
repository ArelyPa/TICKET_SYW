# API Contract Changes: Portal de Cliente

Todos los endpoints ya existen y ya están documentados en Swagger (`/swagger.json`). Esta feature solo amplía payloads/comportamiento — ningún endpoint nuevo salvo lo ya cubierto por reutilización de `GET /api/notifications`.

## `POST /api/auth/login`

**Request** — nuevo campo opcional:

```json
{
  "username_or_email": "coordinador",
  "password": "...",
  "login_mode": "team"
}
```

- `login_mode`: `"team" | "client_portal"`, opcional. Si se omite, se mantiene el comportamiento actual (sin enforcement) — el frontend nuevo siempre lo envía según la pestaña activa.

**Response 401 (nuevo caso)**: mismo shape ya documentado (`{"error": "unauthorized", "message": "Usuario o contraseña incorrectos"}`) cuando `login_mode` no coincide con `role.name` del usuario autenticado por credenciales — sin distinguir este caso de credenciales inválidas en el mensaje (FR-003 exige no confirmar existencia/rol de la cuenta).

## `GET /api/tickets`

Sin cambios de firma HTTP (mismos query params ya documentados). Cambio de comportamiento **solo** cuando el actor autenticado tiene únicamente `tickets:view_own` (Usuario/cliente):

| Antes (hoy) | Después (esta feature) |
|-------------|-------------------------|
| `created_by` forzado a `g.current_user.id`; `search`/`client_id`/`project_id`/`statuses`/`priority`/`severity`/`ticket_type`/`assignee_id`/`escalation_level`/`sla_status` ignorados | `client_id` forzado al Cliente del actor (vía `client_contact`); el resto de filtros arriba listados se respetan si vienen en la query, siempre acotados a ese `client_id` |
| Sin soporte de "asignado a mí" | Nuevo query param `mine=true` (opcional) — cuando el actor es Usuario/cliente, se traduce a `requester_ids=[client_contact_id del actor]` sobre `TicketRepository.list_paginated` |

Mismo tratamiento aplica al listado de Proyectos consumido por el Portal (reutiliza el filtro `client_id` ya existente de `ProjectRepository`, sin cambio de firma).

## `GET /api/tickets/{id}` (detalle, `_ticket_detail`)

Sin cambios de firma. Cambio de comportamiento: cuando el actor tiene únicamente `tickets:view_own`, el array `comments` de la respuesta excluye los elementos con `visibility == "internal"` — el resto de campos del ticket no cambia.

## `POST /api/tickets/{id}/comments`

Sin cambios de firma HTTP. Cambios de autorización:

- El decorador de la ruta pasa de exigir `tickets:transition` a exigir `tickets:transition` **o** `tickets:respond_client` (permiso nuevo, ver `data-model.md`).
- Cuando el actor solo tiene `tickets:respond_client` (Usuario/cliente): `comment_type` distinto de `"respuesta_usuario"` → `403 forbidden`. Un ticket que no esté en `pendiente_usuario` → `409` (ya cubierto hoy por `ticket_fsm.can_transition`, sin cambio). Éxito → mismo `201` con el comentario creado, mismo efecto colateral ya existente (transición a `en_ejecucion` + notificación `user_replied` al resolutor asignado).

## `GET /api/notifications`

Sin cambios de firma ni de autorización — ya filtra por `user_id` del actor (`WHERE user_id = current_user`), por lo que un Usuario/cliente ya solo ve las suyas. Cambio de alcance: se documentan en el backend los `event_type` adicionales que ahora pueden generarse hacia un Usuario/cliente (cambio de estado del ticket, nuevo comentario público) — mismo modelo `Notification` ya existente, sin campo nuevo.
