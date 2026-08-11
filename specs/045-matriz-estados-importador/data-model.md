# Data Model — Matriz de Estados, Acciones Masivas, Extracción Enriquecida y Centro de Importación de Tareas

## Migración `056_entity_mapping_status_metadata` (aditiva, sin tabla nueva)

### `EntityMappingModel` (`teamwork_entity_mappings`) — 2 columnas nuevas

| Columna | Tipo | Default | Uso |
|---------|------|---------|-----|
| `is_discarded` | `BOOLEAN` | `false` (server-side, `NOT NULL`) | Marca persistente del estado `Inactivo` (FR-002) — independiente de `sytix_id`/`match_method`. Nunca tocada por `upsert_from_sync` (preserva el estado en resincronizaciones, FR-007). |
| `teamwork_metadata` | `JSONB` | `NULL` | Metadatos ampliados por tipo de entidad (FR-013 a FR-016), reescrito en cada `upsert_from_sync` como `teamwork_name` (research.md Decisión 5). |

Ninguna otra columna existente (`sytix_id`, `sytix_entity_type`, `match_method`, `parent_teamwork_id`,
`teamwork_email`) cambia de tipo o de semántica.

### Forma de `teamwork_metadata` por `entity_type` (convención de aplicación, sin `CHECK` de esquema — JSONB libre)

| `entity_type` | Claves esperadas | Ausencia de campo en origen |
|----------------|-------------------|-------------------------------|
| `company` | `country`, `address`, `domain`, `phone` | Clave omitida del diccionario, nunca `null` explícito |
| `person` | `job_title`, `timezone` | idem |
| `project` | `description`, `status` (`"active"` \| `"archived"`) | idem |
| `tasklist` | `description`, `status` (`"active"` \| `"archived"`) | idem |

## Estado de sincronización (matriz de 4 valores) — derivado, no una columna nueva salvo `is_discarded`

`entity_mapping_service.derive_sync_status(mapping) -> "pending" | "linked" | "created" | "inactive"`
(Capa 1, reemplaza `_migration_status` de la ruta — research.md Decisión 1):

```text
is_discarded == True                          → "inactive"   (Badge: Inactivo)
sytix_id is None                               → "pending"    (Badge: Pendiente)
match_method == "created_new"                  → "created"    (Badge: Migrado)
sytix_id is not None (cualquier otro método)   → "linked"     (Badge: Homologado)
```

El orden importa: `is_discarded` se evalúa primero, de forma que una fila descartada nunca antes homologada
(`sytix_id IS NULL`) cae en `"inactive"` y no en `"pending"`.

## `EntityMapping` (entidad de dominio, `backend/domain/entities/teamwork_integration.py`) — campos nuevos

| Campo | Tipo | Default |
|-------|------|---------|
| `is_discarded` | `bool` | `False` |
| `teamwork_metadata` | `Optional[dict]` | `None` |

## Estructuras transitorias (no persistidas)

### `TeamworkTaskImportFilter` (Capa 3, request de `preview`/`confirm`)

| Campo | Tipo | Obligatorio |
|-------|------|-------------|
| `client_id` | UUID (SYTIX) | Sí (FR-018) |
| `project_ids` | `UUID[]` (SYTIX) | Sí, al menos 1 (FR-018/019) |
| `date_from` | `date \| null` | No — default: primer día del mes en curso |
| `date_to` | `date \| null` | No — default: último día del mes en curso |
| `task_list_teamwork_id` | `str \| null` | No (FR-018) |

No persiste entre requests — se re-evalúa completo tanto en `preview` como en `confirm` (research.md Decisión
7, evita servir un lote desactualizado).

### `TeamworkTaskDiagnosticRow` (Capa 1, `teamwork_task_import_service.py`)

Extiende `TeamworkTaskRow` (spec 044, reutilizado por import) con la reclasificación estricta de esta feature:

| Campo | Tipo | Origen |
|-------|------|--------|
| `teamwork_id` | `str` | `task.id` |
| `name` | `str` | `task.name` |
| `is_subtask` | `bool` | `parent_task_teamwork_id is not None` |
| `status` | `"ready" \| "blocked"` | `classify_task_for_import` (research.md Decisión 7) |
| `block_reason` | `"project_not_mapped" \| "tasklist_not_mapped" \| "assignee_not_mapped" \| None` | idem |
| `resolve_link` | `{entity_type: str, teamwork_id: str} \| None` | apunta a la homologación faltante cuando `status="blocked"` (FR-021) |
| `resolved` | `dict` | `{client_id, project_id, list_id, assignee_resource_id}` ya resueltos por la Capa 3 (igual forma que `TeamworkTaskRow` de spec 044) |

No se persiste — cada fila `ready` se traduce 1:1 a `TicketRepository.upsert_from_import(...)` ya existente
(spec 041, sin modificar) al confirmar.

### `TeamworkTaskImportDiagnostic` (respuesta de `preview`, no persistida)

```text
{
  "summary": {"total": int, "ready": int, "blocked": int},
  "ready": TeamworkTaskDiagnosticRow[],
  "blocked": TeamworkTaskDiagnosticRow[]
}
```

### Selección masiva de estado (frontend, no persistida)

Estado transitorio de UI en `TeamworkIntegrationPage.tsx`, ahora reutilizable en los 4 catálogos (antes
exclusivo de Personal, spec 044): `Set<string>` de `mapping.id` seleccionados vía checkboxes + la acción masiva
elegida (`bulk-create-new` genérico, `bulk-discard`, `bulk-reactivate`). Se envía una sola vez al confirmar y se
descarta; el efecto persistido es, por fila, el mismo que su acción individual equivalente (`create-new`, o el
toggle de `is_discarded`).

## Diagrama — Resolución de filtros del Importador de Tareas → Diagnóstico

```text
Selección del usuario (SYTIX)              teamwork_entity_mappings (reverse lookup, Decisión 7)
┌───────────────────────┐                  ┌─────────────────────────────────────────────┐
│ client_id (SYTIX)      │                  │                                              │
│ project_ids[] (SYTIX)  │─────────────────▶│ entity_type='project', sytix_id IN (...)     │──▶ teamwork_id[]
│ task_list_teamwork_id  │  (opcional,      │ entity_type='tasklist' (ya trae               │
│                        │   ya es teamwork_id)  parent_context.project_id resuelto)        │
└───────────────────────┘                  └─────────────────────────────────────────────┘
              │
              ▼
   fetch_tasks() [spec 044, sin modificar] ──▶ filtrar por project_id ∈ teamwork_id[], tasklist_id (si aplica),
                                                 due_date/created_at ∈ [date_from, date_to]
              │
              ▼
   classify_task_for_import(raw, resolution)  ──▶ ready | blocked (project_not_mapped | tasklist_not_mapped |
                                                    assignee_not_mapped)
              │ (solo status="ready")
              ▼
   TicketRepository.upsert_from_import(...)   [spec 041, sin modificar]  ──▶ Ticket/Tarea con
                                                                              external_reference_id/url
              │
              ▼ (2ª pasada, tras crear el lote — igual patrón que ticket_imports.py / sync/tasks)
   tickets.external_reference_id == parentTaskId  ──▶  tickets.parent_task_id
```

Si `project_id` o `tasklist_id` no resuelven a un `sytix_id`, o el `assignee_id` de Teamwork no resuelve a un
Recurso homologado, la fila queda `blocked` y **no** se llama a `upsert_from_import` — a diferencia de
`/sync/tasks` (spec 044), donde solo Proyecto/Lista bloquean y el asignado no homologado se crea sin asignar
(divergencia deliberada, research.md Decisión 7).
