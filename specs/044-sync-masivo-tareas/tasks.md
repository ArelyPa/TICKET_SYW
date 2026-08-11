---

description: "Task list template for feature implementation"
---

# Tasks: Operaciones Masivas, Paginación de Sincronización y Migración de Tareas/Subtareas (Teamwork API v3)

**Input**: Design documents from `/specs/044-sync-masivo-tareas/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md (todos presentes)

**Tests**: Incluidos, acotados a ≤10 registros dummy por test (directriz explícita de esta sesión / Principio VII) — solo se corren los archivos de test tocados, nunca la suite completa.

**Organization**: Tareas agrupadas por historia de usuario (spec.md) para permitir implementación y prueba independiente de cada una.

> Revisión `/speckit-analyze` (esta sesión): 2 hallazgos HIGH corregidos en esta versión — FR-010/SC-005
> (paginación fija a 15) no tenía tarea propia (ver T005, nueva) y el endpoint `GET /migrated-refs` (US5)
> podía disparar toasts de error 403 espurios para Resolutor/QM en 5 pantallas de uso diario (ver T023-T028,
> ahora con gate de permiso + `X-Skip-Error-Notify`). También se armonizó la condición canónica del filtro de
> `migrated-refs` (`sytix_id IS NOT NULL`, T021/T029) y se aclaró en dónde se reduce `assignee` de lista a
> valor único (Capa 2, T012).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: Historia de usuario a la que pertenece (US1-US5)
- Rutas de archivo exactas en cada descripción

## Path Conventions

Web app existente: `backend/` (Flask, Clean Architecture 3 capas) + `frontend/src/` (React). Sin
directorios nuevos — todos los cambios caen en archivos ya existentes del namespace `teamwork_integration`
(spec 042/043) más 5 pantallas principales de SYTIX (badge de trazabilidad, US5, ver plan.md § Complexity
Tracking).

---

## Phase 1: Setup

**Purpose**: Preparación de proyecto/esquema previa a las historias de usuario.

**N/A** — research.md confirma que esta feature no requiere migración de Alembic, dependencia nueva ni
estructura de directorios adicional: todas las columnas/tablas necesarias ya existen desde specs 041/042/043.
Se pasa directo a las historias de usuario.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestructura común bloqueante para todas las historias.

**N/A** — a diferencia de spec 043, las 5 historias de esta feature son mutuamente independientes por
diseño (spec.md): no hay una pieza compartida que bloquee a las 5 a la vez. La única infraestructura
compartida real (`_fetch_all_pages`, helper de paginación) nace dentro de US1 (que es quien tiene la
corrección de paginación como requisito, FR-011) y **US3 depende explícitamente de ese task de US1** — ver
§ Dependencies & Execution Order.

---

## Phase 3: User Story 1 - Sincronización de catálogos completa y confiable (Priority: P1) 🎯 MVP

**Goal**: La sincronización recorre todas las páginas que reporta Teamwork (no solo la primera), la tabla
de Personal muestra la Compañía/Empresa de origen de cada persona, y toda tabla de catálogo pagina a
exactamente 15 filas.

**Independent Test**: Sincronizar un catálogo con más de 60 registros de origen (mock de `requests` con 2+
páginas) y verificar que el `synced` reportado coincide con el total real; verificar que una Persona con
`companyId` muestra el nombre de su Compañía y una sin `companyId` muestra "Sin compañía"; verificar que la
tabla muestra exactamente 15 filas por página con más de 15 registros cargados.

### Implementation for User Story 1

- [X] T001 [US1] Agregar helper `_fetch_all_pages(url, auth, params)` en `backend/infra/importers/teamwork_connection_client.py` que incrementa `page=1,2,…` hasta una respuesta con menos elementos que `pageSize` o vacía (research.md Decisión 1); refactorizar `_fetch_entity` para usarlo en vez de una sola request
- [X] T002 [US1] Extender la rama `person` de `_fetch_entity` en `backend/infra/importers/teamwork_connection_client.py` para incluir `"parent_id": _parent_id(item)` (research.md Decisión 2) (depende de T001, mismo archivo/función)
- [X] T003 [US1] Agregar `"person"` a la resolución de `_resolve_parent_context` en `backend/api/routes/teamwork_integration.py`, devolviendo `{status, client_label, client_id}` vía `_resolve_parent_link(db, "company", mapping.parent_teamwork_id)` (research.md Decisión 2) (depende de T002)
- [X] T004 [P] [US1] Agregar columna "Compañía/Empresa de Origen" a la vista de Personal (`extraColumns`, rama `person`) renderizando `row.parent_context?.client_label ?? 'Sin compañía'` en `frontend/src/pages/TeamworkIntegrationPage.tsx` (depende de T003)
- [X] T005 [US1] Cambiar `pagination={false}` a `pagination={{ pageSize: 15, showSizeChanger: false }}` en el `Table` de "Homologación de Entidades" en `frontend/src/pages/TeamworkIntegrationPage.tsx` (research.md Decisión 5, FR-010/SC-005 — hallazgo `/speckit-analyze` E1, sin tarea previa)
- [X] T006 [US1] Test backend (≤10 registros dummy): mockear `requests.get` con 2 páginas para `fetch_people` y verificar que `_fetch_all_pages`/`fetch_people` devuelven la unión completa (no solo la primera página); sincronizar una Persona con `companyId` y otra sin, y verificar `parent_context.client_label`/`status="unmapped"` respectivamente vía `GET /entity-mappings` — en `backend/tests/api/test_teamwork_integration.py` (depende de T001-T003)

**Checkpoint**: US1 funcional y probable de forma independiente — sincronización confiable, Compañía visible y paginación fija a 15.

---

## Phase 4: User Story 2 - Migración masiva de Personal con filtro de correo (Priority: P1)

**Goal**: Filtrar Personal por patrón de correo, seleccionar varias filas y migrarlas/homologarlas en un
solo clic con el mismo Rol y Cliente de destino.

**Independent Test**: Con Personal ya sincronizado, filtrar por un fragmento de correo, seleccionar 3-5
filas, aplicar Rol "Usuario/cliente" + Cliente de destino, y verificar que las filas quedan migradas en una
sola operación, con las ya migradas previamente reportadas como omitidas.

### Implementation for User Story 2

- [X] T007 [US2] Agregar endpoint `POST /entity-mappings/bulk-create-new` en `backend/api/routes/teamwork_integration.py`: valida `mapping_ids`/`role_id` (400 si faltan), por cada `mapping_id` ya vinculado lo agrega a `skipped` con `reason="already_linked"`, para el resto invoca **sin duplicar lógica** el mismo `_create_new_person(db)(mapping, data)` ya existente (líneas 470-518) y `mapping_repo.set_created_new_mapping(...)` en éxito; agrega a `skipped` con el `error` code devuelto por el handler en caso de fallo puntual (sin abortar el lote) — contrato en `contracts/api.md`
- [X] T008 [P] [US2] Agregar `bulkCreateNew(payload)` a `frontend/src/services/teamworkIntegrationService.ts` y tipos `TeamworkBulkCreateNewPayload`/`TeamworkBulkCreateNewResult` a `frontend/src/types/teamworkIntegration.ts`
- [X] T009 [US2] Agregar `rowSelection` (checkboxes) + input de filtro por patrón de correo (client-side sobre `mappings[].teamwork_email`) + barra "Acciones Masivas" (Select Rol + Select Cliente condicional, reutilizando las mismas opciones ya cargadas para el modal "Migrar como Nuevo") a la tabla de Personal en `frontend/src/pages/TeamworkIntegrationPage.tsx` (depende de T008)
- [X] T010 [US2] Test backend (≤10 registros dummy): `bulk-create-new` — éxito para 2-3 filas con Rol interno y con "Usuario/cliente", fila ya vinculada omitida con `already_linked`, `role_id` faltante (400), `client_id` faltante para "Usuario/cliente" (400) — en `backend/tests/api/test_teamwork_integration.py` (depende de T007)

**Checkpoint**: US1+US2 funcionales — Personal se sincroniza completo, con Compañía visible, y se migra en lote.

---

## Phase 5: User Story 3 - Migración masiva de Tareas y Subtareas desde la API v3 (Priority: P2)

**Goal**: Consumir `GET /projects/api/v3/tasks.json`, resolver cada Tarea/Subtarea contra las
homologaciones ya existentes y crear/actualizar los Tickets/Tareas correspondientes en SYTIX con
hipervínculo de origen, preservando la jerarquía Tarea→Subtarea.

**Independent Test**: Con un lote de prueba de 5-10 Tareas/Subtareas cuyo Proyecto/Lista/Asignado ya estén
homologados, ejecutar la migración y verificar Tickets creados con hipervínculo funcional, jerarquía
preservada, tareas sin homologación completa reportadas como omitidas, y re-ejecución sin duplicados.

### Implementation for User Story 3

- [X] T011 [US3] Crear módulo Capa 1 puro `backend/domain/services/teamwork_task_migration_service.py` (sin imports de Flask/SQLAlchemy/`requests`) con el dataclass `TeamworkTaskRow` (campo `assignee_teamwork_id: str | None`, singular — ya reducido en Capa 2, ver T012) y una función `classify_task(raw, resolution)` que decide `status="ready"|"skipped"` + `skip_reason` según si `resolution["project_id"]`/`resolution["list_id"]` están resueltos (data-model.md)
- [X] T012 [US3] Agregar `fetch_tasks(site_url, api_token)` a `backend/infra/importers/teamwork_connection_client.py`, reutilizando `_fetch_all_pages` (T001) contra `GET /projects/api/v3/tasks.json`, devolviendo `{id, name, description, project_id, tasklist_id, parent_task_id, assignee_id}` por fila — `assignee_id` ya reducido acá (Capa 2) al primer elemento de `task.assignees` (o `None` si viene vacía), la Capa 3 no ve la lista cruda (research.md Decisión 8 / hallazgo `/speckit-analyze` A1) (depende de T001)
- [X] T013 [US3] Agregar endpoint `POST /sync/tasks` en `backend/api/routes/teamwork_integration.py`: por cada tarea cruda de T012, resolver `project`/`tasklist`/`assignee` vía `EntityMappingRepository.get_by_teamwork_key(...)`, derivar `client_id` desde `ProjectRepository(db).get_by_id(project_sytix_id).client_id`, clasificar con T011, y para las `ready` invocar `TicketRepository.upsert_from_import(...)` (sin modificar ese método) con `record_type_id` del catálogo "Tarea" (`CatalogRepository`, mismo patrón de lectura que `ticket_imports.py`) y `external_reference_url = f"{site_url}/app/tasks/{teamwork_id}"`; segunda pasada para resolver `parent_task_id` de Subtareas vía `TicketRepository.get_by_external_reference_id(...)` (mismo patrón que `ticket_imports.py` líneas 248-258, sin tocar ese archivo) — contrato en `contracts/api.md` (depende de T011, T012)
- [X] T014 [P] [US3] Agregar `syncTasks()` a `frontend/src/services/teamworkIntegrationService.ts` y tipo `TeamworkTaskSyncResult` a `frontend/src/types/teamworkIntegration.ts`
- [X] T015 [US3] Agregar sección/botón "Migrar Tareas y Subtareas" con resumen del resultado (`created`/`updated`/`skipped` con motivo) en `frontend/src/pages/TeamworkIntegrationPage.tsx` (depende de T014)
- [X] T016 [US3] Test backend (5-10 tareas dummy incluyendo 1-2 Subtareas): cadena resuelta crea Ticket con `external_reference_id`/`url` correctos; Proyecto/Lista no homologados → `skipped` sin Ticket huérfano; Subtarea enlaza a su Tarea padre ya creada en el mismo lote; re-ejecutar el mismo lote actualiza en vez de duplicar — en `backend/tests/api/test_teamwork_integration.py` (depende de T013)

**Checkpoint**: US1+US2+US3 funcionales — catálogos confiables, Personal en lote, y Tareas/Subtareas migradas con trazabilidad.

---

## Phase 6: User Story 4 - Selectores de homologación con contexto de Cliente y filtros globales (Priority: P3)

**Goal**: Los selectores de homologación de Proyectos/Listas de Tareas muestran `Cliente - Proyecto`, y un
bloque de filtros superior por Cliente/Proyecto acota Personal/Proyectos/Listas de Tareas.

**Independent Test**: Con 2 proyectos homónimos de Clientes distintos, confirmar que el selector los
distingue como `Cliente - Proyecto`; aplicar el filtro superior por Cliente y confirmar que las 3 pantallas
acotan sus filas.

### Implementation for User Story 4

- [X] T017 [P] [US4] Cambiar el label de `SYTIX_CANDIDATE_LOADER.project` a `` `${x.client_name} - ${x.name}` `` (fallback a `x.name` si no hay `client_name`) en `frontend/src/pages/TeamworkIntegrationPage.tsx` (research.md Decisión 4)
- [X] T018 [P] [US4] Prefijar cada opción de la carga de candidatos de Lista de Tareas con `` `${client_label} - ${project_label} - ${name}` `` usando el `parent_context` ya resuelto de la fila, en `frontend/src/pages/TeamworkIntegrationPage.tsx`
- [X] T019 [US4] Ajustar el `Select` de la columna "SYTIX" a `minWidth`/`maxWidth` responsive con `title` (tooltip nativo) en vez de `width: 240` fijo, en `frontend/src/pages/TeamworkIntegrationPage.tsx` (depende de T017, T018)
- [X] T020 [US4] Agregar bloque de filtros superior (Select Cliente + Select Proyecto en cascada, client-side sobre `mappings[].parent_context`) en Personal (solo Cliente, Proyecto deshabilitado — spec.md § Assumptions), Proyectos (solo Cliente) y Listas de Tareas (Cliente + Proyecto), en `frontend/src/pages/TeamworkIntegrationPage.tsx` (depende de T003 para que Personal tenga `parent_context.client_id`)

**Checkpoint**: US1-US4 funcionales — selectores desambiguados y filtros globales operativos.

---

## Phase 7: User Story 5 - Distintivos de trazabilidad en pantallas principales de SYTIX (Priority: P3)

**Goal**: Un badge/Tag visible en Clientes, Proyectos, Listas de Tareas, Equipo y Usuario/cliente indica
qué registros fueron migrados/homologados desde Teamwork, consistente con el estado ya visible en el
integrador — sin generar toasts de error para roles que pueden ver esas pantallas pero no tienen permiso de
integración de Teamwork.

**Independent Test**: Migrar un Cliente vía "Migrar como Nuevo" (o la acción masiva de Personal) y
verificar que su fila en la pantalla principal correspondiente de SYTIX muestra el badge, mientras un
registro creado manualmente no lo muestra; logueado como Resolutor/QM (sin `teamwork_integration:operate`),
confirmar que las 5 pantallas cargan sin badge y **sin toast de error**.

### Implementation for User Story 5

- [X] T021 [US5] Agregar `list_sytix_ids_by_type(sytix_entity_type: str) -> list[uuid.UUID]` a `EntityMappingRepository` en `backend/infra/repositories/teamwork_integration_repo.py` (filtra `sytix_entity_type` == parámetro y `sytix_id IS NOT NULL` — condición canónica, research.md Decisión 7 / hallazgo `/speckit-analyze` I1)
- [X] T022 [US5] Agregar endpoint `GET /migrated-refs?sytix_entity_type=<tipo>` en `backend/api/routes/teamwork_integration.py`, validando el parámetro contra `client|project|task_list|resource|user` (400 si inválido) — contrato en `contracts/api.md` (depende de T021)
- [X] T023 [P] [US5] Agregar `getMigratedRefs(sytixEntityType)` a `frontend/src/services/teamworkIntegrationService.ts` con `headers: {'X-Skip-Error-Notify': 'true'}` (mismo patrón que `calendarService.listAbsenceRequestsForResource`) y tipo `TeamworkMigratedRefs` a `frontend/src/types/teamworkIntegration.ts` — hallazgo `/speckit-analyze` U1 (depende de T022)
- [X] T024 [P] [US5] Agregar columna/`Tag` de origen Teamwork (solo lectura) a `frontend/src/pages/ClientsPage.tsx`, llamando a T023 con `sytix_entity_type=client` **solo si** `hasPermission('teamwork_integration','operate')` (mismo patrón `useAuthStore` ya usado en ese archivo para `canManage`) — hallazgo `/speckit-analyze` U1 (depende de T023)
- [X] T025 [P] [US5] Agregar columna/`Tag` de origen Teamwork a `frontend/src/pages/ProjectsPage.tsx`, `sytix_entity_type=project`, mismo gate `hasPermission('teamwork_integration','operate')` que T024 (depende de T023)
- [X] T026 [P] [US5] Agregar columna/`Tag` de origen Teamwork a `frontend/src/pages/ProjectListsPage.tsx`, `sytix_entity_type=task_list`, mismo gate `hasPermission('teamwork_integration','operate')` que T024 (depende de T023)
- [X] T027 [P] [US5] Agregar columna/`Tag` de origen Teamwork a `frontend/src/pages/TeamPage.tsx` (Recursos), `sytix_entity_type=resource`, mismo gate `hasPermission('teamwork_integration','operate')` que T024 (depende de T023)
- [X] T028 [P] [US5] Agregar columna/`Tag` de origen Teamwork a `frontend/src/pages/ClientContactsPage.tsx` (Usuario/cliente), `sytix_entity_type=user`, mismo gate `hasPermission('teamwork_integration','operate')` que T024 (depende de T023)
- [X] T029 [US5] Test backend (≤10 registros dummy): `migrated-refs` devuelve solo `sytix_id` no nulo (`sytix_id IS NOT NULL`, condición canónica) del tipo pedido, excluye pendientes y otros tipos — en `backend/tests/api/test_teamwork_integration.py` (depende de T021, T022)

**Checkpoint**: Las 5 historias de usuario funcionan de forma independiente — incluyendo la ausencia de toasts de error para roles sin `teamwork_integration:operate` en las 5 pantallas principales.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T030 [P] Ejecutar `tsc -b` y corregir errores de tipos en los archivos frontend tocados (`TeamworkIntegrationPage.tsx`, `teamworkIntegrationService.ts`, `types/teamworkIntegration.ts`, `ClientsPage.tsx`, `ProjectsPage.tsx`, `ProjectListsPage.tsx`, `TeamPage.tsx`, `ClientContactsPage.tsx`)
- [X] T031 Ejecutar la validación de `quickstart.md` (US1-US5) contra Docker real, incluyendo explícitamente SC-005 (15 filas por página, T005) y el caso "sin toast de error" de US5 logueado como Resolutor/QM (T023-T028) — sin correr la suite completa de `pytest` (Principio VII)
- [X] T032 [P] Actualizar el bloque "Active feature" de `CLAUDE.md` con el resumen de spec 044 una vez validada (mismo patrón que specs anteriores)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** y **Foundational (Phase 2)**: N/A, sin tareas — ver justificación en cada fase.
- **US1 (Phase 3)**: sin dependencia de otras historias — es la base de la que **US3 depende parcialmente**.
- **US2 (Phase 4)**: independiente de US1/US3/US4/US5 — reutiliza `_create_new_person`, ya existente desde spec 043 (no de esta feature).
- **US3 (Phase 5)**: depende de T001 (`_fetch_all_pages`, US1) para `fetch_tasks` — el resto es independiente.
- **US4 (Phase 6)**: depende de T003 (US1) solo para que el filtro por Cliente de Personal tenga `parent_context.client_id` disponible; el resto (selects Proyecto/Lista, filtros de Proyectos/Listas) es independiente.
- **US5 (Phase 7)**: totalmente independiente de US1-US4 — nuevo endpoint de solo lectura sobre datos ya existentes desde spec 043.
- **Polish (Phase 8)**: depende de que las historias que se vayan a entregar estén completas.

### Parallel Opportunities

- T004 y T005 (US1, frontend) pueden avanzar en paralelo — props distintas del mismo `Table`, sin conflicto real de merge; T006 (test) en paralelo con ambas una vez completado T003.
- T008 (US2) y T014 (US3) en paralelo — archivos de tipos/servicio distintos de la lógica principal.
- T017 y T018 (US4) en paralelo — bloques de código independientes dentro del mismo archivo (mismo criterio que spec 043 T019/T023).
- T024-T028 (US5) en paralelo entre sí — 5 archivos de página distintos, cada uno con un cambio aditivo aislado que sigue el mismo patrón de gate de permiso.
- US2, US4 (salvo T020) y US5 pueden implementarse en paralelo por desarrolladores distintos apenas termine T001/T003 de US1, sin esperar a US3.

---

## Parallel Example: User Story 5

```bash
Task: "Agregar columna/Tag de origen Teamwork a frontend/src/pages/ClientsPage.tsx"
Task: "Agregar columna/Tag de origen Teamwork a frontend/src/pages/ProjectsPage.tsx"
Task: "Agregar columna/Tag de origen Teamwork a frontend/src/pages/ProjectListsPage.tsx"
Task: "Agregar columna/Tag de origen Teamwork a frontend/src/pages/TeamPage.tsx"
Task: "Agregar columna/Tag de origen Teamwork a frontend/src/pages/ClientContactsPage.tsx"
```

## Parallel Example: User Story 1

```bash
Task: "Agregar columna Compañía/Empresa de Origen en frontend/src/pages/TeamworkIntegrationPage.tsx"
Task: "Fijar paginación a 15 filas en el Table de frontend/src/pages/TeamworkIntegrationPage.tsx"
Task: "Test backend de paginación completa y resolución de Compañía en backend/tests/api/test_teamwork_integration.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 2, ambas P1)

1. Completar Phase 3: User Story 1 (sincronización confiable + Compañía + paginación 15)
2. **Detener y validar**: probar US1 de forma independiente (quickstart.md § 1)
3. Completar Phase 4: User Story 2 (migración masiva de Personal)
4. **Detener y validar**: probar US2 de forma independiente (quickstart.md § 2)
5. Demo/entrega si está listo — ambas P1 constituyen el MVP de esta feature

### Incremental Delivery

1. US1 → probar independientemente → demo (base confiable)
2. US2 → probar independientemente → demo (MVP completo, ambas P1)
3. US3 → probar independientemente → demo (Tareas/Subtareas migradas)
4. US4 → probar independientemente → demo (UX de selectores/filtros)
5. US5 → probar independientemente → demo (trazabilidad visible en toda la app, sin toasts espurios)

Cada historia agrega valor sin romper las anteriores.

---

## Notes

- [P] = archivos distintos, sin dependencias pendientes.
- [Story] mapea cada tarea a su historia de usuario para trazabilidad.
- Ningún archivo de `tickets.py`/`clients.py`/`projects.py`/`task_lists.py`/`users.py`/`resources.py`/
  `client_contacts.py`/`ticket_imports.py`/`teamwork_api_client.py`/`teamwork_import_service.py` se modifica
  en ninguna tarea — solo se invocan sus repos/servicios ya existentes. La única excepción documentada son
  las 5 tareas de US5 (T024-T028), que agregan una columna/`Tag` de solo lectura a 5 pantallas principales
  de SYTIX sin tocar su lógica de negocio (plan.md § Complexity Tracking).
- Tests nuevos/modificados: máximo 5-10 registros dummy por test, nunca ejecutar la suite completa.
- Commit sugerido después de cada historia de usuario completa.
