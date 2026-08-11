# API Contracts — Operaciones Masivas, Paginación de Sincronización y Migración de Tareas/Subtareas

Todos los endpoints nuevos viven en el namespace ya existente `teamwork_integration`
(`backend/api/routes/teamwork_integration.py`, `path="/api/teamwork-integration"`), gateados por el permiso ya
existente `teamwork_integration:operate` (Admin/Coordinador) — sin permiso nuevo (research.md). Los endpoints
ya existentes (`GET /entity-mappings`, `POST /sync/<entity_type>`, `PUT /entity-mappings/<id>`,
`GET/POST /entity-mappings/<id>/create-new[-candidates]`) no cambian su contrato, solo su comportamiento
interno (Decisiones 1 y 2 de research.md).

## `POST /api/teamwork-integration/entity-mappings/bulk-create-new`

Migración/asociación masiva de Personal (FR-006 a FR-009). Reutiliza `_create_new_person` fila por fila
(research.md Decisión 6) — mismas reglas de validación que `POST .../entity-mappings/{id}/create-new`.

**Request**:
```json
{
  "mapping_ids": ["<uuid>", "<uuid>", "..."],
  "role_id": "<uuid>",
  "client_id": "<uuid> | null"
}
```
`client_id` requerido solo si el Rol elegido es "Usuario/cliente" (mismo criterio que el endpoint individual).

**Response 200**:
```json
{
  "created": [
    {"mapping_id": "<uuid>", "sytix_id": "<uuid>", "sytix_name": "..."}
  ],
  "skipped": [
    {"mapping_id": "<uuid>", "reason": "already_linked"},
    {"mapping_id": "<uuid>", "reason": "email_in_use"}
  ]
}
```

**Errores**:
- `400 validation_error` — `mapping_ids` vacío, o `role_id` faltante.
- `404 role_not_found` — el `role_id` no existe.
- `401` / `403 Sin permiso teamwork_integration:operate`.
- `500` — error interno (no aborta filas ya procesadas antes del error; ver nota de atomicidad abajo).

**Nota de atomicidad**: cada fila se procesa y confirma independientemente (sin transacción envolvente sobre
todo el lote) — un error puntual en una fila (`email_in_use`, `role_not_found` a nivel de fila si aplica) no
revierte las filas ya migradas con éxito antes en el mismo lote. Igual criterio que el resto de operaciones
masivas de la aplicación (ej. ninguna).

---

## `GET /api/teamwork-integration/migrated-refs`

Distintivo de trazabilidad para pantallas principales de SYTIX (FR-012/013, research.md Decisión 7).

**Query params**: `sytix_entity_type` (requerido) — uno de `client | project | task_list | resource | user`.

**Response 200**:
```json
{"sytix_ids": ["<uuid>", "<uuid>", "..."]}
```

IDs de `teamwork_entity_mappings.sytix_id` donde `sytix_entity_type` coincide y `sytix_id IS NOT NULL`
(homologado manualmente o migrado con "Migrar como Nuevo"/masivo — research.md Decisión 7, condición
canónica).

**Errores**: `400 validation_error` si `sytix_entity_type` no es uno de los 5 valores válidos; `401`/`403`
igual que el resto del namespace.

**Nota de frontend (obligatoria, research.md Decisión 7)**: las 5 pantallas principales que consumen este
endpoint deben (a) chequear `hasPermission('teamwork_integration','operate')` antes de llamarlo — Resolutor/QM
no tienen ese permiso pero sí ven Clientes/Proyectos/Equipo/Usuario-cliente — y (b) pasar
`headers: {'X-Skip-Error-Notify': 'true'}` como defensa adicional, igual patrón que
`calendarService.listAbsenceRequestsForResource`, para no disparar un toast de error 403 en pantallas de uso
diario.

---

## `POST /api/teamwork-integration/sync/tasks`

Migración masiva de Tareas y Subtareas desde `GET /projects/api/v3/tasks.json` (FR-014 a FR-020,
research.md Decisión 8). Mismo patrón de respuesta que `POST /sync/<entity_type>` ya existente, extendido con
`skipped`.

**Request**: sin body.

**Precondición**: igual que el resto de `/sync/*` — `409 connection_not_tested` si la última prueba de
conexión guardada no fue exitosa.

**Response 200**:
```json
{
  "synced": 8,
  "created": 6,
  "updated": 1,
  "skipped": [
    {"teamwork_id": "9001", "reason": "project_not_mapped"},
    {"teamwork_id": "9002", "reason": "tasklist_not_mapped"}
  ]
}
```

**Errores**:
- `409 connection_not_tested` — igual que `/sync/<entity_type>`.
- `502 teamwork_api_error` — la API v3 de Teamwork no respondió o devolvió un error.
- `401` / `403 Sin permiso teamwork_integration:operate`.
- `500` — error interno.

**Nota de validación en este entorno**: sin cuenta real de Teamwork disponible — se valida con un lote de
prueba de 5 a 10 filas simuladas (mock de `requests`, Principio VII), igual criterio que
`teamwork_connection_client`/`teamwork_time_file_parser` de spec 042.
