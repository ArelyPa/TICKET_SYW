# Research — Operaciones Masivas, Paginación de Sincronización y Migración de Tareas/Subtareas

Todas las decisiones parten del código real de spec 042/043 (`backend/api/routes/teamwork_integration.py`,
`backend/infra/importers/teamwork_connection_client.py`, `backend/infra/repositories/teamwork_integration_repo.py`,
`frontend/src/pages/TeamworkIntegrationPage.tsx`), inspeccionado en esta sesión — no hay `NEEDS CLARIFICATION`
pendiente.

## Decisión 1 — Causa raíz confirmada de "150 reportados vs. 60 renderizados" (FR-011)

`_fetch_entity()` en `teamwork_connection_client.py:52` hace **una sola** request con `params={"pageSize": 250}`
y nunca recorre páginas adicionales. La pantalla ya no pagina del lado del cliente (`Table` usa
`pagination={false}`, todo lo que llega se renderiza), así que el "60 de 150" no es un bug de UI: es que la API
v3 de Teamwork, igual que la mayoría de APIs JSON:API, limita cada respuesta a un tope propio del servidor
(históricamente 50–60 para varios endpoints v3) sin importar el `pageSize` pedido, y expone el resto en páginas
siguientes.

- **Decisión**: agregar un helper `_fetch_all_pages(url, auth, params)` en `teamwork_connection_client.py` que
  incrementa `page=1,2,3…` (parámetro estándar de paginación v3) hasta que una respuesta devuelve **menos**
  elementos que el `pageSize` pedido (última página) o una lista vacía — sin depender de un campo `meta.page.*`
  específico no verificado contra una cuenta real (mismo caso ya documentado en specs 041/042/043: sin
  smoke-test posible en este entorno). `_fetch_entity` y el nuevo `fetch_tasks` reutilizan el mismo helper.
- **Alternativas consideradas**: confiar en `meta.page.hasMore`/`meta.page.count` del payload — rechazado por
  no poder verificarse contra una cuenta real; el criterio "página corta = última página" es más robusto y
  funciona igual con o sin esos campos de metadata.

## Decisión 2 — Compañía en Personal (FR-001): reutilizar `parent_teamwork_id`, sin migración nueva

`EntityMappingModel.parent_teamwork_id` (migración 055, spec 043) ya es una columna genérica de texto, hoy solo
poblada para `project`/`tasklist`. `_fetch_entity()` para `entity_type == "person"` hoy descarta cualquier dato
de compañía (`{"id","name","email"}` únicamente), aunque `_parent_id()` (ya usado por project/tasklist) ya sabe
leer `item.get("company")`/`item.get("companyId")`, presente también en el payload de `people.json`.

- **Decisión**: extender la rama `person` de `_fetch_entity` para incluir `"parent_id": _parent_id(item)` (cero
  cambios en `_parent_id`, ya genérico); el endpoint de sync ya pasa `parent_teamwork_id=item.get("parent_id")`
  de forma agnóstica al tipo de entidad, así que no requiere tocar `TeamworkIntegrationSync.post`. En
  `_resolve_parent_context` (Capa 3), agregar `"person"` al mismo branch que ya resuelve `"company"` para
  `project` (`_resolve_parent_link(db, "company", mapping.parent_teamwork_id)`), devolviendo el mismo shape
  `{status, client_label, client_id}` ya usado por `parent_context`.
- **Resultado**: cero columnas nuevas, cero migración — el dato ya tenía dónde vivir.

## Decisión 3 — Filtros por Cliente/Proyecto (FR-002/003): sin endpoint nuevo

Cada fila ya trae (tras la Decisión 2) su `parent_context.client_id`/`project_id` resuelto por el backend.

- **Decisión**: los filtros superiores de Cliente/Proyecto son **client-side** sobre el array `mappings` ya
  cargado — sin nuevo parámetro de query ni endpoint. Aplican a Personal (`parent_context.client_id`, filtro
  por Proyecto deshabilitado — ver spec.md § Assumptions) y Listas de Tareas (`client_id` + `project_id`); en
  Proyectos el filtro por Cliente compara contra su propio `parent_context.client_id` y el filtro por Proyecto
  queda oculto (cada fila ya ES un proyecto). Empresas no muestra el bloque de filtros (spec.md § Assumptions).
- **Alternativa rechazada**: filtrar server-side en `GET /entity-mappings` — más código (nuevos query params +
  lógica de filtro en el repo) para el mismo resultado, dado que hoy el endpoint ya trae todas las filas sin
  paginar server-side.

## Decisión 4 — Selector `Cliente - Proyecto` (FR-004/005): composición de label en frontend

`ProjectListItem` (usado por `SYTIX_CANDIDATE_LOADER.project`) ya trae `client_name` (confirmado en
`frontend/src/types/project.ts`). Para Listas de Tareas, `taskListCandidatesByProject` se arma hoy por
`parent_context.project_id` ya resuelto — el mismo objeto `parent_context` de la fila trae `client_label` y
`project_label`.

- **Decisión**: en `SYTIX_CANDIDATE_LOADER.project`, cambiar `label: x.name` a
  `label: x.client_name ? \`${x.client_name} - ${x.name}\` : x.name`. En la carga de candidatos de Lista de
  Tareas, prefijar cada opción con `${client_label} - ${project_label} - ` antes del nombre de la lista — los
  nombres de Lista de Tareas se repiten muchísimo entre proyectos (ej. "General Tasks" por defecto de
  Teamwork), así que el mismo criterio de desambiguación aplica aunque el pedido original solo nombre el
  formato `Cliente - Proyecto` explícitamente para Proyectos.
- **Ancho**: cambiar el `Select` de `style={{ width: 240 }}` fijo a `style={{ minWidth: 240, maxWidth: 360 }}`
  con `title` (tooltip nativo) sobre la opción seleccionada para que un texto largo no rompa el layout de la
  fila de la tabla.

## Decisión 5 — Paginación fija a 15 (FR-010): cambio de prop en `Table`

- **Decisión**: `pagination={false}` → `pagination={{ pageSize: 15, showSizeChanger: false }}` en el único
  `Table` de `TeamworkIntegrationPage.tsx`. Sin cambios de backend (la lista ya viaja completa al cliente).

## Decisión 6 — Acciones masivas de Personal (FR-006 a FR-009): reutilizar `_create_new_person`

`_create_new_person(db)` (líneas 470-518 de `teamwork_integration.py`) ya encapsula **toda** la regla de
negocio de migración individual de una Persona: valida rol, dominio `@sywork.net`, `Cliente` requerido para
"Usuario/cliente", detecta `email_in_use` (409) y crea Usuario+Recurso o Usuario+ClientContact según
corresponda — es exactamente la función que ya invoca `TeamworkEntityMappingCreateNew.post` fila por fila.

- **Decisión**: nuevo endpoint `POST /entity-mappings/bulk-create-new` que recibe
  `{"mapping_ids": [...], "role_id", "client_id"}` y por cada `mapping_id`: si ya está vinculada
  (`mapping.sytix_id`), la cuenta como `skipped` con motivo `already_linked` (FR-009, Escenario 3); si no,
  invoca **la misma** `_create_new_person(db)(mapping, data)` ya existente y, en éxito, el mismo
  `mapping_repo.set_created_new_mapping(...)`. Cada fila se procesa de forma independiente (un `email_in_use`
  en una fila no aborta el lote) — el resultado agrega `{created: [...], skipped: [{mapping_id, reason}]}`.
- **Por qué no un helper genérico para "demás catálogos"**: spec.md § Assumptions ya deja explícito que la
  combinación Rol+Cliente solo tiene sentido de negocio para Personal; los demás catálogos conservan su
  homologación fila por fila de spec 043. Generalizar el endpoint bulk a Empresa/Proyecto/Lista sería código
  sin requerimiento funcional detrás (Principio VII).
- **Filtro de correo (FR-007)**: client-side sobre `mappings[].teamwork_email`, ya presente en cada fila — sin
  cambios de backend.

## Decisión 7 — Distintivo de trazabilidad en pantallas principales (FR-012/013)

Hoy la "Homologación de Entidades" ya muestra un badge de estado (`MIGRATION_STATUS_BADGE`,
`migration_status` ya calculado en `_migration_status(mapping)`) — FR-013 (integrador) ya está resuelto para
ese lado. Falta el mismo distintivo en las pantallas principales de SYTIX (`ClientsPage.tsx`,
`ProjectsPage.tsx`, `ProjectListsPage.tsx` — Listas de Tareas, `TeamPage.tsx` — Recursos internos,
`ClientContactsPage.tsx` — Usuario/cliente).

- **Decisión**: nuevo endpoint de solo lectura `GET /api/teamwork-integration/migrated-refs?sytix_entity_type=<tipo>`
  que devuelve `{"sytix_ids": ["<uuid>", ...]}` — los `sytix_id` de `teamwork_entity_mappings` donde
  `sytix_entity_type` coincide y `sytix_id IS NOT NULL` (homologado o migrado; verificado contra
  `teamwork_integration_repo.py` que `sytix_id`/`match_method` siempre se escriben juntos en los tres paths de
  escritura existentes — `upsert_from_sync` con sugerencia, `set_manual_mapping`, `set_created_new_mapping` —
  así que filtrar por cualquiera de las dos columnas da hoy el mismo resultado; se fija `sytix_id IS NOT NULL`
  como condición canónica en todos los documentos de esta feature por ser el campo que efectivamente se
  proyecta en la respuesta). Cada una de las 5 pantallas principales pide esta lista una vez al cargar y pinta
  un `<Tag icon={<SyncOutlined/>}>Teamwork</Tag>` (o similar) en las filas cuyo `id` está en el set — sin tocar
  la lógica de negocio de esas pantallas, solo una columna/adorno visual adicional.
- **Permiso y manejo de errores en el frontend**: se gatea con el mismo `teamwork_integration:operate` ya
  existente (Admin/Coordinador — sin permiso nuevo, Principio VII), igual que el resto del namespace. Efecto:
  Resolutor/QM, que hoy pueden ver Clientes/Proyectos/Equipo/Usuario-cliente (`clients:view`/`projects:view`/
  etc., migración 009) pero no tienen `teamwork_integration:operate`, no verán el badge aunque vean la fila.
  Para que esto no dispare un toast de error espurio en 4 pantallas maestras de uso diario (`apiClient.ts` ya
  muestra un toast en cualquier respuesta no-401 salvo que la request lleve `X-Skip-Error-Notify: 'true'`), las
  5 pantallas **DEBEN** aplicar el mismo patrón ya usado por `calendarService.listAbsenceRequestsForResource`
  (`frontend/src/services/calendarService.ts`): (a) verificar `hasPermission('teamwork_integration','operate')`
  del `authStore` antes de siquiera llamar a `getMigratedRefs`, y (b) pasar igualmente
  `headers: {'X-Skip-Error-Notify': 'true'}` en la request como defensa adicional. Sin esto, cada login de
  QM/Resolutor dispararía un toast de error 403 al abrir Clientes/Proyectos/Listas de Tareas/Equipo/Usuario-
  cliente — regresión de UX detectada en el análisis de consistencia de esta sesión (`/speckit-analyze`,
  hallazgo U1).
- **Alcance de la modificación fuera del namespace `teamwork_integration`**: el pedido del usuario (FR-012) es
  explícito en pedir el badge "tanto en las pantallas del integrador como en sus respectivas pantallas
  principales dentro de SYTIX", lo que exige tocar 5 archivos de página fuera de
  `TeamworkIntegrationPage.tsx`. Es una adición puramente presentacional (una columna/`Tag` de solo lectura, sin
  lógica de negocio ni cambio de contrato de esas pantallas) — se documenta como desviación acotada del
  principio de aislamiento de sesión en `plan.md § Complexity Tracking`, justificada porque es un requisito
  explícito y ya validado del propio spec.md (FR-012/FR-013), no una ampliación de alcance decidida por el
  agente.

## Decisión 8 — Migración masiva de Tareas/Subtareas (FR-014 a FR-020)

No se crea una fila de homologación por Tarea — a diferencia de Empresa/Proyecto/Lista/Persona, una Tarea no
se "homologa" manualmente ni se selecciona por dropdown: se resuelve automáticamente contra las homologaciones
ya existentes o se omite. La deduplicación/trazabilidad ya tiene mecanismo propio y probado:
`tickets.external_reference_id`/`external_reference_url` (migración `053`, spec 041) +
`TicketRepository.upsert_from_import(...)` (ya soporta upsert por `external_reference_id`, `parent_task_id`,
`list_id`, `client_id`, `project_id`, `assignee_id` — sin modificar el archivo).

- **Decisión de resolución**: nuevo módulo Capa 1 puro `backend/domain/services/teamwork_task_migration_service.py`
  (sin imports de Flask/SQLAlchemy/`requests`, mismo patrón que `entity_mapping_service.py`) que clasifica cada
  tarea cruda + su resolución ya armada por la Capa 3 en `ready` (cadena Cliente→Proyecto→Lista resuelta) o
  `skipped` (con motivo: `project_not_mapped`, `tasklist_not_mapped`) — igual división de responsabilidades que
  `teamwork_import_service.classify_row` de spec 041, pero **sin reutilizar ni modificar ese archivo** (mismo
  criterio de aislamiento ya aplicado en spec 043 frente a spec 041/042).
- **Decisión de fetch**: nueva función `fetch_tasks(site_url, api_token)` en `teamwork_connection_client.py`
  (mismo archivo que ya tiene `fetch_companies`/`fetch_projects`/`fetch_people`/`fetch_tasklists`, reutilizando
  `_fetch_all_pages` de la Decisión 1) contra `GET /projects/api/v3/tasks.json`, devolviendo
  `{id, name, description, project_id, tasklist_id, parent_task_id, assignee_id}` por fila — la reducción de
  `task.assignees` (lista, puede traer más de un asignado en Teamwork) a un único `assignee_id` (SYTIX no
  soporta múltiples asignados por Ticket) ocurre **acá, en Capa 2** (primer elemento de la lista, o `None` si
  viene vacía), no en la Capa 3 — evita que el endpoint tenga que conocer la forma cruda del payload de
  Teamwork.
- **Decisión de resolución de IDs**: la Capa 3 (nuevo endpoint) resuelve, por cada tarea:
  - Proyecto: `EntityMappingRepository.get_by_teamwork_key("project", task.project_id)` → si `sytix_id` es
    `None`, se omite (FR-016). Si está resuelto, `ProjectRepository(db).get_by_id(sytix_id)` da el `client_id`
    directo (evita recorrer de nuevo la cadena `parent_teamwork_id`, ya materializada en el Proyecto real).
  - Lista de Tareas: `get_by_teamwork_key("tasklist", task.tasklist_id)` → `sytix_id` (o se omite).
  - Asignado: `get_by_teamwork_key("person", assignee_id)` → `sytix_id` (Recurso); si no está homologado, la
    Tarea se crea sin asignar (mismo criterio ya validado en spec 041, no bloquea).
  - Tarea padre (Subtarea): segunda pasada idéntica al patrón ya usado en `ticket_imports.py` líneas 248-258 —
    tras crear/actualizar todo el lote, resolver `parent_task_id` vía
    `TicketRepository.get_by_external_reference_id(parent_teamwork_id)` y `update_fields(...)`.
- **Hipervínculo (FR-018)**: se construye inline en el nuevo módulo de ruta —
  `f"{config.site_url.rstrip('/')}/app/tasks/{teamwork_id}"` — sin importar
  `teamwork_import_service.build_external_reference_url` (que depende de `TEAMWORK_DOMAIN`, variable de
  entorno de spec 041, mecanismo de credenciales distinto al de spec 042/043 documentado en `research.md` de
  spec 042 Decisión 1). El campo ya existe en `tickets.external_reference_url`; el frontend del detalle del
  Ticket ya renderiza ese hipervínculo desde spec 041 — sin cambios ahí.
- **Tipo de registro**: se reutiliza sin cambios el catálogo `record-types` → "Tarea" vía `CatalogRepository`,
  igual que `ticket_imports.py` (líneas 205-209) — sin tocar ese archivo, solo el mismo patrón de lectura.
- **Endpoint**: `POST /api/teamwork-integration/sync/tasks` (mismo namespace, mismo permiso
  `teamwork_integration:operate`, FR-020) — no usa el patrón preview→confirm de spec 041/042 porque no hay
  ambigüedad que un usuario deba resolver fila por fila: cada tarea o tiene su cadena homologada (se crea/
  actualiza directo) o no la tiene (se omite y se reporta). Devuelve
  `{synced, created, updated, skipped: [{teamwork_id, reason}]}`.
- **Migración de base de datos**: **ninguna** — todas las columnas/tablas necesarias ya existen
  (`tickets.external_reference_id/url` de la migración 053, `teamwork_entity_mappings` de la 054/055).

## Resumen de impacto en dependencias y esquema

- **Dependencias nuevas**: ninguna (reutiliza `requests` ya aprobado).
- **Migraciones nuevas**: ninguna.
- **Permisos nuevos**: ninguno (todo bajo `teamwork_integration:operate` ya existente).
- **Archivos de spec 041 tocados**: ninguno (`ticket_imports.py`, `teamwork_api_client.py`,
  `teamwork_import_service.py` quedan intactos, mismo criterio que specs 042/043).
