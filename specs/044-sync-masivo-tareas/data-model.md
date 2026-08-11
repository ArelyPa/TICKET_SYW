# Data Model — Operaciones Masivas, Paginación de Sincronización y Migración de Tareas/Subtareas

Sin migraciones de Alembic nuevas (research.md § Resumen de impacto). Este documento describe cómo se
reutilizan/extienden las estructuras ya existentes y las estructuras transitorias (no persistidas) que
introduce esta feature.

## Entidades persistidas reutilizadas (sin cambio de esquema)

### `EntityMappingModel` (`teamwork_entity_mappings`, migraciones 054/055 — sin cambios de columnas)

| Columna | Uso nuevo en esta feature |
|---------|---------------------------|
| `parent_teamwork_id` | Ahora también se puebla para `entity_type='person'` (Decisión 2) con el `companyId` de Teamwork — antes solo `project`/`tasklist`. |
| `sytix_id` / `sytix_entity_type` / `match_method` | Fuente única de verdad del distintivo de trazabilidad (FR-012/013) — un registro está "migrado/homologado" si `sytix_id IS NOT NULL`. |

Sin tabla ni columna nueva para Tareas/Subtareas — ver "Resolución de Tareas (no persistida)" abajo.

### `TicketModel` (`tickets`, migración 053 — sin cambios de columnas)

| Columna | Uso en esta feature |
|---------|----------------------|
| `external_reference_id` | Identificador de origen de la Tarea/Subtarea de Teamwork (FR-018) — clave de upsert, ya usada por `TicketRepository.upsert_from_import`. |
| `external_reference_url` | Hipervínculo a la tarea en Teamwork (FR-018), construido como `{site_url}/app/tasks/{teamwork_id}` (Decisión 8) — el detalle del Ticket ya lo renderiza desde spec 041. |
| `parent_task_id` | Relación Subtarea → Tarea padre (FR-017), resuelta en una segunda pasada tras crear/actualizar el lote (mismo patrón de `ticket_imports.py`). |

## Estructuras transitorias (no persistidas)

### `TeamworkTaskRow` (Capa 1, `teamwork_task_migration_service.py`)

Representa una fila cruda de `GET /projects/api/v3/tasks.json` ya combinada con su resolución armada por la
Capa 3 (mismo patrón que `ImportRow` de spec 041, sin heredar de ese módulo):

| Campo | Tipo | Origen |
|-------|------|--------|
| `teamwork_id` | `str` | `task.id` de Teamwork |
| `name` | `str` | `task.name` |
| `description` | `str \| None` | `task.description` |
| `project_teamwork_id` | `str \| None` | `task.project.id` / `task.projectId` |
| `tasklist_teamwork_id` | `str \| None` | `task.tasklist.id` / `task.tasklistId` |
| `parent_task_teamwork_id` | `str \| None` | `task.parentTask.id` / `task.parentTaskId` — presente en Subtareas |
| `assignee_teamwork_id` | `str \| None` | primer elemento de `task.assignees.userIds` (o campo equivalente v3) |
| `status` | `"ready" \| "skipped"` | calculado por la clasificación pura, según si Proyecto+Lista están homologados |
| `skip_reason` | `str \| None` | `"project_not_mapped"` \| `"tasklist_not_mapped"` cuando `status="skipped"` |
| `resolved` | `dict` | `{client_id, project_id, list_id, assignee_resource_id}` ya resueltos por la Capa 3 (UUIDs de SYTIX o `None`) |

No se persiste como tabla — cada fila `ready` se traduce 1:1 a una llamada a
`TicketRepository.upsert_from_import(...)` ya existente.

### Selección masiva de Personal (frontend, no persistida)

Estado transitorio de UI: `Set<string>` de `mapping.id` seleccionados vía checkboxes + `{role_id, client_id}`
del formulario de Acciones Masivas. Se envía una sola vez al confirmar (`POST .../bulk-create-new`) y se
descarta; el resultado persistido es, para cada fila migrada con éxito, el mismo efecto que "Migrar como
Nuevo" individual (Usuario/Recurso o Usuario/ClientContact ya definidos en spec 043 data-model.md).

### `TeamworkMigratedRefs` (respuesta de solo lectura, no persistida)

`{"sytix_ids": string[]}` — proyección calculada en el momento desde `teamwork_entity_mappings` filtrando por
`sytix_entity_type` y `sytix_id IS NOT NULL` (condición canónica, research.md Decisión 7 — `match_method` se
escribe siempre junto a `sytix_id` en los tres paths de escritura existentes, así que ambas condiciones son
hoy equivalentes, pero se documenta `sytix_id` como la única fuente de verdad para evitar drift); usada por
las 5 pantallas principales de SYTIX para pintar el badge de trazabilidad (FR-012), cada una gateada
client-side por `hasPermission('teamwork_integration','operate')` (research.md Decisión 7). Sin caché ni tabla
propia.

## Diagrama de resolución — Tarea/Subtarea → Ticket

```text
Teamwork /tasks.json                 teamwork_entity_mappings (ya sincronizado, spec 042/043)
┌─────────────────────┐              ┌───────────────────────────────────────────┐
│ task.projectId       │─────────────▶│ entity_type='project', teamwork_id=?      │──▶ sytix_id (Project.id)
│ task.tasklistId       │─────────────▶│ entity_type='tasklist', teamwork_id=?     │──▶ sytix_id (TaskList.id)
│ task.assignees[0]     │─────────────▶│ entity_type='person', teamwork_id=?       │──▶ sytix_id (Resource.id)
│ task.parentTaskId     │──┐
└─────────────────────┘  │  (2ª pasada, tras crear el lote)
                           ▼
                  tickets.external_reference_id == parentTaskId ──▶ tickets.parent_task_id

Project.id (ya resuelto) ──▶ ProjectRepository.get_by_id ──▶ .client_id  (evita recorrer parent_teamwork_id de nuevo)
```

Si `project` o `tasklist` no resuelven a un `sytix_id`, la fila se marca `skipped` y **no** se llama a
`upsert_from_import` (FR-016 — sin Ticket huérfano). Si solo el `assignee` no resuelve, la Tarea se crea sin
asignar (mismo criterio que spec 041).
