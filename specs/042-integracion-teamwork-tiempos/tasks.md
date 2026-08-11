---

description: "Task list for spec 042 — Integración API Teamwork v3, Homologación de Catálogos e Importador de Tiempos Mensuales"
---

# Tasks: Integración API Teamwork v3, Homologación de Catálogos e Importador de Tiempos Mensuales

**Input**: Design documents from `/specs/042-integracion-teamwork-tiempos/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Incluidos, pero ultra-limitados (Principio VII de la Constitución — máx. 5-10 registros
por test). Un fixture nuevo y reducido del reporte de tiempos (`ejemplo-reporte-tiempos.xlsx`/
`.csv`, ≤10 filas, T022) es la única fuente de datos para los tests de importación de tiempos —
mismo criterio que `ejemplo-teamwork-tasks.xlsx` de spec 041. No correr la suite completa de
`pytest` en ningún momento — solo los archivos tocados por cada tarea.

**Organization**: Tareas agrupadas por Historia de Usuario (spec.md) para permitir implementación
y prueba independiente de cada una.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivo distinto, sin dependencias pendientes)
- **[Story]**: US1 (P1), US2 (P1), US3 (P1), US4 (P2), US5 (P3) — ver spec.md
- Rutas de archivo exactas en cada descripción

---

## Phase 1: Setup

- [X] T001 [P] Confirmar que no se requieren dependencias nuevas (Principio V): `requests` y
      `openpyxl` ya están en `backend/requirements.txt` (usadas por spec 041/034); ninguna
      dependencia nueva de `frontend/package.json`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: ninguna Historia de Usuario puede completarse sin esta fase.

- [X] T002 Migración `backend/infra/migrations/versions/054_teamwork_integration_time_imports.py`:
      crea `teamwork_integration_configs`, `teamwork_entity_mappings`, `time_import_batches`
      (columnas exactas en data-model.md); agrega `external_time_id` (Text, nullable) a
      `work_sessions` con índice único parcial (`WHERE external_time_id IS NOT NULL`); inserta los
      permisos `teamwork_integration:manage` (rol Admin) y `teamwork_integration:operate` (roles
      Admin, Coordinador) — mismo patrón SQL crudo que las migraciones 048/051/052/053
- [X] T003 [P] Crear `backend/infra/models/teamwork_integration_model.py`: modelos SQLAlchemy
      `TeamworkIntegrationConfigModel`, `EntityMappingModel` (con `to_entity`/`from_entity`) y
      `TimeImportBatchModel` (solo infra, sin entidad de dominio — data-model.md)
- [X] T004 [P] Agregar columna `external_time_id = Column(Text, nullable=True)` a
      `WorkSessionModel` en `backend/infra/models/work_session_model.py` (aditivo, incluir en
      `to_entity`/`from_entity`)
- [X] T005 [P] Crear `backend/domain/entities/teamwork_integration.py` (Capa 1, sin imports de
      Flask/SQLAlchemy): dataclasses `TeamworkIntegrationConfig` y `EntityMapping` con los campos
      de data-model.md
- [X] T006 [P] Agregar `external_time_id: Optional[str] = None` a la entidad `WorkSession` en
      `backend/domain/entities/work_session.py` (aditivo)
- [X] T007 Implementar `backend/infra/repositories/teamwork_integration_repo.py`:
      `TeamworkIntegrationConfigRepository` (`get()`/`upsert(...)` — patrón singleton, siempre
      actualiza la única fila existente o crea la primera; `record_test_result(status, message)`),
      `EntityMappingRepository` (`list(entity_type=None, unresolved_only=False)`,
      `upsert_from_sync(entity_type, teamwork_id, teamwork_name, suggested_match=None)`,
      `set_manual_mapping(mapping_id, sytix_id)`, `get_by_teamwork_key(entity_type, teamwork_id)`),
      `TimeImportBatchRepository` (`create(...)`) — depende de T003, T005
- [X] T008 [P] Agregar `WorkSessionRepository.get_by_external_time_id(external_time_id)` y
      `upsert_from_import(external_time_id, resource_id, ticket_id, work_date, duration_minutes,
      note, started_at, ended_at, created_by)` en
      `backend/infra/repositories/work_session_repo.py` — depende de T004, T006

**Checkpoint**: esquema y repos listos — las Historias de Usuario pueden avanzar.

---

## Phase 3: User Story 1 - Configurar y Probar Conexión con Teamwork v3 (Priority: P1)

**Goal**: un Administrador guarda URL/token/entorno y confirma con "Probar Conexión" que las
credenciales son válidas, sin exponer el token en la interfaz.

**Independent Test**: guardar credenciales inválidas → badge de error de autenticación; corregir
y volver a probar → badge de éxito; recargar la pantalla confirma que el token no se muestra en
texto plano (`has_token: true`, sin el valor).

### Tests for User Story 1

- [X] T009 [P] [US1] Test unitario con `requests` mockeado en
      `backend/tests/infra/test_teamwork_connection_client.py`: `test_connection(site_url, token)`
      devuelve `success`/`auth_error` (401)/`connection_error` (timeout o DNS) según la respuesta
      simulada — sin dependencia nueva de testing (`unittest.mock`)
- [X] T010 [P] [US1] Test de API en `backend/tests/api/test_teamwork_integration.py`: `GET/PUT
      /api/teamwork-integration/config` (el `GET` nunca incluye el token, solo `has_token`); `POST
      /api/teamwork-integration/test-connection` con `requests` mockeado actualiza
      `last_test_status`; `403` sin permiso `teamwork_integration:manage`

### Implementation for User Story 1

- [X] T011 [US1] Implementar `backend/infra/importers/teamwork_connection_client.py` (Capa 2):
      `test_connection(site_url: str, api_token: str) -> dict` — `GET
      /projects/api/v3/projects.json?pageSize=1` con Basic Auth (token como usuario, mismo
      mecanismo que `teamwork_api_client.py` de spec 041, pero credenciales por parámetro, nunca
      por variable de entorno — research.md Decisión 1)
- [X] T012 [US1] Implementar `backend/api/routes/teamwork_integration.py` (namespace nuevo
      `teamwork_integration`): `GET /api/teamwork-integration/config` y `PUT .../config`
      (`require_permission("teamwork_integration", "manage")`, cifra el token con `_encrypt` de
      `backend/infra/models/client_model.py` — mismo mecanismo que `client_access`); `POST
      .../test-connection` (mismo permiso) usando T011, actualiza y devuelve `last_test_status` —
      depende de T007, T011
- [X] T013 [US1] Registrar `ns_teamwork_integration` en `backend/app.py` (mismo patrón que
      `ns_ticket_imports`) — depende de T012
- [X] T014 [P] [US1] Crear `frontend/src/types/teamworkIntegration.ts`:
      `TeamworkIntegrationConfig`, `TestConnectionResult`
- [X] T015 [P] [US1] Crear `frontend/src/services/teamworkIntegrationService.ts`: `getConfig()`,
      `saveConfig(config)`, `testConnection()`
- [X] T016 [US1] Crear `frontend/src/pages/TeamworkIntegrationPage.tsx`: formulario (URL del
      sitio, Token, Entorno), botón "Guardar" y botón "Probar Conexión" con badge de estado
      (`success`/`auth_error`/`connection_error`) — depende de T014, T015
- [X] T017 [US1] Agregar ruta `/integraciones/teamwork` en `frontend/src/App.tsx`
      (`ProtectedRoute` con `{module: 'teamwork_integration', action: 'manage'}`) — depende de T016
- [X] T018 [P] [US1] Agregar ítem de navegación "Integración Teamwork" (grupo Maestros) en
      `frontend/src/config/navigation.tsx`

**Checkpoint**: US1 funcional y probable de forma independiente.

---

## Phase 4: User Story 2 - Importar y Validar Reporte Mensual de Tiempos (Priority: P1) 🎯 MVP

**Goal**: un Coordinador/Admin sube el archivo mensual de tiempos y ve el resumen de válidas vs.
con conflicto, sin persistir nada todavía.

**Independent Test**: subir `ejemplo-reporte-tiempos.xlsx` (T022) y verificar que el resumen
distingue correctamente filas válidas de filas en conflicto (`who_not_found`/`project_not_found`/
`task_not_found`/`description_missing`), sin crear ningún `WorkSession`.

### Tests for User Story 2

- [X] T019 [P] [US2] Test unitario en `backend/tests/domain/test_time_import_service.py`: usando
      las filas de `ejemplo-reporte-tiempos.csv` (T022), verificar clasificación
      `valid`/`conflict`/`error`, prioridad `Decimal hours` > `Hours`+`Minutes` (research.md
      Decisión 5), y `description_missing` bloqueando aunque el resto resuelva
- [X] T020 [P] [US2] Test unitario en `backend/tests/infra/test_teamwork_time_file_parser.py`:
      parseo de `.xlsx`/`.csv` reconociendo `ID`, `Date/time`/`End date/time`,
      `Hours`/`Minutes`/`Decimal hours`, `Who` (o `First name`+`Last name`/`User ID`), `Company`,
      `Project`, `Task`/`Task ID`, `Description`; columnas mínimas faltantes lanza
      `TeamworkTimeFileParseError`
- [X] T021 [P] [US2] Test de API en `backend/tests/api/test_time_imports.py`: `POST
      /api/time-imports/preview` (multipart con `ejemplo-reporte-tiempos.xlsx`) devuelve el
      resumen `{total, valid, conflict, error}` esperado para el fixture; nada se persiste

### Implementation for User Story 2

- [X] T022 [US2] Crear fixture reducido `ejemplo-reporte-tiempos.xlsx`/`.csv` (≤10 filas) en
      `specs/042-integracion-teamwork-tiempos/` — al menos 1 fila válida, 1 con `Who` sin match, 1
      con `Project` sin match, 1 con `Description` vacía (Principio VII)
- [X] T023 [US2] Implementar `backend/infra/importers/teamwork_time_file_parser.py` (Capa 2): lee
      `.xlsx` (`openpyxl`) o `.csv` (módulo `csv`) según extensión, homologa cada fila a un `dict`
      crudo (`external_time_id`, `started_at`, `ended_at`, `duration_minutes` ya resuelto por la
      regla de research.md Decisión 5, `who_name`, `company_name`, `project_name`,
      `task_reference`, `description`) — sin lógica de resolución contra la base de datos
- [X] T024 [US2] Implementar `backend/domain/services/time_import_service.py` (Capa 1, sin
      imports de Flask/SQLAlchemy/`openpyxl`/`requests`): recibe cada fila cruda + un `dict` de
      resolución ya armado por la Capa 3 (mismo patrón que `teamwork_import_service.classify_row`
      de spec 041) y devuelve `TimeImportRow` con `status`/`issues` según data-model.md
- [X] T025 [US2] Implementar `POST /api/time-imports/preview` en `backend/api/routes/time_imports.py`
      (namespace nuevo `time_imports`, `require_permission("teamwork_integration", "operate")`):
      resuelve `Who`→`ResourceRepository.get_by_email`/`get_by_full_name`
      (`backend/infra/repositories/resource_repo.py`, ya existen), `Company`→`ClientRepository.get_by_name`,
      `Project`→`ProjectRepository.get_by_client_and_name`, `Task`→
      `TicketRepository.get_by_external_reference_id` (spec 041) — cada resolución primero
      consulta `EntityMappingRepository` (T007) por si ya está homologado — usando T023 + T024,
      sin persistir nada — depende de T007, T023, T024
- [X] T026 [US2] Registrar `ns_time_imports` en `backend/app.py` — depende de T025
- [X] T027 [P] [US2] Crear `frontend/src/types/timeImport.ts`: `TimeImportRow`, `TimeImportSummary`
- [X] T028 [P] [US2] Crear `frontend/src/services/timeImportService.ts`: `previewFile(file)`
- [X] T029 [US2] Crear `frontend/src/pages/TimeImportsPage.tsx`: `Upload.Dragger` de Ant Design +
      `Table` de resumen con columna de estado (válida/conflicto) — depende de T027, T028
- [X] T030 [US2] Agregar ruta `/importacion-tiempos` en `frontend/src/App.tsx` (`ProtectedRoute`
      con `{module: 'teamwork_integration', action: 'operate'}`) — depende de T029
- [X] T031 [P] [US2] Agregar ítem de navegación "Importación de Tiempos" (grupo Maestros) en
      `frontend/src/config/navigation.tsx`

**Checkpoint**: US2 funcional de forma independiente (vista previa completa; confirmar llega en
US3).

---

## Phase 5: User Story 3 - Resolver Conflictos de Importación y Confirmar Carga (Priority: P1)

**Goal**: sobre el mismo resumen de US2, resolver cada fila en conflicto (homologar/crear/omitir)
y confirmar la carga real de `WorkSession`.

**Independent Test**: retomar el resumen de una carga con conflictos, resolver una fila por
homologación manual, otra creando el Recurso faltante, omitir una tercera, confirmar, y verificar
que solo se crean `WorkSession` para las filas válidas + homologadas + creadas.

### Tests for User Story 3

- [X] T032 [P] [US3] Extender `backend/tests/api/test_time_imports.py`: `POST
      /api/time-imports/confirm` — `action="resolve"` homologa contra un Recurso/Proyecto/Ticket
      existente, `action="create"` con `create_entity_type="resource"` crea un Recurso sin
      `user_id`, `action="omit"` no crea nada, `action="create"` con `create_entity_type="project"`
      devuelve `400 invalid_action`; reimportar el mismo `external_time_id` actualiza en vez de
      duplicar (FR-013)

### Implementation for User Story 3

- [X] T033 [US3] Agregar `build_resolution_action(row, action_payload)` en
      `time_import_service.py` (Capa 1) que valida `action="create"` solo admite
      `create_entity_type` en `{"resource", "client"}` (data-model.md) — depende de T024
- [X] T034 [US3] Implementar `POST /api/time-imports/confirm` en `time_imports.py`: por cada fila,
      aplica la acción (`resolve`: usa los IDs ya provistos; `create`: `ResourceRepository.create`
      con `user_id=None` para `resource`, `ClientRepository.create` para `client`; `omit`: se
      salta) y hace upsert de `WorkSession` vía `WorkSessionRepository.upsert_from_import` (T008);
      registra un `TimeImportBatch` (T007) con los conteos finales — depende de T025, T007, T008,
      T033
- [X] T035 [US3] En `frontend/src/pages/TimeImportsPage.tsx`: UI de resolución por fila en
      conflicto (selector "Homologar" / botón "Crear" / botón "Omitir") y botón "Confirmar carga"
      con el resumen final — depende de T029, T034
- [X] T036 [P] [US3] Agregar `confirm(rows)` a `frontend/src/services/timeImportService.ts` —
      depende de T028

**Checkpoint**: US1+US2+US3 completos = importador de tiempos funcional de punta a punta (MVP del
objetivo de negocio principal).

---

## Phase 6: User Story 4 - Sincronizar Catálogos desde Teamwork (Priority: P2)

**Goal**: traer Empresas/Proyectos/Personal/Listas de Tareas desde la API v3 hacia la tabla de
homologación.

**Independent Test**: con la conexión de US1 en `success`, sincronizar cada uno de los 4 catálogos
y verificar que `entity-mappings` refleja lo recibido; con la conexión sin probar, la sincronización
se bloquea con el mismo error que "Probar Conexión".

### Tests for User Story 4

- [X] T037 [P] [US4] Extender `test_teamwork_connection_client.py`: `fetch_companies`/
      `fetch_projects`/`fetch_people`/`fetch_tasklists` homologan la respuesta mockeada (estilo
      JSON:API, mismo criterio ya verificado en spec 041 para `tasks.json`) a `{id, name}`
- [X] T038 [P] [US4] Extender `test_teamwork_integration.py`: `POST
      /api/teamwork-integration/sync/company` upserta en `entity-mappings` (mock); `409
      connection_not_tested` si `last_test_status` no es `success`

### Implementation for User Story 4

- [X] T039 [US4] Agregar `fetch_companies`/`fetch_projects`/`fetch_people`/`fetch_tasklists` a
      `teamwork_connection_client.py` (mismo patrón que T011, un `GET` por endpoint v3) — depende
      de T011
- [X] T040 [US4] Implementar `POST /api/teamwork-integration/sync/<entity_type>` en
      `teamwork_integration.py`: valida `entity_type`, bloquea si no hay `last_test_status:
      "success"` vigente, upserta cada resultado vía `EntityMappingRepository.upsert_from_sync`
      (T007) — depende de T012, T039
- [X] T041 [US4] En `TeamworkIntegrationPage.tsx`: 4 botones "Sincronizar Catálogos" (uno por
      `entity_type`) con conteo de sincronizados — depende de T016, T040
- [X] T042 [P] [US4] Agregar `syncCatalog(entityType)` a `teamworkIntegrationService.ts` —
      depende de T015

**Checkpoint**: US4 funcional de forma independiente (requiere la conexión de US1 ya probada).

---

## Phase 7: User Story 5 - Homologación Manual de Entidades (Priority: P3)

**Goal**: tabla comparativa Teamwork↔SYTIX con automapeo sugerido y corrección manual.

**Independent Test**: con entidades sincronizadas (US4) donde algunas tienen coincidencia exacta
por correo/nombre y otras no, verificar que el automapeo sugiere las primeras y deja las segundas
para selección manual; guardar una homologación manual la deja disponible para la próxima
sincronización/importación.

### Tests for User Story 5

- [X] T043 [P] [US5] Test unitario en `backend/tests/domain/test_entity_mapping_service.py`
      (≤10 registros): `suggest_match(teamwork_entity, sytix_candidates)` sugiere por correo
      exacto, luego por ID externo, luego por nombre exacto, y `None` si no hay coincidencia
- [X] T044 [P] [US5] Extender `test_teamwork_integration.py`: `GET
      /api/teamwork-integration/entity-mappings?entity_type=person` devuelve las filas con su
      sugerencia; `PUT .../entity-mappings/{id}` guarda `match_method: "manual"` y lo refleja en
      el siguiente `GET`

### Implementation for User Story 5

- [X] T045 [US5] Implementar `backend/domain/services/entity_mapping_service.py` (Capa 1 pura):
      `suggest_match(teamwork_entity: dict, sytix_candidates: list[dict]) -> dict | None` — por
      correo exacto, luego `external_id`, luego nombre exacto (FR-006)
- [X] T046 [US5] Usar T045 dentro de `EntityMappingRepository.upsert_from_sync` (T007) para
      calcular `match_method`/`sytix_id` automáticamente al sincronizar — depende de T040, T045
- [X] T047 [US5] Implementar `GET /api/teamwork-integration/entity-mappings` y `PUT
      .../entity-mappings/<mapping_id>` en `teamwork_integration.py` — depende de T007, T012
- [X] T048 [US5] En `TeamworkIntegrationPage.tsx`: tab "Homologación de Entidades" con tabla
      comparativa (Teamwork vs. SYTIX) y selector manual por fila — depende de T041, T047
- [X] T049 [P] [US5] Agregar `listEntityMappings(entityType?)`/`setEntityMapping(id, sytixId)` a
      `teamworkIntegrationService.ts` — depende de T015

**Checkpoint**: las 5 Historias de Usuario funcionan de forma independiente.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T050 [P] Ejecutar contra Docker real y validar `quickstart.md` completo (las 5 Historias de
      Usuario end-to-end, login Admin para US1/US4/US5 y Coordinador para US2/US3)
- [X] T051 [P] Confirmar `GET /swagger.json` incluye los namespaces `teamwork_integration` y
      `time_imports` con los modelos/responses de `contracts/api.md` (Principio I)
- [X] T052 [P] Ejecutar únicamente los tests nuevos/tocados de esta feature
      (`test_teamwork_connection_client.py`, `test_teamwork_time_file_parser.py`,
      `test_time_import_service.py`, `test_entity_mapping_service.py`,
      `test_teamwork_integration.py`, `test_time_imports.py`) contra Postgres real — Principio VII,
      nunca la suite completa de `pytest`
- [X] T053 Verificar con `git diff --stat` que ningún archivo de spec 041
      (`ticket_imports.py`/`teamwork_api_client.py`/`teamwork_file_parser.py`/
      `teamwork_import_service.py`) fue modificado (quickstart.md § Verificación de alcance)
- [X] T054 [P] `tsc -b` sin errores

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias.
- **Foundational (Phase 2)**: depende de Setup — BLOQUEA las 5 Historias de Usuario.
- **US1 (Phase 3)**: depende solo de Foundational.
- **US2 (Phase 4)**: depende solo de Foundational — **no depende de US1** (trabaja sobre el
  archivo, sin necesitar la conexión API configurada). Es el MVP del objetivo de negocio.
- **US3 (Phase 5)**: depende de Foundational **y** de la infraestructura de US2 (T025, T029 — el
  endpoint de preview y la pantalla que extiende con la resolución/confirmación). No es
  independiente de US2 en implementación (mismo endpoint/pantalla), aunque juntas (US2+US3) sí son
  independientes de US1/US4/US5.
- **US4 (Phase 6)**: depende de Foundational **y** de la conexión de US1 (T011, T012 — usa el
  cliente y el permiso `manage` para bloquear si no está probada). Independiente de US2/US3.
- **US5 (Phase 7)**: depende de Foundational **y** de la infraestructura de US4 (T040 — la
  sincronización que produce las entidades a homologar). Independiente de US2/US3.
- **Polish (Phase 8)**: depende de todas las historias que se decidan entregar.

### Parallel Opportunities

- Foundational: T003, T004, T005, T006 en paralelo (archivos distintos); T007/T008 después.
- US1: T009/T010 en paralelo entre sí y con T011 (tests, no bloquean si se sigue TDD); T014/T015
  en paralelo; T018 en paralelo con T017.
- US2: T019/T020/T021 en paralelo entre sí; T027/T028 en paralelo.
- US1 y US2 pueden implementarse en paralelo entre sí una vez completada Foundational (no
  comparten archivos backend; sí comparten `navigation.tsx`/`App.tsx` — coordinar esos 2 archivos).
- US4 debe esperar a que T011/T012 (US1) existan; US5 debe esperar a que T040 (US4) exista.

---

## Parallel Example: User Story 2 (MVP)

```bash
# Tests (si se sigue TDD, antes de la implementación):
Task: "Test unitario de time_import_service en backend/tests/domain/test_time_import_service.py"
Task: "Test de teamwork_time_file_parser en backend/tests/infra/test_teamwork_time_file_parser.py"
Task: "Test de API de time-imports en backend/tests/api/test_time_imports.py"

# Frontend, una vez completado T025:
Task: "Tipos en frontend/src/types/timeImport.ts"
Task: "Servicio en frontend/src/services/timeImportService.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 + 2 + 3)

1. Completar Phase 1 (Setup) + Phase 2 (Foundational).
2. Completar Phase 3 (US1) — configurar y probar conexión (prerrequisito de negocio, aunque US2 no
   dependa técnicamente de ella).
3. Completar Phase 4 (US2) + Phase 5 (US3) — importar, validar, resolver conflictos y confirmar.
4. **Detener y validar**: correr la Independent Test de US2+US3 contra Docker real con
   `ejemplo-reporte-tiempos.xlsx`.
5. US1+US2+US3 ya resuelven el problema central (cerrar reportes mensuales de tiempo sin carga
   manual fila por fila).

### Incremental Delivery

1. Setup + Foundational → base lista.
2. US1 → validar independientemente (conexión configurable y probada).
3. US2 → validar independientemente (vista previa de un archivo real).
4. US3 → validar independientemente (resolución + confirmación) → MVP completo.
5. US4 → validar independientemente (sincronización de catálogos, requiere US1).
6. US5 → validar independientemente (homologación manual, requiere US4).

---

## Notes

- Ningún test de esta feature debe insertar más de 5-10 registros (Principio VII) — usar siempre
  `ejemplo-reporte-tiempos.xlsx`/`.csv` (T022, ≤10 filas) como fuente para los tests de importación.
- Prohibido correr la suite completa de `pytest` en cualquier punto de esta feature.
- Prohibido modificar `ticket_imports.py`/`teamwork_api_client.py`/`teamwork_file_parser.py`/
  `teamwork_import_service.py` de spec 041 (T053 lo verifica al final).
- `[P]` = archivos distintos, sin dependencias pendientes entre sí.
- `[US1]`/`[US2]`/`[US3]`/`[US4]`/`[US5]` trazan cada tarea a su Historia de Usuario en spec.md.
