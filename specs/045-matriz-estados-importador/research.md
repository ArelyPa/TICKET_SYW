# Research — Matriz de Estados, Acciones Masivas Ampliadas, Extracción Enriquecida y Centro de Importación de Tareas

Todas las decisiones parten del código real de spec 042-044 (`backend/api/routes/teamwork_integration.py`,
`backend/infra/repositories/teamwork_integration_repo.py`, `backend/infra/models/teamwork_integration_model.py`,
`backend/domain/services/entity_mapping_service.py`, `backend/domain/services/teamwork_task_migration_service.py`,
`backend/infra/importers/teamwork_connection_client.py`, `frontend/src/pages/TeamworkIntegrationPage.tsx`),
inspeccionado en esta sesión — no hay `NEEDS CLARIFICATION` pendiente.

## Decisión 1 — Persistencia del estado `Inactivo` (FR-001/002): columna `is_discarded`, no un enum sustituto

Hoy `_migration_status(mapping)` (`teamwork_integration.py:161-168`) deriva 3 estados **solo** de
`sytix_id`/`match_method` — sin `sytix_id` es `pending`, con `match_method="created_new"` es `created`, cualquier
otro `sytix_id` no nulo es `linked`. Un cuarto estado "descartado explícitamente por el usuario" no puede vivir
ahí: una fila nunca homologada (`sytix_id IS NULL`) debe poder marcarse Inactivo sin inventarle un `sytix_id`
falso.

- **Decisión**: nueva columna `is_discarded BOOLEAN NOT NULL DEFAULT false` en `teamwork_entity_mappings`
  (migración `056`). La derivación de estado se mueve a una función pura de Capa 1,
  `entity_mapping_service.derive_sync_status(mapping) -> Literal["pending","linked","created","inactive"]`:
  `is_discarded=True` → `"inactive"` (chequeo primero, independiente de `sytix_id`); si no, la misma lógica de 3
  valores ya existente. `_migration_status` en la ruta se elimina y se reemplaza por una llamada a esta función
  (consolida en Capa 1 una regla de negocio que hoy vive indebidamente en Capa 3 — corrige la deuda ya señalada
  en el mapeo de código de esta sesión).
- **Alternativas consideradas**:
  - Reemplazar los 3 estados derivados por una columna `sync_status` única de 4 valores — rechazado: requeriría
    backfill de todas las filas ya sincronizadas y duplicaría una fuente de verdad (`sytix_id`/`match_method`)
    que ya funciona correctamente para los otros 3 estados; más superficie de cambio sin beneficio.
  - Sobrecargar `match_method="inactive"` — rechazado: `match_method` significa "cómo se resolvió el match"
    (`email`/`external_id`/`name`/`manual`/`created_new`); usarlo también para "el usuario lo descartó" pierde
    la información de cómo se había resuelto antes si el usuario luego reactiva la fila (FR-006), y colisiona
    semánticamente con su propósito original.
- **Reactivación (FR-006)**: `set_discarded(mapping_id, discarded=False, ...)` simplemente vuelve `is_discarded`
  a `false` — el `sytix_id`/`match_method` (si existían antes de descartar, caso borde poco común pero posible
  si se descarta una fila que en teoría ya no debería estar en el pool de "pendientes elegibles") quedan
  intactos, así que reactivar no pierde ninguna homologación previa.
- **Preservación en resincronización (FR-007)**: `upsert_from_sync` (repo, líneas 100-126) nunca toca
  `is_discarded` — ni para escribirlo ni para leerlo como condición — así que una fila descartada permanece
  descartada en cualquier sincronización posterior sin cambio de código adicional, más allá de no incluir esa
  columna en el `UPDATE` de refresco.

## Decisión 2 — Acciones masivas de "Migrar como Nuevos" en los 4 catálogos (FR-008/009): generalizar `bulk-create-new`, no 4 endpoints nuevos

`POST /entity-mappings/bulk-create-new` (spec 044) hoy solo sirve a Personal: recibe `{mapping_ids, role_id,
client_id}` y llama `_create_new_person` fila por fila. El endpoint individual `POST
/entity-mappings/<id>/create-new` **ya** despacha por tipo vía `_CREATE_NEW_HANDLERS` (`company`→
`_create_new_client`, `project`→`_create_new_project`, `tasklist`→`_create_new_task_list`, `person`→
`_create_new_person`) — el mismo dispatcher sirve para generalizar el bulk sin duplicar reglas de negocio.

- **Decisión**: extender `bulk-create-new` para aceptar `mapping_ids` de **cualquier** `entity_type`. Por cada
  fila: resuelve `handler = _CREATE_NEW_HANDLERS[mapping.entity_type]`; si `mapping.entity_type == "person"`,
  exige `role_id` (y `client_id` si el rol es Usuario/cliente, igual que hoy); para `company`/`project`/
  `tasklist` invoca el handler sin esos campos (mismas validaciones de jerarquía ya vigentes en el endpoint
  individual — ej. Proyecto sin Empresa homologada se omite con motivo `parent_not_resolved`, igual criterio que
  spec 043). Fila ya vinculada (`sytix_id` no nulo) o descartada (`is_discarded=True`) → `skipped` con motivo
  `already_linked`/`discarded`, sin abortar el lote (FR-011).
- **Por qué no 4 endpoints separados**: los 4 handlers ya existen, están probados y no comparten forma de
  request distinta más allá de `role_id`/`client_id` (exclusivo de `person`) — un único endpoint con un cuerpo
  opcionalmente extendido evita 3 rutas nuevas casi idénticas (Principio VII, menor superficie de código).

## Decisión 3 — Acción masiva "Inactivar / Descartar Seleccionados" (FR-010): nuevos endpoints simétricos `bulk-discard`/`bulk-reactivate`

- **Decisión**: `POST /entity-mappings/bulk-discard` (`{mapping_ids}`) marca `is_discarded=true` en cada fila
  cuyo `sytix_id` sea `NULL` (solo se puede descartar una fila que todavía no tiene contraparte en SYTIX,
  consistente con la definición de Inactivo en FR-001 — "sin registro de SYTIX asociado"); una fila ya
  Homologada/Migrada se omite con motivo `already_linked` (FR-011). `POST /entity-mappings/bulk-reactivate`
  (`{mapping_ids}`) es la operación inversa, sin restricción de `sytix_id` (siempre válida sobre una fila
  `is_discarded=true`, Decisión 1). Ambos devuelven `{updated: [...], skipped: [{mapping_id, reason}]}`, mismo
  shape que `bulk-create-new` (consistencia de contrato dentro del mismo namespace).
- **Selección vacía o sin filas elegibles (FR-012)**: si `mapping_ids` está vacío, o las 2000 filas
  seleccionadas ya están todas en el estado destino, el endpoint devuelve `updated: []` con el conteo en 0 sin
  tocar la base de datos — el frontend interpreta esa respuesta para mostrar "nada que hacer" en vez de un error.

## Decisión 4 — Pestañas de filtro por estado en los 4 Grids (FR-003/005): client-side, sin endpoint nuevo

Mismo criterio que las decisiones 2/3 de research.md de spec 044: cada fila ya viaja completa al cliente desde
`GET /entity-mappings` (sin paginación server-side, `teamwork_integration_repo.py:69-77`), y la UI ya filtra
client-side por Cliente/Proyecto/correo.

- **Decisión**: `Tabs` (o `Segmented`) sobre el `sync_status` ya calculado por fila (ahora expuesto por el
  backend como parte de la serialización de `GET /entity-mappings`, ver Decisión 1) — `Todos` no aplica ningún
  filtro adicional; las otras 4 pestañas filtran el array `mappings` ya cargado en memoria. Se combina con los
  filtros de Cliente/Proyecto/correo existentes sin interferir entre sí (AND lógico).
- **Alternativa rechazada**: agregar `status` como query param server-side — igual razón que spec 044 Decisión
  3: no hay paginación server-side hoy, así que filtrar en el cliente da el mismo resultado con cero cambios de
  contrato.

## Decisión 5 — Extracción ampliada de metadatos (FR-013 a FR-016): columna `teamwork_metadata` JSONB, no columnas por campo

Los campos pedidos varían por tipo de entidad (4 para Empresa, 2 para Persona, 2 para Proyecto/Lista) y ninguno
tiene hoy dónde vivir en `EntityMappingModel`.

- **Decisión**: una columna `teamwork_metadata JSONB NULL` (migración `056`, junto con `is_discarded`) que
  guarda un diccionario libre por fila, poblado según `entity_type`:
  - `company`: `{"country", "address", "domain", "phone"}`
  - `person`: `{"job_title", "timezone"}` (Cargo/Zona horaria — Correo y Compañía ya cubiertos por columnas
    propias de specs 043/044, no se duplican acá)
  - `project` / `tasklist`: `{"description", "status"}` (`status` con valores `"active"`/`"archived"`)
  - Un campo no informado en el origen se omite de ese diccionario (no se escribe `null` explícito) — el
    frontend interpreta la ausencia de la clave como "No informado" (FR-016), sin distinguir de un error.
- **Por qué JSONB y no columnas dedicadas**: 8 campos repartidos en 4 tipos de entidad implicarían columnas
  mayormente `NULL` para los otros 3 tipos en cada fila (esparcidad alta) y una migración nueva cada vez que
  Teamwork exponga un campo adicional útil; JSONB evita ambos problemas y es nativo de PostgreSQL/SQLAlchemy ya
  usado en el proyecto (`sqlalchemy.dialects.postgresql`, ya importado en el mismo archivo del modelo para
  `UUID`) — sin dependencia nueva.
- **Refresco en cada sincronización**: `upsert_from_sync` gana un parámetro opcional `metadata: dict | None`
  que se reescribe en cada sync (igual criterio que `teamwork_name`, líneas 106-108 del repo hoy) — a diferencia
  de `is_discarded`/`sytix_id`, que **no** se tocan en el resync.
- **Extracción en `_fetch_entity`**: se extiende el dict-comprehension por rama (`company`/`person`/`project`/
  `tasklist`) para incluir los campos nuevos, contra los nombres de campo documentados en la API v3 oficial de
  Teamwork — sin smoke-test contra una cuenta real disponible en este entorno (mismo caso ya documentado en
  specs 041-044); se valida con un mock de `requests` de 5 a 10 filas (Principio VII).
- **Alcance de persistencia**: exclusivamente dentro de `teamwork_entity_mappings` — no se agrega ninguna
  columna a `clients`/`projects`/`task_lists`/`users` ni se toca ningún repositorio de esas tablas (spec.md §
  Assumptions, coherente con el alcance de esta sesión).

## Decisión 6 — Rango de fechas del importador (FR-018): 2 `<input type="date">` nativos + `date-fns`, no `DatePicker.RangePicker`

El proyecto no usa hoy ningún selector de rango de fechas (`grep` sin resultados en todo `frontend/src`).
`DatePicker.RangePicker` de AntD5 requiere internamente `dayjs` como su motor de fecha — la hipótesis inicial
de esta decisión era que, al venir empaquetado como dependencia transitiva de `antd`, se podía usar sin
declarar nada nuevo en `package.json`. **Verificado directamente en el `node_modules` real del contenedor
frontend durante la implementación**: `dayjs` no tiene un directorio propio en `node_modules/dayjs` (pnpm en
modo estricto solo lo deja accesible dentro de `node_modules/.pnpm/dayjs@.../`, aislado de cualquier `import`
directo del código de la aplicación) — un `import dayjs from 'dayjs'` en `TeamworkTaskImporterPage.tsx`
habría fallado en build/tipos pese a que `antd` sí puede resolverlo internamente (su propio `node_modules`
anidado sí lo ve).

- **Decisión corregida**: usar 2 elementos `<input type="date">` nativos (sin ningún componente de AntD5 para
  esto) para "Fecha Inicio"/"Fecha Fin", cuyo valor ya es un string `YYYY-MM-DD` nativo del navegador — exactamente
  el formato que espera `POST .../task-imports/preview|confirm` (contracts/api.md), sin conversión alguna. El
  valor por defecto (mes en curso, FR-018) se calcula con `date-fns` ya aprobado (`startOfMonth`, `endOfMonth`,
  `format(..., 'yyyy-MM-dd')`), consistente con el resto de la aplicación. Cero dependencias nuevas, ninguna
  transitiva mal resuelta.
- **Alternativa rechazada (la original de este documento)**: `DatePicker.RangePicker` de `antd` — inviable tal
  como estaba planteada, ver hallazgo de verificación arriba; usarla igual habría exigido agregar `dayjs` como
  dependencia directa nueva de `package.json`, lo que sí requeriría aprobación explícita de gobernanza
  (Principio V) que esta sesión no tiene motivo suficiente para pedir cuando 2 inputs nativos + `date-fns`
  resuelven el mismo requisito sin ningún costo adicional.

## Decisión 7 — Centro Independiente de Importación de Tareas (FR-017 a FR-025): módulo nuevo, reutiliza `classify_task` sin modificarlo

`POST /sync/tasks` (spec 044) migra el universo completo de tareas del sitio sin filtros ni paso de
prevalidación — apropiado para una migración inicial masiva, pero no para segmentar por Cliente/Proyecto/fecha
ni para mostrarle al usuario, antes de ejecutar, cuántas tareas quedarían bloqueadas y por qué.

- **Decisión de estructura**: archivo de ruta nuevo `backend/api/routes/teamwork_task_imports.py` (namespace
  Flask-RESTX independiente, `path="/api/teamwork-integration/task-imports"`, mismo permiso
  `teamwork_integration:operate`) + servicio de dominio nuevo `backend/domain/services/teamwork_task_import_service.py`
  (Capa 1 pura, sin imports de Flask/SQLAlchemy/`requests`) — **ninguno de los dos modifica**
  `teamwork_task_migration_service.py` ni `teamwork_integration.py`'s `/sync/tasks`; el nuevo servicio
  **importa y reutiliza** `classify_task`/`TeamworkTaskRow` del módulo existente (spec 044) para el chequeo base
  de Proyecto/Lista, igual criterio de aislamiento que specs 043/044 aplicaron entre sí.
- **Filtro Cliente/Proyecto(s) (FR-018/019)**: los selectores son **SYTIX-side** (reutilizan `projectService.list({client_id})`
  ya usado en el resto de la app para la cascada Cliente→Proyecto, ej. `TicketsPage.tsx`), no un selector crudo
  de Proyectos de Teamwork — un Proyecto solo puede producir tareas `ready` si ya está Homologado/Migrado, así
  que anclar el filtro al catálogo SYTIX evita mostrarle al usuario proyectos de Teamwork irrelevantes. La Capa
  3 resuelve cada `project_id` de SYTIX seleccionado a su `teamwork_id` correspondiente vía un método de lectura
  nuevo en el repo, `get_teamwork_ids_for_sytix("project", sytix_ids)` (reverse-lookup sobre
  `teamwork_entity_mappings`, sin cambio de esquema adicional al de la Decisión 1/5), y usa ese conjunto de
  `teamwork_id`s para filtrar el resultado de `fetch_tasks()` por `task.project_id`.
- **Filtro Lista de Tareas opcional**: reutiliza `GET /entity-mappings?entity_type=tasklist`, cuyas filas ya
  traen `parent_context.project_id` resuelto (spec 044, Decisión 3 de su research.md) — el frontend ofrece como
  opciones solo las Listas cuyo `parent_context.project_id` esté entre los Proyectos ya seleccionados, sin
  endpoint nuevo; al elegir una, se envía su `teamwork_id` crudo como filtro adicional sobre `task.tasklist_id`.
- **Filtro de fechas (FR-018)**: `fetch_tasks()` (spec 044) hoy no extrae fechas — se le agregan `created_at` y
  `due_date` (mismos nombres de campo v3 ya usados por el resto del archivo, sin smoke-test posible, igual
  advertencia que Decisión 5). El filtro se aplica sobre `due_date` si está presente, si no sobre `created_at`
  (el más confiable de los dos para tareas sin vencimiento definido) — **no** se persiste en el Ticket creado
  (mismo criterio ya establecido en spec 041: Start/Due date quedan fuera del modelo de `tickets`, el motor de
  SLA no las usa). Rango por defecto: mes en curso si el usuario no especifica (FR-018).
- **Clasificación estricta ready/blocked (US4, AC3)**: a diferencia de `classify_task` (que **no** bloquea por
  asignado sin homologar — crea la Tarea sin asignar, spec 044), el spec de esta feature exige que el
  diagnóstico del importador trate un Usuario asignado sin homologar como **bloqueante** ("cantidad de tareas
  listas... cuyos... usuarios ya están Homologados", spec.md US4). `teamwork_task_import_service.classify_task_for_import`
  compone así, sin tocar el módulo original: (1) llama `classify_task(raw, resolution)` → si ya viene `skipped`,
  se mantiene con su motivo (`project_not_mapped`/`tasklist_not_mapped`); (2) si viene `ready` mismo así, pero
  `raw.assignee_id` no es `None` y `resolution.assignee_resource_id` es `None`, se reclasifica como `blocked`
  con motivo nuevo `assignee_not_mapped` (exclusivo de este módulo); (3) una tarea sin ningún asignado en
  Teamwork nunca cae en este motivo (nada que homologar). Esta es una divergencia de negocio deliberada y
  documentada del comportamiento permisivo de `/sync/tasks` — no una modificación de ese endpoint.
- **Enlace de resolución (FR-021)**: cada fila bloqueada expone `{entity_type, teamwork_id}` de la homologación
  faltante (Proyecto/Lista/Persona según el motivo); el frontend navega a `/integraciones/teamwork` pasando
  `state: {entityType, teamworkId}` vía React Router — la página ya existente lee ese `state` al montar para
  preseleccionar el filtro `mappingFilter` correspondiente y aplicar una búsqueda por `teamwork_id` sobre las
  filas ya cargadas (sin nuevo query param de URL, sin cambio de contrato del endpoint `GET /entity-mappings`).
- **Preview sin escritura, confirm re-clasifica en el momento (FR-020/022)**: ambos endpoints
  (`POST .../task-imports/preview` y `POST .../task-imports/confirm`) reciben el **mismo** cuerpo de filtros y
  ejecutan la misma clasificación; `preview` solo la devuelve, `confirm` además ejecuta
  `TicketRepository.upsert_from_import(...)` (spec 041, sin modificar) sobre las filas `ready` resultantes de
  volver a clasificar en el momento de la confirmación (no sobre una lista congelada del `preview` anterior) —
  evita servir un lote desactualizado si, entre preview y confirm, el usuario homologa la fila que faltaba
  desde otra pestaña. Segunda pasada de resolución de Subtarea→Tarea padre idéntica a la ya usada en
  `ticket_imports.py`/`sync/tasks` (líneas 248-258 / 816-824 respectivamente).
- **Hipervínculo y deduplicación (FR-023/024)**: mismo mecanismo que `/sync/tasks` — `external_reference_id` +
  `f"{site_url}/app/tasks/{teamwork_id}"`, upsert por ese identificador.
- **Endpoint no reemplazado**: `POST /sync/tasks` permanece intacto, sin cambios de contrato ni de
  comportamiento — el nuevo módulo es 100% aditivo (spec.md § Assumptions).

## Resumen de impacto en dependencias y esquema

- **Dependencias nuevas**: ninguna (`dayjs` vía `antd` ya empaquetado, Decisión 6).
- **Migraciones nuevas**: 1 (`056`, aditiva — `is_discarded BOOLEAN NOT NULL DEFAULT false`,
  `teamwork_metadata JSONB NULL`, ambas en `teamwork_entity_mappings`, sin tabla nueva).
- **Permisos nuevos**: ninguno (todo bajo `teamwork_integration:operate` ya existente).
- **Archivos de specs previas tocados**: ninguno modificado — `ticket_imports.py`, `teamwork_api_client.py`,
  `teamwork_import_service.py`, `teamwork_task_migration_service.py` quedan intactos (solo se importa/reutiliza
  `classify_task` desde el nuevo módulo, sin editar ese archivo), mismo criterio que specs 042-044.
