# Data Model: Integración API Teamwork v3, Homologación de Catálogos e Importador de Tiempos Mensuales

Todas las tablas nuevas se crean en una única migración (`054_teamwork_integration_time_imports`,
ver plan.md § Migración). Ninguna tabla existente se modifica salvo `work_sessions` (una columna
nueva, aditiva).

## Tablas nuevas

### `teamwork_integration_configs`

Fila única (patrón singleton — el repositorio siempre actualiza la fila existente o crea la
primera si no hay ninguna; no hay UI para tener más de una configuración activa a la vez).

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `site_url` | Text | ej. `https://empresa.teamwork.com`, sin token |
| `api_token` | Bytea | cifrado con `_encrypt`/`_decrypt` (mismo mecanismo app-level que `client_access`, `backend/infra/models/client_model.py`) |
| `environment` | Text | `test` \| `production`, informativo (Assumptions spec.md) |
| `last_test_status` | Text nullable | `success` \| `auth_error` \| `connection_error` \| null (nunca probada) |
| `last_test_at` | Timestamptz nullable | |
| `last_test_message` | Text nullable | detalle del último resultado, para mostrar en el badge |
| `updated_by` | UUID FK `users.id` | |
| `updated_at` | Timestamptz | |

### `teamwork_entity_mappings`

Homologación Teamwork↔SYTIX, una fila por entidad de Teamwork vista alguna vez (por sincronización
o por resolución manual de un conflicto de importación). Único por (`entity_type`, `teamwork_id`).

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `entity_type` | Text | `company` \| `project` \| `person` \| `tasklist` |
| `teamwork_id` | Text | ID externo de Teamwork |
| `teamwork_name` | Text | nombre/email tal como vino de Teamwork (para mostrar en la tabla comparativa) |
| `sytix_entity_type` | Text nullable | `client` \| `project` \| `resource` \| `task_list` — coincide con `entity_type` pero se guarda explícito para no acoplar el nombre de tabla SYTIX al de Teamwork |
| `sytix_id` | UUID nullable | FK lógica (no `ForeignKey` de BD porque apunta a distintas tablas según `sytix_entity_type`); `NULL` = pendiente de homologar |
| `match_method` | Text nullable | `email` \| `external_id` \| `name` \| `manual` \| null |
| `created_at` / `updated_at` | Timestamptz | |
| `updated_by` | UUID FK `users.id` nullable | quién hizo la última homologación manual |

**Reutilización por el importador de tiempos**: al resolver `Who`/`Company`/`Project` de una fila
del reporte de tiempos, la Capa 3 primero busca una homologación existente en esta tabla
(`entity_type` + nombre/email de la fila) antes de intentar coincidencia directa contra los
catálogos de SYTIX o de pedirle al usuario que resuelva el conflicto (FR-007).

### `time_import_batches`

Auditoría agregada por carga confirmada (FR-015) — no hay tabla de staging por fila (research.md
Decisión 2); los conteos de omitidas/creadas no son derivables de `work_sessions` por sí solas.

| Columna | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `filename` | Text | |
| `imported_by` | UUID FK `users.id` | |
| `imported_at` | Timestamptz | |
| `total_rows` | Integer | |
| `valid_rows` | Integer | válidas de origen, sin conflicto |
| `resolved_rows` | Integer | conflicto homologado o con registro creado |
| `skipped_rows` | Integer | conflicto omitido explícitamente |
| `error_rows` | Integer | filas con error de datos (ej. duración inconsistente) que ni siquiera llegaron a confirmarse |

## Cambios a tablas existentes

### `work_sessions` (aditivo)

| Columna nueva | Tipo | Notas |
|---|---|---|
| `external_time_id` | Text nullable, índice único parcial (`WHERE external_time_id IS NOT NULL`) | `ID` del reporte de Teamwork; reimportar el mismo valor actualiza en vez de duplicar (FR-013) |

No se agregan más columnas — `note` (Descripción) y `off_hours` ya existen y se usan tal cual.

## Entidades de dominio (Capa 1, `backend/domain/entities/`)

- **`TeamworkIntegrationConfig`**: `id`, `site_url`, `api_token` (valor plano en memoria de
  dominio — el cifrado es responsabilidad de la Capa 2, igual que `Client.vpn_credentials`),
  `environment`, `last_test_status`, `last_test_at`, `last_test_message`.
- **`EntityMapping`**: `id`, `entity_type`, `teamwork_id`, `teamwork_name`, `sytix_entity_type`,
  `sytix_id`, `match_method`.

No se crea entidad de dominio para `TimeImportBatch` (es un registro de auditoría de Capa 2/3, sin
reglas de negocio propias — mismo criterio que otras tablas de auditoría del proyecto).

## Clasificación de una fila del reporte de tiempos (Capa 1 pura, `time_import_service.py`)

Mismo patrón que `ImportRow`/`classify_row` de spec 041 (`teamwork_import_service.py`): la Capa 3
resuelve cada campo contra la base de datos y le pasa a la Capa 1 un `dict` de resolución ya
armado; la Capa 1 solo decide `status`/`issues`.

```
TimeImportRow:
  source_row_number: int
  external_time_id: str | None
  status: "valid" | "conflict" | "error"
  issues: list[str]            # "who_not_found" | "project_not_found" | "task_not_found" |
                                # "description_missing" | "duplicate_external_id_in_file" |
                                # "duration_inconsistent"
  resolved: dict                # started_at, ended_at, duration_minutes, description,
                                 # who_name, company_name, project_name, task_reference,
                                 # resource_id | None, project_id | None, ticket_id | None
```

Reglas de clasificación:
- `status="error"` (bloquea incluso la resolución manual): `duplicate_external_id_in_file`,
  `duration_inconsistent` (ver research.md Decisión 5), `description_missing`.
- `status="conflict"`: `who_not_found`, `project_not_found` o `task_not_found` — resoluble por el
  usuario (homologar / crear si aplica / omitir, FR-011).
- `status="valid"`: `resource_id`, `project_id` y `ticket_id` resueltos y descripción presente.

## Acción de resolución enviada al confirmar (`POST /api/time-imports/confirm`)

Por cada fila con conflicto, el frontend envía una acción explícita:

```
{
  "source_row_number": int,
  "action": "resolve" | "create" | "omit",
  // action="resolve": homologa contra un registro ya existente
  "resource_id": uuid | null,      // para who_not_found
  "project_id": uuid | null,       // para project_not_found
  "ticket_id": uuid | null,        // para task_not_found
  // action="create": ver research.md Decisión 4 — solo Recurso (who) o Cliente (company)
  "create_entity_type": "resource" | "client" | null
}
```

`action="create"` con `create_entity_type` distinto de `resource`/`client` es inválido (400) —
Proyecto y Tarea/Ticket nunca se crean automáticamente.
