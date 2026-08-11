# Research: Integración API Teamwork v3, Homologación de Catálogos e Importador de Tiempos Mensuales

## Contexto de código existente relevante

- **spec 041 (`backend/infra/importers/teamwork_api_client.py`, `teamwork_file_parser.py`,
  `backend/domain/services/teamwork_import_service.py`, `backend/api/routes/ticket_imports.py`)**
  ya implementó la importación de **tareas** de Teamwork (no tiempos) con un patrón de
  preview→confirm sin persistencia intermedia que esta feature replica. Su cliente API usa
  credenciales por variable de entorno (`TEAMWORK_DOMAIN`/`TEAMWORK_API_TOKEN`), no configurables
  desde la UI — esta feature necesita credenciales editables por Admin desde una pantalla, por lo
  que **no** se reutiliza ese cliente ni sus variables de entorno (ver Decisión 1).
- `tickets.external_reference_id`/`external_reference_url` (migración 053, spec 041) ya existen —
  la resolución de la columna `Task`/`Task ID` del reporte de tiempos puede intentar primero un
  lookup exacto por `TicketRepository.get_by_external_reference_id` antes de caer a nombre/código,
  igual que ya hace `ticket_imports.py` para el padre de una subtarea.
- `ResourceModel.user_id` es **nullable** (`backend/infra/models/resource_model.py:41`) — un
  Recurso puede existir sin cuenta de usuario/login. Esto habilita FR-014 (crear solo el registro
  de referencia, sin acceso) sin tocar el modelo.
- `work_sessions` (`backend/infra/models/work_session_model.py`) ya tiene `note` (Descripción) y
  `off_hours`; solo falta una columna para el `ID` externo de Teamwork (idempotencia, FR-013).
- El patrón de cifrado app-level ya usado para `client_access`/VPN (`_encrypt`/`_decrypt` en
  `backend/infra/models/client_model.py`) se reutiliza para el token de API de Teamwork — mismo
  mecanismo, ninguna dependencia nueva.
- El patrón de permiso de único-uso vía migración de datos (`ticket_imports:run`, migración 053;
  `manage_skills_all_internal_roles`, migración 051) se reutiliza para los 2 permisos nuevos de
  esta feature.

## Decisiones

**Decisión 1 — Cliente de conexión propio, no reutilizar `teamwork_api_client.py` de spec 041**
Se crea `backend/infra/importers/teamwork_connection_client.py`, un cliente separado que recibe
`site_url`/`api_token` como parámetros (no lee variables de entorno) para probar conexión y
sincronizar catálogos. `teamwork_api_client.py` (spec 041, tareas) queda intacto — alcance de
sesión (Principio VII): no se refactoriza un módulo de otra feature ya implementada.
- Alternativas consideradas: extender `teamwork_api_client.py` para aceptar credenciales
  dinámicas — rechazada porque mezclaría dos mecanismos de configuración (env vars vs. DB) en un
  mismo módulo y violaría el aislamiento de sesión pedido explícitamente por el usuario.

**Decisión 2 — Sin tabla de staging por fila para tiempos; mismo patrón preview→confirm sin
persistencia intermedia que spec 041**
`POST /api/time-imports/preview` procesa el archivo en memoria y responde filas clasificadas
(válida/conflicto) sin guardar nada. `POST /api/time-imports/confirm` recibe esas mismas filas ya
resueltas por el usuario (acción por fila: `resolve` con `resource_id`/`project_id`/etc., `create`,
u `omit`) y en esa única llamada crea/actualiza `WorkSession` y, si aplica, los registros de
referencia nuevos (Recurso/Cliente).
- Alternativas consideradas: tabla de staging (`time_import_rows`) para persistir el archivo
  cargado entre preview y confirm — rechazada por ser el mismo caso ya resuelto en spec 041
  (research.md Decisión 1-3 de esa feature) sin necesidad real, y por consumo de tokens/alcance
  (Principio VII).

**Decisión 3 — Tabla única `teamwork_entity_mappings` para homologación (todas las entidades)**
Una sola tabla con `entity_type` (`company`/`project`/`person`/`tasklist`) discrimina el tipo, en
vez de 4 tablas paralelas. La sincronización de catálogos (US4) upserta filas ahí (por
`entity_type` + `teamwork_id`) con `sytix_id=NULL` hasta que se homologan; la pantalla de
Homologación (US5) es sobre esta misma tabla. El importador de tiempos (US2/US3) también consulta
esta tabla para resolver `Who`/`Company`/`Project` antes de pedirle al usuario que resuelva el
conflicto manualmente — así una homologación guardada se reutiliza automáticamente (FR-007).
- Alternativas consideradas: 4 tablas específicas (una por tipo de entidad) — rechazada por
  duplicar columnas idénticas sin beneficio real, y por inflar el número de tablas/migraciones
  que Principio VII pide minimizar.

**Decisión 4 — Auto-creación (FR-011.b/FR-014) limitada a Usuario (`Who`→Recurso sin login) y
Cliente (`Company`); Proyecto y Tarea/Ticket solo se homologan o se omiten, nunca se crean
automáticamente**
El enunciado original ("crear automáticamente el usuario/cliente faltante") solo nombra esas dos
entidades. Crear un Proyecto o un Ticket/Tarea automáticamente exigiría datos que el reporte de
tiempos no trae (SLA, fechas, tipo de registro) y generaría entidades de negocio incompletas —
fuera del alcance de un importador de tiempos. Si `Project` o `Task` no se encuentran, la fila
queda en conflicto con las opciones (a) homologar a uno existente o (c) omitir únicamente.
- Alternativas consideradas: extender la creación automática a Proyecto/Tarea — rechazada por
  requerir campos obligatorios (SLA, tipo de registro) sin origen en el archivo de tiempos, y por
  el riesgo de crear Tickets "fantasma" sin flujo FSM real detrás.

**Decisión 5 — Fuente de verdad de duración: `Decimal hours` > `Hours`+`Minutes` > error**
Si el archivo trae `Decimal hours`, se usa esa columna (ya viene en horas decimales, se convierte a
minutos redondeando). Si no viene, se usa `Hours`+`Minutes`. Si ninguna de las dos formas está
presente o son inconsistentes entre sí, la fila se marca como conflicto de datos (no se adivina).
- Alternativas consideradas: sumar las tres columnas o promediarlas — rechazada, generaría
  duraciones incorrectas silenciosamente (contradice Edge Cases del spec).

**Decisión 6 — Permisos: `teamwork_integration:manage` (solo Admin) para credenciales de
conexión + `teamwork_integration:operate` (Admin, Coordinador) para sincronizar catálogos,
homologar entidades e importar tiempos**
Refleja la resolución de `/speckit-clarify` con el usuario (spec.md FR-002): edición de
credenciales restringida a Admin; el resto del módulo (uso día a día) abierto también a
Coordinador, igual que `ticket_imports:run` en spec 041. Ambos permisos se crean en la misma
migración que las tablas nuevas (patrón ya usado en migraciones 048/051/052/053).

**Decisión 7 — Sin smoke-test contra una cuenta real de Teamwork en este entorno**
Mismo caso ya documentado y aceptado en spec 041 (sin credenciales de una cuenta real disponibles
en este entorno de desarrollo). El cliente de conexión y la sincronización de catálogos se
implementan y prueban con `requests` mockeado, contra la forma de respuesta documentada en
apidocs.teamwork.com para `companies.json`/`projects.json`/`people.json`/`tasklists.json`
(estilo JSON:API, igual que `tasks.json` ya verificado en spec 041).

## Sin NEEDS CLARIFICATION pendientes

Los 2 marcadores originales del spec (alcance de acceso, alcance de auto-creación) se resolvieron
con el usuario en `/speckit-specify` y quedan reflejados en spec.md (FR-002, FR-014) y en la
Decisión 4 y 6 de este documento.
