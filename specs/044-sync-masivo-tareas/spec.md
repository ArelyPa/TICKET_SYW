# Feature Specification: Operaciones Masivas, Paginación de Sincronización y Migración de Tareas/Subtareas (Teamwork API v3)

**Feature Branch**: `044-sync-masivo-tareas`

**Created**: 2026-08-10

**Status**: Draft

**Input**: User description: "Ampliar la suite de sincronización de Teamwork en SYTIX: incluir la compañía en la vista de personal, habilitar acciones masivas de asociación/migración con filtros de correo, corregir la paginación (150 reportados vs. 60 renderizados), enriquecer los selectores de proyectos (formato Cliente - Proyecto), agregar distintivos de trazabilidad y ejecutar la migración masiva de Tareas y Subtareas desde la API v3 de Teamwork (`GET /projects/api/v3/tasks.json`), con hipervínculo de origen. La migración de tiempos registrados queda para una fase posterior."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sincronización de catálogos completa y confiable (Priority: P1)

Un Coordinador o Admin sincroniza el catálogo de Personal desde Teamwork y necesita confiar en que la lista que ve en pantalla contiene efectivamente todos los registros que Teamwork reporta como existentes (hoy la sincronización reporta 150 registros totales pero la pantalla solo muestra 60), y necesita ver a qué Compañía/Empresa de origen pertenece cada persona para poder decidir a qué Cliente de SYTIX homologarla o migrarla.

**Why this priority**: Es la base de todo lo demás — si los datos sincronizados están incompletos o sin el contexto de Compañía, cualquier homologación (manual o masiva) hecha sobre esa lista parcial deja personas sin migrar de forma silenciosa, y las acciones masivas de la Historia 2 heredarían el mismo problema.

**Independent Test**: Sincronizar el catálogo de Personal contra un sitio de prueba con más de 60 registros y verificar que el conteo total informado por la sincronización coincide exactamente con el número de filas visibles/paginables en la tabla, y que cada fila muestra su Compañía de origen.

**Acceptance Scenarios**:

1. **Given** un sitio de Teamwork con 150 personas registradas, **When** el Coordinador sincroniza el catálogo de Personal, **Then** la sincronización reporta 150 registros sincronizados y las 150 filas quedan disponibles en la tabla (repartidas en sus páginas), no solo 60.
2. **Given** una persona sincronizada que en Teamwork pertenece a la compañía "Arcor", **When** se visualiza la tabla de Personal, **Then** la columna "Compañía/Empresa de Origen" muestra "Arcor" para esa fila.
3. **Given** una persona sincronizada sin compañía asociada en Teamwork, **When** se visualiza la tabla de Personal, **Then** la columna de Compañía muestra un indicador explícito de ausencia (ej. "Sin compañía") en vez de quedar vacía o generar error.

---

### User Story 2 - Migración masiva de Personal con filtro de correo (Priority: P1)

Un Coordinador o Admin filtra la lista de Personal sincronizada por un patrón de correo (ej. `@arcor.com`), selecciona varias filas con checkboxes y aplica en un solo clic el mismo Rol (ej. Usuario/cliente) y el mismo Cliente de destino a todas las seleccionadas, en vez de repetir la migración fila por fila.

**Why this priority**: Es el pedido central de la ampliación — hoy homologar o migrar decenas de personas de un mismo dominio de correo a un mismo Cliente es una operación manual repetitiva; esta historia es la que más tiempo de operación ahorra y da valor de negocio directo.

**Independent Test**: Con Personal ya sincronizado (Historia 1), filtrar por un fragmento de correo, seleccionar 5 filas resultantes, ejecutar la asignación masiva de Rol "Usuario/cliente" + Cliente "Aris", y verificar que las 5 personas quedan migradas/homologadas a ese Cliente con ese Rol sin repetir el flujo individual.

**Acceptance Scenarios**:

1. **Given** la tabla de Personal sincronizada, **When** el usuario escribe `@aris.ming.com` en el filtro de correo, **Then** solo se listan las filas cuyo correo de Teamwork contiene ese fragmento.
2. **Given** un subconjunto de filas filtradas y seleccionadas por checkbox, **When** el usuario abre "Acciones Masivas" y elige Rol "Usuario/cliente" + Cliente "Aris" y confirma, **Then** cada persona seleccionada queda migrada/homologada contra ese Cliente con ese Rol, en una sola operación.
3. **Given** una selección masiva que incluye una persona ya migrada previamente, **When** se ejecuta la acción masiva, **Then** esa fila se omite (no se re-crea ni se duplica) y el resultado final informa cuántas se migraron y cuántas se omitieron por ya estar migradas.
4. **Given** una selección masiva con Rol "Usuario/cliente" pero sin Cliente de destino elegido, **When** el usuario intenta confirmar, **Then** el sistema bloquea la acción y exige seleccionar un Cliente antes de continuar (mismo requisito que ya aplica a la migración individual).

---

### User Story 3 - Migración masiva de Tareas y Subtareas desde la API v3 (Priority: P2)

Un Coordinador o Admin, con Clientes/Proyectos/Listas de Tareas/Personal ya homologados o migrados, ejecuta la migración masiva de Tareas y Subtareas desde Teamwork: el sistema consulta `GET /projects/api/v3/tasks.json`, resuelve cada tarea contra las homologaciones ya existentes, y crea los Tickets/Tareas correspondientes en SYTIX con un hipervínculo que lleva de vuelta a la tarea original en Teamwork.

**Why this priority**: Depende de que los catálogos base (Historia 1) y sus homologaciones ya existan para poder resolver Cliente/Proyecto/Lista/Usuario de cada tarea; es el segundo entregable en importancia de esta ampliación, pero no puede ejecutarse de forma útil ni válida antes que la Historia 1.

**Independent Test**: Con un lote de prueba de 5 a 10 Tareas/Subtareas de Teamwork (Proyecto, Lista de Tareas y Asignado ya homologados de antemano), ejecutar la migración masiva y verificar que se crean los Tickets/Tareas correspondientes en SYTIX, con jerarquía Tarea→Subtarea preservada y el hipervínculo de origen funcional.

**Acceptance Scenarios**:

1. **Given** una Tarea de Teamwork cuyo Proyecto y Lista de Tareas ya están homologados/migrados a SYTIX, **When** se ejecuta la migración masiva de Tareas, **Then** se crea un Ticket/Tarea en SYTIX vinculado a ese Proyecto y Lista, con el ID de origen de Teamwork guardado y un hipervínculo visible sobre el número de ticket que abre la tarea original en Teamwork.
2. **Given** una Subtarea de Teamwork cuya Tarea padre también vino en el mismo lote y ya fue creada en SYTIX, **When** se ejecuta la migración, **Then** la Subtarea se crea en SYTIX enlazada como hija de la Tarea padre recién creada (mismo patrón jerárquico Tarea/Subtarea ya existente en SYTIX).
3. **Given** una Tarea de Teamwork cuyo Proyecto o Cliente todavía no está homologado, **When** se ejecuta la migración masiva, **Then** esa tarea se omite de la creación (no se crea un Ticket huérfano) y queda reportada como pendiente de homologación previa.
4. **Given** una Tarea ya migrada anteriormente por su ID de origen, **When** se vuelve a ejecutar la migración sobre el mismo lote, **Then** el Ticket existente se actualiza en vez de duplicarse.

---

### User Story 4 - Selectores de homologación con contexto de Cliente y filtros globales (Priority: P3)

Un Coordinador que homologa Proyectos o Listas de Tareas necesita distinguir entre proyectos homónimos de distintos Clientes (ej. dos proyectos "Soporte") directamente en el selector desplegable, y necesita poder acotar las tres pantallas de sincronización de catálogos (Personal, Proyectos, Listas de Tareas) a un Cliente y/o Proyecto puntual en vez de revisar listas completas.

**Why this priority**: Es una mejora de usabilidad sobre un flujo que ya funciona (spec 043) — reduce errores de homologación por ambigüedad de nombres, pero no bloquea ni las Historias 1-3 ni el valor de negocio principal.

**Independent Test**: Con al menos dos proyectos de nombre "Soporte" pertenecientes a Clientes distintos ya homologados, abrir el selector de homologación de Proyectos y confirmar que ambos aparecen distinguibles como "Cliente A - Soporte" / "Cliente B - Soporte"; luego aplicar el filtro superior por Cliente y confirmar que las tres pantallas de catálogo acotan sus filas a ese Cliente.

**Acceptance Scenarios**:

1. **Given** dos Proyectos SYTIX de nombre idéntico pertenecientes a Clientes distintos, **When** el usuario abre el selector de homologación de una fila de tipo Proyecto o Lista de Tareas, **Then** cada opción se muestra en formato `Cliente - Proyecto` y ambos quedan distinguibles sin truncarse ni desbordar la tabla.
2. **Given** las pantallas de sincronización de Personal, Proyectos y Listas de Tareas, **When** el usuario selecciona un Cliente en el bloque de filtros superior, **Then** las tres pantallas acotan sus filas a las relacionadas con ese Cliente (directamente o a través de su jerarquía Empresa→Proyecto→Lista ya resuelta en spec 043).
3. **Given** el filtro superior con un Cliente ya elegido, **When** el usuario elige además un Proyecto, **Then** el selector de Proyecto solo ofrece los proyectos de ese Cliente (cascada), consistente con el patrón Cliente→Proyecto ya usado en el resto de SYTIX.

---

### User Story 5 - Distintivos de trazabilidad en pantallas principales de SYTIX (Priority: P3)

Un Admin que revisa un Cliente, Proyecto, Lista de Tareas o Usuario directamente en las pantallas principales de SYTIX (fuera del integrador de Teamwork) necesita poder identificar de un vistazo si ese registro fue migrado/homologado desde Teamwork, sin tener que ir a buscar la homologación correspondiente en la pantalla de integración.

**Why this priority**: Es un complemento de visibilidad/auditoría sobre datos que ya existen (el vínculo Teamwork↔SYTIX ya se guarda desde spec 043); no habilita ninguna operación nueva, por lo que es la de menor prioridad relativa.

**Independent Test**: Con un Cliente creado vía "Migrar como Nuevo" desde el integrador, abrir la pantalla principal de Clientes de SYTIX y verificar que ese registro muestra el distintivo, mientras un Cliente creado manualmente (sin relación con Teamwork) no lo muestra.

**Acceptance Scenarios**:

1. **Given** un Cliente/Proyecto/Lista de Tareas/Usuario que fue migrado o homologado desde el integrador de Teamwork, **When** se visualiza su fila en la pantalla principal correspondiente de SYTIX, **Then** se muestra un badge o icono distintivo e inconfundible de origen Teamwork.
2. **Given** un registro creado manualmente en SYTIX sin relación con Teamwork, **When** se visualiza en su pantalla principal, **Then** no muestra ningún distintivo de migración.
3. **Given** una homologación existente en el integrador, **When** se visualiza esa misma fila tanto en el integrador como en la pantalla principal de SYTIX, **Then** el distintivo mostrado en ambos lugares es consistente entre sí (mismo estado de trazabilidad).

---

### Edge Cases

- ¿Qué pasa si Teamwork reporta un total de registros que cambia entre el inicio y el fin de una sincronización paginada (alguien crea/borra un registro durante la sincronización)? El sistema debe completar la sincronización con los datos obtenidos sin fallar, aunque el conteo final difiera levemente del reportado al inicio.
- ¿Qué pasa si una acción masiva se ejecuta sobre una selección vacía o solo con filas ya migradas? El sistema no debe ejecutar ninguna operación y debe informarlo claramente sin error técnico.
- ¿Qué pasa si dentro de una selección masiva de Personal hay filas con Compañía de origen distinta pero se intenta asignar un único Cliente de destino? Se permite (el Cliente de destino es una decisión explícita del usuario, independiente de la Compañía de origen), pero la Compañía de origen visible en la fila ayuda al usuario a evitar el error antes de confirmar.
- ¿Qué pasa si una Subtarea de Teamwork llega en un lote sin su Tarea padre (padre fuera del lote o aún no migrado)? Se importa de forma independiente sin padre asignado y queda reportada para revisión manual (mismo tratamiento que ya existe para tareas huérfanas en la importación por archivo).
- ¿Qué pasa si el usuario no tiene el permiso de integración de Teamwork e intenta ejecutar una acción masiva o la migración de Tareas? Se bloquea igual que cualquier otra operación del integrador hoy.
- ¿Qué pasa si el filtro de correo no coincide con ninguna fila? La tabla y la barra de acciones masivas quedan vacías/deshabilitadas, sin error.

## Requirements *(mandatory)*

### Functional Requirements

**Compañía y filtros globales**

- **FR-001**: El sistema MUST mostrar una columna "Compañía/Empresa de Origen" en la tabla de sincronización de Personal, poblada con el nombre de la compañía de Teamwork asociada a cada persona, o un indicador explícito de ausencia si la persona no tiene compañía asociada en el origen.
- **FR-002**: El sistema MUST ofrecer un bloque de filtros superior por Cliente y por Proyecto en las pantallas de sincronización de Personal, Proyectos y Listas de Tareas, acotando las filas visibles a la jerarquía Cliente/Proyecto seleccionada (resuelta vía las homologaciones ya existentes).
- **FR-003**: El filtro por Proyecto MUST ofrecer únicamente los proyectos pertenecientes al Cliente seleccionado (cascada), y MUST quedar deshabilitado u oculto en pantallas donde no aplica un contexto de Proyecto directo.

**Selectores de homologación**

- **FR-004**: En los selectores de asignación a SYTIX de las filas de tipo Proyecto y Lista de Tareas, cada opción MUST mostrar el texto combinado `Cliente - Proyecto` en vez de solo el nombre del proyecto/lista.
- **FR-005**: El componente selector de homologación MUST ajustar su ancho para que el texto combinado no quede cortado ni distorsione el layout de la tabla, en resoluciones de escritorio estándar.

**Acciones masivas**

- **FR-006**: El sistema MUST permitir seleccionar múltiples filas mediante checkboxes en la tabla de Personal, y exponer una barra de "Acciones Masivas" visible solo cuando hay al menos una fila seleccionada.
- **FR-007**: El sistema MUST permitir filtrar la tabla de Personal por un patrón de texto sobre el correo de Teamwork (coincidencia parcial, ej. dominio), combinable con los filtros de Cliente/Proyecto de FR-002.
- **FR-008**: El sistema MUST permitir aplicar en una sola operación el mismo Rol y el mismo Cliente de destino a todas las filas de Personal seleccionadas, reutilizando las mismas reglas de validación ya vigentes para la migración individual (Cliente obligatorio si el Rol es Usuario/cliente, dominio de correo permitido para roles internos, rechazo si el correo ya está en uso).
- **FR-009**: Al ejecutar una acción masiva, el sistema MUST omitir sin error las filas que ya estén migradas u homologadas, y MUST informar al finalizar cuántas filas se procesaron con éxito, cuántas se omitieron y por qué motivo cada una.

**Paginación y trazabilidad**

- **FR-010**: Todas las pantallas de sincronización de catálogos (Personal, Proyectos, Listas de Tareas, Empresas) MUST paginar sus tablas a exactamente 15 registros por página.
- **FR-011**: La sincronización de cada catálogo contra Teamwork MUST recorrer todas las páginas disponibles en el origen hasta agotarlas, de forma que el número de registros sincronizados coincida con el total real reportado por Teamwork (corrige el caso donde se reportan 150 registros pero solo se procesan/renderizan 60).
- **FR-012**: El sistema MUST mostrar un badge o icono distintivo e inconfundible sobre todo registro (Cliente, Proyecto, Lista de Tareas, Usuario) que haya sido migrado o homologado desde Teamwork, tanto en las pantallas del integrador como en su pantalla principal correspondiente dentro de SYTIX.
- **FR-013**: El distintivo de FR-012 MUST reflejar el mismo estado de trazabilidad en ambos lugares (integrador y pantalla principal) sin requerir una sincronización adicional del usuario.

**Migración masiva de Tareas y Subtareas**

- **FR-014**: El sistema MUST consultar el endpoint `GET /projects/api/v3/tasks.json` de Teamwork para obtener el listado completo de Tareas y Subtareas del sitio configurado, recorriendo todas sus páginas (FR-011).
- **FR-015**: El sistema MUST resolver cada Tarea/Subtarea recibida contra las homologaciones ya existentes de Cliente, Proyecto, Lista de Tareas y Usuario, y MUST crear el Ticket/Tarea correspondiente en SYTIX solo cuando esa cadena de homologación esté resuelta (Proyecto y Lista de Tareas ya migrados u homologados).
- **FR-016**: Una Tarea/Subtarea cuya cadena de homologación no esté completa MUST quedar excluida de la creación automática y reportada como pendiente, sin generar un Ticket huérfano ni interrumpir el resto del lote.
- **FR-017**: El sistema MUST preservar la relación jerárquica Tarea padre → Subtarea al crear los Tickets/Tareas en SYTIX, usando el mismo mecanismo de Tarea padre ya existente en SYTIX.
- **FR-018**: El sistema MUST guardar el identificador de origen de Teamwork de cada Tarea/Subtarea migrada y MUST mostrar sobre el número de Ticket en SYTIX un hipervínculo que redirija directamente a la tarea correspondiente en la plataforma de Teamwork.
- **FR-019**: Re-ejecutar la migración masiva sobre una Tarea/Subtarea ya migrada previamente (mismo identificador de origen) MUST actualizar el Ticket/Tarea existente en vez de crear un duplicado.
- **FR-020**: La migración masiva de Tareas y Subtareas MUST quedar restringida al mismo permiso ya vigente para operar el integrador de Teamwork, sin introducir un permiso nuevo.

### Key Entities *(include if feature involves data)*

- **Homologación de Persona (Personal)**: Registro existente de homologación Teamwork↔SYTIX para el tipo `person`, ampliado en su representación visible con la Compañía/Empresa de origen (ya disponible como vínculo jerárquico, hoy no resuelto para este tipo de entidad).
- **Selección masiva**: Conjunto transitorio de filas de Personal elegidas por el usuario en una operación, más el Rol y Cliente de destino elegidos para aplicar a todas ellas en una sola confirmación; no persiste como entidad propia, solo como resultado (cada fila queda migrada/homologada individualmente).
- **Tarea/Subtarea de Teamwork**: Unidad de trabajo traída desde `GET /projects/api/v3/tasks.json`, con relación a Proyecto, Lista de Tareas, Usuario asignado y, opcionalmente, una Tarea padre — se traduce a un Ticket/Tarea de SYTIX conservando su identificador de origen y la jerarquía padre-hijo.
- **Distintivo de trazabilidad**: Indicador visual asociado a un registro de SYTIX (Cliente, Proyecto, Lista de Tareas, Usuario) que señala que ese registro fue migrado o está homologado contra una entidad de Teamwork, derivado del estado ya existente de la homologación correspondiente.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En una sincronización de catálogo con más de 60 registros de origen, el número de registros sincronizados reportado por el sistema coincide al 100% con el número de filas efectivamente disponibles para el usuario en pantalla.
- **SC-002**: Un Coordinador puede migrar/homologar 10 o más personas de un mismo dominio de correo al mismo Rol y Cliente en una sola operación, en menos de 1 minuto, frente al flujo actual de una migración por fila.
- **SC-003**: El 100% de los registros migrados u homologados desde Teamwork muestran un distintivo visible tanto en el integrador como en su pantalla principal de SYTIX, y el 0% de los registros creados manualmente sin relación con Teamwork muestran ese distintivo.
- **SC-004**: Un lote de prueba de 5 a 10 Tareas/Subtareas de Teamwork con su cadena de homologación completa se migra a Tickets/Tareas de SYTIX sin generar duplicados al repetir la migración sobre el mismo lote, y cada Ticket resultante tiene un hipervínculo de origen funcional.
- **SC-005**: Todas las pantallas de sincronización de catálogos muestran exactamente 15 registros por página, sin excepción.

## Assumptions

- "Todas las pantallas de sincronización de catálogos" se interpreta como Personal, Proyectos, Listas de Tareas y Empresas (las 4 ya existentes desde spec 042/043); el bloque de filtros por Cliente/Proyecto de FR-002 aplica a Personal, Proyectos y Listas de Tareas — en Empresas no aplica un filtro por Cliente/Proyecto porque la Empresa es la raíz de esa jerarquía.
- En la pantalla de Personal, el filtro por Proyecto no tiene una relación directa en los datos de origen de Teamwork (una persona no trae Proyecto propio, solo Compañía); ese filtro queda deshabilitado en Personal y solo aplica el filtro por Cliente/Compañía, consistente con FR-003.
- Las acciones masivas de Rol + Cliente (FR-006 a FR-009) aplican específicamente a la vista de Personal, por ser el único catálogo donde Rol y Cliente de destino tienen sentido de negocio; los demás catálogos (Empresas, Proyectos, Listas de Tareas) conservan su homologación fila por fila ya existente desde spec 043.
- El endpoint `GET /projects/api/v3/tasks.json` de Teamwork soporta paginación por página de forma análoga a los endpoints v3 ya integrados (`companies.json`, `projects.json`, `people.json`, `tasklists.json`); se implementa contra la documentación oficial, sin smoke-test contra una cuenta real de Teamwork disponible en este entorno (mismo caso ya documentado en specs 041/042/043).
- La resolución de Usuario asignado en la migración de Tareas/Subtareas reutiliza el mismo criterio de homologación de Personal ya existente (por correo/ID/nombre); una Tarea cuyo asignado no esté homologado se crea sin asignar, quedando disponible para asignación manual en SYTIX (mismo tratamiento que la importación por archivo de spec 041).
- El distintivo de trazabilidad (FR-012/FR-013) se deriva del estado ya existente en `teamwork_entity_mappings` (homologado o migrado); no requiere una columna nueva de trazabilidad en las tablas principales de SYTIX.
- Queda fuera de alcance de esta especificación: la migración de tiempos registrados de las Tareas de Teamwork (fase posterior, según alcance explícito del pedido) y cualquier cambio a la lógica de negocio central de Tickets fuera del namespace de integración de Teamwork.
