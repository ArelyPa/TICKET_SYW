# Contract: Integración API Teamwork v3, Homologación de Catálogos e Importador de Tiempos
Mensuales (spec 042)

Endpoints nuevos, documentados en Swagger vía Flask-RESTX (Principio I) antes de implementarse.
Ninguno reutiliza ni modifica el namespace `ticket_imports` de spec 041.

## Configuración de conexión (`backend/api/routes/teamwork_integration.py`, namespace
`teamwork_integration`)

### `GET /api/teamwork-integration/config`

**Permiso**: `require_permission("teamwork_integration", "manage")` (solo Admin).

**200**:
```json
{"site_url": "https://empresa.teamwork.com", "environment": "test",
 "has_token": true, "last_test_status": "success",
 "last_test_at": "2026-08-09T10:00:00Z", "last_test_message": null}
```
El token nunca se devuelve — solo `has_token` (booleano) para que la UI sepa si ya hay uno
guardado.

### `PUT /api/teamwork-integration/config`

**Permiso**: `require_permission("teamwork_integration", "manage")` (solo Admin).

**Body**: `{"site_url": "...", "api_token": "...", "environment": "test"|"production"}` —
`api_token` es opcional en la actualización (si se omite, se conserva el token ya guardado).

**200**: mismo shape que el `GET`. **400** `validation_error`: `site_url` no es una URL válida o
`environment` no es uno de los dos valores permitidos.

### `POST /api/teamwork-integration/test-connection`

**Permiso**: `require_permission("teamwork_integration", "manage")` (solo Admin).

Consulta `GET /projects/api/v3/projects.json` de Teamwork con las credenciales guardadas
(`pageSize=1`, no necesita traer resultados reales, solo confirmar autenticación).

**200**: `{"status": "success"}` \| `{"status": "auth_error", "message": "..."}` \|
`{"status": "connection_error", "message": "..."}` — siempre 200; el estado va en el body para
que la UI pinte el badge sin tratar un fallo de autenticación como error HTTP. Actualiza
`last_test_status`/`last_test_at`/`last_test_message` de la configuración guardada.

**409** `no_config`: no hay configuración guardada todavía.

## Sincronización de catálogos (mismo namespace)

### `POST /api/teamwork-integration/sync/<entity_type>`

`<entity_type>` ∈ `company` \| `project` \| `person` \| `tasklist`.

**Permiso**: `require_permission("teamwork_integration", "operate")` (Admin, Coordinador).

Llama al endpoint v3 correspondiente (`companies.json`/`projects.json`/`people.json`/
`tasklists.json`) y upserta cada resultado en `teamwork_entity_mappings` (por `entity_type` +
`teamwork_id`), sin tocar `sytix_id` de filas ya homologadas.

**200**: `{"entity_type": "company", "synced": 12, "new": 3, "updated": 9}`

**409** `connection_not_tested`: la conexión no tiene un `last_test_status: "success"` vigente.
**502** `teamwork_api_error`: la API v3 de Teamwork no respondió o devolvió error.

## Homologación de entidades (mismo namespace)

### `GET /api/teamwork-integration/entity-mappings?entity_type=company&unresolved_only=false`

**Permiso**: `require_permission("teamwork_integration", "operate")` (Admin, Coordinador).

**200**:
```json
{"rows": [
  {"id": "uuid", "entity_type": "person", "teamwork_id": "556", "teamwork_name": "juan@aris.com",
   "sytix_entity_type": "resource", "sytix_id": "uuid", "sytix_name": "Juan Pérez",
   "match_method": "email"},
  {"id": "uuid", "entity_type": "company", "teamwork_id": "12", "teamwork_name": "Aris Ming",
   "sytix_entity_type": null, "sytix_id": null, "sytix_name": null, "match_method": null}
]}
```
El automapeo (correo/ID externo/nombre exacto, FR-006) se calcula en la sincronización (arriba) y
al listar; `match_method: null` = sin sugerencia, pendiente de selección manual.

### `PUT /api/teamwork-integration/entity-mappings/<mapping_id>`

**Permiso**: `require_permission("teamwork_integration", "operate")` (Admin, Coordinador).

**Body**: `{"sytix_id": "uuid"}` — guarda como `match_method: "manual"`. `{"sytix_id": null}`
limpia la homologación (vuelve a quedar pendiente).

**200**: la fila actualizada (mismo shape que el listado). **404**: `mapping_id` no existe.

## Importación de tiempos (`backend/api/routes/time_imports.py`, namespace `time_imports`)

### `POST /api/time-imports/preview`

**Permiso**: `require_permission("teamwork_integration", "operate")` (Admin, Coordinador).

**Body**: `multipart/form-data` con campo `file` (`.xlsx`/`.csv`, formato estándar de reporte de
tiempos mensual de Teamwork — columnas en data-model.md).

**200**:
```json
{"rows": [
  {"source_row_number": 2, "external_time_id": "9001", "status": "valid", "issues": [],
   "resolved": {"who_name": "Juan Pérez", "resource_id": "uuid", "company_name": "Aris",
                "project_name": "Soporte", "project_id": "uuid", "task_reference": "41972833",
                "ticket_id": "uuid", "description": "Ajuste de reporte",
                "started_at": "2026-07-01T09:00:00", "ended_at": "2026-07-01T10:30:00",
                "duration_minutes": 90}},
  {"source_row_number": 3, "external_time_id": "9002", "status": "conflict",
   "issues": ["who_not_found"], "resolved": {"who_name": "Nuevo Colaborador", "resource_id": null,
              "...": "..."}}
], "summary": {"total": 2, "valid": 1, "conflict": 1, "error": 0}}
```

**400** `validation_error`: columnas mínimas faltantes en el archivo.

### `POST /api/time-imports/confirm`

**Permiso**: `require_permission("teamwork_integration", "operate")` (Admin, Coordinador).

**Body**:
```json
{"rows": [
  {"source_row_number": 2},
  {"source_row_number": 3, "action": "resolve", "resource_id": "uuid"},
  {"source_row_number": 4, "action": "create", "create_entity_type": "client"},
  {"source_row_number": 5, "action": "omit"}
]}
```
Las filas `status: "valid"` en la preview original no necesitan `action` (se procesan tal cual).
Las filas `status: "error"` de la preview se ignoran aunque vengan en el body.

**200**:
```json
{"created_time_entries": 3, "updated_time_entries": 1, "created_resources": 1,
 "created_clients": 0, "skipped": 1, "errors": [{"source_row_number": 6, "reason": "..."}]}
```

**400** `invalid_action`: `action="create"` con `create_entity_type` distinto de
`resource`/`client` (Proyecto y Tarea/Ticket nunca se crean automáticamente, ver data-model.md).

## Response de error compartido

Todos los endpoints anteriores usan el mismo modelo `_error`/`server_error()` ya establecido en
`backend/api/routes/_shared.py` (Principio I, reutilizado sin cambios).
