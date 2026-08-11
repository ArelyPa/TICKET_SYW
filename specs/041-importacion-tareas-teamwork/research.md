# Research: Migración e Importación de Tareas desde Teamwork

## Decisión 1 — Columnas nuevas y alcance exacto de la migración

**Decisión**: Una única migración Alembic (`053_ticket_external_reference.py`) agrega
`external_reference_id` (`Text`, nullable) y `external_reference_url` (`Text`, nullable) a la
tabla `tickets` existente, con un índice sobre `external_reference_id` (usado por el upsert de
FR-009). La misma migración inserta el permiso nuevo `ticket_imports:run` (Admin, Coordinador)
siguiendo el patrón ya usado por la migración `048` (una migración puede combinar un cambio de
esquema puntual con su alta de permiso, cuando ambos pertenecen a la misma feature).

**Rationale**: `tickets` es la única tabla que respalda tanto "Tickets" como "Tareas" (Nivel 4/5
del modelo de datos, ver `ticket_model.py` — `ticket_type`, `list_id`, `parent_task_id` ya
conviven en la misma fila), así que no hace falta tocar más de una tabla. No se crea una tabla de
staging/preview ni una tabla de auditoría de importaciones (ver Decisión 3) — respeta la
instrucción explícita de esta sesión de limitar la migración a los campos de referencia.

**Alternatives considered**: Tabla `external_references` separada (1:1 con `tickets`) — rechazada
por ser una normalización innecesaria para 2 columnas opcionales que siempre se leen junto con el
ticket (mismo patrón ya usado para otros campos opcionales de `tickets`, ej. `resolution_type_id`).

## Decisión 2 — Vista previa sin tabla de staging

**Decisión**: La vista previa (US1/US3) es puramente en memoria/respuesta HTTP: el endpoint de
preview parsea el archivo (o la respuesta de la API v3) y devuelve el array completo de filas
resueltas al frontend, sin persistir nada. El endpoint de confirmación recibe de vuelta ese mismo
array (ya editado/filtrado por el usuario en el navegador, ej. filas excluidas) y recién ahí
inserta/actualiza en `tickets`.

**Rationale**: Evita crear una tabla nueva de staging (fuera del alcance autorizado de esta
sesión, ver directriz de "Limitación del Código"). El volumen esperado (reportes de Teamwork,
cientos de filas) cabe cómodo en una respuesta JSON; no hay necesidad de paginar la vista previa
en el servidor.

**Alternatives considered**: Persistir un "import batch" en una tabla intermedia antes de
confirmar — rechazada por requerir una migración adicional no autorizada en el alcance de esta
sesión.

## Decisión 3 — Trazabilidad de la ejecución de importación (FR-015) sin tabla nueva

**Decisión**: FR-015 se satisface con el resumen (creados/actualizados/con error) que devuelve el
propio endpoint de confirmación en su respuesta HTTP — visible de inmediato en la pantalla de
importación tras confirmar — más el log de aplicación estándar del backend (usuario, fecha,
origen, conteos). No se crea una tabla de auditoría de importaciones dedicada.

**Rationale**: Igual que la Decisión 2, una tabla de historial de importaciones sería una segunda
tabla nueva fuera del alcance explícitamente autorizado ("únicamente la migración... con los
nuevos campos de referencia"). El resultado inmediato en pantalla ya es "consultable" por quien
ejecutó la importación, que es el único actor con permiso para hacerlo.

**Alternatives considered**: Tabla `ticket_import_runs` — más completa (permitiría consultar
importaciones pasadas desde cualquier sesión), pero requiere una migración de esquema adicional
no solicitada; queda fuera de alcance de esta feature.

## Decisión 4 — Parser de Excel/CSV y cliente API v3: sin dependencias nuevas

**Decisión**: El parser de archivo usa `openpyxl` (ya aprobado y en `requirements.txt` desde spec
034, export de Reportes) para `.xlsx` y el módulo estándar `csv` de Python para `.csv` — mismo
archivo de servicio decide el parser según la extensión. El cliente de la API v3 de Teamwork usa
`requests` (ya en `requirements.txt`). Ninguna dependencia nueva a `backend/requirements.txt`
(Principio V).

**Rationale**: Ambas librerías ya están aprobadas y en uso; agregar `pandas` u otra librería de
importación sería una dependencia no aprobada y no justificada para este alcance.

**Alternatives considered**: `pandas.read_excel`/`read_csv` — más cómodo para mapeo tabular, pero
introduce una dependencia nueva no aprobada (Principio V) solo para un mapeo de columnas fijo que
`openpyxl`/`csv` resuelven sin problema.

## Decisión 5 — Homologación por capas (Clean Architecture)

**Decisión**:
- **Capa 1** (`backend/domain/services/teamwork_import_service.py`): lógica pura de mapeo y
  validación de una fila ya extraída a `dict` (resolución de Cliente/Proyecto/Lista de
  Tareas/Asignado/Solicitante contra colecciones ya cargadas, conversión de minutos a horas,
  construcción de `external_reference_url`, detección de duplicados/errores de fila). Sin imports
  de Flask/SQLAlchemy/`openpyxl`/`requests`.
- **Capa 2** (`backend/infra/importers/`): `teamwork_file_parser.py` (lee `.xlsx`/`.csv` y emite
  filas `dict` crudas) y `teamwork_api_client.py` (llama a
  `GET /projects/api/v3/tasks.json` de Teamwork y emite las mismas filas `dict` crudas,
  homologando nombres de campo a los mismos que usa el parser de archivo para que Capa 1 sea
  agnóstica al origen).
- **Capa 3** (`backend/api/routes/ticket_imports.py`, namespace nuevo `ticket_imports`): expone
  `POST /api/ticket-imports/preview` (`multipart/form-data` con `file`, o `{"source": "api"}`
  para API v3) y `POST /api/ticket-imports/confirm` (recibe las filas ya revisadas). Ambos
  protegidos por `require_permission("ticket_imports", "run")`.

**Rationale**: Mismo patrón de tres capas ya usado en toda la base de código (Principio II); el
mismo servicio de dominio sirve a ambas vías de entrada (US1 y US3) sin duplicar reglas de mapeo.

## Decisión 6 — Asignación de Tickets/Tareas a Coordinador

**Decisión**:
- `AssignmentService.ASSIGN_MODE_REQUIRED_ROLE["resolver"]` pasa de `"Resolutor"` (string) a un
  conjunto `{"Resolutor", "Coordinador"}`; la validación cambia de igualdad a pertenencia. El modo
  `"pre_analysis"` (QM) no cambia.
- Nuevo endpoint `GET /api/tickets/coordinador-candidates` (mismo permiso `tickets:assign`),
  espejo exacto de `GET /api/tickets/qm-candidates` (spec 033): lista usuarios con rol
  Coordinador por `UserRepository`, no por `resources` (un Coordinador puede no tener perfil de
  Recurso propio).
- `TicketAssign.post` (modo `resolver`) y `TicketReassign.post`: si `resource_repo.get_by_id
  (assignee_id)` no encuentra nada, se intenta resolver `assignee_id` como `user_id` de un
  usuario con rol Coordinador y se aprovisiona su Recurso con
  `ResourceRepository.get_or_create_for_user` (mismo mecanismo ya usado para QM en modo
  `pre_analysis`), antes de continuar con el flujo existente.
- Frontend: `useResourceCandidates` combina los Recursos activos (Resolutor, como hoy) con los
  candidatos de `coordinador-candidates`, distinguidos con una etiqueta de rol en
  `ResourceCandidateGrid`, en el panel de asignación inicial y en el modal de reasignación.

**Rationale**: Reutiliza exactamente el patrón ya validado en spec 033 para QM (rol sin perfil de
Recurso por defecto, candidatos listados por rol, aprovisionamiento perezoso al asignar) en vez de
introducir un mecanismo nuevo — mínimo código, cero tablas nuevas, y cumple la instrucción de
"no refactorizar la lógica de negocio general" porque solo añade una alternativa de resolución
sin tocar el resto de `AssignmentService`/`ReassignmentService`/FSM. El registro de reasignación
"resolutor anterior ➡️ nuevo resolutor" (spec 023) no requiere cambios: ya opera sobre
`resource_id` sin importar el rol del usuario dueño de ese Recurso.

**Alternatives considered**: Nuevo modo `"coordinador"` en `ASSIGN_MODES`/
`ASSIGN_MODE_REQUIRED_ROLE` — rechazado porque el ticket sigue yendo al mismo estado FSM
(`contacto`) que con un Resolutor; no hay una transición ni un tipo de comentario distintos que
justifiquen un modo nuevo, solo el rol permitido cambia.

## Decisión 7 — Homologación de "Assigned to"/"Created by" contra usuarios de SYTIX

**Decisión**: La resolución busca primero coincidencia exacta de correo (si el reporte trae
correo) y, si no, coincidencia exacta de nombre completo contra `users.username` /
`resources.full_name`, sin fuzzy-matching. Sin coincidencia única, la fila queda marcada como
pendiente de resolución en la vista previa (FR-003) — nunca bloquea el resto del archivo.

**Rationale**: Evita falsos positivos de un matching aproximado (asignar la tarea a la persona
equivocada) — más seguro fallar hacia "requiere revisión manual" que adivinar.

**Alternatives considered**: Matching aproximado (Levenshtein/fuzzy) — rechazado por el riesgo de
asignación incorrecta sin que el usuario lo note en un archivo de cientos de filas.

## Decisión 8 — Pantalla de importación

**Decisión**: Nueva página `frontend/src/pages/TicketImportsPage.tsx`, ruta `/importacion-tareas`,
ítem de navegación nuevo bajo el grupo "Maestros" (mismo patrón visual que "Catálogos"), visible
solo con el permiso `ticket_imports:run` (Admin/Coordinador). Reutiliza el componente `Upload` de
Ant Design (ya usado en `ClientsPage.tsx`/`CommentComposer.tsx`) para el archivo, y una `Table`
con columnas de estado (lista/pendiente/error) para la vista previa, igual al patrón ya usado por
`ReportsPage.tsx` para tablas de datos dinámicos.

**Rationale**: Reutiliza componentes y patrones de UI ya aprobados (Principio V/VII) sin
introducir una librería de UI nueva.

## Decisión 9 — Resolución exacta de `Created by` (`created_by` vs. `client_contact_id`)

**Decisión**: `tickets.created_by` es `NOT NULL` (FK a `users.id`); `client_contact_id` es
opcional. La fila importada resuelve `Created by` en este orden:
1. Coincidencia exacta contra un Recurso interno (`ResourceRepository.get_by_full_name`/
   `get_by_email`, Decisión 7) → `created_by` = el `user_id` de ese Recurso;
   `requester_client_contact_id` queda `None`.
2. Si no hay match interno, coincidencia exacta contra un Usuario/cliente del Cliente ya resuelto
   (`ClientContactRepository.get_by_name_or_email(client_id, value)`) → `requester_client_contact_id`
   = ese contacto; `created_by` cae al usuario que ejecuta la importación (Coordinador/Admin),
   igual que cualquier otra creación administrativa en SYTIX.
3. Si ninguno resuelve, la fila queda `needs_review` (issue `creator_not_found`); al confirmarse
   igualmente `created_by` cae al usuario que ejecuta la importación y `client_contact_id` queda
   `None`.

**Rationale**: `created_by` nunca puede quedar nulo (constraint de base de datos ya existente);
el ejecutor de la importación es siempre un actor válido para asumir ese rol cuando el
"solicitante" real no se puede identificar con certeza — mismo principio que Decisión 7 (fallar
hacia revisión manual antes que adivinar).
