---

description: "Task list template for feature implementation"
---

# Tasks: Ampliación y Ajustes Finos en la Sincronización de Catálogos de Teamwork (Mapeo, Homologación y Creación Dinámica)

**Input**: Design documents from `/specs/043-sync-catalogos-homologacion/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md (todos presentes)

**Tests**: Incluidos, acotados a ≤10 registros dummy por test (directriz explícita de esta sesión / Principio VII) — solo se corren los archivos de test tocados, nunca la suite completa.

**Organization**: Tareas agrupadas por historia de usuario (spec.md) para permitir implementación y prueba independiente de cada una.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: Historia de usuario a la que pertenece (US1-US4)
- Rutas de archivo exactas en cada descripción

## Path Conventions

Web app existente: `backend/` (Flask, Clean Architecture 3 capas) + `frontend/src/` (React). Sin
directorios nuevos — todos los cambios caen en los archivos ya existentes del módulo
`teamwork_integration` de spec 042 (ver plan.md § Project Structure).

---

## Phase 1: Setup

**Purpose**: Preparar el esqueleto de la migración nueva antes de tocar modelos/repos.

- [X] T001 Crear revisión de Alembic vacía `055_teamwork_entity_mappings_context.py` encadenada tras `054` (`down_revision = "054_teamwork_integration_time_imports"`) en `backend/infra/migrations/versions/055_teamwork_entity_mappings_context.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Captura y persistencia del contexto jerárquico (`parent_teamwork_id`) y del correo
(`teamwork_email`) que las 4 historias de usuario necesitan.

**⚠️ CRITICAL**: Ninguna historia de usuario puede implementarse hasta completar esta fase.

- [X] T002 Agregar columnas `parent_teamwork_id` (Text, nullable) y `teamwork_email` (Text, nullable) a `teamwork_entity_mappings` en `backend/infra/migrations/versions/055_teamwork_entity_mappings_context.py` (depende de T001)
- [X] T003 [P] Agregar campos `parent_teamwork_id: str | None` y `teamwork_email: str | None` a la entidad de dominio `EntityMapping` en `backend/domain/entities/teamwork_integration.py`
- [X] T004 Agregar columnas, `to_entity()` y `from_entity()` con `parent_teamwork_id`/`teamwork_email` en `EntityMappingModel` de `backend/infra/models/teamwork_integration_model.py` (depende de T002, T003)
- [X] T005 [P] Extender `_fetch_entity` en `backend/infra/importers/teamwork_connection_client.py` para devolver `parent_id` cuando `entity_type` sea `project` (Empresa dueña) o `tasklist` (Proyecto dueño), con `None` si el payload no lo trae (research.md Decisión 2)
- [X] T006 Extender `EntityMappingRepository.upsert_from_sync` para aceptar/persistir `parent_teamwork_id`/`teamwork_email`, y agregar `set_created_new_mapping(mapping_id, sytix_id, sytix_entity_type, updated_by)` (`match_method="created_new"`) en `backend/infra/repositories/teamwork_integration_repo.py` (depende de T004)
- [X] T007 Agregar entradas `"task_list"` a `_SYTIX_REPO_BY_TYPE`/`_SYTIX_NAME_ATTR` en `backend/api/routes/teamwork_integration.py` para que las filas de Lista de Tareas resuelvan `sytix_name` (research.md Decisión 8) (depende de T004)
- [X] T008 Actualizar el handler `POST /sync/<entity_type>` para pasar `parent_id`/`email` de cada ítem sincronizado a `upsert_from_sync` en `backend/api/routes/teamwork_integration.py` (depende de T005, T006)

**Checkpoint**: La sincronización captura y persiste todo el contexto necesario — listo para implementar historias de usuario.

---

## Phase 3: User Story 1 - Elegir Homologar o Migrar Nuevo por fila (Priority: P1) 🎯 MVP

**Goal**: Cada fila sin resolver ofrece "Homologar" (ya existente) y "Migrar como Nuevo", que crea
el registro en SYTIX y vincula la fila; una fila ya vinculada no puede volver a migrarse.

**Independent Test**: Sincronizar Empresas, tomar una fila sin coincidencia, "Migrar como Nuevo",
confirmar, verificar que aparece un Cliente nuevo en Maestros > Clientes vinculado a esa fila, y
que reintentar la acción sobre esa misma fila queda deshabilitado.

### Implementation for User Story 1

- [X] T009 [US1] Agregar endpoint `GET /entity-mappings/<mapping_id>/create-new-candidates` — rama `company`: `{"defaults": {"name": mapping.teamwork_name}}`; 409 `already_linked` si ya tiene `sytix_id` — en `backend/api/routes/teamwork_integration.py`
- [X] T010 [US1] Agregar endpoint `POST /entity-mappings/<mapping_id>/create-new` con dispatch por `entity_type`; implementar rama `company`: `Client.create(name=mapping.teamwork_name)` + `ClientRepository.create` + `ClientService.validate_unique_name` (409 `duplicate_name`), luego `EntityMappingRepository.set_created_new_mapping` — en `backend/api/routes/teamwork_integration.py` (depende de T006, T009)
- [X] T011 [P] [US1] Agregar `getCreateNewCandidates(mappingId)` y `createNew(mappingId, payload)` a `frontend/src/services/teamworkIntegrationService.ts`
- [X] T012 [P] [US1] Agregar tipos `MigrationStatus`, `ParentContext`, `CreateNewCandidates`, `CreateNewPayload` a `frontend/src/types/teamworkIntegration.ts`
- [X] T013 [US1] Agregar botón "Migrar como Nuevo" + modal de confirmación por fila en `frontend/src/pages/TeamworkIntegrationPage.tsx`, deshabilitado cuando la fila ya tiene `sytix_id` (FR-004) (depende de T011, T012)
- [X] T014 [US1] Test backend (≤10 registros dummy): `create-new` de `company` — éxito, `already_linked` (409), `duplicate_name` (409) en `backend/tests/api/test_teamwork_integration.py`

**Checkpoint**: US1 funcional y probable de forma independiente para Empresas.

---

## Phase 4: User Story 2 - Contexto de Cliente en Proyectos y Listas de Tareas (Priority: P1)

**Goal**: Las filas de Proyecto muestran "Cliente Asociado" y las de Lista de Tareas muestran
"Cliente"/"Proyecto"; "Migrar como Nuevo"/"Homologar" quedan bloqueadas hasta que el padre
jerárquico esté resuelto; se completan las ramas `project`/`tasklist` de "Migrar como Nuevo".

**Independent Test**: Sincronizar 2 proyectos homónimos de empresas distintas (una homologada, otra
no) y verificar que la columna distingue correctamente a cada uno, y que "Migrar como Nuevo" está
deshabilitado para el proyecto de la empresa sin homologar.

### Implementation for User Story 2

- [X] T015 [US2] Agregar resolución de `parent_context` (`unmapped`/`pending`/`resolved` + `label`, research.md Decisión 2) y enriquecer `GET /entity-mappings` con ese campo para `entity_type` `project`/`tasklist` en `backend/api/routes/teamwork_integration.py` (depende de T007)
- [X] T016 [US2] Completar rama `project` de `create-new-candidates`/`create-new`: resolver `client_id` desde `parent_teamwork_id` (409 `parent_not_resolved` si no), `Project.create(client_id, name=mapping.teamwork_name, start_date=today)` + `ProjectRepository.create` + `ProjectService.validate_create` en `backend/api/routes/teamwork_integration.py` (depende de T010, T015)
- [X] T017 [US2] Completar rama `tasklist` de `create-new-candidates`/`create-new`: resolver `project_id` desde `parent_teamwork_id` (409 `parent_not_resolved` si no), `TaskListRepository.get_or_create_by_name(project_id, mapping.teamwork_name)` + `TaskListService.validate_create` en `backend/api/routes/teamwork_integration.py` (depende de T016)
- [X] T018 [US2] Cargar candidatos de "Homologar" para Listas de Tareas vía `GET /projects/{project_id}/task-lists` una vez resuelto `project_id` (research.md Decisión 7) en `SYTIX_CANDIDATE_LOADER` de `frontend/src/pages/TeamworkIntegrationPage.tsx` (depende de T015)
- [X] T019 [P] [US2] Agregar columna "Cliente Asociado" (Proyectos) y columnas "Cliente"/"Proyecto" (Listas de Tareas) a la tabla, deshabilitando "Migrar como Nuevo"/"Homologar" cuando `parent_context.status !== "resolved"` en `frontend/src/pages/TeamworkIntegrationPage.tsx` (depende de T015, T012)
- [X] T020 [US2] Test backend (≤10 registros dummy): `create-new` de `project`/`tasklist` — éxito con padre resuelto, `parent_not_resolved` (409) sin padre, `parent_context` correcto en `GET /entity-mappings`, en `backend/tests/api/test_teamwork_integration.py` (depende de T016, T017)

**Checkpoint**: US1+US2 funcionales — Proyectos/Listas de Tareas muestran contexto y bloquean correctamente.

---

## Phase 5: User Story 3 - Correo, Rol y creación de cuenta al migrar Personal (Priority: P2)

**Goal**: La tabla de Personal muestra el correo; migrar una Persona exige elegir un Rol (y un
Cliente si el rol es "Usuario/cliente") antes de crear la cuenta; un correo ya existente se rechaza.

**Independent Test**: Sincronizar Personal, elegir "Migrar como Nuevo" en una fila sin coincidencia,
elegir el rol "Resolutor", confirmar, y verificar que se crea la cuenta con ese correo/rol; repetir
con un correo ya usado y verificar el rechazo.

### Implementation for User Story 3

- [X] T021 [US3] Completar rama `person` de `create-new-candidates`: `defaults.email` (`teamwork_email`), `roles` (`RoleRepository.list(active=True)`), `clients` (`ClientRepository.list_paginated`) en `backend/api/routes/teamwork_integration.py` (depende de T009)
- [X] T022 [US3] Completar rama `person` de `create-new`: exigir `role_id` (400 si falta); si el rol es `Usuario/cliente` exigir `client_id` (400 si falta) y usar `ClientContactRepository.create` + `ClientContactService.validate_create`; en cualquier otro rol usar `UserRepository.create` + `ResourceRepository.create` (mismo patrón de dos pasos de `TeamPage.tsx`); 409 `email_already_used` si `teamwork_email` ya pertenece a un usuario — en `backend/api/routes/teamwork_integration.py` (depende de T010, T021)
- [X] T023 [P] [US3] Agregar columna "Correo" a la vista de Personal en `frontend/src/pages/TeamworkIntegrationPage.tsx` (`teamwork_email` ya disponible desde Foundational) (depende de T004)
- [X] T024 [US3] Agregar selector de Rol (+ selector de Cliente condicional) al modal "Migrar como Nuevo" de Personal, reutilizando `roleService.list({ active: true })`, en `frontend/src/pages/TeamworkIntegrationPage.tsx` (depende de T013, T021)
- [X] T025 [US3] Test backend (≤10 registros dummy): `create-new` de `person` — rol interno crea Usuario+Recurso, rol `Usuario/cliente` exige y usa `client_id`, `role_id` faltante (400), correo duplicado (409), en `backend/tests/api/test_teamwork_integration.py` (depende de T022)

**Checkpoint**: US1+US2+US3 funcionales — Personal se migra con rol y correo visibles.

---

## Phase 6: User Story 4 - Trazabilidad visible de IDs externos y estado de migración (Priority: P2)

**Goal**: Cada fila muestra un badge distinto para "Pendiente"/"Homologado"/"Migrado", persistente
tras recargar o re-sincronizar.

**Independent Test**: Con filas en los 3 estados, verificar badges distintos, que persisten tras
recargar la página y tras re-sincronizar el mismo catálogo (sin regresar a "Pendiente").

### Implementation for User Story 4

- [X] T026 [US4] Derivar `migration_status` (`pending`/`linked`/`created`) de `sytix_id`/`match_method` en el serializador de `GET /entity-mappings` en `backend/api/routes/teamwork_integration.py` (depende de T006, T010)
- [X] T027 [P] [US4] Renderizar badge de `migration_status` (color/etiqueta distintos por estado, "Migrado" separado de "Homologado") en `frontend/src/pages/TeamworkIntegrationPage.tsx`, reemplazando el badge actual basado solo en `match_method` (depende de T026)
- [X] T028 [US4] Test backend (≤10 registros dummy): sincronizar dos veces una fila ya `created_new`/`manual` y confirmar que `sytix_id`/`match_method`/`migration_status` no cambian (regresión FR-014), en `backend/tests/api/test_teamwork_integration.py` (depende de T026)

**Checkpoint**: Las 4 historias de usuario funcionan de forma independiente.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T029 [P] Ejecutar `tsc -b` y corregir errores de tipos en `TeamworkIntegrationPage.tsx`/`teamworkIntegrationService.ts`/`types/teamworkIntegration.ts`
- [X] T030 Ejecutar la validación de `quickstart.md` (US1-US4) contra Docker real — sin correr la suite completa de `pytest` (Principio VII)
- [X] T031 [P] Actualizar el bloque "Active feature" de `CLAUDE.md` con el resumen de spec 043 una vez validada (mismo patrón que specs anteriores)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias — inicia de inmediato.
- **Foundational (Phase 2)**: depende de Setup — bloquea las 4 historias de usuario.
- **US1 (Phase 3)**: depende de Foundational. Sin dependencia de otras historias.
- **US2 (Phase 4)**: depende de Foundational y de la infraestructura de `create-new` creada en US1 (T010, T009) — reutiliza el mismo endpoint, agrega las ramas `project`/`tasklist`.
- **US3 (Phase 5)**: depende de Foundational y de la misma infraestructura de US1 (T010, T009) — agrega la rama `person`. Independiente de US2.
- **US4 (Phase 6)**: depende de Foundational y de T006/T010 (necesita que existan filas `created_new` para tener algo que mostrar) — independiente de US2/US3 en implementación, aunque su prueba manual es más rica con ambas ya presentes.
- **Polish (Phase 7)**: depende de que las historias que se vayan a entregar estén completas.

### Notas de dependencia entre historias

US2 y US3 comparten el mismo endpoint `create-new`/`create-new-candidates` creado por US1 (T009/T010)
pero agregan ramas de `entity_type` distintas (`project`/`tasklist` vs. `person`) en archivos/bloques
de código independientes dentro de la misma función de dispatch — pueden implementarse en paralelo
por desarrolladores distintos una vez completado US1, con el único punto de coordinación siendo no
pisarse al editar el mismo archivo `teamwork_integration.py` (mismo criterio que el resto del
namespace).

### Parallel Opportunities

- T003 y T005 (Foundational) en paralelo — archivos distintos.
- T011 y T012 (US1) en paralelo — archivos distintos.
- T019 (US2) y T023 (US3) en paralelo una vez completado Foundational — tocan zonas distintas de la misma tabla, pero como ambas son adiciones de columna independientes pueden desarrollarse en ramas separadas y mergearse.
- T027 (US4) puede avanzar en paralelo con T024 (US3)/T019 (US2) una vez que T026 esté listo.

---

## Parallel Example: Foundational

```bash
Task: "Agregar campos parent_teamwork_id/teamwork_email a EntityMapping en backend/domain/entities/teamwork_integration.py"
Task: "Extender _fetch_entity para capturar parent_id en backend/infra/importers/teamwork_connection_client.py"
```

## Parallel Example: User Story 1

```bash
Task: "Agregar getCreateNewCandidates/createNew a frontend/src/services/teamworkIntegrationService.ts"
Task: "Agregar tipos MigrationStatus/ParentContext/CreateNewPayload a frontend/src/types/teamworkIntegration.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: Setup
2. Completar Phase 2: Foundational (crítico — bloquea las 4 historias)
3. Completar Phase 3: User Story 1 (acción "Migrar como Nuevo" funcional para Empresas)
4. **Detener y validar**: probar US1 de forma independiente (quickstart.md § US1)
5. Demo/entrega si está listo

### Incremental Delivery

1. Setup + Foundational → base lista
2. US1 → probar independientemente → demo (MVP)
3. US2 → probar independientemente → demo (Proyectos/Listas de Tareas con contexto)
4. US3 → probar independientemente → demo (Personal con rol/correo)
5. US4 → probar independientemente → demo (badges de trazabilidad)

Cada historia agrega valor sin romper las anteriores — todas comparten el mismo endpoint `create-new`
de US1, extendido con ramas nuevas por tipo de entidad.

---

## Notes

- [P] = archivos distintos, sin dependencias pendientes.
- [Story] mapea cada tarea a su historia de usuario para trazabilidad.
- Ningún archivo de `clients.py`/`projects.py`/`users.py`/`resources.py`/`client_contacts.py`/
  `task_lists.py`/`ticket_imports.py`/`time_imports.py` se modifica en ninguna tarea — solo se
  invocan sus repos/servicios ya existentes desde `teamwork_integration.py` (Principio VII).
- Tests nuevos/modificados: máximo 5-10 registros dummy por test, nunca ejecutar la suite completa.
- Commit sugerido después de cada tarea o grupo lógico (Foundational; cada historia completa).
