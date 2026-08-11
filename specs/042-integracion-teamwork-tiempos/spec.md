# Feature Specification: Integración API Teamwork v3, Homologación de Catálogos e Importador de Tiempos Mensuales

**Feature Branch**: `042-integracion-teamwork-tiempos`

**Created**: 2026-08-09

**Status**: Draft

**Input**: User description: "Módulo de Integración API Teamwork v3, Homologación de Catálogos e Importador de Tiempos Mensuales — pantalla de configuración de conexión (URL del sitio, token, entorno) con prueba de conexión; sincronización de catálogos (Clientes/Empresas, Proyectos, Personal, Listas de Tareas) vía API v3; interfaz de homologación de entidades con automapeo (correo/ID externo/nombre exacto) y mapeo manual; importador de reportes de tiempos mensuales (CSV/Excel) con prevalidación, resumen de registros válidos/con conflicto y pantalla de resolución (homologar/crear/omitir) antes de confirmar la carga."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configurar y Probar Conexión con Teamwork v3 (Priority: P1)

Un Administrador abre **Administración / Integraciones / Teamwork**, ingresa la URL del sitio Teamwork, el token de API y selecciona el entorno (Test o Producción), guarda la configuración y usa "Probar Conexión" para confirmar que las credenciales son válidas antes de depender de ellas en cualquier sincronización o importación.

**Why this priority**: Es el prerrequisito de todo lo demás — sin una conexión configurada y verificada no tiene sentido sincronizar catálogos, y es además la única pieza que involucra credenciales sensibles, por lo que debe quedar validada primero.

**Independent Test**: Puede probarse de forma aislada guardando una configuración con credenciales inválidas y verificando que "Probar Conexión" muestra el badge de error, y luego con credenciales válidas verificando el badge de éxito — sin necesidad de ejecutar ninguna sincronización real.

**Acceptance Scenarios**:

1. **Given** un Administrador en la pantalla de Integraciones Teamwork sin configuración previa, **When** completa URL del sitio, token y entorno y guarda, **Then** la configuración queda persistida y visible al recargar la pantalla, sin exponer el token en texto plano en la interfaz.
2. **Given** una configuración guardada con credenciales válidas, **When** el Administrador presiona "Probar Conexión", **Then** el sistema consulta la API v3 de Teamwork y muestra un badge de "Conexión exitosa".
3. **Given** una configuración guardada con credenciales inválidas o vencidas, **When** el Administrador presiona "Probar Conexión", **Then** el sistema muestra un badge de "Error de autenticación" con un mensaje que distingue error de credenciales de error de red/sitio no encontrado.

---

### User Story 2 - Importar y Validar Reporte Mensual de Tiempos (Priority: P1)

Un Coordinador o Administrador sube un archivo CSV/Excel de registro de tiempos mensuales exportado de Teamwork. El sistema procesa el archivo y muestra un resumen de validación separando filas válidas (usuario, proyecto y tarea reconocidos o ya homologados) de filas con conflicto, sin guardar nada todavía.

**Why this priority**: Es el objetivo de negocio principal de la feature — cerrar reportes mensuales de tiempo sin tener que cargar cada registro manualmente — y es independiente de si la integración de API/catálogos está configurada, porque trabaja sobre el archivo exportado.

**Independent Test**: Puede probarse subiendo un archivo de prueba reducido (5-10 filas, con al menos una fila cuyo usuario o proyecto no exista en SYTIX) y verificando que el resumen muestra el conteo correcto de válidas vs. con conflicto, sin que se cree ningún registro de tiempo todavía.

**Acceptance Scenarios**:

1. **Given** un archivo con columnas `ID`, `Date/time`, `Hours`/`Minutes`/`Decimal hours`, `Who`, `Company`, `Project`, `Task`, `Description`, **When** el Coordinador lo carga en la pantalla de importación, **Then** el sistema muestra el total de filas leídas, cuántas son válidas y cuántas tienen conflicto, antes de cualquier confirmación.
2. **Given** una fila cuyo campo `Description` viene vacío, **When** se prevalida el archivo, **Then** esa fila se marca como inválida/con conflicto (la descripción es obligatoria) y no se cuenta como válida.
3. **Given** una fila cuyo `Who` coincide por nombre exacto o por una homologación ya guardada con un Recurso de SYTIX, **When** se prevalida el archivo, **Then** esa fila se clasifica como válida.

---

### User Story 3 - Resolver Conflictos de Importación y Confirmar Carga (Priority: P1)

Sobre el mismo resumen de validación, el Coordinador/Administrador resuelve cada fila con conflicto (usuario o proyecto no reconocido) eligiendo homologarla a un registro existente de SYTIX, crear el registro faltante, u omitir la fila, y finalmente confirma la carga para que los registros de tiempo válidos y resueltos se guarden.

**Why this priority**: Sin esta resolución, un archivo mensual con cualquier fila no reconocida (el caso más común en la práctica, según la feature 041 ya validada) nunca podría completarse — es lo que hace utilizable a la importación.

**Independent Test**: Puede probarse retomando el resumen de validación de una carga con filas en conflicto, resolviendo una por homologación manual, otra creando el registro faltante y otra omitiéndola, confirmando la carga y verificando que solo se crean registros de tiempo para las filas válidas + homologadas + creadas (no para la omitida).

**Acceptance Scenarios**:

1. **Given** una fila con conflicto porque el `Who` no tiene coincidencia en SYTIX, **When** el usuario la homologa manualmente a un Recurso existente mediante un selector, **Then** la fila pasa a estar lista para confirmarse con ese Recurso asociado.
2. **Given** una fila con conflicto porque el `Company`/`Project` no existe en SYTIX, **When** el usuario elige "Crear" desde la misma vista, **Then** el sistema crea el registro faltante y lo asocia a la fila sin salir de la pantalla de importación.
3. **Given** filas ya resueltas (homologadas, creadas u omitidas) y filas válidas desde el inicio, **When** el usuario confirma la carga, **Then** el sistema crea un registro de tiempo por cada fila válida/homologada/creada, ninguno por las omitidas, y muestra un resumen final de cuántos se guardaron.
4. **Given** una fila cuyo `ID` (`external_time_id`) ya fue importado en una carga anterior, **When** se confirma la carga, **Then** el registro de tiempo existente se actualiza en vez de duplicarse.

---

### User Story 4 - Sincronizar Catálogos desde Teamwork (Priority: P2)

Con la conexión ya configurada y probada, un Administrador presiona los botones "Sincronizar Catálogos" para traer desde la API v3 de Teamwork las Empresas/Clientes, Proyectos, Personal y Listas de Tareas, dejándolos disponibles para homologar contra los catálogos de SYTIX.

**Why this priority**: Acelera la homologación (US5) y reduce el trabajo manual de las importaciones, pero el importador de tiempos (US2/US3) ya funciona sin esto mediante homologación manual fila por fila — por eso es P2, no bloqueante para el valor principal.

**Independent Test**: Puede probarse presionando "Sincronizar Catálogos" por cada uno de los 4 tipos de entidad con la conexión ya validada (US1) y verificando que la lista de entidades pendientes de homologar se actualiza con lo recibido de la API, sin modificar ningún catálogo de SYTIX todavía.

**Acceptance Scenarios**:

1. **Given** una conexión Teamwork válida, **When** el Administrador presiona "Sincronizar Catálogos" para Clientes/Empresas, **Then** el sistema consulta `companies.json` y muestra la lista resultante disponible para homologar.
2. **Given** una conexión sin probar o inválida, **When** el Administrador intenta sincronizar cualquier catálogo, **Then** el sistema bloquea la acción y muestra el mismo mensaje de error de conexión que en "Probar Conexión".
3. **Given** una sincronización ya ejecutada previamente, **When** se vuelve a ejecutar, **Then** la lista de entidades pendientes se actualiza (agrega nuevas, refleja cambios de nombre) sin duplicar entidades ya homologadas.

---

### User Story 5 - Homologación Manual de Entidades (Priority: P3)

Un Administrador abre la interfaz de Homologación de Entidades y ve una tabla comparativa entre las entidades traídas de Teamwork (US4) y las de SYTIX, con las coincidencias automáticas ya sugeridas (por correo, ID externo o nombre exacto) y la posibilidad de corregir manualmente cualquier fila mediante un selector.

**Why this priority**: Es la capa de refinamiento sobre la sincronización de catálogos (US4) — mejora la precisión de futuras importaciones pero no es necesaria para completar una carga de tiempos puntual, que ya puede resolverse fila por fila (US3).

**Independent Test**: Puede probarse con un conjunto de entidades sincronizadas donde algunas tienen coincidencia exacta por correo/nombre y otras no, verificando que el automapeo sugiere correctamente las primeras y deja las segundas para selección manual, y que guardar una homologación manual la deja disponible para las siguientes importaciones/sincronizaciones.

**Acceptance Scenarios**:

1. **Given** una entidad de Teamwork cuyo correo coincide exactamente con un usuario de SYTIX, **When** se abre la tabla de homologación, **Then** esa fila aparece premapeada automáticamente con esa coincidencia.
2. **Given** una entidad de Teamwork sin coincidencia automática, **When** el Administrador selecciona manualmente el registro de SYTIX correspondiente desde el dropdown, **Then** la homologación queda guardada y disponible para reutilizarse en la próxima sincronización o importación.
3. **Given** una homologación ya guardada, **When** el Administrador la cambia por otro registro de SYTIX, **Then** la nueva asociación reemplaza a la anterior sin dejar duplicados.

### Edge Cases

- ¿Qué ocurre si el archivo de tiempos mensual trae una fila con `Hours`, `Minutes` y `Decimal hours` simultáneamente y con valores inconsistentes entre sí? El sistema debe usar una única fuente de verdad documentada (`Decimal hours` si viene, si no `Hours`+`Minutes`) y no sumar las tres.
- ¿Qué ocurre si el token de Teamwork configurado deja de ser válido después de haber sido probado con éxito (revocado del lado de Teamwork)? La siguiente sincronización o "Probar Conexión" debe mostrar el error de autenticación, sin que la UI siga asumiendo que la conexión sigue vigente.
- ¿Qué ocurre si dos filas del mismo archivo mensual comparten el mismo `ID` (`external_time_id`) duplicado dentro del propio archivo? Debe marcarse como conflicto/alerta explícito, no procesarse silenciosamente dos veces.
- ¿Qué ocurre si una fila con conflicto se resuelve como "Omitir" pero el mismo `external_time_id` ya existía de una carga previa? Omitir no debe borrar ni tocar el registro existente.
- ¿Qué ocurre si se sube un archivo con una fila cuyo `Task`/`Task ID` no corresponde a ningún Ticket/Tarea de SYTIX? Se trata igual que un conflicto de Proyecto: alerta y opción de homologar/crear/omitir.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST proveer una pantalla de configuración en Administración / Integraciones / Teamwork con los campos URL del sitio, Token de API y Entorno (Test/Producción).
- **FR-002**: El sistema MUST almacenar el token de API de forma segura (nunca en texto plano visible en la interfaz una vez guardado). El acceso al módulo (sincronizar catálogos, homologar entidades, importar tiempos) MUST estar disponible para los roles Admin y Coordinador; la edición de las credenciales de conexión (URL del sitio/token/entorno) MUST quedar restringida solo a Admin.
- **FR-003**: El sistema MUST ofrecer un botón "Probar Conexión" que consulte la API v3 de Teamwork con las credenciales guardadas y MUST mostrar un badge visual distinguiendo éxito de error de autenticación.
- **FR-004**: El sistema MUST ofrecer una acción de sincronización independiente para cada uno de los 4 catálogos de Teamwork (Clientes/Empresas, Proyectos, Personal, Listas de Tareas) y MUST bloquear la sincronización si la conexión no ha sido probada con éxito.
- **FR-005**: El sistema MUST mostrar una tabla comparativa de Homologación de Entidades entre lo sincronizado de Teamwork y los catálogos existentes de SYTIX.
- **FR-006**: El sistema MUST sugerir automáticamente una coincidencia (automapeo) por correo electrónico, ID externo o nombre exacto, y MUST permitir al usuario sobrescribir cualquier sugerencia mediante selección manual.
- **FR-007**: Una homologación guardada (automática confirmada o manual) MUST reutilizarse en sincronizaciones e importaciones posteriores sin tener que rehacerla.
- **FR-008**: El sistema MUST permitir cargar un archivo CSV/Excel de registro de tiempos mensuales reconociendo las columnas `ID`, `Date/time`/`End date/time`, `Hours`/`Minutes`/`Decimal hours`, `Who` (o `First name`+`Last name`/`User ID`), `Company`, `Project`, `Task`/`Task ID`, `Description`.
- **FR-009**: El sistema MUST prevalidar el archivo antes de guardar nada, calculando y mostrando el conteo de filas válidas y filas con conflicto/alerta.
- **FR-010**: Una fila MUST clasificarse como válida solo si Usuario, Proyecto y Tarea existen en SYTIX o ya están homologados, y la Descripción no viene vacía.
- **FR-011**: El sistema MUST ofrecer, para cada fila con conflicto, las tres acciones de resolución: (a) homologar a un registro existente de SYTIX mediante selector, (b) crear automáticamente el registro faltante desde la misma vista, (c) omitir la fila.
- **FR-012**: El sistema MUST permitir confirmar la carga solo después de que el usuario haya resuelto o descartado explícitamente cada fila con conflicto (no se guardan filas sin resolver).
- **FR-013**: Reimportar un archivo con el mismo `ID` (`external_time_id`) de un registro de tiempo ya importado MUST actualizar el registro existente en vez de duplicarlo.
- **FR-014**: Cuando la resolución de un conflicto sea "crear automáticamente el usuario/cliente faltante" (FR-011.b), el sistema MUST crear únicamente el registro de referencia correspondiente (Cliente/Proyecto, o el Recurso interno vinculado al `Who`) sin otorgar cuenta de usuario con acceso de login — la creación de credenciales de acceso, si se necesita, MUST hacerse aparte por un Administrador desde los módulos ya existentes (Equipo/Clientes).
- **FR-015**: El sistema MUST dejar un registro de auditoría por cada importación de tiempos confirmada (quién, cuándo, cuántas filas de cada tipo).

### Key Entities *(include if feature involves data)*

- **Configuración de Integración Teamwork**: URL del sitio, token de API (almacenado de forma segura), entorno (Test/Producción), resultado y fecha de la última prueba de conexión.
- **Homologación de Entidad**: vínculo entre una entidad de Teamwork (tipo: cliente/proyecto/persona/lista de tareas, ID y nombre externos) y su registro correspondiente en SYTIX, con el método de coincidencia (automático por correo/ID externo/nombre, o manual).
- **Carga de Tiempos Mensual**: archivo procesado, fecha de carga, usuario que la ejecutó, totales de filas válidas/con conflicto/omitidas/creadas.
- **Registro de Tiempo Importado**: fila individual del archivo con su `external_time_id`, fecha/hora, duración, Usuario/Cliente/Proyecto/Tarea resueltos, descripción, y estado de resolución (válida de origen, homologada, creada, omitida).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un Administrador puede configurar y confirmar una conexión válida con Teamwork en menos de 3 minutos.
- **SC-002**: Un Coordinador puede cargar un reporte mensual de tiempos de hasta 200 filas y ver el resumen de validación (válidas vs. con conflicto) en menos de 30 segundos.
- **SC-003**: El 100% de las filas con conflicto quedan resueltas (homologadas, creadas u omitidas) antes de poder confirmar la carga — ningún registro de tiempo se guarda sin que su Usuario, Proyecto y Tarea estén determinados.
- **SC-004**: Reimportar el mismo archivo (o uno con filas repetidas) no genera registros de tiempo duplicados en ningún caso.
- **SC-005**: Una vez homologada manualmente una entidad, el 100% de las importaciones/sincronizaciones posteriores la reconocen automáticamente sin pedir la misma resolución de nuevo.

## Assumptions

- El módulo de Homologación de Entidades (US5) y las tablas de Configuración de Integración/Homologación son nuevos y **no** reutilizan el mecanismo por variables de entorno (`TEAMWORK_DOMAIN`/`TEAMWORK_API_TOKEN`) usado por el importador de Tareas ya existente (spec 041, `backend/infra/importers/teamwork_api_client.py`) — este módulo requiere credenciales configurables desde la UI y persistidas en base de datos, por lo que se trata de un mecanismo de conexión independiente, aunque ambos consuman la misma API v3 de Teamwork.
- Esta feature importa **registros de tiempo** (time logs) desde un reporte mensual; es un flujo distinto e independiente del importador de **tareas** de la spec 041 (que crea Tickets/Tareas), aunque ambos compartan el origen de datos (Teamwork) y algunos catálogos a homologar (Cliente, Proyecto, Persona).
- "Entorno (Test/Producción)" es un dato informativo de la configuración (para que el usuario sepa contra qué cuenta de Teamwork está apuntando) — no implica que SYTIX mantenga dos configuraciones activas simultáneas ni dos bases de datos separadas.
- El archivo de reporte mensual de tiempos sigue el formato de exportación estándar de Teamwork ya documentado por el usuario; no se asume un formato distinto por país/cliente.
- La sincronización de catálogos (US4) es de solo lectura hacia SYTIX: trae datos de Teamwork para mostrarlos en la homologación, pero no crea ni modifica registros de los catálogos de SYTIX automáticamente (la creación solo ocurre explícitamente vía FR-011.b, dentro de la resolución de conflictos de una carga de tiempos).
- Sin acceso a una cuenta real de Teamwork en este entorno de desarrollo (mismo caso ya documentado en spec 041): "Probar Conexión" y la sincronización de catálogos se implementan y prueban contra la documentación oficial de la API v3 y con mocks, sin smoke-test contra una cuenta real.
