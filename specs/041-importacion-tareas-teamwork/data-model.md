# Data Model: Migración e Importación de Tareas desde Teamwork

## Entidad existente ampliada

### `tickets` (backend/infra/models/ticket_model.py)

Dos columnas nuevas, ambas nullable (aplican por igual a Tickets y Tareas, ya que ambos tipos
viven en esta misma tabla vía `ticket_type`):

| Columna | Tipo | Nullable | Notas |
|---|---|---|---|
| `external_reference_id` | `Text` | Sí | `ID` original de Teamwork. Indexado (lookup de upsert, FR-009). |
| `external_reference_url` | `Text` | Sí | Enlace directo a la tarea en Teamwork, construido por el servicio de importación. |

Sin cambios a `NOT NULL`/`UNIQUE` de columnas existentes. Sin cambios de RLS (migración 012 ya
cubre `tickets`, estas columnas no son sensibles ni cambian el criterio de acceso).

## Entidades transitorias (no persistidas)

Estas estructuras existen solo en memoria durante una importación (Decisión 2 de
`research.md`) — no son tablas nuevas.

### `ImportRow` (Capa 1, `teamwork_import_service.py`)

| Campo | Descripción |
|---|---|
| `source_row_number` | Posición en el archivo/respuesta de origen, para mostrar errores. |
| `external_id` | `ID` de Teamwork. |
| `status` | `"ready"` \| `"needs_review"` \| `"error"` |
| `issues` | Lista de motivos cuando `status != "ready"` (ej. `"client_not_found"`, `"duplicate_external_id_in_file"`, `"assignee_ambiguous"`). |
| `resolved` | Objeto con los valores ya mapeados a IDs de SYTIX: `client_id`, `project_id`, `list_id` (o `list_name` si se creará), `title`, `description`, `start_date`, `due_date`, `assignee_resource_id` \| `assignee_user_id` \| `None`, `requester_client_contact_id` \| `None`, `estimated_hours`, `parent_external_id` \| `None`, `existing_ticket_id` (si ya existía, para el upsert). |

### `ImportSummary` (respuesta de `POST /api/ticket-imports/confirm`)

| Campo | Descripción |
|---|---|
| `created` | Cantidad de Tareas creadas. |
| `updated` | Cantidad de Tareas actualizadas (upsert por `external_reference_id`). |
| `errors` | Cantidad de filas no insertadas, con su detalle (`source_row_number` + motivo). |

## Relaciones y reglas de negocio relevantes

- `external_reference_id` no es `UNIQUE` a nivel de base de datos (una migración futura podría
  necesitar reimportar el mismo `ID` bajo un dominio Teamwork distinto); la unicidad práctica
  para el upsert (FR-009) la garantiza el servicio de importación buscando por
  `external_reference_id` antes de insertar.
- Una fila con `Parent task ID` se resuelve como `parent_task_id` de `tickets` (ya existente,
  Nivel 5 del modelo) buscando primero entre las filas del mismo lote y, si no aparece ahí, entre
  Tickets/Tareas ya existentes por `external_reference_id`.
- `Task list` reutiliza `task_lists` (ya existente, Nivel 3) — se busca por nombre dentro del
  `project_id` resuelto; si no existe, se crea (FR-005).
- El campo Asignado de una Tarea importada (`assignee_id` de `tickets`, FK a `resources.id`)
  puede resolver a un Recurso de un Resolutor existente o, vía el nuevo mecanismo de asignación a
  Coordinador (Decisión 6), a un Recurso aprovisionado perezosamente para un usuario Coordinador.
- **`Start date`/`Due date` no tienen columna propia en `tickets`** (no existe un campo genérico
  de fecha de inicio/vencimiento — el "Vencimiento" de un Ticket lo calcula dinámicamente el motor
  de SLA a partir de `sla_phase_limit_minutes`/`sla_last_resume_at`, y las Tareas importadas
  (Assumptions) nunca calculan SLA). Dado el alcance de migración explícitamente restringido a
  los dos campos de referencia (instrucción de esta sesión), estas dos columnas del reporte se
  muestran en la vista previa como referencia informativa pero **no se persisten** en ningún
  campo — no hay pérdida silenciosa de datos porque el usuario las ve antes de confirmar, pero
  tampoco se inventa una columna nueva fuera del alcance autorizado.

## Sin entidades nuevas persistidas

No se agregan tablas (`import_batches`, `ticket_import_runs`, etc.) — ver Decisión 2/3 de
`research.md` para el razonamiento.
