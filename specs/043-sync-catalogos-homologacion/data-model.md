# Data Model: Ampliación y Ajustes Finos en la Sincronización de Catálogos de Teamwork

Una sola migración aditiva (`055_teamwork_entity_mappings_context`, ver research.md Decisión 4).
Ninguna tabla nueva, ninguna tabla destino (`clients`/`projects`/`resources`/`users`/`task_lists`)
se modifica — ver research.md Decisión 1.

## Cambios a `teamwork_entity_mappings` (aditivo)

| Columna nueva | Tipo | Notas |
|---|---|---|
| `parent_teamwork_id` | Text nullable | ID de Teamwork del padre jerárquico inmediato: para `entity_type="project"`, el `id` de la Empresa dueña; para `entity_type="tasklist"`, el `id` del Proyecto dueño. `null` para `company`/`person` (research.md Decisión 2). |
| `teamwork_email` | Text nullable | Correo tal como vino de Teamwork; solo se popula para `entity_type="person"` (research.md Decisión 3). |

`match_method` (columna ya existente, sin cambio de esquema) gana un valor nuevo permitido:
`"created_new"` — fila resuelta por la acción "Migrar como Nuevo" de esta feature, distinta de
`"manual"` (vínculo a un registro ya existente elegido a mano). Valores totales:
`email | external_id | name | manual | created_new | null`.

## Entidad de dominio `EntityMapping` (Capa 1, `backend/domain/entities/teamwork_integration.py`)

Se amplía con los dos campos nuevos, ambos opcionales:

```
EntityMapping:
  id, entity_type, teamwork_id, teamwork_name, sytix_entity_type, sytix_id, match_method,
  parent_teamwork_id: str | None,   # NUEVO
  teamwork_email: str | None,       # NUEVO
```

## Resolución de contexto jerárquico (sin columnas nuevas por nivel — research.md Decisión 2)

Dado un `EntityMapping` de `entity_type="project"`:

```
company_mapping = EntityMappingRepository.get_by_teamwork_key("company", project_mapping.parent_teamwork_id)
cliente_asociado =
  "Sin homologar" (parent_teamwork_id is None o company_mapping is None)
  "Pendiente de homologar: <teamwork_name de la Empresa>" (company_mapping existe pero company_mapping.sytix_id is None)
  <nombre del Cliente en SYTIX>  (company_mapping.sytix_id resuelto)
```

Dado un `EntityMapping` de `entity_type="tasklist"`, la misma resolución se encadena una vez más
para el Proyecto (`get_by_teamwork_key("project", tasklist_mapping.parent_teamwork_id)`) y, a
partir de ese Proyecto, para su Empresa — dos columnas mostradas ("Cliente", "Proyecto"), una sola
cadena de 2 lookups adicionales por fila (sin N+1 relevante al volumen ya manejado por spec 042,
página server-side no pagina esta tabla hoy).

## Acción "Migrar como Nuevo" (`POST /entity-mappings/<mapping_id>/create-new`)

Payload por `entity_type` (todos los campos no listados se toman de la fila de homologación, no
se piden de nuevo en el request — research.md Decisión 5):

```
entity_type="company":  {}                                    # usa teamwork_name como Client.name
entity_type="project":  {}                                    # requiere parent_teamwork_id ya resuelto a un Cliente
entity_type="tasklist": {}                                    # requiere parent_teamwork_id ya resuelto a un Proyecto
entity_type="person":   {
  "role_id": uuid,                                             # obligatorio (FR-009)
  "client_id": uuid | null                                     # obligatorio solo si el rol elegido es "Usuario/cliente" (FR-010)
}
```

Respuesta (200): la fila de `EntityMapping` actualizada (`sytix_id` apuntando al registro nuevo,
`match_method="created_new"`) junto con el `id`/nombre del registro creado, mismo shape que
`_entity_mapping_out` ya usado por el resto de la API de este namespace.

Errores (propagados tal cual desde el repo/servicio de creación real reutilizado — research.md
Decisión 5, sin nueva capa de validación):

| Código | Caso |
|---|---|
| 400 | `entity_type="person"` sin `role_id`, o rol `Usuario/cliente` sin `client_id` |
| 404 | `mapping_id` no existe |
| 409 | fila ya vinculada a un `sytix_id` (FR-004); padre jerárquico (Empresa/Proyecto) sin homologar (FR-006/FR-007); nombre de Cliente/Proyecto/Lista duplicado (misma regla que su creación manual); correo de Teamwork ya usado por un usuario existente (FR-011) |

## Candidatos de homologación manual para `tasklist` (research.md Decisión 7)

`GET /entity-mappings?entity_type=tasklist` sigue devolviendo las filas tal cual (sin cambio de
contrato); lo que cambia es que el frontend, una vez resuelto el `project_id` de la fila (a partir
de `parent_teamwork_id`), pide sus candidatos con `GET /projects/{project_id}/task-lists` (endpoint
ya existente, `backend/api/routes/task_lists.py`) en vez de un listado global — antes esta
homologación manual no tenía candidatos que ofrecer.
