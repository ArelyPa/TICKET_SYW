# API Contracts — Matriz de Estados, Acciones Masivas Ampliadas, Extracción Enriquecida y Centro de Importación de Tareas

Todos los endpoints, nuevos y extendidos, viven bajo el permiso ya existente `teamwork_integration:operate`
(Admin/Coordinador) — sin permiso nuevo (research.md). Los endpoints de estado/bulk viven en el namespace ya
existente `teamwork_integration` (`backend/api/routes/teamwork_integration.py`,
`path="/api/teamwork-integration"`); el Importador de Tareas vive en un namespace hermano nuevo,
`teamwork_task_imports` (`backend/api/routes/teamwork_task_imports.py`,
`path="/api/teamwork-integration/task-imports"`).

## `GET /api/teamwork-integration/entity-mappings` (contrato existente, extendido)

Sin cambio de query params (`entity_type`, `unresolved_only`). Cada fila de la respuesta agrega 2 campos:

```json
{
  "id": "<uuid>",
  "entity_type": "company",
  "teamwork_id": "123",
  "teamwork_name": "Arcor",
  "sytix_id": "<uuid> | null",
  "sytix_name": "Arcor SYTIX | null",
  "match_method": "email | external_id | name | manual | created_new | null",
  "migration_status": "pending | linked | created | inactive",
  "teamwork_metadata": {"country": "AR", "address": "...", "domain": "arcor.com", "phone": "..."} 
}
```

`migration_status` pasa de 3 a 4 valores posibles (research.md Decisión 1) — el frontend ya consume este campo,
sin romper compatibilidad de forma (mismo nombre de campo, un valor nuevo posible). `teamwork_metadata` es
`null` si la fila fue sincronizada antes de esta feature y aún no se resincronizó.

---

## `POST /api/teamwork-integration/entity-mappings/bulk-create-new` (contrato existente, generalizado)

**Request** (antes exclusivo de `person`, ahora acepta cualquier `entity_type` dentro de `mapping_ids`):
```json
{
  "mapping_ids": ["<uuid>", "..."],
  "role_id": "<uuid> | null",
  "client_id": "<uuid> | null"
}
```
`role_id` requerido solo si algún `mapping_id` de la selección corresponde a `entity_type="person"`; `client_id`
requerido solo si, además, el Rol elegido es "Usuario/cliente" (mismo criterio que hoy).

**Response 200**:
```json
{
  "created": [{"mapping_id": "<uuid>", "sytix_id": "<uuid>", "sytix_name": "..."}],
  "skipped": [
    {"mapping_id": "<uuid>", "reason": "already_linked"},
    {"mapping_id": "<uuid>", "reason": "discarded"},
    {"mapping_id": "<uuid>", "reason": "parent_not_resolved"},
    {"mapping_id": "<uuid>", "reason": "email_in_use"}
  ]
}
```

**Errores**: `400 validation_error` (`mapping_ids` vacío, o `role_id` faltante habiendo `person` en la
selección), `401`/`403 Sin permiso teamwork_integration:operate`, `500`.

**Nota de atomicidad**: cada fila se procesa y confirma independientemente (sin transacción envolvente sobre
todo el lote), igual criterio que la versión de spec 044.

---

## `POST /api/teamwork-integration/entity-mappings/bulk-discard`

Nuevo — Acciona "Inactivar / Descartar Seleccionados" (FR-010).

**Request**:
```json
{"mapping_ids": ["<uuid>", "..."]}
```

**Response 200**:
```json
{
  "updated": [{"mapping_id": "<uuid>"}],
  "skipped": [{"mapping_id": "<uuid>", "reason": "already_linked"}]
}
```
Una fila con `sytix_id` no nulo (Homologada o Migrada) se omite con `reason="already_linked"` — solo se puede
descartar una fila `Pendiente` (FR-001, definición de Inactivo).

**Errores**: `400 validation_error` si `mapping_ids` vacío; `401`/`403`; `500`.

---

## `POST /api/teamwork-integration/entity-mappings/bulk-reactivate`

Nuevo — revierte el estado Inactivo a Pendiente (FR-006).

**Request**:
```json
{"mapping_ids": ["<uuid>", "..."]}
```

**Response 200**:
```json
{
  "updated": [{"mapping_id": "<uuid>"}],
  "skipped": [{"mapping_id": "<uuid>", "reason": "not_discarded"}]
}
```

**Errores**: igual que `bulk-discard`.

---

## `POST /api/teamwork-integration/task-imports/preview`

Nuevo — namespace independiente `teamwork_task_imports`. Prevalidación diagnóstica del Importador de Tareas y
Subtareas (FR-020/021), sin escribir en la base de datos.

**Request**:
```json
{
  "client_id": "<uuid>",
  "project_ids": ["<uuid>", "..."],
  "date_from": "2026-08-01 | null",
  "date_to": "2026-08-31 | null",
  "task_list_teamwork_id": "456 | null"
}
```
`client_id` y `project_ids` (mínimo 1) son obligatorios; sin `date_from`/`date_to` se usa el mes en curso
(FR-018).

**Response 200**:
```json
{
  "summary": {"total": 8, "ready": 6, "blocked": 2},
  "ready": [
    {"teamwork_id": "9001", "name": "Ajuste de reporte", "is_subtask": false}
  ],
  "blocked": [
    {
      "teamwork_id": "9003",
      "name": "Subtarea sin lista",
      "is_subtask": true,
      "block_reason": "tasklist_not_mapped",
      "block_reason_label": "Lista de Tareas sin homologar en SYTIX",
      "resolve_link": {"entity_type": "tasklist", "teamwork_id": "778"}
    },
    {
      "teamwork_id": "9004",
      "name": "Revisión de acceso",
      "is_subtask": false,
      "block_reason": "assignee_not_mapped",
      "block_reason_label": "Usuario asignado sin homologar en SYTIX",
      "resolve_link": {"entity_type": "person", "teamwork_id": "551"}
    }
  ]
}
```

**Errores**:
- `400 validation_error` — `client_id`/`project_ids` faltante o vacío.
- `409 connection_not_tested` — igual que `/sync/*`.
- `502 teamwork_api_error` — la API v3 de Teamwork no respondió o devolvió error.
- `401` / `403 Sin permiso teamwork_integration:operate`.

---

## `POST /api/teamwork-integration/task-imports/confirm`

Nuevo — ejecuta por lotes solo las filas que resultarían `ready` al re-evaluar el mismo filtro en el momento de
confirmar (research.md Decisión 7 — evita servir un lote desactualizado respecto al `preview`).

**Request**: mismo cuerpo que `preview` (FR-022, re-clasifica en vez de recibir de vuelta las filas del
preview).
```json
{
  "client_id": "<uuid>",
  "project_ids": ["<uuid>", "..."],
  "date_from": "2026-08-01 | null",
  "date_to": "2026-08-31 | null",
  "task_list_teamwork_id": "456 | null"
}
```

**Response 200**:
```json
{
  "summary": {"created": 5, "updated": 1, "skipped": 2},
  "skipped": [
    {"teamwork_id": "9003", "block_reason": "tasklist_not_mapped"},
    {"teamwork_id": "9004", "block_reason": "assignee_not_mapped"}
  ]
}
```
Cada Ticket/Tarea creado o actualizado guarda `external_reference_id`/`external_reference_url` (FR-023) y
preserva la relación Tarea padre → Subtarea (FR-025), igual mecanismo que `POST /sync/tasks` (spec 044).
Re-ejecutar `confirm` sobre el mismo filtro actualiza en vez de duplicar (FR-024).

**Errores**: mismos que `preview`, más `500` en error interno (no revierte filas ya procesadas antes del error
dentro del mismo lote, igual criterio que el resto de operaciones masivas del namespace).

**Nota de validación en este entorno**: sin cuenta real de Teamwork disponible — se valida con un lote de
prueba de 5 a 10 filas simuladas (mock de `requests`, Principio VII), igual criterio que el resto del
namespace desde spec 042.
