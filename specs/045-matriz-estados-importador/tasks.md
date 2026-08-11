---

description: "Task list template for feature implementation"
---

# Tasks: Matriz de Estados de Sincronización, Acciones Masivas Ampliadas, Extracción Enriquecida de Datos y Centro Independiente de Importación de Tareas (Teamwork API v3)

**Input**: Design documents from `/specs/045-matriz-estados-importador/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md (todos presentes)

**Tests**: Incluidos, acotados a ≤10 registros dummy por test (Principio VII) — solo se corren los archivos de test tocados/nuevos, nunca la suite completa.

**Organization**: Tareas agrupadas por historia de usuario (spec.md) para permitir implementación y prueba independiente de cada una.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: Historia de usuario a la que pertenece (US1-US4)
- Rutas de archivo exactas en cada descripción

## Path Conventions

Web app existente: `backend/` (Flask, Clean Architecture 3 capas) + `frontend/src/` (React). Sin directorios
nuevos fuera de lo ya previsto en plan.md — todos los cambios caen en el namespace `teamwork_integration` ya
existente (specs 042-044) más el namespace hermano nuevo `teamwork_task_imports` (US4).

---

## Phase 1: Setup

**Purpose**: Preparación de proyecto/esquema previa a las historias de usuario.

**N/A** — sin inicialización de proyecto ni dependencia nueva que instalar (research.md § Resumen de impacto).
Se pasa directo a Foundational.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Persistencia y derivación de estado compartidas por US1/US2/US3. **US4 no depende de esta fase**
(el Importador de Tareas no usa `is_discarded`/`teamwork_metadata` ni `derive_sync_status`) — puede
implementarse en paralelo total, ver § Dependencies.

**⚠️ CRITICAL**: US1, US2 y US3 no pueden empezar hasta completar esta fase.

- [X] T001 Crear migración `backend/infra/migrations/versions/056_entity_mapping_status_metadata.py`: agrega `is_discarded BOOLEAN NOT NULL DEFAULT false` y `teamwork_metadata JSONB NULL` a `teamwork_entity_mappings` (data-model.md, aditiva, sin tabla nueva)
- [X] T002 [P] Agregar columnas `is_discarded` (`Boolean`) y `teamwork_metadata` (`JSONB`, importar de `sqlalchemy.dialects.postgresql`) a `EntityMappingModel` en `backend/infra/models/teamwork_integration_model.py`, propagándolas en `to_entity()`/`from_entity()` (depende de T001)
- [X] T003 [P] Agregar campos `is_discarded: bool = False` y `teamwork_metadata: Optional[dict] = None` al dataclass `EntityMapping` en `backend/domain/entities/teamwork_integration.py`
- [X] T004 Agregar función pura `derive_sync_status(mapping) -> Literal["pending", "linked", "created", "inactive"]` a `backend/domain/services/entity_mapping_service.py` — `is_discarded=True` se evalúa primero (research.md Decisión 1) (depende de T003)
- [X] T005 Reemplazar `_migration_status(mapping)` en `backend/api/routes/teamwork_integration.py` por una llamada a `entity_mapping_service.derive_sync_status(mapping)`, y exponer `teamwork_metadata` en la serialización de `GET /entity-mappings` (depende de T002, T004)

**Checkpoint**: `is_discarded`/`teamwork_metadata` persistidos; `GET /entity-mappings` devuelve `migration_status` de 4 valores y `teamwork_metadata` crudo.

---

## Phase 3: User Story 1 - Matriz de 4 estados con filtros por pestaña en los Grids (Priority: P1) 🎯 MVP

**Goal**: Las tablas de los 4 catálogos muestran un badge de 4 estados (Pendiente/Homologado/Migrado/Inactivo)
y ofrecen pestañas para filtrar por cada uno.

**Independent Test**: Sobre un catálogo con filas en al menos 3 estados distintos, aplicar cada pestaña y
confirmar que solo se listan las filas que le corresponden; confirmar los 4 colores de badge distintos.

### Implementation for User Story 1

- [X] T006 [US1] Actualizar el tipo `TeamworkMigrationStatus` a 4 valores y agregar la entrada `inactive` a `MIGRATION_STATUS_BADGE` (nuevo color distintivo, ej. `{color: 'red', text: 'Inactivo'}`) en `frontend/src/types/teamworkIntegration.ts` / `frontend/src/pages/TeamworkIntegrationPage.tsx`
- [X] T007 [US1] Agregar un control de pestañas de estado (`Segmented`: Todos/Pendientes/Homologados/Migrados/Inactivos) sobre el `Table` de "Homologación de Entidades" en `frontend/src/pages/TeamworkIntegrationPage.tsx`, filtrando client-side el array `mappings` por `migration_status`, combinable (AND) con los filtros de Cliente/Proyecto/correo ya existentes (depende de T006)
- [X] T008 [P] [US1] Test backend (≤10 registros dummy): `derive_sync_status` cubre los 4 estados — `is_discarded=True` da `"inactive"` incluso sin `sytix_id`, y tiene prioridad sobre `sytix_id`/`match_method` si ambos estuvieran presentes — en `backend/tests/domain/test_entity_mapping_service.py` (archivo ya existente desde spec 042, extendido en vez de creado nuevo) (depende de T004)

**Checkpoint**: US1 funcional y probable de forma independiente — 4 estados visibles y filtrables en los 4 catálogos.

---

## Phase 4: User Story 2 - Acciones masivas de "Migrar como Nuevos" e "Inactivar/Descartar" (Priority: P1)

**Goal**: Seleccionar varias filas en cualquiera de los 4 catálogos y migrarlas como nuevas o inactivarlas en
una sola operación, con reversión posible desde Inactivo.

**Independent Test**: En Proyectos, migrar 3 filas seleccionadas de una vez y verificar que quedan en
"Migrado"; inactivar otras 2 y verificar que quedan en "Inactivo" sin registro nuevo en SYTIX; reactivar una y
confirmar que vuelve a "Pendiente".

### Implementation for User Story 2

- [X] T009 [US2] Generalizar `POST /entity-mappings/bulk-create-new` en `backend/api/routes/teamwork_integration.py` para aceptar `mapping_ids` de cualquier `entity_type`, despachando por el `_CREATE_NEW_HANDLERS` ya existente; exigir `role_id`/`client_id` solo si hay filas `person` en el lote; omitir filas ya vinculadas (`already_linked`) o descartadas (`discarded`) sin abortar el lote (research.md Decisión 2) (depende de T005)
- [X] T010 [US2] Agregar `set_discarded(mapping_id, discarded: bool, updated_by)` a `EntityMappingRepository` en `backend/infra/repositories/teamwork_integration_repo.py` (depende de T002)
- [X] T011 [US2] Agregar endpoints `POST /entity-mappings/bulk-discard` y `POST /entity-mappings/bulk-reactivate` en `backend/api/routes/teamwork_integration.py`, reutilizando T010 — `bulk-discard` omite filas con `sytix_id` no nulo (`already_linked`); `bulk-reactivate` omite filas con `is_discarded=False` (`not_discarded`) — contratos en `contracts/api.md` (depende de T010)
- [X] T012 [P] [US2] Agregar `bulkDiscard(mappingIds)`/`bulkReactivate(mappingIds)` a `frontend/src/services/teamworkIntegrationService.ts` y los tipos de request/response correspondientes a `frontend/src/types/teamworkIntegration.ts` (depende de T011)
- [X] T013 [US2] Extender `rowSelection` + la barra de "Acciones Masivas" a las tablas de Empresas, Proyectos y Listas de Tareas (hoy exclusivas de Personal, spec 044) con el botón "Migrar Masivamente como Nuevos" (sin campos Rol/Cliente fuera de Personal) y el nuevo botón "Inactivar / Descartar Seleccionados", en `frontend/src/pages/TeamworkIntegrationPage.tsx` (depende de T009, T012)
- [X] T014 [US2] Agregar acción por fila "Reactivar", visible solo para filas en estado Inactivo, invocando `bulkReactivate([mapping.id])`, en `frontend/src/pages/TeamworkIntegrationPage.tsx` (depende de T012)
- [X] T015 [US2] Test backend (≤10 registros dummy): `bulk-create-new` generalizado crea Empresa/Proyecto/Lista además de Persona y omite filas ya vinculadas/descartadas; `bulk-discard` marca `is_discarded=true` y omite filas ya vinculadas; `bulk-reactivate` revierte y omite filas no descartadas — en `backend/tests/api/test_teamwork_integration.py` (depende de T009, T011) — 1 test preexistente (`test_bulk_create_new_missing_role_id_returns_400`) ajustado a `test_bulk_create_new_invalid_role_id_format_returns_400` (comportamiento cambió intencionalmente al generalizar, `role_id` ya no obligatorio a nivel de request)

**Checkpoint**: US1+US2 funcionales — matriz de estados con acciones masivas de migración e inactivación en los 4 catálogos.

---

## Phase 5: User Story 3 - Extracción ampliada de metadatos de la API v3 (Priority: P2)

**Goal**: Las filas de Empresas, Personal, Proyectos y Listas de Tareas muestran metadatos adicionales de
Teamwork (País/Dirección/Dominio/Teléfono; Cargo/Zona horaria; descripción/estado).

**Independent Test**: Sincronizar Empresas contra un fixture con País/Dirección/Dominio/Teléfono cargados en
al menos una fila y verificar que los 4 campos se ven en la tabla, con "No informado" donde falte un dato.

### Implementation for User Story 3

- [X] T016 [US3] Extender `upsert_from_sync(...)` en `backend/infra/repositories/teamwork_integration_repo.py` con parámetro opcional `metadata: dict | None = None`, reescrito en cada sync igual que `teamwork_name` (research.md Decisión 5) (depende de T002)
- [X] T017 [US3] Extender `_fetch_entity()` en `backend/infra/importers/teamwork_connection_client.py`: rama `company` agrega `country`/`address`/`domain`/`phone`; rama `person` agrega `job_title`/`timezone`; ramas `project`/`tasklist` agregan `description`/`status`, como un diccionario `"metadata"` por fila que omite las claves no informadas en el origen
- [X] T018 [US3] Pasar `metadata=item.get("metadata")` desde `POST /sync/<entity_type>` en `backend/api/routes/teamwork_integration.py` hacia `upsert_from_sync` (depende de T016, T017)
- [X] T019 [US3] Mostrar los campos de `teamwork_metadata` por `entity_type` (columnas adicionales, con "No informado" para claves ausentes; descripción/dirección con `Text ellipsis+tooltip` para no romper el layout) en `extraColumns` de `frontend/src/pages/TeamworkIntegrationPage.tsx` (depende de T006 — mismo archivo de tipos ya extendido en US1)
- [X] T020 [US3] Test backend (5-10 filas, mock de `requests`): sincronizar 1 Empresa/1 Persona/2 Proyectos con metadata completa y filas sin metadata; verificar que `GET /entity-mappings` devuelve los campos esperados en `teamwork_metadata` o `None` sin error, y que una resincronización refresca el metadata igual que `teamwork_name` — en `backend/tests/api/test_teamwork_integration.py` (depende de T018)

**Checkpoint**: US1+US2+US3 funcionales — estado, acciones masivas y metadatos enriquecidos operativos en los 4 catálogos.

---

## Phase 6: User Story 4 - Centro Independiente de Importación de Tareas y Subtareas por filtros (Priority: P1)

**Goal**: Pantalla propia "Importador de Tareas y Subtareas" con filtros de Cliente/Proyecto(s)/fecha/Lista de
Tareas opcional, prevalidación diagnóstica (listas vs. bloqueadas con motivo y enlace) y ejecución por lotes.

**Independent Test**: Con un lote de prueba de 5-10 Tareas/Subtareas repartidas entre 2 Clientes/2 meses
(algunas con cadena de homologación completa, otras no), filtrar por un Cliente y un mes, prevalidar, y
verificar que el conteo de listas/bloqueadas es correcto antes de confirmar la importación.

### Implementation for User Story 4

- [X] T021 [P] [US4] Extender `fetch_tasks()` en `backend/infra/importers/teamwork_connection_client.py` para incluir `created_at`/`due_date` por fila (research.md Decisión 7) — sin modificar su uso existente en `POST /sync/tasks` (spec 044)
- [X] T022 [P] [US4] Agregar `get_teamwork_ids_for_sytix(entity_type: str, sytix_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]` a `EntityMappingRepository` en `backend/infra/repositories/teamwork_integration_repo.py` (reverse lookup SYTIX→Teamwork, sin cambio de esquema)
- [X] T023 [US4] Crear módulo Capa 1 puro `backend/domain/services/teamwork_task_import_service.py`: `filter_tasks_by_date(raw_tasks, date_from, date_to)` (filtra por `due_date`, si no por `created_at`) y `classify_task_for_import(raw, resolution)`, que **importa sin modificar** `classify_task`/`TeamworkTaskRow` de `teamwork_task_migration_service.py` y agrega el motivo `assignee_not_mapped` cuando el asignado de Teamwork no resuelve a un Recurso (research.md Decisión 7 — divergencia deliberada respecto a `/sync/tasks`, que no bloquea por asignado) (depende de T021)
- [X] T024 [US4] Crear namespace nuevo `backend/api/routes/teamwork_task_imports.py` (`path="/api/teamwork-integration/task-imports"`, permiso `teamwork_integration:operate`) con `POST /preview` (sin escritura; resuelve `client_id`/`project_ids` a `teamwork_id`s vía T022, filtra `fetch_tasks()` por proyecto/lista/fecha, clasifica con T023, devuelve `{summary, ready[], blocked[]}` con `resolve_link` por fila bloqueada) y `POST /confirm` (repite la misma resolución+clasificación en el momento y ejecuta `TicketRepository.upsert_from_import(...)` — sin modificar ese método, spec 041 — solo sobre las filas `ready`, con segunda pasada de Subtarea→Tarea padre igual que `/sync/tasks`) — contratos en `contracts/api.md` (depende de T022, T023)
- [X] T025 [US4] Registrar el namespace nuevo en `backend/app.py` (`from backend.api.routes.teamwork_task_imports import ns as ns_teamwork_task_imports` + `api.add_namespace(ns_teamwork_task_imports)`, mismo patrón que el resto de namespaces) (depende de T024)
- [X] T026 [P] [US4] Crear `frontend/src/types/teamworkTaskImport.ts` (filtro, fila de diagnóstico, resultado de confirm) y `frontend/src/services/teamworkTaskImportService.ts` (`preview(filter)`, `confirm(filter)`) (depende de T024)
- [X] T027 [US4] Crear página `frontend/src/pages/TeamworkTaskImporterPage.tsx`: formulario Cliente (`clientService`) → Proyecto(s) en cascada (`projectService.list({client_id})`, obligatorios) → rango de fechas opcional (default mes en curso) → Lista de Tareas opcional (opciones = `GET /entity-mappings?entity_type=tasklist` filtradas por `parent_context.project_id` de los proyectos elegidos) → botón "Prevalidar" (`preview`) → tabla de diagnóstico (listas/bloqueadas con motivo y enlace) → botón "Importar Lote" (`confirm`) con resumen final — el rango de fechas usa 2 `<input type="date">` nativos + `date-fns` en vez de `DatePicker.RangePicker`/`dayjs` (research.md Decisión 6, corregida: `dayjs` no resoluble como import directo bajo pnpm estricto pese a ser dependencia transitiva de `antd`) (depende de T026)
- [X] T028 [US4] Al hacer clic en el enlace de una fila bloqueada, navegar a `/integraciones/teamwork` pasando `state: {entityType, teamworkId}` (React Router `navigate`); en `frontend/src/pages/TeamworkIntegrationPage.tsx`, leer ese `state` al montar (`useLocation`) para preseleccionar `mappingFilter` y aplicar una búsqueda por `teamwork_id` sobre las filas ya cargadas, con indicador visible y botón para limpiar el filtro (research.md Decisión 7) (depende de T027)
- [X] T029 [US4] Agregar la entrada "Importador de Tareas y Subtareas" a `frontend/src/config/navigation.tsx` (`module: 'teamwork_integration', action: 'operate'`) y la ruta `integraciones/teamwork/importador-tareas` en `frontend/src/App.tsx` (mismo patrón `ProtectedRoute` que `TeamworkIntegrationPage`) (depende de T027)
- [X] T030 [US4] Test backend (5-10 tareas dummy incluyendo 1-2 Subtareas y los 3 motivos de bloqueo): `preview` clasifica correctamente `ready`/`blocked` con `block_reason`/`resolve_link`; `confirm` crea/actualiza solo las `ready`, preserva jerarquía Tarea→Subtarea, y una fila con asignado sin homologar queda bloqueada (a diferencia de `/sync/tasks`); re-ejecutar `confirm` sobre el mismo filtro actualiza en vez de duplicar — en `backend/tests/api/test_teamwork_task_imports.py` (nuevo) (depende de T024, T025)

**Checkpoint**: US1-US4 funcionales — matriz de estados, acciones masivas, metadatos enriquecidos e Importador de Tareas por filtros, todos operativos.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T031 [P] Ejecutar `tsc -b` y corregir errores de tipos en los archivos frontend tocados/nuevos (`TeamworkIntegrationPage.tsx`, `TeamworkTaskImporterPage.tsx`, `teamworkIntegrationService.ts`, `teamworkTaskImportService.ts`, `teamworkIntegration.ts`, `teamworkTaskImport.ts`, `navigation.tsx`, `App.tsx`) — 3 corridas (`--force` incluido), sin errores en ninguna
- [X] T032 Ejecutar la validación de `quickstart.md` (US1-US4) contra Docker real — sin correr la suite completa de `pytest` (Principio VII). Validado en navegador real logueado como Admin contra datos ya sincronizados (~72 páginas de Personal, Empresas Aris/ATINA/Arcor reales): pestañas de estado (`Todos/Pendientes/Homologados/Migrados/Inactivos`) confirmadas presentes y funcionales sobre Personal; barra de Acciones Masivas confirmada ("1 seleccionados" + Rol + "Migrar seleccionados" + "Inactivar / Descartar Seleccionados") al marcar un checkbox; columnas "Cargo"/"Zona horaria" (US3) confirmadas renderizando "No informado" sobre filas reales sin ese dato; página nueva `/integraciones/teamwork/importador-tareas` confirmada cargando sin errores de consola, con los 5 filtros (Cliente/Proyecto(s)/Fecha Inicio/Fecha Fin/Lista de Tareas) y default de rango de fechas correcto (mes en curso, `2026-08-01`–`2026-08-31`); cascada Cliente→Proyecto confirmada en vivo contra la BD real (Cliente "Aris" → 4 Proyectos reales: Evolutivo/Preventa/SOPORTE ARIS 2024/Soporte); botón "Prevalidar" confirmado disparando `POST .../task-imports/preview` contra la configuración real de Teamwork guardada (conexión ya prevista como exitosa) y devolviendo con gracia `502 teamwork_api_error` (mismo caso ya documentado en specs 041-044 — sin cuenta real de Teamwork accesible desde este entorno), mostrado como toast de error sin excepción no controlada ni pantalla rota. 57/57 tests automatizados en verde (`test_entity_mapping_service.py` 11, `test_teamwork_integration.py` 42, `test_teamwork_task_imports.py` 4), acotados a los archivos tocados de esta sesión — sin correr la suite completa de `pytest` en ningún momento.
- [X] T033 [P] Actualizar el bloque "Active feature" de `CLAUDE.md` con el resumen de spec 045 una vez validada (mismo patrón que specs anteriores)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: N/A, sin tareas.
- **Foundational (Phase 2)**: bloquea US1, US2 y US3 (columnas `is_discarded`/`teamwork_metadata` y
  `derive_sync_status`). **No bloquea US4** — el Importador de Tareas no usa esas columnas ni esa función.
- **US1 (Phase 3)**: depende de Foundational (T004/T005) — sin dependencia de otras historias.
- **US2 (Phase 4)**: depende de Foundational (T002/T005); independiente de US1/US3/US4 (reutiliza
  `_CREATE_NEW_HANDLERS`, ya existente desde spec 043).
- **US3 (Phase 5)**: depende de Foundational (T002) para la columna `teamwork_metadata`; independiente de
  US1/US2/US4.
- **US4 (Phase 6)**: totalmente independiente de Foundational/US1/US2/US3 — puede implementarse en paralelo
  desde el inicio por otro desarrollador.
- **Polish (Phase 7)**: depende de que las historias que se vayan a entregar estén completas.

### Parallel Opportunities

- T002 y T003 (Foundational) en paralelo — modelo SQLAlchemy vs. dataclass de dominio, archivos distintos.
- T012 (US2, frontend types/service) puede avanzar en paralelo con T009-T011 (US2, backend) una vez que ambos
  conozcan el contrato de `contracts/api.md`.
- T021 y T022 (US4) en paralelo — archivos distintos (`teamwork_connection_client.py` vs.
  `teamwork_integration_repo.py`), sin dependencia entre sí.
- T026 (US4, frontend types/service) en paralelo con T023 (US4, backend domain service) — ambos solo dependen
  del contrato ya fijado en `contracts/api.md`, no uno del otro.
- **US4 completa puede avanzar en paralelo con Foundational+US1+US2+US3** por ser independiente (ver arriba) —
  la oportunidad de paralelismo más grande de esta feature.

---

## Parallel Example: User Story 4

```bash
Task: "Extender fetch_tasks() con created_at/due_date en backend/infra/importers/teamwork_connection_client.py"
Task: "Agregar get_teamwork_ids_for_sytix a backend/infra/repositories/teamwork_integration_repo.py"
Task: "Crear frontend/src/types/teamworkTaskImport.ts y frontend/src/services/teamworkTaskImportService.ts"
```

## Parallel Example: Foundational

```bash
Task: "Agregar is_discarded/teamwork_metadata a EntityMappingModel en backend/infra/models/teamwork_integration_model.py"
Task: "Agregar is_discarded/teamwork_metadata al dataclass EntityMapping en backend/domain/entities/teamwork_integration.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 2 + User Story 4, las 3 P1)

1. Completar Phase 2: Foundational (bloquea US1/US2/US3, no bloquea US4)
2. Completar Phase 3: User Story 1 (matriz de 4 estados) — **detener y validar** (quickstart.md § 1)
3. Completar Phase 4: User Story 2 (acciones masivas ampliadas) — **detener y validar** (quickstart.md § 2)
4. Completar Phase 6: User Story 4 (Importador de Tareas) en paralelo a los pasos 1-3 — **detener y validar**
   (quickstart.md § 4)
5. Demo/entrega si está listo — las 3 P1 constituyen el MVP de esta feature; US3 (P2) queda como incremento
   posterior

### Incremental Delivery

1. Foundational → base lista para US1/US2/US3
2. US1 → probar independientemente → demo (estados visibles)
3. US2 → probar independientemente → demo (MVP de operación masiva completo)
4. US4 → probar independientemente → demo (importación segmentada con prevalidación) — puede llegar antes que
   US1/US2 si se paraleliza
5. US3 → probar independientemente → demo (contexto enriquecido para decidir)

Cada historia agrega valor sin romper las anteriores.

---

## Notes

- [P] = archivos distintos, sin dependencias pendientes.
- [Story] mapea cada tarea a su historia de usuario para trazabilidad.
- Ningún archivo de `tickets.py`/`clients.py`/`projects.py`/`task_lists.py`/`users.py`/`resources.py`/
  `client_contacts.py`/`ticket_imports.py`/`teamwork_api_client.py`/`teamwork_import_service.py`/
  `teamwork_task_migration_service.py` se modifica en ninguna tarea — solo se invocan/importan sin cambios sus
  repos/servicios/funciones ya existentes (plan.md § Constraints). Sin desviación que documentar en Complexity
  Tracking (a diferencia de spec 044).
- Tests nuevos/modificados: máximo 5-10 registros dummy por test, nunca ejecutar la suite completa de `pytest`.
- Commit sugerido después de cada historia de usuario completa.
