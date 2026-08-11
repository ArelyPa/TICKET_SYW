---

description: "Task list for spec 041 — Migración e Importación de Tareas desde Teamwork"
---

# Tasks: Migración e Importación de Tareas desde Teamwork (API v3 / Excel) con Trazabilidad y Asignación a Coordinador

**Input**: Design documents from `/specs/041-importacion-tareas-teamwork/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Incluidos, pero ultra-limitados (Principio VII de la Constitución — máx. 5-10 registros
por test; el fixture real de 8 filas en [`ejemplo-teamwork-tasks.xlsx`](ejemplo-teamwork-tasks.xlsx)/
[`.csv`](ejemplo-teamwork-tasks.csv) es la fuente de datos para los tests de importación). No
correr la suite completa de `pytest` en ningún momento — solo los archivos tocados por cada tarea.

**Organization**: Tareas agrupadas por Historia de Usuario (spec.md) para permitir implementación
y prueba independiente de cada una.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivo distinto, sin dependencias pendientes)
- **[Story]**: US1 (P1), US2 (P2), US3 (P3), US4 (P2) — ver spec.md
- Rutas de archivo exactas en cada descripción

---

## Phase 1: Setup

- [X] T001 Crear el paquete `backend/infra/importers/__init__.py` (Capa 2, adaptadores de origen
      externo para la importación — research.md Decisión 5)

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: ninguna Historia de Usuario puede completarse sin esta fase.

- [X] T002 Migración `backend/infra/migrations/versions/053_ticket_external_reference.py`:
      agrega `external_reference_id` (Text, nullable, indexado) y `external_reference_url`
      (Text, nullable) a `tickets`; inserta el permiso `ticket_imports:run` y lo asigna a los
      roles `Admin` y `Coordinador` (mismo patrón SQL crudo que la migración `048`/`052`)
- [X] T003 [P] Agregar columnas `external_reference_id`/`external_reference_url` a `TicketModel`
      en `backend/infra/models/ticket_model.py`
- [X] T004 [P] Agregar campos `external_reference_id: Optional[str]` /
      `external_reference_url: Optional[str]` a la entidad de dominio `Ticket` en
      `backend/domain/entities/ticket.py`
- [X] T005 [P] Agregar `external_reference_id`/`external_reference_url` a la interfaz
      `TicketDetail` en `frontend/src/types/ticket.ts`
- [X] T006 Exponer `external_reference_id`/`external_reference_url` en el serializador
      `_ticket_detail` de `backend/api/routes/tickets.py` (depende de T003/T004)
- [X] T007 Agregar `TicketRepository.get_by_external_reference_id(external_id: str)` en
      `backend/infra/repositories/ticket_repo.py` (usado por el upsert de importación, FR-009)

**Checkpoint**: esquema y tipos listos — las Historias de Usuario pueden avanzar.

---

## Phase 3: User Story 1 - Carga masiva de tareas desde Excel/CSV con vista previa (Priority: P1) 🎯 MVP

**Goal**: un Coordinador/Admin carga un archivo Excel/CSV del reporte estándar de Teamwork, revisa
la vista previa del mapeo y confirma la inserción/actualización masiva de Tareas.

**Independent Test**: cargar `ejemplo-teamwork-tasks.xlsx` (8 filas), verificar la vista previa
(1 fila marcada `needs_review` por cliente/proyecto no resuelto, el resto `ready`), confirmar,
verificar que la Tarea hija (`ID` 43340224) queda como Subtarea de la Tarea padre sintética
(`ID` 42106353), y que repetir la carga del mismo archivo actualiza en vez de duplicar.

### Tests for User Story 1

- [X] T008 [P] [US1] Test unitario de mapeo/resolución en
      `backend/tests/domain/test_teamwork_import_service.py`: usando las 8 filas de
      `ejemplo-teamwork-tasks.csv`, verificar conversión minutos→horas, construcción de
      `external_reference_url`, vínculo padre-hijo dentro del lote (42106353→43340224), y que la
      fila huérfana de padre (43266714, padre 43266697 ausente) se resuelve como Tarea de primer
      nivel sin bloquear el resto
- [X] T009 [P] [US1] Test de API en `backend/tests/api/test_ticket_imports.py`: `POST
      /api/ticket-imports/preview` (multipart con `ejemplo-teamwork-tasks.xlsx`) devuelve 8 filas
      con su `status`; `POST /api/ticket-imports/confirm` crea las Tareas; repetir `confirm` con
      el mismo payload reporta `updated` (no `created`) para esas filas — sin duplicados

### Implementation for User Story 1

- [X] T010 [US1] Implementar `backend/infra/importers/teamwork_file_parser.py` (Capa 2): lee
      `.xlsx` (`openpyxl`) o `.csv` (módulo `csv`) según extensión y homologa cada fila a un
      `dict` con las claves de `ImportRow.resolved` (`external_id`, `company_name`,
      `project_name`, `list_name`, `title`, `description`, `start_date`, `due_date`,
      `assignee_name`, `requester_name`, `estimated_minutes`, `parent_external_id`) — sin lógica
      de resolución contra la base de datos
- [X] T011 [US1] Implementar `backend/domain/services/teamwork_import_service.py` (Capa 1, sin
      imports de Flask/SQLAlchemy/`openpyxl`). Desviación del diseño original: en vez de recibir
      colecciones completas precargadas, recibe cada fila cruda + un `dict` de resolución ya
      armado por la Capa 3 (mismo patrón que `AssignmentService.validate`, que tampoco consulta
      repositorios) — evita precargar Clientes/Proyectos/Recursos completos en memoria. Devuelve
      `ImportRow` con `status` (`ready`/`needs_review`/`error`), detecta `ID` duplicado dentro del
      mismo archivo, resuelve `Parent task ID` contra el propio lote primero y contra
      `external_reference_id` ya existentes en SYTIX después (chequeo hecho por la Capa 3), y
      convierte `Time estimate` (minutos) a horas para la vista previa
- [X] T012 [P] [US1] Agregar `TaskListRepository.get_or_create_by_name(project_id, name)` en
      `backend/infra/repositories/task_list_repo.py` (FR-005)
- [X] T013 [P] [US1] Agregar `ResourceRepository.get_by_full_name(full_name)` (vía
      `resources.full_name`, exacto) en `backend/infra/repositories/resource_repo.py`
- [X] T014 [P] [US1] Agregar `ClientContactRepository.get_by_name_or_email(value)` en
      `backend/infra/repositories/client_contact_repo.py` — resolución de "Created by" acotada al
      `client_id` ya determinado para la fila (research.md Decisión 7/9)
- [X] T015 [US1] Implementar `TicketRepository.upsert_from_import(...)` en
      `backend/infra/repositories/ticket_repo.py` (kwargs explícitos, no un dict genérico): busca
      por `external_reference_id` (T007); si existe, actualiza campos mapeados; si no, crea una
      Tarea nueva (`record_type_id` = "Tarea", resuelto una vez en la Capa 3) — `list_id` y
      `parent_task_id` se resuelven/vinculan en una segunda pasada desde la ruta (T016), ya que el
      padre puede aparecer más adelante en el mismo array — depende de T007, T012, T013, T014
- [X] T016 [US1] Implementar `backend/api/routes/ticket_imports.py` (namespace nuevo
      `ticket_imports`, `require_permission("ticket_imports", "run")`): `POST
      /api/ticket-imports/preview` (solo `multipart/form-data` con `file` en esta historia — el
      `source: "api_v3"` se agrega en US3) usando T010+T011; `POST /api/ticket-imports/confirm`
      usando T015, devuelve `{created, updated, errors}` — depende de T010, T011, T015
- [X] T017 [US1] Registrar `ns_ticket_imports` en `backend/app.py` (mismo patrón que
      `ns_reports`) — depende de T016
- [X] T018 [P] [US1] Implementar `frontend/src/services/ticketImportService.ts`:
      `previewFile(file)`/`previewApiV3()` y `confirm(rows: ImportRow[])`
- [X] T019 [US1] Implementar `frontend/src/pages/TicketImportsPage.tsx`: `Upload.Dragger` de Ant
      Design para el archivo, `Table` de vista previa con columna de estado
      (ready/needs_review/error) y botón "Confirmar importación" — depende de T018
- [X] T020 [US1] Agregar ruta `/importacion-tareas` en `frontend/src/App.tsx`
      (`ProtectedRoute` con `{module: 'ticket_imports', action: 'run'}`) — depende de T019
- [X] T021 [P] [US1] Agregar ítem de navegación "Importación de Tareas" (grupo Maestros) en
      `frontend/src/config/navigation.tsx`

**Checkpoint**: US1 funcional y probable de forma independiente — MVP entregable.

---

## Phase 4: User Story 2 - Trazabilidad visible del origen Teamwork en el detalle del Ticket/Tarea (Priority: P2)

**Goal**: el detalle de un Ticket/Tarea con referencia externa muestra un enlace/insignia de
Teamwork que abre la tarea original en una pestaña nueva.

**Independent Test**: sobre un Ticket de prueba con `external_reference_id`/`external_reference_url`
asignados directamente (sin pasar por una importación real), verificar que el badge/enlace
aparece y funciona; verificar que un Ticket sin esos campos no lo muestra.

### Tests for User Story 2

- [X] T022 [P] [US2] Test de API en `backend/tests/api/test_tickets_external_reference.py`
      (2 tickets de prueba): `GET /api/tickets/{id}` incluye `external_reference_id`/
      `external_reference_url` cuando existen, y los devuelve `null` cuando no

### Implementation for User Story 2

- [X] T023 [US2] Agregar insignia/enlace de Teamwork en `frontend/src/pages/TicketDetailPage.tsx`
      (Tag con `LinkOutlined` envuelto en `<a target="_blank" rel="noopener noreferrer">`, junto
      al resto de badges del encabezado), visible solo cuando `external_reference_id` no es
      `null` — depende de T006

**Checkpoint**: US2 funcional de forma independiente.

---

## Phase 5: User Story 3 - Sincronización directa vía API v3 de Teamwork (Priority: P3)

**Goal**: activar la sincronización contra `/projects/api/v3/tasks.json` desde la misma pantalla,
reutilizando la vista previa/confirmación de US1.

**Independent Test**: con `requests` mockeado devolviendo un payload equivalente a
`ejemplo-teamwork-tasks.xlsx`, activar la sincronización y verificar que produce la misma vista
previa/resultado que la carga por archivo; con una respuesta de error simulada, verificar
`502 teamwork_api_error` sin filas insertadas.

### Tests for User Story 3

- [X] T024 [P] [US3] Test unitario en `backend/tests/infra/test_teamwork_api_client.py` con
      `requests` mockeado (`unittest.mock.patch`, sin dependencia nueva de testing): homologación
      de la respuesta de la API v3 (estilo JSON:API con bloque `included`, verificado contra
      apidocs.teamwork.com) al mismo formato de fila que `teamwork_file_parser.py`, error HTTP y
      falta de configuración

### Implementation for User Story 3

- [X] T025 [US3] Implementar `backend/infra/importers/teamwork_api_client.py` (Capa 2): `GET
      https://{TEAMWORK_DOMAIN}.teamwork.com/projects/api/v3/tasks.json` (Basic Auth con
      `TEAMWORK_API_TOKEN`, nunca expuesto al frontend — Principio IV), resuelve el bloque
      `included` (projects/companies/tasklists/users) y homologa a las mismas claves que emite
      T010. Nota: field-mapping verificado contra la documentación pública de Teamwork al momento
      de esta sesión, sin smoke-test contra una cuenta real — revisar antes de usar en producción
- [X] T026 [US3] Extender `POST /api/ticket-imports/preview`
      (`backend/api/routes/ticket_imports.py`) para aceptar `{"source": "api_v3"}` usando T025 +
      T011, devolviendo `502 teamwork_api_error` si la conexión falla — depende de T016, T025
- [X] T027 [US3] Agregar el control "Sincronizar con Teamwork (API v3)" en
      `frontend/src/pages/TicketImportsPage.tsx`, reutilizando la misma tabla de vista previa de
      US1 — depende de T019, T026 (implementado junto con T019, ya que la pantalla se diseñó con
      ambas vías de entrada desde el principio)

**Checkpoint**: US3 funcional, reutiliza preview/confirm de US1 sin duplicar lógica.

---

## Phase 6: User Story 4 - Asignación de Tickets/Tareas a usuarios con rol Coordinador (Priority: P2)

**Goal**: un Coordinador puede quedar como responsable de un Ticket/Tarea igual que un Resolutor,
en asignación inicial y en reasignación.

**Independent Test**: sin importar nada de Teamwork, abrir el selector de asignación de un Ticket
existente, confirmar que lista usuarios con rol Coordinador, asignarlo, y luego reasignarlo a un
Resolutor verificando el historial "Coordinador ➡️ Resolutor".

### Tests for User Story 4

- [X] T028 [P] [US4] Test unitario en `backend/tests/domain/test_assignment_service.py`:
      `AssignmentService.validate(..., mode="resolver", assignee_role_name="Coordinador")` ya no
      lanza `assignee_role_mismatch`; un rol fuera de `{"Resolutor", "Coordinador"}` sigue
      rechazado (5/5 tests del archivo en verde, sin DB)
- [X] T029 [P] [US4] Test de API en `backend/tests/api/test_assign.py` +
      `backend/tests/api/test_reassign.py` (fixture `coordinador_user` nuevo en `conftest.py`,
      mismo patrón que `qm_user`): `GET /api/tickets/coordinador-candidates` lista usuarios con
      rol Coordinador; `POST .../assign` con ese `user_id` en modo `resolver` aprovisiona el
      Recurso y asigna; `POST .../reassign` hacia ese Coordinador funciona igual que entre
      Resolutores. Requieren Postgres (Docker) para correr — ver nota de verificación al final

### Implementation for User Story 4

- [X] T030 [US4] En `backend/domain/services/assignment_service.py`: cambió
      `ASSIGN_MODE_REQUIRED_ROLE["resolver"]` de `"Resolutor"` a `{"Resolutor", "Coordinador"}` y
      la validación de igualdad a pertenencia de conjunto (research.md Decisión 6)
- [X] T031 [US4] Agregado `GET /api/tickets/coordinador-candidates` en
      `backend/api/routes/tickets.py` (espejo exacto de `qm-candidates`: lista por
      `UserRepository.list_paginated(role="Coordinador")`, `require_permission("tickets",
      "assign")`)
- [X] T032 [US4] En `TicketAssign.post` (modo `resolver`) y `TicketReassign.post`
      (`backend/api/routes/tickets.py`): si `resource_repo.get_by_id(assignee_id)` no encuentra
      nada, se intenta resolver `assignee_id` como `user_id` de un usuario con rol `Coordinador` y
      se aprovisiona su Recurso con `ResourceRepository.get_or_create_for_user` antes de continuar
      — depende de T030, T031
- [X] T033 [P] [US4] En `frontend/src/components/tickets/useResourceCandidates.ts`: combina los
      Recursos activos existentes con los candidatos de `GET /api/tickets/coordinador-candidates`
      (sintetizados como `Resource` mínimo, sin tocar el tipo compartido) + nuevo mapa
      `candidateRoles`; wireado en `AssignModal.tsx` y `ReassignModal.tsx`
- [X] T034 [US4] En `frontend/src/components/tickets/ResourceCandidateGrid.tsx`: prop opcional
      `candidateRoles` que muestra un `Tag` "Coordinador" por candidato — depende de T033

**Checkpoint**: las 4 Historias de Usuario funcionan de forma independiente.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T035 [P] Ejecutado contra Docker real (Docker Desktop arrancó a mitad de sesión; se
      reconstruyó la imagen `backend`/`worker` porque estaba desactualizada respecto a
      `requirements.txt` — `openpyxl` faltaba en la imagen vieja, causaba crash-loop de
      `sywork_backend`, ajeno a esta feature). Validado en el navegador real, logueado como
      Coordinador: US1 — subido `ejemplo-teamwork-tasks.xlsx` vía la pantalla de Importación,
      vista previa de 8 filas con estados/observaciones correctos (Andes resuelve Cliente+
      Proyecto, Aris resuelve Cliente pero no Proyecto, el resto queda `client_not_found`),
      "Confirmar importación" devolvió `{created, updated, errors}` coherente; US2 — TK-000001
      (importado) muestra el badge "Teamwork #41972833" en el detalle, TK-000002 (no importado)
      no lo muestra; US4 — el modal "Asignar ticket (Triage Push)" en modo Resolutor lista a
      `coordinador`/`coordinador2`/`coordinador3`/etc. con la etiqueta "Coordinador", y asignar
      TK-000002 a `coordinador` funcionó de punta a punta (recurso aprovisionado perezosamente,
      transición Nuevo → Contacto, comentario automático "Asignado a coordinador por
      coordinador"). US3 no se validó contra una cuenta real de Teamwork (sin credenciales
      disponibles en este entorno) — cubierto por el mock de `test_teamwork_api_client.py`
- [X] T036 [P] Confirmado tanto sin Docker (Flask app + `test_client()` en proceso local, sin
      DB) como con Docker real: `GET /swagger.json` incluye el tag `ticket_imports`, las rutas
      `/api/ticket-imports/preview` (200/400/401/403/500/502), `/api/ticket-imports/confirm`
      (200/400/401/403/500) y `/api/tickets/coordinador-candidates` (200/401/403/500), y
      `TicketDetail.allOf[1].properties` incluye `external_reference_id`/`external_reference_url`
      con su descripción (Principio I)
- [X] T037 [P] Ejecutados todos los tests nuevos/tocados de esta feature contra Postgres real
      (Docker): `test_teamwork_import_service.py`, `test_assignment_service.py`,
      `test_teamwork_api_client.py`, `test_ticket_imports.py`, `test_tickets_external_reference.py`,
      `test_assign.py`, `test_reassign.py` — **37/37 en verde**. Ajustes hechos durante la
      verificación real (no eran bugs de implementación, sino supuestos incorrectos de los
      tests): `test_ticket_imports.py` asumía que ninguna fila resolvía Cliente salvo "Andes"
      sembrado por el propio test — en la práctica Aris (cliente ya sembrado en este entorno,
      spec 026) también resuelve Cliente pero no Proyecto ("SOPORTE ARIS" no coincide con los
      proyectos sembrados), y el fixture de Cliente se volvió `find-or-create` porque esta suite
      no aísla datos entre corridas (mismo criterio que el resto de tests de la base de código).
      No se corrió la suite completa de `pytest` en ningún momento (Principio VII)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias.
- **Foundational (Phase 2)**: depende de Setup — BLOQUEA las 4 Historias de Usuario.
- **US1 (Phase 3)**: depende solo de Foundational. Es el MVP.
- **US2 (Phase 4)**: depende solo de Foundational (T006) — **no depende de US1**, se puede probar
  con datos de prueba insertados directamente.
- **US3 (Phase 5)**: depende de Foundational **y** de la infraestructura de US1 (T016, T019 — el
  endpoint y la pantalla que extiende). No es independiente de US1 en implementación, aunque sí
  lo es en valor entregado.
- **US4 (Phase 6)**: depende solo de Foundational — completamente independiente de US1/US2/US3.
- **Polish (Phase 7)**: depende de todas las historias que se decidan entregar.

### Parallel Opportunities

- Foundational: T003, T004, T005 en paralelo (archivos distintos); T006/T007 después.
- US1: T012, T013, T014 en paralelo entre sí (después de T011); T008/T009 en paralelo entre sí y
  con T010/T011 (son tests, no bloquean implementación si se sigue TDD).
- US2, US4 pueden implementarse en paralelo entre sí y en paralelo con US1 una vez completada la
  fase Foundational (no comparten archivos, salvo T032/T034 dentro de US4 mismo).
- US3 debe esperar a que T016/T019 (US1) existan.

---

## Parallel Example: User Story 1

```bash
# Tests (si se sigue TDD, antes de la implementación):
Task: "Test unitario de teamwork_import_service en backend/tests/domain/test_teamwork_import_service.py"
Task: "Test de API de ticket-imports en backend/tests/api/test_ticket_imports.py"

# Repositorios de resolución, una vez completado T011:
Task: "TaskListRepository.get_or_create_by_name en backend/infra/repositories/task_list_repo.py"
Task: "ResourceRepository.get_by_full_name en backend/infra/repositories/resource_repo.py"
Task: "ClientContactRepository.get_by_name_or_email en backend/infra/repositories/client_contact_repo.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Completar Phase 1 (Setup) + Phase 2 (Foundational).
2. Completar Phase 3 (US1) — cargar `ejemplo-teamwork-tasks.xlsx`, ver preview, confirmar.
3. **Detener y validar**: correr la Independent Test de US1 contra Docker real.
4. US1 por sí sola ya resuelve el problema central (migrar tareas de Teamwork con trazabilidad).

### Incremental Delivery

1. Setup + Foundational → base lista.
2. US1 → validar independientemente → MVP.
3. US2 → validar independientemente (badge de trazabilidad ya visible sin depender de US1).
4. US4 → validar independientemente (asignación a Coordinador, sin relación con importación).
5. US3 → validar independientemente (mismo preview de US1, ahora también por API v3).

---

## Notes

- Ningún test de esta feature debe insertar más de 5-10 registros (Principio VII) — usar siempre
  `ejemplo-teamwork-tasks.xlsx`/`.csv` (8 filas) como fuente.
- Prohibido correr la suite completa de `pytest` en cualquier punto de esta feature.
- `[P]` = archivos distintos, sin dependencias pendientes entre sí.
- `[US1]`/`[US2]`/`[US3]`/`[US4]` trazan cada tarea a su Historia de Usuario en spec.md.
