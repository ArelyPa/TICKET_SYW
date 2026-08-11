# Contract: Ampliación y Ajustes Finos en la Sincronización de Catálogos de Teamwork (spec 043)

Todos los cambios viven en el namespace ya existente `teamwork_integration`
(`backend/api/routes/teamwork_integration.py`), documentados en Swagger vía Flask-RESTX (Principio
I) antes de implementarse. No se agrega namespace ni permiso nuevo — se reutilizan
`teamwork_integration:manage`/`operate` de spec 042.

## Cambios a endpoints existentes

### `POST /api/teamwork-integration/sync/<entity_type>` (sin cambio de firma)

Se amplía el fetcher de Capa 2 (`teamwork_connection_client._fetch_entity`) para que, cuando
`entity_type` sea `project` o `tasklist`, cada ítem incluya también `parent_id` (Empresa dueña o
Proyecto dueño, respectivamente — research.md Decisión 2), y cuando sea `person`, ya venía `email`
pero ahora se persiste. `upsert_from_sync` gana dos parámetros opcionales (`parent_teamwork_id`,
`teamwork_email`), sin romper la firma para `company` (ambos quedan `None`). Respuesta `200` sin
cambios: `{"entity_type": ..., "synced": N, "new": N, "updated": N}`.

### `GET /api/teamwork-integration/entity-mappings?entity_type=...` (respuesta ampliada, aditiva)

**Permiso**: `require_permission("teamwork_integration", "operate")` (sin cambio).

Cada fila del `rows[]` gana 3 campos nuevos, todos opcionales/derivados — el resto del shape no
cambia:

```json
{
  "id": "...", "entity_type": "project", "teamwork_id": "...", "teamwork_name": "Soporte",
  "sytix_entity_type": "project", "sytix_id": null, "sytix_name": null,
  "match_method": null,
  "parent_context": {
    "status": "resolved" | "pending" | "unmapped",
    "client_label": "Arcor", "project_label": null,
    "client_id": "uuid|null", "project_id": "uuid|null"
  },
  "teamwork_email": null,
  "migration_status": "pending" | "linked" | "created"
}
```

- `parent_context`: solo presente para `entity_type` en `project`/`tasklist` (para `tasklist`
  incluye además `label` con el formato `"Cliente: X | Proyecto: Y"`, ver US2). `status="unmapped"`
  si el padre nunca se sincronizó; `"pending"` si se sincronizó pero aún no tiene `sytix_id`;
  `"resolved"` si ya está homologado/migrado — la UI deshabilita "Migrar como Nuevo" salvo en
  `"resolved"` (FR-006/FR-007).
- `teamwork_email`: solo presente para `entity_type="person"` (FR-008).
- `migration_status`: **derivado** de `sytix_id`/`match_method` para pintar el badge de FR-013 —
  `"pending"` (`sytix_id is None`), `"created"` (`match_method == "created_new"`), `"linked"`
  (cualquier otro `match_method` con `sytix_id` presente — automapeo o vínculo manual).

### `GET /api/teamwork-integration/entity-mappings/<mapping_id>/create-new-candidates` (nuevo, solo lectura)

**Permiso**: `require_permission("teamwork_integration", "operate")`.

Precarga los datos que el modal "Migrar como Nuevo" necesita antes de mostrarse, sin que el
frontend tenga que orquestar varias llamadas: valores por defecto tomados de Teamwork y, para
`person`, la lista de Roles (`RoleRepository.list(active=True)`, ya reusado por `roleService` del
frontend — research.md Decisión 9) y de Clientes (para el caso `Usuario/cliente`).

**200** (`entity_type="person"`):
```json
{"defaults": {"name": "Ana Pérez", "email": "ana.perez@teamwork-demo.com"},
 "roles": [{"id": "...", "name": "Resolutor"}, ...],
 "clients": [{"id": "...", "name": "Aris"}, ...]}
```
**200** (`entity_type` en `company`/`project`/`tasklist`): `{"defaults": {"name": "Soporte"}}`.

**409** `already_linked`: la fila ya tiene `sytix_id` (FR-004). **409** `parent_not_resolved`:
Empresa/Proyecto padre sin homologar (FR-006/FR-007).

## Endpoint nuevo: acción "Migrar como Nuevo"

### `POST /api/teamwork-integration/entity-mappings/<mapping_id>/create-new`

**Permiso**: `require_permission("teamwork_integration", "operate")` (mismo permiso que
"Homologar"/`PUT /entity-mappings/{id}` ya existente — no se distingue por acción, FR-001 no lo pide).

**Body** por `entity_type` (research.md Decisión 5 / data-model.md):

```json
// company | project | tasklist
{}

// person
{"role_id": "uuid", "client_id": "uuid|null"}
```

**200**: fila de `EntityMapping` actualizada (mismo shape que `GET /entity-mappings`, con
`migration_status="created"`) + `{"created": {"id": "uuid", "name": "..."}}`.

**400** `validation_error`: `entity_type="person"` sin `role_id`, o rol `Usuario/cliente` sin
`client_id`.

**404** `not_found`: `mapping_id` no existe.

**409**:
- `already_linked` — la fila ya tiene `sytix_id` (FR-004).
- `parent_not_resolved` — Empresa (para `project`) o Proyecto (para `tasklist`) sin homologar
  (FR-006/FR-007).
- `duplicate_name` — mismo error que ya devuelve la creación manual de Cliente/Proyecto/Lista de
  Tareas ante un nombre repetido (`ClientBusinessError`/`ProjectBusinessError`/`TaskListService`).
- `email_already_used` — el correo de Teamwork ya pertenece a un usuario de SYTIX (FR-011); el
  mensaje sugiere usar "Homologar".

**500**: error interno (mismo patrón `server_error()` del resto del namespace).

## Sin cambios

`GET/PUT /api/teamwork-integration/config`, `POST /api/teamwork-integration/test-connection`,
`PUT /api/teamwork-integration/entity-mappings/<id>` (acción "Homologar" ya existente, sin cambio
de contrato — solo la UI que la invoca gana más contexto para elegir bien el candidato) quedan
exactamente igual que en spec 042.
