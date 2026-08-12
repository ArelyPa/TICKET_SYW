# Research: Portal de Cliente

Sin `[NEEDS CLARIFICATION]` pendientes en el spec (las 3 originales se resolvieron con el usuario vía `AskUserQuestion` durante `/speckit.specify`). Este documento registra las decisiones de diseño técnico necesarias para pasar de esas respuestas a un plan concreto, apoyadas en lo ya existente en el código (verificado por lectura directa, no supuesto).

## Decisión 1: Enforcement de `login_mode` en `POST /api/auth/login`

- **Decision**: Agregar un campo opcional `login_mode: "team" | "client_portal"` al payload de login. Si viene presente, tras validar credenciales (mismo orden que hoy: usuario existe → activo → password), se compara contra `user.role.name`: `team` exige rol ∈ {Admin, Coordinador, QM, Resolutor}; `client_portal` exige rol == `Usuario/cliente`. Si no coincide, responde `401` con el mismo mensaje genérico ya usado para credenciales inválidas (`"Usuario o contraseña incorrectos"`) — no se crea un código de error distinto para no filtrar por timing/mensaje si la cuenta existe pero está en la pestaña equivocada.
- **Rationale**: `backend/api/routes/auth.py` (`AuthLogin.post`) ya calcula `user.role.name` antes de emitir el JWT (línea usada para `additional_claims`); el chequeo es una comparación adicional sin nueva tabla ni columna. Reutiliza el mismo path de error 401 ya contemplado por el frontend (`LoginPage.tsx` ya maneja `response.data?.message`).
- **Alternatives considered**: (a) Enforcement solo en frontend (ocultar el submit si el rol no calza) — rechazada, no cumple "Estricto por rol" acordado con el usuario, un cliente API directo lo saltaría. (b) Endpoint de login separado por pestaña — rechazada, duplicaría lógica de verificación de password/activo sin necesidad (FR-001 exige "mismo formulario base... mismo mecanismo").

## Decisión 2: Ámbito de "empresa completa" en `tickets:view_own`

- **Decision**: En `GET /api/tickets` (`backend/api/routes/tickets.py`, clase de listado), cuando `own_only = has_view_own and not has_view`, en vez de forzar `created_by=g.current_user.id` y anular el resto de filtros (comportamiento actual, línea ~752-786), resolver el `client_id` del actor vía `ClientContactRepository(db).get_by_user_id(g.current_user.id)` y forzar `client_id = contact.client_id` en `TicketRepository.list_paginated`, preservando `search`/`statuses`/`priority`/`severity`/`sort` (ya seguros de exponer dentro del propio Cliente) pero **sin** permitir que el cliente sobreescriba `client_id`/`project_id` recibido por query — el project_id si se recibe se valida que pertenezca al `client_id` resuelto. Si el actor no tiene `client_contact` asociado, la lista responde vacía (mismo criterio que el Edge Case ya documentado en spec.md).
- **Rationale**: `ticket_repo.list_paginated` ya acepta `client_id`/`project_id`/`statuses`/etc. como parámetros independientes — no requiere nueva query, solo cambiar qué valor recibe `client_id` y dejar de anular los demás filtros para este rol. Esto es exactamente lo que la User Story 2 (spec) y la respuesta "Empresa completa" piden.
- **Alternatives considered**: RLS de PostgreSQL a nivel de fila por `client_id` — rechazada para esta feature: la RLS del proyecto es deliberadamente permisiva desde migración 012 (decisión ya tomada en sesiones previas, spec 038 US1 la respetó); introducirla ahora sería una desviación de alcance no pedida y de mayor riesgo/superficie que el cambio acotado al repositorio.
- **Aplicación al listado de Proyectos**: mismo patrón — el endpoint de Proyectos ya filtra por `client_id`; se fuerza igual que Tickets cuando el actor es Usuario/cliente (sin nuevo parámetro de repo, reutiliza el filtro `client_id` ya existente en `ProjectRepository`).

## Decisión 3: Filtro "Asignado a mí" para Usuario/cliente

- **Decision**: Nuevo parámetro opcional en `TicketRepository.list_paginated`, `requester_ids: list[uuid] | None`, que filtra `TicketModel.created_by.in_(requester_ids) OR TicketModel.client_contact_id.in_(client_contact_ids_del_actor)`. En la práctica un Usuario/cliente normalmente tiene un único `client_contact_id` propio; se resuelve igual que en Decisión 2. El frontend (`TicketsPage.tsx`/`MyTasksPage.tsx`) envía un flag `mine=true` que el backend traduce a este filtro adicional, aplicado **sobre** el `client_id` ya forzado por Decisión 2 (nunca lo reemplaza).
- **Rationale**: Sigue el mismo patrón ya usado por `tickets:view_assigned` (Resolutor, spec 038 US1: fuerza `assignee_id` sin tocar el resto de filtros) — consistente con el resto del código.
- **Alternatives considered**: Reutilizar el parámetro `created_by` existente tal cual — rechazada, no cubre el caso "solicitante explícito" (`client_contact_id`) pedido literalmente en FR-014.

## Decisión 4: Filtrado de comentarios `internal` en la respuesta de API

- **Decision**: En `_ticket_detail` (`backend/api/routes/tickets.py`), antes de serializar `comment.visibility` para la respuesta, si el actor no tiene `tickets:view` ni `tickets:view_assigned` (es decir, solo `tickets:view_own`, el mismo predicado `own_only` ya usado en el listado), excluir del array los comentarios con `visibility == "internal"`.
- **Rationale**: El campo `visibility` ya se calcula y persiste por comentario desde su creación (`Comment.create`, `comment.py`); no requiere cómputo nuevo, solo un filtro condicional al serializar. Es un cambio de una función, sin tocar el modelo de datos.
- **Alternatives considered**: Filtrar en el frontend — rechazada explícitamente por FR-006 ("no basta con ocultarlos en el frontend"), y por el requerimiento original del usuario ("Visibilidad Oculta... estrictamente").

## Decisión 5: Habilitar `respuesta_usuario` para Usuario/cliente

- **Decision**: Dos cambios coordinados:
  1. **Ruta** (`POST /<ticket_id>/comments`, hoy gateada por `@require_permission("tickets", "transition")`, permiso que Usuario/cliente NO tiene): se agrega un permiso nuevo y acotado `tickets:respond_client` (module=`tickets`, action=`respond_client`) otorgado únicamente al rol `Usuario/cliente` (migración aditiva `057`). El decorador de la ruta pasa a aceptar `tickets:transition` **o** `tickets:respond_client`.
  2. **Dominio** (`comment_service.validate`): se agrega un parámetro `actor_is_client: bool` (True cuando el actor solo tiene `tickets:respond_client`, sin `can_manage` ni `resource_id`). Cuando `actor_is_client` es True: **solo** se permite `comment_type == "respuesta_usuario"` (cualquier otro tipo → 403 `forbidden`); la verificación de que el ticket pertenece al Cliente del actor ya la garantiza `_get_ticket_or_404` reutilizando el mismo scoping de Decisión 2; la verificación de que el ticket está en `pendiente_usuario` ya la garantiza `ticket_fsm.can_transition` (la transición `respuesta_usuario` solo tiene `pendiente_usuario` como origen — sin cambio necesario ahí).
- **Rationale**: `backend/api/routes/tickets.py` (líneas ~1483-1500) **ya** ejecuta la transición FSM y **ya** dispara `NotificationRepository(db).add(_notif_svc.build(assignee.user_id, "user_replied", ...))` cuando `trigger == "respuesta_usuario"` — funcionalidad completa y sin cambios necesarios ahí. El único bloqueo real está en la puerta de permisos (ruta) y en la validación de autoría (dominio). No otorgar `tickets:transition` completo evita que un Usuario/cliente pueda disparar `confirmacion_atencion`/`termina_analisis`/`solicitud_cierre`/`comentario_interno` por el mismo endpoint.
- **Alternatives considered**: Endpoint dedicado `POST /<ticket_id>/respond` — rechazada, duplicaría toda la lógica de adjuntos/transición/notificación ya escrita y probada en el endpoint de comentarios existente, violando el alcance "no modificar controladores centrales" al crear uno nuevo en paralelo.

## Decisión 6: Centro de Notificaciones para Usuario/cliente

- **Decision**: Reutilizar `GET /api/notifications`/`NotificationRepository`/`NotificationBell.tsx` sin cambios estructurales; el único ajuste es de alcance de datos — las notificaciones ya se generan `by user_id` (destinatario), así que un Usuario/cliente solo verá las suyas de forma natural sin filtro adicional por Cliente. Se amplían los `event_type` que generan notificación para incluir cambios de estado relevantes y nuevos comentarios públicos sobre tickets donde el Usuario/cliente es `client_contact_id` o pertenece al mismo Cliente — reutilizando `_MESSAGES` de `notification_service.py` (ya tiene `user_replied`; se documentan los eventos adicionales necesarios en data-model.md).
- **Rationale**: El mecanismo ya está `user_id`-scoped por diseño (no requiere lógica de aislamiento por Cliente nueva); es la opción de menor riesgo y ya validada en producción para eventos de asignación (spec 032 OBS-0062).
- **Alternatives considered**: Mecanismo de notificación paralelo específico del Portal — rechazado, redundante y fuera del alcance de "no modificar controladores centrales fuera de este rol".

## Decisión 7: Alta simplificada de Ticket — conservar, ocultar Tareas y campos avanzados

- **Decision**: Sin cambios en `backend/api/routes/tickets.py POST /` (la rama `if isEncargado` ya limita los campos aceptados desde spec 010). Del lado frontend, `TicketsPage.tsx` (línea ~52, `isEncargado`) ya oculta creación de Cliente/Recurso; se extiende la misma condición para además ocultar la acción "Crear Tarea" (que hoy no existe como opción distinta visible para este rol, se verifica en Fase de implementación) y cualquier campo avanzado que hoy dependa de `!isEncargado`.
- **Rationale**: `isEncargado` ya es el guard existente para "alta simplificada" — no se introduce un guard nuevo, se audita que cubra el 100% de los campos avanzados pedidos por FR-008.
- **Alternatives considered**: N/A — decisión ya tomada con el usuario en `/speckit.specify` (Q3: "Conservar alta simplificada").

## Resumen de impacto en Data Model

Ninguna decisión requiere una tabla o columna nueva salvo la fila de permiso `tickets:respond_client` (Decisión 5) — ver `data-model.md`.
