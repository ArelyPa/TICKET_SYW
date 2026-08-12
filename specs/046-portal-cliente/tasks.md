---

description: "Task list for Portal de Cliente (046-portal-cliente)"
---

# Tasks: Portal de Cliente (Login Diferenciado, Aislamiento por Cliente, Comentarios Públicos y Respuesta a Solicitud de Información)

**Input**: Design documents from `/specs/046-portal-cliente/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/api-changes.md](./contracts/api-changes.md), [quickstart.md](./quickstart.md)

**Tests**: Incluidos, siguiendo la convención ya vigente en este proyecto (specs 030-045) — **acotados a máximo 5 registros de prueba por test** (instrucción explícita del usuario en esta sesión, más estricta que el Principio VII). Prohibido correr la suite completa de `pytest` en ningún momento.

**Alcance de archivos** (instrucción explícita del usuario, ver plan.md § Constraints): solo pantalla de Login, guardia de permisos de `Usuario/cliente`, componentes de comentarios y el filtro de visibilidad por cliente **en tickets**. No se modifica `projects.py` ni ningún otro controlador central fuera de lo estrictamente necesario para este rol (ver nota en Fase 4).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: Historia de usuario a la que pertenece (US1-US6, spec.md)

---

## Phase 1: Setup

- [X] T001 Verificar stack Docker corriendo (`sywork_backend`/`sywork_frontend`/`sywork_db`) y credenciales de prueba disponibles (`docs/credenciales_dev.txt`, Cliente Aris + Usuario/cliente activo) — prerrequisito para validar cada historia contra Docker real. Sin dependencias ni librerías nuevas que instalar (Principio V, cero deps nuevas confirmado en plan.md).

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: bloquea US2, US3, US4 y US6 (todas necesitan resolver el Cliente/contacto del actor autenticado). US1 y US5 no dependen de esta fase.

- [X] T002 Agregar helper privado `_resolve_client_scope(db, user) -> tuple[uuid.UUID, uuid.UUID] | None` (retorna `(client_id, client_contact_id)` del `Usuario/cliente` autenticado, o `None` si no tiene `client_contact` asociado) en `backend/api/routes/tickets.py`, usando `ClientContactRepository(db).get_by_user_id(user.id)` (research.md Decisión 2/3, ya existente sin cambios de firma).

**Checkpoint**: helper listo — US2, US3, US4 y US6 pueden implementarse.

---

## Phase 3: User Story 1 - Acceso diferenciado en el Login (Priority: P1) 🎯 MVP

**Goal**: pestañas "Equipo / Empleados" / "Portal de Clientes / Colaboradores" en `/login`, con enforcement estricto de rol contra pestaña.

**Independent Test**: quickstart.md sección 1 — loguear con cuenta interna por la pestaña de Portal (401) y con Usuario/cliente por la pestaña de Equipo (401); ambas cuentas funcionan en su pestaña correcta.

### Tests for User Story 1

- [X] T003 [P] [US1] Test acotado (≤5 registros) en `backend/tests/api/test_auth.py`: `POST /api/auth/login` con `login_mode="client_portal"` y una cuenta interna → `401`; con `login_mode="team"` y una cuenta `Usuario/cliente` → `401`; sin `login_mode` → comportamiento actual sin cambios.

### Implementation for User Story 1

- [X] T004 [US1] Modificar `AuthLogin.post` en `backend/api/routes/auth.py`: aceptar `login_mode: "team" | "client_portal"` opcional en `_login_input`; tras validar credenciales, si viene informado comparar contra `user.role.name` (`team` → {Admin, Coordinador, QM, Resolutor}; `client_portal` → {Usuario/cliente}); no coincide → mismo `401` genérico ya usado para credenciales inválidas (research.md Decisión 1).
- [X] T005 [P] [US1] Agregar tipo `LoginMode = 'team' | 'client_portal'` en `frontend/src/types/auth.ts` (o archivo de tipos de auth existente).
- [X] T006 [US1] Modificar `frontend/src/services/authService.ts`: `login()` acepta y envía `login_mode`.
- [X] T007 [US1] Modificar `frontend/src/pages/LoginPage.tsx`: agregar `Tabs` de Ant Design 5 ("Equipo / Empleados" seleccionada por defecto / "Portal de Clientes / Colaboradores") sobre el mismo formulario y flujo de "¿Olvidaste tu contraseña?" ya existentes, reutilizando `AuthLayout.tsx` sin cambios de identidad visual (FR-001/002).
- [X] T008 [US1] Validar manualmente contra Docker real (quickstart.md sección 1).

**Checkpoint**: Login diferenciado funcional de forma independiente.

---

## Phase 4: User Story 2 - Aislamiento de datos por Cliente (Priority: P1)

**Goal**: `GET /api/tickets` (Tickets y Tareas, misma tabla) para un Usuario/cliente devuelve todo lo de su empresa, no solo lo propio; imposible forzar otro `client_id` por query.

**Independent Test**: quickstart.md sección 2.

**Nota de alcance**: el listado de Proyectos del Portal ya usa `GET /api/client-contacts/me/projects` (existente desde spec 010, acotado por membresía vía `project_members`, sin pasar por `projects.py`/`projects:view` — permiso que Usuario/cliente no tiene). Se audita en T011 que ya cumple el aislamiento pedido; **no se modifica `projects.py`**, respetando el alcance de archivos de esta sesión.

### Tests for User Story 2

- [X] T009 [P] [US2] Test acotado (≤5 registros) en `backend/tests/api/test_tickets_crud.py`: Usuario/cliente con solo `tickets:view_own` ve tickets de su empresa creados por **otro** `client_contact` de la misma empresa (no solo los propios); un `client_id` de otro cliente enviado por query es ignorado.

### Implementation for User Story 2

- [X] T010 [US2] Modificar `TicketList.get` en `backend/api/routes/tickets.py`: cuando `own_only`, usar el helper de T002 para forzar `client_id = client_id resuelto` en `TicketRepository.list_paginated` en vez de `created_by`; dejar de anular `search`/`statuses`/`priority`/`severity`/`sort`/`escalation_level`/`sla_status`; si viene `project_id` en la query, validar que pertenezca al `client_id` resuelto antes de aplicarlo (research.md Decisión 2).
- [X] T011 [US2] Auditar `GET /api/client-contacts/me/projects` (`backend/api/routes/client_contacts.py`) contra un Usuario/cliente de prueba: confirmar que solo devuelve proyectos de su propio Cliente — sin cambios de código si ya cumple (ver Nota de alcance arriba).
- [X] T012 [US2] Validar manualmente contra Docker real (quickstart.md sección 2).

**Checkpoint**: US1 + US2 funcionan de forma independiente y combinada.

---

## Phase 5: User Story 3 - Comentarios internos nunca visibles (Priority: P1)

**Goal**: `_ticket_detail` excluye comentarios `visibility="internal"` de la respuesta cuando el actor solo tiene `tickets:view_own`.

**Independent Test**: quickstart.md sección 3.

### Tests for User Story 3

- [X] T013 [P] [US3] Test acotado (≤5 registros) en `backend/tests/api/test_tickets_crud.py`: `GET /api/tickets/{id}` con un Ticket que tiene 1 comentario `comentario_interno` + 1 `confirmacion_atencion` — actor `tickets:view_own` recibe solo el externo; actor Coordinador recibe ambos (no-regresión).

### Implementation for User Story 3

- [X] T014 [US3] Modificar `_ticket_detail` en `backend/api/routes/tickets.py`: cuando el actor solo tiene `tickets:view_own` (mismo predicado `own_only` de T010), filtrar el array de comentarios excluyendo `visibility == "internal"` antes de serializar (research.md Decisión 4).
- [X] T015 [US3] Validar manualmente contra Docker real (quickstart.md sección 3).

**Checkpoint**: US1 + US2 + US3 funcionan de forma independiente y combinada.

---

## Phase 6: User Story 4 - Responder una "Solicitud de información" (Priority: P2)

**Goal**: un Usuario/cliente puede registrar el comentario `respuesta_usuario` sobre un Ticket de su empresa en estado `pendiente_usuario`; el ticket transiciona a `en_ejecucion` y notifica al resolutor asignado — reutilizando sin cambios la lógica de transición/notificación ya implementada en `POST /<ticket_id>/comments`.

**Independent Test**: quickstart.md sección 4.

- [X] T016 [US4] Nueva migración `backend/infra/migrations/versions/057_tickets_respond_client_permission.py`: permiso `tickets:respond_client` (module=`tickets`, action=`respond_client`) otorgado únicamente al rol `Usuario/cliente` — mismo patrón que `052_tickets_view_assigned.py` (data-model.md).

### Tests for User Story 4

- [X] T017 [P] [US4] Test acotado (≤5 registros) en `backend/tests/domain/test_comment_service.py`: `CommentService.validate(..., actor_is_client=True)` permite `respuesta_usuario` sobre un ticket en `pendiente_usuario` y rechaza (403) cualquier otro `comment_type` para ese mismo actor.
- [X] T018 [P] [US4] Test acotado (≤5 registros) en `backend/tests/api/test_tickets_crud.py` (o archivo de comentarios existente): `POST /<ticket_id>/comments` con `tickets:respond_client` y `comment_type="respuesta_usuario"` sobre un ticket `pendiente_usuario` → `201`, ticket pasa a `en_ejecucion`, se crea notificación `user_replied` para el resolutor asignado.

### Implementation for User Story 4

- [X] T019 [US4] Modificar `CommentService.validate` en `backend/domain/services/comment_service.py`: nuevo parámetro `actor_is_client: bool = False`; cuando es `True`, solo permitir `comment_type == "respuesta_usuario"` (cualquier otro → `CommentError("forbidden", ..., status_code=403)`), preservando el resto de la validación existente (research.md Decisión 5).
- [X] T020 [US4] Modificar `backend/api/routes/tickets.py`: decorador de `TicketComments.post` acepta `tickets:transition` **o** `tickets:respond_client`; `_actor_context` calcula `actor_is_client` (actor con `tickets:respond_client` y sin `can_manage`/`resource_id`) y lo pasa a `_comment_svc.validate(...)`.
- [X] T021 [P] [US4] Modificar `frontend/src/components/tickets/CommentThread.tsx`: mostrar caja de respuesta cuando `ticket.status === 'pendiente_usuario'` y el rol del actor es `Usuario/cliente` (FR-009/012).
- [X] T022 [P] [US4] Extender/reutilizar `frontend/src/components/tickets/CommentComposer.tsx` para enviar `comment_type: 'respuesta_usuario'` desde esa caja de respuesta.
- [X] T023 [US4] Validar manualmente contra Docker real (quickstart.md sección 4), incluida la notificación real al resolutor asignado.

**Checkpoint**: US1-US4 funcionan de forma independiente y combinada.

---

## Phase 7: User Story 5 - Solo alta simplificada de Ticket, sin Tareas ni campos avanzados (Priority: P2)

**Goal**: el guard `isEncargado` ya existente en `TicketsPage.tsx` cubre el 100% de lo pedido (oculta creación de Tarea y campos de perfil interno) sin retirar el alta simplificada ya validada (spec 010/033).

**Independent Test**: quickstart.md sección 5.

### Tests for User Story 5

- [X] T024 [P] [US5] Test acotado (≤5 registros) en `backend/tests/api/test_tickets_crud.py`: `POST /api/tickets` con `record_type_id` de "Tarea" desde una cuenta `Usuario/cliente` → rechazado (verificar si ya existe cobertura equivalente antes de duplicar).

### Implementation for User Story 5

- [X] T025 [US5] Auditar `frontend/src/pages/TicketsPage.tsx` (guard `isEncargado`, línea ~52): confirmar que oculta 100% de los campos avanzados de perfil interno (Proyecto/Herramienta/Proceso/Skills/asignación manual) y cualquier acción de "Crear Tarea"; ajustar solo si falta algún campo (FR-008).
- [X] T026 [US5] Validar manualmente contra Docker real (quickstart.md sección 5): alta simplificada de Ticket sigue funcionando sin fricción.

**Checkpoint**: US1-US5 funcionan de forma independiente y combinada.

---

## Phase 8: User Story 6 - Centro de notificaciones y filtro "Asignado a mí" (Priority: P3)

**Goal**: `GET /api/tickets?mine=true` acota el listado a los registros donde el Usuario/cliente es creador o `client_contact_id`; el centro de notificaciones ya existente (`user_id`-scoped) cubre eventos relevantes sin cambio estructural.

**Independent Test**: quickstart.md sección 6.

### Tests for User Story 6

- [X] T027 [P] [US6] Test acotado (≤5 registros) en `backend/tests/api/test_tickets_crud.py`: `GET /api/tickets?mine=true` para Usuario/cliente devuelve solo tickets donde es `created_by` o `client_contact_id`, dentro del `client_id` ya forzado por US2.

### Implementation for User Story 6

- [X] T028 [US6] Modificar `TicketRepository.list_paginated` en `backend/infra/repositories/ticket_repo.py`: nuevo parámetro opcional `requester_ids: list[uuid.UUID] | None` — filtra `created_by IN (...) OR client_contact_id IN (...)` (research.md Decisión 3).
- [X] T029 [US6] Modificar `TicketList.get` en `backend/api/routes/tickets.py`: nuevo query param `mine` (bool); cuando `True` y el actor es Usuario/cliente, resolver `requester_ids` con el helper de T002 y pasarlo a `list_paginated`, aplicado **sobre** el `client_id` ya forzado por US2 (nunca lo reemplaza).
- [X] T030 [P] [US6] Modificar `frontend/src/services/ticketService.ts`: nuevo parámetro `mine?: boolean` en `list()`.
- [X] T031 [P] [US6] Modificar `frontend/src/pages/TicketsPage.tsx` y `frontend/src/pages/MyTasksPage.tsx`: exponer el control "Asignado a mí" también para Usuario/cliente (Tickets y Tareas, FR-014).
- [X] T032 [US6] Documentar en `backend/domain/services/notification_service.py` los `event_type` ya existentes/necesarios que aplican a un Usuario/cliente (cambio de estado del ticket, nuevo comentario público) — sin cambio estructural, `NotificationBell.tsx` se reutiliza tal cual (research.md Decisión 6).
- [X] T033 [US6] Validar manualmente contra Docker real (quickstart.md sección 6).

**Checkpoint**: Las 6 historias funcionan de forma independiente y combinada.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T034 [P] Ejecutar `tsc -b` en `frontend/` y corregir cualquier error de tipos introducido.
- [X] T035 Ejecutar la sección "Verificación de no-regresión (roles internos)" de quickstart.md: Coordinador/QM/Resolutor/Admin sin cambios de comportamiento.
- [X] T036 Actualizar a mano el bloque `<!-- SPECKIT START -->` de `CLAUDE.md` (Active feature → "implementada, pendiente commit") tras validar en Docker real — **no ejecutar el hook/skill `speckit-agent-context-update`**, confirmado destructivo del historial curado en sesiones previas (memoria `feedback-agent-context-hook-destructive`).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias.
- **Foundational (Phase 2)**: depende de Setup — bloquea US2, US3, US4, US6. US1 y US5 no dependen de esta fase y pueden arrancar en paralelo con ella.
- **User Stories (Phase 3-8)**: US1 y US5 solo dependen de Setup; US2, US3, US4, US6 dependen además de Foundational (T002).
- **Polish (Phase 9)**: depende de que las historias que se vayan a entregar estén completas.

### User Story Dependencies

- **US1 (P1)**: sin dependencia de otras historias.
- **US2 (P1)**: depende de T002 (Foundational). Independiente de US1/US3-US6.
- **US3 (P1)**: depende de T002. Independiente de US1/US2/US4-US6 (aunque comparte el mismo `own_only` que US2, cada una es verificable por separado).
- **US4 (P2)**: depende de T002 y de la migración T016 (propia de esta historia). No depende de US1/US2/US3, aunque en la práctica un Usuario/cliente real llega a esta pantalla vía US1+US2.
- **US5 (P2)**: sin dependencia de otras historias (auditoría de un guard ya existente).
- **US6 (P2)**: depende de T002; el filtro "Asignado a mí" se apoya en el `client_id` ya forzado por US2 (T010) pero puede implementarse y probarse por separado con un `client_id` fijo.

### Parallel Opportunities

- T003 (test US1) es paralelo a T002 (Foundational, otra historia).
- T005 (tipo `LoginMode`) es paralelo a T004 (backend).
- Dentro de US4: T017/T018 (tests) en paralelo entre sí; T021/T022 (frontend) en paralelo entre sí y con T019/T020 (backend, mismo archivo `tickets.py` en T020 → secuencial con T019 en `comment_service.py`, archivos distintos así que en la práctica también paralelizable).
- Dentro de US6: T030/T031 (frontend) en paralelo entre sí; T028/T029 (backend) secuenciales (mismo flujo, archivos distintos, T029 depende de la firma nueva de T028).
- Con capacidad de equipo, US1 y US5 pueden trabajarse en paralelo con Foundational + US2/US3/US4/US6 desde el inicio.

---

## Parallel Example: User Story 4

```bash
# Tests en paralelo:
Task: "Test acotado de CommentService.validate con actor_is_client en backend/tests/domain/test_comment_service.py"
Task: "Test acotado de POST /<id>/comments con tickets:respond_client en backend/tests/api/test_tickets_crud.py"

# Frontend en paralelo (tras T019/T020 backend):
Task: "Caja de respuesta condicionada a pendiente_usuario en frontend/src/components/tickets/CommentThread.tsx"
Task: "Envío de comment_type respuesta_usuario en frontend/src/components/tickets/CommentComposer.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) + Phase 3 (US1) → Login diferenciado funcional y demostrable de forma aislada, sin depender del resto.
2. **STOP and VALIDATE**: quickstart.md sección 1.

### Incremental Delivery

1. Setup + Foundational (T001-T002) → base lista para US2/US3/US4/US6.
2. US1 (Login) → demo independiente (MVP).
3. US2 (Aislamiento) → demo independiente — a partir de aquí el Portal ya es seguro de exponer.
4. US3 (Comentarios internos ocultos) → demo independiente — cierra la última brecha de confidencialidad.
5. US4 (Responder solicitud de información) → demo independiente — valor funcional central del Portal.
6. US5 (Sin creación avanzada) → ajuste de UI de bajo riesgo.
7. US6 (Notificaciones + "Asignado a mí") → mejora de usabilidad final.
8. Polish (Phase 9).

### Orden recomendado de implementación real

Dado que US2 y US3 son ambas P1 de confidencialidad y comparten el predicado `own_only`, conviene implementarlas juntas inmediatamente después de US1 antes de exponer el Portal a un Usuario/cliente real, aunque cada una siga siendo independientemente verificable.

---

## Notes

- [P] = archivos distintos, sin dependencias pendientes entre sí.
- Cada historia es independientemente completable y verificable vía su sección de `quickstart.md`.
- Commit sugerido tras cada Checkpoint de fase, no tarea por tarea (consistente con el patrón de commits ya usado en specs previas de este repo).
- Evitar: tocar `projects.py` (fuera del alcance de archivos de esta sesión, ver Nota de alcance en Phase 4); otorgar `tickets:transition` completo a `Usuario/cliente` (expondría tipos de comentario no pedidos); ejecutar la suite completa de `pytest` o generar más de 5 registros de prueba por test.

## Estado final: 36/36 tareas completas, todas validadas contra Docker real

Desviaciones menores respecto a la ubicación de archivo planeada originalmente (sin desviación de comportamiento):

- Los tests de US1/US2/US3/US5/US6 se agregaron a `backend/tests/api/test_auth_login_api.py` (ya existente para auth) y `backend/tests/api/test_tickets_encargado.py` (ya existente y ya dedicado a este rol) en vez de crear `test_auth.py` nuevo o usar `test_tickets_crud.py` — reutiliza fixtures ya existentes (`encargado_auth`, `ticket_client`, `make_ticket`) en vez de duplicarlas.
- T028 (`list_paginated`): en vez de un único `requester_ids: list[uuid.UUID]`, se implementó como `requester_client_contact_id: uuid.UUID | None` combinado por OR con el parámetro `created_by` ya existente — más preciso, ya que son dos columnas distintas (`created_by` es `user_id`, `client_contact_id` es su propia PK).
- Hallazgo durante US2 que amplió el alcance real de T010: `TicketDetail.get` (no solo `TicketList.get`) también forzaba `ticket.created_by != user.id` → 404 — se corrigió en el mismo cambio para que un ticket de la misma empresa (no solo el propio) sea visible en el detalle, consistente con la decisión "empresa completa".
- US2/US3 (T014) se implementaron en una sola pasada por compartir el mismo bloque de código en `TicketDetail.get` — ambas quedan igualmente cubiertas por tests y verificación manual independientes.

Validación end-to-end contra Docker real (Cliente Aris, Usuario/cliente `Eliseon@aris.ming.com`, resolutor `Resolutor Semilla`): pestañas de Login con enforcement confirmado en ambos sentidos; listado de Tickets/Tareas de Aris visible completo (incluidos registros creados por otros contactos/Admin, antes invisibles); detalle de un ticket ajeno a la empresa devuelve 404; comentario interno confirmado ausente de la respuesta de API para el Usuario/cliente y presente para Coordinador; ciclo completo "Solicitud de información" → caja de respuesta → "Respuesta de usuario" → transición a En Ejecución → notificación real al resolutor, verificado en TK-000144; modal "Nuevo ticket" confirmado con solo Título/Descripción/Proyecto opcional (sin Tarea/Cliente/Herramienta/Skills); filtro "Asignado a mí" confirmado acotando de 7 a 1 registro (TK-000194, el único creado por Eliseon). `pytest` acotado a los archivos tocados en 103/103 (más 1 fallo preexistente no relacionado en `test_tickets_sla.py`, confirmado reproducible contra el baseline limpio vía `git stash`); `tsc -b` sin errores.
