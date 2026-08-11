# Feature Specification: Matriz de Estados de Sincronización, Acciones Masivas Ampliadas, Extracción Enriquecida de Datos y Centro Independiente de Importación de Tareas (Teamwork API v3)

**Feature Branch**: `045-matriz-estados-importador`

**Created**: 2026-08-10

**Status**: Draft

**Input**: User description: "Módulo Independiente de Importación de Tareas, Matriz de Estados (Homologado/Migrado/Inactivo) y Extracción Ampliada API v3 — implementar la matriz de estados de vida (Pendiente, Homologado, Migrado e Inactivo), habilitar operaciones masivas de migración/inactivación en los grids de catálogos, extraer metadatos ampliados de la API v3 de Teamwork (País, Dirección, Dominio, Teléfono para Clientes; Cargo, País/Zona Horaria, Correo y Compañía para Personal; descripción/estado/cliente propietario para Proyectos y Listas) y crear un Módulo Independiente de Importación de Tareas por Filtros/Segmentos (Cliente, Proyecto(s), rango de fechas, Lista de Tareas opcional) con prevalidación diagnóstica (listas vs. bloqueadas) y ejecución por lotes."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Matriz de 4 estados con filtros por pestaña en los Grids de catálogos (Priority: P1)

Un Coordinador o Admin que trabaja sobre las tablas de sincronización de Empresas, Proyectos, Listas de Tareas y Personal necesita distinguir de un vistazo, y filtrar explícitamente, entre los registros que aún no tienen ninguna acción (`Pendiente`), los que ya están vinculados a un registro existente de SYTIX (`Homologado`), los que ya generaron un registro nuevo en SYTIX (`Migrado`) y los que el equipo decidió descartar por no ser relevantes para SYTIX (`Inactivo`) — hoy solo existe un badge derivado de 3 estados y ninguna forma de descartar filas que no interesa migrar, por lo que quedan mezcladas para siempre entre las pendientes.

**Why this priority**: Es la base de todo lo demás en esta ampliación — sin un cuarto estado explícito y persistente para "descartar" una fila, las Historias 2 y 3 (acciones masivas de inactivación y su distintivo visual) no tienen dónde apoyarse, y sin filtros por estado cualquier catálogo con cientos de filas sincronizadas (caso ya confirmado en spec 044, ~285 Personal) se vuelve impracticable de operar.

**Independent Test**: Sobre un catálogo ya sincronizado con filas en al menos 3 estados distintos, aplicar cada pestaña/filtro (`Todos`, `Pendientes`, `Homologados`, `Migrados`, `Inactivos`) uno por uno y verificar que cada uno muestra exactamente las filas que le corresponden según su estado actual, sin mezclarlas.

**Acceptance Scenarios**:

1. **Given** una tabla de catálogo sincronizada con filas homologadas, migradas, pendientes e inactivas mezcladas, **When** el usuario selecciona la pestaña/filtro "Pendientes", **Then** solo se listan las filas que no tienen ninguna homologación, migración ni marca de inactivo.
2. **Given** la misma tabla, **When** el usuario selecciona "Inactivos", **Then** solo se listan las filas marcadas explícitamente como Inactivo, incluidas aquellas que nunca tuvieron una homologación o migración previa.
3. **Given** una fila homologada individualmente contra un registro existente de SYTIX, **When** se visualiza en la tabla, **Then** su badge de estado muestra "Homologado" en un color distintivo, distinto del badge "Migrado" (creado como registro nuevo) y del badge "Inactivo".
4. **Given** el filtro "Todos" seleccionado, **When** el usuario cambia a cualquier otra pestaña de estado, **Then** el conteo total de filas visibles disminuye o se mantiene, nunca aumenta, y la paginación de 15 filas por página (spec 044) se conserva dentro de cada filtro.

---

### User Story 2 - Acciones masivas de "Migrar como Nuevos" e "Inactivar/Descartar" en los Grids (Priority: P1)

Un Coordinador o Admin selecciona varias filas con checkboxes en cualquiera de los catálogos (Empresas, Proyectos, Listas de Tareas, Personal) y aplica en una sola operación "Migrar Masivamente como Nuevos" (crea el registro correspondiente en SYTIX para cada fila seleccionada) o "Inactivar / Descartar Seleccionados" (marca las filas como Inactivo, sin crear ni tocar ningún registro de SYTIX), en vez de repetir la acción fila por fila — spec 044 ya resolvió esto para Personal con Rol+Cliente; esta historia lo extiende a los otros 3 catálogos y agrega la acción de descarte que hoy no existe en ninguno.

**Why this priority**: Junto con la Historia 1, es el pedido central de esta ampliación — habilita en la práctica la operación diaria sobre catálogos grandes (Empresas y Proyectos hoy solo se homologan o migran fila por fila) y resuelve el caso, ya observado en operación real, de registros de Teamwork que nunca van a tener contraparte en SYTIX y hoy quedan indefinidamente "pendientes".

**Independent Test**: Sobre la tabla de Proyectos con al menos 5 filas pendientes, seleccionar 3 con checkbox y ejecutar "Migrar Masivamente como Nuevos"; verificar que las 3 quedan en estado Migrado con su Proyecto creado en SYTIX. Sobre las 2 filas restantes, ejecutar "Inactivar / Descartar Seleccionados" y verificar que quedan en estado Inactivo sin ningún Proyecto nuevo creado.

**Acceptance Scenarios**:

1. **Given** varias filas seleccionadas por checkbox en la tabla de Empresas, Proyectos o Listas de Tareas, **When** el usuario ejecuta "Migrar Masivamente como Nuevos", **Then** cada fila seleccionada que aún no tenga homologación ni migración genera su registro nuevo correspondiente en SYTIX y pasa a estado Migrado, sin abortar el lote si una fila puntual falla.
2. **Given** varias filas seleccionadas en cualquiera de los 4 catálogos, **When** el usuario ejecuta "Inactivar / Descartar Seleccionados" y confirma, **Then** cada fila pasa a estado Inactivo sin crear ni modificar ningún registro de SYTIX, y deja de aparecer en los filtros "Pendientes"/"Todos" por defecto.
3. **Given** una selección masiva de "Migrar como Nuevos" que incluye una fila ya Homologada o ya Migrada, **When** se ejecuta la acción, **Then** esa fila se omite (no se re-crea ni se duplica) y el resultado final informa cuántas se migraron y cuántas se omitieron, con el motivo.
4. **Given** una fila marcada como Inactivo, **When** el usuario decide reconsiderarla, **Then** existe una acción explícita para devolverla a estado Pendiente (o para homologarla/migrarla directamente), sin que quede bloqueada de forma permanente.
5. **Given** una selección masiva vacía o compuesta solo por filas que ya están en el estado destino de la acción, **When** el usuario intenta ejecutar la acción, **Then** el sistema no ejecuta ninguna operación y lo informa claramente, sin error técnico.

---

### User Story 3 - Extracción ampliada de metadatos de la API v3 (Clientes, Personal, Proyectos y Listas) (Priority: P2)

Un Coordinador o Admin que homologa o migra una fila de Empresa, Persona, Proyecto o Lista de Tareas necesita ver, sin salir de la fila, datos de contexto adicionales que Teamwork ya provee y que hoy la sincronización no trae: para Empresas, País, Dirección, Dominio/Web y Teléfono; para Personal, Cargo/Título, País/Zona horaria y Correo (ya parcialmente cubierto por spec 043) junto con la Compañía de origen (ya cubierta por spec 044); para Proyectos y Listas, descripción, estado (activo/archivado) y el Cliente propietario — para decidir con más contexto a qué registro de SYTIX corresponde cada fila, o si conviene inactivarla (ej. un proyecto ya archivado en Teamwork).

**Why this priority**: Mejora la calidad de la decisión de homologación/migración/inactivación (Historias 1 y 2) pero no bloquea su funcionamiento — un Coordinador puede seguir operando con los datos mínimos ya disponibles (nombre/correo) mientras esta historia no esté disponible, por lo que queda en segundo nivel de prioridad.

**Independent Test**: Sincronizar el catálogo de Empresas contra un sitio de prueba donde al menos una compañía tenga País, Dirección, Dominio y Teléfono cargados en Teamwork, y verificar que esos 4 campos se ven en la fila correspondiente de la tabla sin necesidad de otra consulta.

**Acceptance Scenarios**:

1. **Given** una Empresa de Teamwork con País, Dirección, Dominio y Teléfono cargados, **When** se sincroniza y se visualiza en la tabla de Empresas, **Then** los 4 campos se muestran en la fila o en su detalle expandible, y un campo no informado en Teamwork se muestra con un indicador explícito de ausencia (ej. "No informado") en vez de quedar vacío o romper la fila.
2. **Given** una Persona de Teamwork con Cargo/Título y Zona Horaria cargados, **When** se sincroniza y se visualiza en la tabla de Personal, **Then** ambos campos se muestran junto al correo y la Compañía de origen ya existente.
3. **Given** un Proyecto de Teamwork marcado como archivado en el origen, **When** se sincroniza y se visualiza en la tabla de Proyectos, **Then** su estado "Archivado" se muestra de forma distinguible del estado "Activo", y su descripción y Cliente propietario también son visibles.
4. **Given** una Lista de Tareas de Teamwork con descripción cargada, **When** se sincroniza y se visualiza en la tabla de Listas de Tareas, **Then** la descripción se muestra sin truncar el layout de la tabla (ej. mediante tooltip o expansión), junto a su Proyecto y Cliente ya existentes (spec 043).

---

### User Story 4 - Centro Independiente de Importación de Tareas y Subtareas por filtros (Priority: P1)

Un Coordinador o Admin necesita, desde una pantalla propia y separada del integrador de catálogos ("Importador de Tareas y Subtareas"), acotar qué Tareas/Subtareas de Teamwork migrar mediante Cliente, Proyecto(s), rango de fechas (ej. un mes puntual) y opcionalmente una Lista de Tareas — en vez de migrar siempre el universo completo de tareas del sitio (comportamiento ya existente de spec 044) — y necesita ver antes de confirmar cuántas de esas tareas están listas para migrar y cuáles quedarían bloqueadas por falta de homologación, con un enlace directo para resolver el maestro faltante sin perder el filtro ya aplicado.

**Why this priority**: Es el segundo pedido central de esta ampliación junto con la Historia 2 — sin segmentación por Cliente/Proyecto/fecha, migrar tareas de un solo Cliente o de un mes puntual obliga a traer y filtrar manualmente todo el universo de tareas del sitio, y sin la prevalidación diagnóstica el usuario descubre las tareas bloqueadas recién después de intentar migrar, en vez de antes.

**Independent Test**: Con un lote de prueba de 5 a 10 Tareas/Subtareas de Teamwork repartidas entre 2 Clientes y 2 meses distintos (algunas con Proyecto/Usuario ya homologado, otras sin homologar), abrir el Importador de Tareas, filtrar por un Cliente y un rango de un mes, y verificar que la prevalidación distingue correctamente cuántas tareas de ese subconjunto están listas y cuáles están bloqueadas, antes de ejecutar la importación.

**Acceptance Scenarios**:

1. **Given** la pantalla "Importador de Tareas y Subtareas", **When** el usuario selecciona un Cliente, uno o más Proyectos de ese Cliente y un rango de fechas, **Then** el sistema restringe la consulta a Teamwork a las Tareas/Subtareas de esos Proyectos creadas o con fecha de vencimiento dentro del rango indicado.
2. **Given** los mismos filtros con una Lista de Tareas específica adicional, **When** se aplica, **Then** el subconjunto se acota además a esa Lista de Tareas puntual.
3. **Given** un filtro ya aplicado, **When** el usuario ejecuta la prevalidación diagnóstica antes de importar, **Then** el sistema muestra por separado la cantidad de tareas listas para migrar (Proyecto, Lista de Tareas y Usuario asignado ya Homologados o Migrados) y la cantidad de tareas bloqueadas, con el motivo de bloqueo de cada una (ej. "Proyecto sin homologar", "Usuario asignado sin homologar").
4. **Given** una tarea bloqueada en la prevalidación por falta de homologación de su Proyecto, **When** el usuario hace clic en el enlace de esa advertencia, **Then** navega directamente a la pantalla de homologación del catálogo correspondiente con esa fila identificable, sin perder el filtro de importación ya configurado (puede retomarlo al volver).
5. **Given** una prevalidación con al menos una tarea lista, **When** el usuario confirma la ejecución por lotes, **Then** el sistema crea/actualiza únicamente las tareas marcadas como listas, guarda el identificador de origen (`external_reference_id`) y el hipervínculo hacia Teamwork de cada una, y deja las bloqueadas sin tocar.
6. **Given** un filtro sin ningún Cliente ni Proyecto seleccionado, **When** el usuario intenta ejecutar la prevalidación o la importación, **Then** el sistema exige al menos Cliente y Proyecto antes de continuar (el rango de fechas y la Lista de Tareas son opcionales, con el rango de fechas por defecto cubriendo el mes en curso si no se especifica).
7. **Given** una Tarea/Subtarea ya migrada previamente por su identificador de origen, **When** vuelve a aparecer dentro de un filtro y se re-ejecuta la importación, **Then** el Ticket/Tarea existente se actualiza en vez de duplicarse (mismo comportamiento ya vigente en spec 044).

---

### Edge Cases

- ¿Qué pasa si una fila se marca como Inactivo y luego el mismo registro vuelve a aparecer en una sincronización posterior del catálogo? Conserva su estado Inactivo (no se reinicia a Pendiente automáticamente); solo una acción explícita del usuario la reactiva.
- ¿Qué pasa si se intenta ejecutar "Migrar Masivamente como Nuevos" sobre una fila cuyo registro padre (Empresa de un Proyecto, Proyecto de una Lista) todavía está Pendiente o Inactivo? Esa fila se omite del lote (mismo bloqueo por jerarquía ya vigente para la migración individual desde spec 043), y queda reportada junto a las demás omisiones del resultado.
- ¿Qué pasa si el filtro de fechas del Importador de Tareas no devuelve ninguna tarea de Teamwork? La prevalidación muestra 0 listas y 0 bloqueadas, sin error, y el botón de ejecutar la importación queda deshabilitado.
- ¿Qué pasa si un campo ampliado (ej. Teléfono de una Empresa, Cargo de una Persona) no está informado en Teamwork? Se muestra con un indicador explícito de ausencia, nunca en blanco ni generando error de sincronización.
- ¿Qué pasa si el usuario aplica un filtro de Proyecto(s) en el Importador de Tareas que pertenecen a Clientes distintos por error? El selector de Proyecto(s) solo ofrece los proyectos del Cliente ya elegido (cascada), evitando esa combinación inválida.
- ¿Qué pasa si el usuario no tiene el permiso de integración de Teamwork e intenta acceder al Importador de Tareas o ejecutar una acción masiva de estado? Se bloquea igual que cualquier otra operación del integrador hoy (mismo permiso `teamwork_integration:operate`).

## Requirements *(mandatory)*

### Functional Requirements

**Matriz de estados**

- **FR-001**: El sistema MUST reconocer 4 estados explícitos y mutuamente excluyentes para cada fila de homologación de catálogo: `Pendiente` (sin ninguna acción), `Homologado` (vinculada a un registro existente de SYTIX), `Migrado` (generó un registro nuevo en SYTIX) e `Inactivo` (descartada explícitamente por el usuario, sin registro de SYTIX asociado).
- **FR-002**: El sistema MUST persistir el estado `Inactivo` de forma independiente de la homologación/migración, de manera que una fila nunca antes homologada ni migrada pueda marcarse como Inactivo sin requerir un registro de SYTIX.
- **FR-003**: Las tablas de sincronización de Empresas, Proyectos, Listas de Tareas y Personal MUST ofrecer pestañas o selectores de filtro por estado (`Todos`, `Pendientes`, `Homologados`, `Migrados`, `Inactivos`), combinables con los filtros de Cliente/Proyecto/correo ya existentes (spec 044).
- **FR-004**: Cada fila MUST mostrar un badge de estado visualmente distinguible por color/etiqueta entre los 4 estados (ej. Azul "Homologado", Verde "Migrado", gris/neutro "Pendiente", y un color propio para "Inactivo"), consistente con el mismo criterio ya usado en el badge de trazabilidad de spec 044.
- **FR-005**: Una fila marcada como Inactivo MUST excluirse por defecto de los filtros "Todos" y "Pendientes" salvo que el usuario seleccione explícitamente la pestaña "Inactivos".
- **FR-006**: El sistema MUST permitir revertir una fila desde el estado Inactivo hacia Pendiente (o migrarla/homologarla directamente), sin límite de veces.
- **FR-007**: Una sincronización posterior de un catálogo MUST preservar el estado Homologado/Migrado/Inactivo ya asignado a una fila existente, sin reiniciarlo a Pendiente.

**Acciones masivas**

- **FR-008**: Las tablas de Empresas, Proyectos y Listas de Tareas MUST ofrecer selección múltiple por checkbox y una barra de "Acciones Masivas" visible solo cuando hay al menos una fila seleccionada (extiende a estos 3 catálogos el patrón ya vigente para Personal desde spec 044).
- **FR-009**: El sistema MUST permitir ejecutar "Migrar Masivamente como Nuevos" sobre la selección de cualquiera de los 4 catálogos, creando en SYTIX el registro correspondiente de cada fila que aún no esté Homologada ni Migrada, respetando las mismas validaciones de jerarquía y de datos ya vigentes para la migración individual de cada tipo de entidad (spec 043).
- **FR-010**: El sistema MUST permitir ejecutar "Inactivar / Descartar Seleccionados" sobre la selección de cualquiera de los 4 catálogos, marcando cada fila elegida como Inactivo sin crear, modificar ni eliminar ningún registro de SYTIX.
- **FR-011**: Al ejecutar cualquier acción masiva de esta especificación, el sistema MUST omitir sin interrumpir el lote las filas que no apliquen a la acción (ya migradas/homologadas para "Migrar como Nuevos"; ya inactivas para "Inactivar"), y MUST informar al finalizar cuántas filas se procesaron con éxito, cuántas se omitieron y el motivo de cada omisión.
- **FR-012**: Una acción masiva ejecutada sobre una selección vacía, o compuesta solo por filas ya en el estado destino, MUST no ejecutar ninguna operación contra SYTIX y MUST informarlo claramente al usuario.

**Extracción ampliada de datos**

- **FR-013**: La sincronización del catálogo de Empresas MUST extraer y mostrar, cuando estén disponibles en Teamwork, País, Dirección, Dominio/Web y Teléfono de cada compañía.
- **FR-014**: La sincronización del catálogo de Personal MUST extraer y mostrar, cuando estén disponibles en Teamwork, Cargo/Título y Zona Horaria/País de cada persona, junto con el Correo (spec 043) y la Compañía de origen (spec 044) ya existentes.
- **FR-015**: La sincronización de los catálogos de Proyectos y Listas de Tareas MUST extraer y mostrar, cuando estén disponibles en Teamwork, la descripción y el estado (activo/archivado) de cada Proyecto o Lista, además del Cliente propietario ya resuelto (spec 043).
- **FR-016**: Un campo ampliado no informado en el origen de Teamwork MUST mostrarse con un indicador explícito de ausencia, nunca como un valor vacío indistinguible de un error de sincronización.

**Centro Independiente de Importación de Tareas**

- **FR-017**: El sistema MUST ofrecer una pantalla propia, separada de la sincronización de catálogos, llamada "Importador de Tareas y Subtareas", accesible con el mismo permiso ya vigente para operar el integrador de Teamwork (`teamwork_integration:operate`).
- **FR-018**: El Importador MUST exigir la selección de un Cliente y al menos un Proyecto de ese Cliente antes de permitir la prevalidación o la ejecución; el rango de fechas y la Lista de Tareas MUST ser opcionales, con el rango de fechas por defecto cubriendo el mes en curso cuando no se especifique.
- **FR-019**: El selector de Proyecto(s) del Importador MUST ofrecer únicamente los proyectos pertenecientes al Cliente ya seleccionado (cascada).
- **FR-020**: Antes de ejecutar cualquier importación, el sistema MUST procesar el subconjunto de Tareas/Subtareas de Teamwork que cumple los filtros indicados y MUST mostrar por separado la cantidad lista para migrar (cadena de homologación de Proyecto, Lista de Tareas y Usuario asignado ya resuelta) y la cantidad bloqueada, cada una con su motivo de bloqueo específico.
- **FR-021**: Cada advertencia de tarea bloqueada MUST incluir un enlace que lleve directamente a la pantalla de homologación del catálogo correspondiente a la homologación faltante.
- **FR-022**: El sistema MUST ejecutar la importación por lotes (batch), creando o actualizando únicamente las Tareas/Subtareas marcadas como listas en la prevalidación, sin generar Tickets huérfanos a partir de las bloqueadas.
- **FR-023**: Cada Tarea/Subtarea importada MUST guardar su identificador de origen de Teamwork (`external_reference_id`) y mostrar en SYTIX un hipervínculo funcional hacia la tarea original en Teamwork (mismo mecanismo ya vigente en spec 044).
- **FR-024**: Re-ejecutar la importación sobre una Tarea/Subtarea ya migrada previamente por el mismo identificador de origen MUST actualizar el Ticket/Tarea existente en vez de duplicarlo.
- **FR-025**: El Importador de Tareas MUST preservar la relación jerárquica Tarea padre → Subtarea al crear los registros en SYTIX, igual que la migración masiva ya existente (spec 044).

### Key Entities *(include if feature involves data)*

- **Estado de sincronización**: Clasificación de 4 valores (`Pendiente`, `Homologado`, `Migrado`, `Inactivo`) asociada a cada fila de homologación de catálogo (Empresa, Proyecto, Lista de Tareas, Persona); determina su badge visual y su visibilidad bajo cada pestaña de filtro.
- **Selección masiva de estado**: Conjunto transitorio de filas elegidas por el usuario en cualquiera de los 4 catálogos, más la acción elegida (Migrar como Nuevos / Inactivar) para aplicar a todas en una sola confirmación; no persiste como entidad propia, solo como resultado sobre cada fila.
- **Metadato ampliado**: Atributo adicional extraído de la API v3 de Teamwork por tipo de entidad (País/Dirección/Dominio/Teléfono para Empresa; Cargo/Zona horaria para Persona; descripción/estado para Proyecto y Lista de Tareas) que enriquece la fila de homologación sin alterar el criterio de automapeo ya existente.
- **Filtro de importación de Tareas**: Combinación de Cliente, Proyecto(s), rango de fechas y Lista de Tareas opcional que acota qué Tareas/Subtareas de Teamwork se consultan y prevalidan en el Importador; transitorio por sesión de uso, no persiste entre visitas.
- **Diagnóstico de prevalidación**: Resultado del procesamiento de un filtro de importación antes de ejecutar, con el listado de Tareas/Subtareas clasificadas como listas o bloqueadas y, para cada bloqueada, el motivo puntual de bloqueo y el enlace a la homologación faltante.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un Coordinador puede localizar todas las filas Pendientes, Homologadas, Migradas o Inactivas de un catálogo con más de 100 registros sincronizados en menos de 3 clics, sin tener que revisar la lista completa manualmente.
- **SC-002**: Un Coordinador puede migrar masivamente 10 o más filas de cualquiera de los 4 catálogos, o inactivar 10 o más filas irrelevantes, en una sola operación de menos de 1 minuto, frente al flujo actual de una acción por fila.
- **SC-003**: El 100% de las filas marcadas como Inactivo permanecen así tras una resincronización posterior del mismo catálogo, sin reaparecer como Pendientes.
- **SC-004**: Sobre un lote de prueba de 5 a 10 Tareas/Subtareas de Teamwork segmentado por Cliente/Proyecto/fecha, la prevalidación del Importador clasifica correctamente el 100% de las tareas listas y bloqueadas, y la ejecución por lotes solo crea/actualiza las tareas marcadas como listas.
- **SC-005**: Un Coordinador puede pasar de una advertencia de tarea bloqueada a la pantalla de homologación del maestro faltante en un solo clic, sin perder los filtros de importación ya configurados.

## Assumptions

- Esta especificación amplía y reemplaza el badge de 3 estados introducido en spec 043 (Pendiente/Homologado/Migrado) por la matriz de 4 estados aquí definida; el estado Inactivo es nuevo y requiere una marca persistente propia (no derivable solo de `sytix_id`/`match_method` como los otros 3), sin definir aquí el mecanismo de persistencia concreto (detalle de implementación).
- "Acciones masivas" en Empresas, Proyectos y Listas de Tareas replica el patrón ya validado en Personal (spec 044): checkboxes + barra de acciones, sin filtro de correo (ese filtro es específico de Personal) pero sí combinable con los filtros de Cliente/Proyecto ya existentes.
- El Centro Independiente de Importación de Tareas es una pantalla nueva, adicional a la migración masiva sin filtros ya existente (`POST .../sync/tasks`, spec 044); no la reemplaza ni la elimina, y puede reutilizar internamente la misma lógica de resolución de homologaciones (Capa 1) ya construida para ese endpoint.
- El rango de fechas del Importador de Tareas se interpreta sobre la fecha de creación o de vencimiento de la tarea en Teamwork (el que la API v3 exponga de forma más confiable para filtrar), no sobre la fecha de sincronización en SYTIX.
- Los campos ampliados de País/Dirección/Dominio/Teléfono/Cargo/Zona horaria/descripción/estado se muestran únicamente dentro de las pantallas del integrador de Teamwork (tabla o detalle expandible de cada fila); no se persisten en las tablas principales de SYTIX (Cliente/Proyecto/Lista/Usuario) ni alteran su modelo de datos existente, consistente con el alcance estricto de esta ampliación.
- El criterio de automapeo automático (por correo/ID externo/nombre exacto, spec 042) no cambia con la extracción de metadatos ampliados; los nuevos campos son solo informativos para la decisión humana de homologar/migrar/inactivar.
- Queda fuera de alcance: modificar la lógica central de Tickets/Tareas existente fuera del namespace de integración de Teamwork y del nuevo módulo de importación (instrucción explícita del pedido), y ejecutar la suite completa de pruebas automatizadas (Principio VII) — cualquier test nuevo se limita a un dataset reducido de 5 a 10 registros mock.
