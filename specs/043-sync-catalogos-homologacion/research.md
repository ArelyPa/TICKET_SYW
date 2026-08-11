# Research: Ampliación y Ajustes Finos en la Sincronización de Catálogos de Teamwork

**Feature**: 043-sync-catalogos-homologacion | **Fecha**: 2026-08-10

Todas las decisiones parten de auditar el código real de spec 042 (`backend/api/routes/teamwork_integration.py`,
`backend/infra/repositories/teamwork_integration_repo.py`, `backend/infra/models/teamwork_integration_model.py`,
`frontend/src/pages/TeamworkIntegrationPage.tsx`) antes de proponer cambios — sin `[NEEDS CLARIFICATION]` pendientes.

## Decisión 1 — Trazabilidad de ID externo: ampliar `teamwork_entity_mappings`, no agregar columnas por tabla destino

**Decisión**: El ID externo de Teamwork (`teamwork_id`) y su nombre (`teamwork_name`) ya se guardan de forma
persistente y única (`UniqueConstraint(entity_type, teamwork_id)`) en `teamwork_entity_mappings` desde spec 042.
`upsert_from_sync` ya preserva `sytix_id`/`match_method` de una fila ya resuelta al re-sincronizar (confirmado
leyendo el método — no sobrescribe si `sytix_id is not None`), lo que ya satisface FR-014 sin cambios. Por lo
tanto **no se agrega `teamwork_user_id` ni ninguna columna equivalente a `clients`/`projects`/`resources`/`users`/
`task_lists`** — sería una segunda fuente de verdad redundante y tocaría 5 modelos fuera del alcance permitido.
En su lugar, `match_method` (columna `Text` libre, ya existente) gana un valor nuevo `"created_new"` — sin cambio
de esquema — que la UI usa para distinguir el badge "Migrado" de "Homologado" (`"manual"`) y de los tres métodos
de automapeo (`"email"`/`"external_id"`/`"name"`).

**Alternativas consideradas**: (a) columna `external_id` en cada tabla destino — rechazada, redundante y fuera
del alcance de sesión (tocaría 5 modelos y sus repos en vez de solo el módulo de integración). (b) tabla de
auditoría nueva de "migraciones" — rechazada, `teamwork_entity_mappings` ya cumple ese rol.

## Decisión 2 — Contexto jerárquico (Cliente de un Proyecto; Cliente+Proyecto de una Lista de Tareas): una sola columna aditiva `parent_teamwork_id`

**Decisión**: Se agrega una columna nullable `parent_teamwork_id` (`Text`) a `teamwork_entity_mappings`: para una
fila `entity_type="project"` guarda el `id` de la Empresa de Teamwork dueña del proyecto; para una fila
`entity_type="tasklist"` guarda el `id` del Proyecto de Teamwork dueño de la lista. `entity_type` en `"company"`/
`"person"` deja el campo en `null`. La resolución de "Cliente Asociado" de un Proyecto es una sola consulta
(`EntityMappingRepository.get_by_teamwork_key("company", parent_teamwork_id)` → su `sytix_id`/`sytix_name`). La
resolución de "Cliente"+"Proyecto" de una Lista de Tareas es la misma consulta encadenada una vez más: la lista
resuelve su Proyecto (`get_by_teamwork_key("project", parent_teamwork_id)`), y ese Proyecto resuelve su Empresa
con la misma lógica del punto anterior — sin necesitar guardar el `company_id` de la Empresa directamente en la
fila de la Lista.

**Origen del dato**: la API v3 de Teamwork expone la Empresa dueña de un proyecto (`companyId`/`company.id` según
el payload) y el Proyecto dueño de una lista de tareas (`projectId`/`project.id`) en las mismas respuestas
`projects.json`/`tasklists.json` ya consumidas por `_fetch_entity` (`backend/infra/importers/
teamwork_connection_client.py`) — hoy se descarta ese campo, solo se extraen `id`/`name`. Se amplía `_fetch_entity`
para devolver también `parent_id` cuando `entity_type` sea `project` o `tasklist`, verificado contra la
documentación oficial (apidocs.teamwork.com) al momento de esta sesión — **sin smoke-test contra una cuenta real**
(mismo caso ya documentado en spec 041/042; el nombre exacto del campo en el JSON real se confirma en
implementación, con fallback a `None` si el payload no lo trae, sin romper la sincronización existente).

**Alternativas consideradas**: guardar `company_id`+`company_name` denormalizados en cada fila de Proyecto/Lista
— rechazada, duplica datos que ya viven en la fila de la Empresa/Proyecto correspondiente y se desincroniza si esa
Empresa se re-homologa a otro Cliente.

## Decisión 3 — Correo de Personal: columna aditiva `teamwork_email`

**Decisión**: `_fetch_entity` para `entity_type="person"` ya devuelve `email` (usado hoy solo para automapeo en
memoria, `entity_mapping_service.suggest_match`) pero **no se persiste** en `teamwork_entity_mappings`. Se agrega
columna nullable `teamwork_email` (`Text`) para: (a) mostrarla en la columna "Correo" de la tabla (FR-008), (b)
usarla como valor por defecto y check de duplicado al migrar una Persona como Usuario/Recurso nuevo (FR-009/FR-011),
sin tener que volver a llamar a la API de Teamwork en el momento de migrar. Solo se popula para `entity_type="person"`;
queda `null` para el resto.

## Decisión 4 — Migración única, aditiva, sobre tabla existente

**Decisión**: Migración `055_teamwork_entity_mappings_context.py` agrega **2 columnas nullable** a
`teamwork_entity_mappings` (`parent_teamwork_id`, `teamwork_email`) — sin tabla nueva, sin `NOT NULL`, sin
backfill de datos históricos (las filas de spec 042 ya sincronizadas simplemente quedan con ambos campos en
`null` hasta la próxima sincronización, que los completa vía `upsert_from_sync` ampliado). Coherente con el
patrón ya usado en spec 041 (`external_reference_id` aditivo en `tickets`) y spec 042 (`external_time_id`
aditivo en `work_sessions`).

## Decisión 5 — Acción "Migrar como Nuevo": un endpoint por fila, reutilizando los repos/servicios de creación ya existentes

**Decisión**: Nuevo endpoint `POST /api/teamwork-integration/entity-mappings/<mapping_id>/create-new`
(namespace ya existente `teamwork_integration`, gateado por el permiso ya existente `teamwork_integration:operate`
— sin permiso nuevo, US1/FR-001 no lo pide). El handler vive en `backend/api/routes/teamwork_integration.py`
(Capa 3, ya en alcance permitido) y **no reimplementa validación**: llama exactamente a los mismos repos/servicios
de Capa 1/2 que ya usa la creación manual de cada entidad, confirmados por auditoría del código real:

| `entity_type` | Servicio/repo reutilizado (sin cambios) | Campos que llegan del `teamwork_entity_mappings` | Campos que el usuario debe elegir |
|---|---|---|---|
| `company` | `Client.create(name=...)` + `ClientRepository.create` + `ClientService.validate_unique_name` | `teamwork_name` → `name` | ninguno |
| `project` | `Project.create(client_id, name, start_date)` + `ProjectRepository.create` + `ProjectService.validate_create` | `teamwork_name` → `name`; `client_id` resuelto de `parent_teamwork_id` (Decisión 2) | ninguno (`start_date` = fecha de hoy, Decisión 6) |
| `person` | `UserRepository.create` (+ `RoleRepository.get_by_id`) y, según el rol elegido: `ResourceRepository.create` (roles internos) o `ClientContactRepository.create` (`Usuario/cliente`) | `teamwork_name` → `full_name`/nombre; `teamwork_email` → `email` | `role_id` (obligatorio, FR-009); `client_id` (obligatorio solo si el rol es `Usuario/cliente`, FR-010) |
| `tasklist` | `TaskListRepository.get_or_create_by_name(project_id, name)` (ya existe, mismo método reusado por el importador de tareas de spec 041) + `TaskListService.validate_create` | `teamwork_name` → `name`; `project_id` resuelto de `parent_teamwork_id` encadenado (Decisión 2) | ninguno |

Todos los casos de error de validación (nombre duplicado, cliente inactivo, correo ya en uso, etc.) se propagan
tal cual los devuelve el servicio/repo ya existente — mismos códigos HTTP (400/404/409) que sus endpoints de
creación manual (US1 escenario 4).

**Alternativas consideradas**: reutilizar directamente `POST /api/clients`/`POST /api/projects`/etc. desde el
frontend en dos pasos (crear, luego `PUT /entity-mappings/{id}` para vincular) — rechazada: no hay forma atómica
de marcar `match_method="created_new"` en el mismo request que crea el registro, y duplica en el frontend la
lógica de "qué repo llamar según `entity_type`" que hoy vive centralizada en el backend.

## Decisión 6 — Valor por defecto de `start_date` al migrar un Proyecto

**Decisión**: `Project.create` exige `start_date` y `ProjectService.validate_create` rechaza fechas de un mes ya
pasado — Teamwork no expone necesariamente una fecha de inicio directamente equivalente en el mismo payload ya
consumido por `_fetch_entity`. Se usa la fecha del día de la migración como `start_date` por defecto (editable
después desde la pantalla de Proyectos, sin bloquear el flujo de migración con un campo adicional en el modal).

**Alternativas consideradas**: exponer un campo de fecha en el modal de "Migrar como Nuevo" de Proyecto — se
descarta para mantener acotado el alcance de UI pedido (US1 no lo menciona); queda como ajuste manual posterior,
igual que cualquier otro campo opcional de Proyecto no cubierto por los datos de Teamwork.

## Decisión 7 — Candidatos de homologación manual para Listas de Tareas (gap heredado de spec 042)

**Decisión**: Hoy `_sytix_candidates` devuelve `[]` para `tasklist` (comentario explícito en el código: "sin
listado global propio... homologación manual únicamente" pero el frontend tampoco tiene un `SYTIX_CANDIDATE_LOADER`
para `tasklist`, por lo que "Homologar" tampoco funciona hoy para este tipo). Se resuelve como parte de esta
feature (no es un cambio de alcance nuevo, es completar lo que spec 042 dejó pendiente para este mismo tipo de
entidad que ahora se amplía): los candidatos de Lista de Tareas se cargan con `TaskListRepository.list_by_project`
una vez resuelto el `project_id` de la fila (Decisión 2) — igual que "Migrar Nuevo", "Homologar" para una Lista de
Tareas queda deshabilitado hasta que su Proyecto esté resuelto.

## Decisión 8 — Resolución de nombre SYTIX para `tasklist` en la respuesta de la API

**Decisión**: `_SYTIX_REPO_BY_TYPE`/`_SYTIX_NAME_ATTR` (usados por `_resolve_sytix_name`) no tienen entrada para
`task_list` — se agrega `"task_list": lambda db: TaskListRepository(db)` / `"task_list": "name"`, reutilizando
`TaskListRepository.get_by_id` ya existente. Cambio de una línea en cada diccionario, sin lógica nueva.

## Decisión 9 — Rol asignable al migrar Personal: reutilizar `roleService`/`RoleRepository` ya existentes

**Decisión**: El selector de Rol del modal "Migrar como Nuevo" de Personal reutiliza `roleService.list({ page_size:
100, active: true })` (`frontend/src/services/roleService.ts`, ya usado por `TeamPage.tsx`) — mismo catálogo de
roles que el resto de SYTIX, sin endpoint ni tabla nueva.
