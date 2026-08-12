# Data Model: Portal de Cliente

Ninguna entidad nueva. Todos los cambios son de comportamiento/alcance sobre entidades y tablas ya existentes, más una fila aditiva de catálogo (permiso). Se documentan aquí solo los campos/relaciones que esta feature efectivamente lee o modifica.

## Entidades existentes reutilizadas (sin cambio de esquema)

### `User` / `Role` (`users`, `roles`)

- `role.name` — ya existente. Nuevo uso: comparado contra `login_mode` en `POST /api/auth/login` (Decisión 1). Valores relevantes: `Admin`, `Coordinador`, `QM`, `Resolutor` (modo `team`) vs. `Usuario/cliente` (modo `client_portal`).
- `user.active` — ya existente (spec 034). Sin cambio: una cuenta inactiva ya no puede loguear por ninguna pestaña (`jwt_required_active`/chequeo de login ya lo cubre).

### `ClientContact` (`client_contacts`)

- `client_contact.user_id` / `client_contact.client_id` — ya existentes. Nuevo uso: `ClientContactRepository.get_by_user_id(user_id)` (ya existe, sin cambio de firma) resuelve el `client_id` del actor para el scoping de Decisión 2, y su `id` para el filtro "asignado a mí" de Decisión 3.

### `Ticket`/`Comment` (`tickets`, `comments`)

- `ticket.client_id`, `ticket.project_id`, `ticket.client_contact_id`, `ticket.status` — ya existentes, sin cambio de esquema. Nuevo uso: base de los filtros de Decisiones 2/3, y `status == "pendiente_usuario"` como condición (ya implícita en la FSM) para habilitar la caja de respuesta en el frontend.
- `comment.comment_type`, `comment.visibility` — ya existentes (`backend/domain/entities/comment.py`), calculados en `Comment.create()`. Nuevo uso: `visibility` se usa para filtrar la respuesta de `_ticket_detail` (Decisión 4); `comment_type == "respuesta_usuario"` es el único tipo permitido a un actor `Usuario/cliente` (Decisión 5).

### `Notification` (`notifications`)

- Sin cambio de esquema. `notification_service._MESSAGES["user_replied"]` ya existe y ya se dispara desde `POST /<ticket_id>/comments` cuando `trigger == "respuesta_usuario"` — esta feature es la primera vez que ese código deja de ser inalcanzable (hoy nunca se ejecuta porque ningún Usuario/cliente puede producir ese trigger).

## Cambio aditivo de catálogo: permiso `tickets:respond_client`

Migración nueva `057_tickets_respond_client_permission.py` (mismo patrón que `052_tickets_view_assigned.py`):

| Campo | Valor |
|-------|-------|
| `permissions.module` | `tickets` |
| `permissions.action` | `respond_client` |
| Rol otorgado | `Usuario/cliente` (único) |

**Semántica**: habilita `POST /<ticket_id>/comments` para un Usuario/cliente, pero **solo** para `comment_type == "respuesta_usuario"` — la restricción de tipo vive en `comment_service.validate` (Capa 1), no en el permiso (Capa 3), siguiendo el Principio I de la Constitución. No se otorga `tickets:transition` (evita exponer `confirmacion_atencion`/`termina_analisis`/`solicitud_cierre`/`comentario_interno` a este rol).

## Parámetros de servicio/repositorio afectados (sin cambio de esquema, solo de firma)

| Función | Cambio |
|---------|--------|
| `TicketRepository.list_paginated` | Nuevo parámetro opcional `requester_ids: list[uuid] \| None` (Decisión 3) — filtra `created_by IN (...) OR client_contact_id IN (...)`. `client_id` ya existía como parámetro; lo nuevo es que la ruta deja de anularlo para `own_only`. |
| `CommentService.validate` | Nuevo parámetro `actor_is_client: bool = False` (Decisión 5) — cuando es `True`, solo permite `comment_type == "respuesta_usuario"`; cualquier otro tipo levanta `CommentError("forbidden", ..., status_code=403)`. |
| `_ticket_detail` (función interna de `tickets.py`) | Nuevo parámetro/flag interno `exclude_internal_comments: bool` derivado de `own_only` — filtra la lista de comentarios antes de serializar. |

## State Transitions

Sin cambios en `backend/domain/fsm/ticket_fsm.py` — la transición `respuesta_usuario` (`pendiente_usuario` → `en_ejecucion`) ya existe y ya es la única transición válida disparada por ese tipo de comentario; esta feature solo amplía **quién** puede dispararla, nunca **cómo** se dispara.

```
... → PENDIENTE DE USUARIO ──"respuesta_usuario" (ahora también por Usuario/cliente)──> EN EJECUCIÓN
```
