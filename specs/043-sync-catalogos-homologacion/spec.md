# Feature Specification: Ampliación y Ajustes Finos en la Sincronización de Catálogos de Teamwork (Mapeo, Homologación y Creación Dinámica)

**Feature Branch**: `043-sync-catalogos-homologacion`

**Created**: 2026-08-10

**Status**: Draft

**Input**: User description: "Ampliación y Ajustes Finos en la Sincronización de Catálogos de Teamwork (Mapeo, Homologación y Creación Dinámica) — mayor contexto (Cliente, Proyecto, Correo) en la tabla de Homologación de Entidades de la Integración Teamwork (spec 042), acción explícita Homologar vs. Migrar Nuevo por fila, asignación de Rol previa a migrar una Persona, y trazabilidad de IDs externos con badge de estado."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Elegir Homologar o Migrar Nuevo por fila (Priority: P1)

Un Coordinador o Admin sincroniza un catálogo de Teamwork (Empresas, Proyectos, Personal o Listas de Tareas) y, para cada fila sin resolver, decide explícitamente si quiere **vincular** la entidad de Teamwork a un registro de SYTIX ya existente, o **crear un registro nuevo** en SYTIX con los datos que trae Teamwork — hoy la tabla de Homologación de Entidades (`TeamworkIntegrationPage.tsx`) solo ofrece un selector de vínculo a un registro existente; no hay forma de crear uno nuevo desde ahí.

**Why this priority**: Es el cambio central que pide el usuario — sin esta acción, cualquier entidad de Teamwork que no tenga aún equivalente en SYTIX queda permanentemente sin homologar, obligando a crearla manualmente en otra pantalla y homologarla después.

**Independent Test**: Sincronizar el catálogo de Empresas, tomar una fila sin coincidencia sugerida, presionar "Migrar como Nuevo", confirmar el formulario con los datos precargados de Teamwork, y verificar que aparece un Cliente nuevo en Maestros > Clientes y que la fila de homologación queda vinculada a él automáticamente.

**Acceptance Scenarios**:

1. **Given** una fila de Homologación de Entidades sin `sytix_id`, **When** el usuario elige "Modificar/Vincular a Existente", **Then** ve el mismo selector de búsqueda ya existente para elegir el registro de SYTIX y vincularlo (comportamiento actual, sin cambios).
2. **Given** una fila de Homologación de Entidades sin `sytix_id` (cualquier tipo de entidad: Empresa, Proyecto, Persona o Lista de Tareas), **When** el usuario elige "Migrar como Nuevo" y confirma, **Then** el sistema crea el registro correspondiente en SYTIX con los datos traídos de Teamwork, aplica las mismas validaciones que su formulario de creación manual ya tiene, y vincula la fila de homologación al registro recién creado.
3. **Given** una fila ya vinculada (por automapeo o manualmente) a un registro de SYTIX, **When** el usuario la ve en la tabla, **Then** las acciones "Migrar como Nuevo"/"Homologar" quedan deshabilitadas o reemplazadas por la opción de cambiar el vínculo existente, para no crear duplicados por error.
4. **Given** la creación de un registro nuevo falla una validación de SYTIX (ej. nombre duplicado, dominio de correo inválido), **When** el usuario confirma "Migrar como Nuevo", **Then** el sistema muestra el error de validación sin crear el registro ni modificar la fila de homologación.

---

### User Story 2 - Contexto de Cliente en Proyectos y Listas de Tareas (Priority: P1)

Un Coordinador sincroniza el catálogo de Proyectos o de Listas de Tareas y ve, junto a cada nombre, el Cliente/Empresa de Teamwork al que pertenece — hoy la tabla solo muestra el nombre de Teamwork, lo que hace indistinguibles a dos proyectos homónimos ("Soporte", "Evolutivo") de clientes distintos.

**Why this priority**: Sin este contexto, homologar o migrar un Proyecto o una Lista de Tareas es una operación insegura: el usuario no tiene forma de saber a qué Cliente real corresponde el registro antes de vincularlo o crearlo.

**Independent Test**: Sincronizar Proyectos de una cuenta de Teamwork con al menos dos proyectos llamados igual pero de empresas distintas, y verificar que la columna "Cliente Asociado" muestra el nombre correcto de cada empresa (u "Homologar Empresa primero" si la empresa de Teamwork aún no está vinculada a un Cliente de SYTIX).

**Acceptance Scenarios**:

1. **Given** la tabla de Homologación de Entidades filtrada por "Proyectos", **When** se muestra cada fila, **Then** aparece una columna "Cliente Asociado" con el nombre de la Empresa de Teamwork dueña del proyecto.
2. **Given** la Empresa de Teamwork de un Proyecto ya fue homologada o migrada a un Cliente de SYTIX, **When** se muestra la fila del Proyecto, **Then** la columna "Cliente Asociado" refleja el nombre del Cliente de SYTIX vinculado (no solo el nombre crudo de Teamwork).
3. **Given** la Empresa de Teamwork de un Proyecto todavía no tiene homologación, **When** se muestra la fila del Proyecto, **Then** la columna "Cliente Asociado" indica claramente que la Empresa está pendiente de homologar, y la acción "Migrar como Nuevo" del Proyecto queda deshabilitada hasta resolverlo (un Proyecto en SYTIX siempre requiere un Cliente).
4. **Given** la tabla de Homologación de Entidades filtrada por "Listas de Tareas", **When** se muestra cada fila, **Then** aparecen las columnas "Cliente" y "Proyecto" a las que pertenece la lista en Teamwork, con el mismo criterio de resolución de los puntos 2 y 3.

---

### User Story 3 - Correo, Rol y creación de cuenta al migrar Personal (Priority: P2)

Un Coordinador sincroniza el catálogo de Personal de Teamwork, ve el correo de cada persona junto a su nombre (para detectar si ya existe como Recurso o Usuario/cliente en SYTIX) y, al migrar una persona nueva, elige el Rol que va a tener en SYTIX antes de crear su cuenta.

**Why this priority**: Depende de la acción "Migrar como Nuevo" de US1; agrega el dato (correo) y el control (rol) que la creación de un usuario/recurso real necesita, evitando cuentas mal configuradas que haya que corregir después.

**Independent Test**: Sincronizar Personal, ubicar una persona sin homologar cuyo correo no coincide con ningún Recurso/Usuario existente, elegir el rol "Resolutor" en el selector de la fila, confirmar "Migrar como Nuevo", y verificar que se crea la cuenta con ese rol y ese correo, respetando las mismas validaciones que la creación manual de usuarios ya tiene (formato de correo, unicidad, dominio permitido para Recursos sin acceso de login cuando aplique).

**Acceptance Scenarios**:

1. **Given** la tabla de Homologación de Entidades filtrada por "Personal", **When** se muestra cada fila, **Then** aparece una columna "Correo" con el email traído de Teamwork.
2. **Given** una fila de Personal sin `sytix_id`, **When** el usuario abre la acción "Migrar como Nuevo", **Then** debe elegir un Rol (Admin, Coordinador, QM, Resolutor o Usuario/cliente) antes de poder confirmar la creación.
3. **Given** el rol elegido es "Usuario/cliente", **When** se confirma la migración, **Then** el sistema exige además asociar la cuenta nueva a un Cliente de SYTIX (mismo requisito que ya aplica a la creación manual de un Usuario/cliente), reutilizando la homologación de Empresa si ya existe.
4. **Given** el correo de Teamwork ya pertenece a un usuario existente de SYTIX, **When** el usuario intenta "Migrar como Nuevo", **Then** el sistema rechaza la operación con un mensaje claro y sugiere usar "Homologar" en su lugar.

---

### User Story 4 - Trazabilidad visible de IDs externos y estado de migración (Priority: P2)

Cualquier usuario con acceso al módulo puede ver de un vistazo, en la tabla de Homologación de Entidades, cuáles filas ya fueron resueltas (homologadas a un registro existente o migradas como nuevo) y cuáles siguen pendientes, sin tener que abrir cada una para revisarlo.

**Why this priority**: Es la salvaguarda que evita reprocesar la misma entidad dos veces (crear un duplicado o pisar una homologación ya hecha) a medida que crece el volumen de catálogos sincronizados.

**Independent Test**: Con una tabla que mezcla filas homologadas manualmente, filas migradas como nuevas, filas automapeadas y filas pendientes, verificar que cada grupo muestra un badge distinto y que el estado persiste después de recargar la página o volver a sincronizar el mismo catálogo.

**Acceptance Scenarios**:

1. **Given** una fila fue resuelta con la acción "Migrar como Nuevo", **When** se muestra en la tabla, **Then** su badge de estado indica "Migrado" (distinto del badge "Homologado" que ya existe hoy para vínculos manuales, y de los badges de automapeo por correo/ID/nombre).
2. **Given** una fila de Personal fue migrada como nuevo, **When** se consulta el registro creado en SYTIX, **Then** conserva de forma persistente el ID original de Teamwork (`teamwork_user_id`), reutilizable en sincronizaciones futuras para automapear por ID externo sin depender solo del correo.
3. **Given** se vuelve a sincronizar un catálogo cuyas filas ya están "Migrado" o "Homologado", **When** la sincronización corre, **Then** esas filas conservan su vínculo y estado (no se sobrescriben ni se ofrecen de nuevo como pendientes).

---

### Edge Cases

- ¿Qué pasa si el usuario intenta "Migrar como Nuevo" un Proyecto cuya Empresa de Teamwork nunca fue sincronizada como catálogo de Empresas? → Debe pedirse sincronizar/homologar Empresas primero; no se permite crear un Proyecto sin Cliente resuelto.
- ¿Qué pasa si dos filas distintas de Teamwork (ej. dos Personas con el mismo nombre pero correos distintos) intentan migrarse como nuevo una tras otra? → Cada una se valida y crea de forma independiente; el correo (único) es lo que evita colisión, no el nombre.
- ¿Qué pasa si el usuario cambia el Rol elegido después de haber empezado a llenar el formulario de "Migrar como Nuevo" de una Persona y el nuevo rol exige un campo que el anterior no exigía (ej. pasa de Resolutor a Usuario/cliente)? → El formulario debe recalcular los campos obligatorios visibles sin perder los datos ya cargados de Teamwork (nombre, correo).
- ¿Qué pasa si una Lista de Tareas se intenta migrar antes de que su Proyecto esté homologado o migrado? → La acción "Migrar como Nuevo" de la Lista de Tareas queda deshabilitada, igual que para Proyecto sin Cliente resuelto (US2, escenario 3).
- ¿Qué pasa con filas de Homologación de Entidades creadas antes de esta funcionalidad (ya en producción desde la spec 042), que no tienen aún estado "Migrado" definido? → Se tratan como "Homologado" si ya tienen `sytix_id`, o "Pendiente" si no, sin requerir ninguna migración de datos retroactiva.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST ofrecer, en cada fila sin resolver de la tabla de Homologación de Entidades, dos acciones explícitas: "Modificar/Vincular a Existente" (comportamiento ya existente) y "Migrar como Nuevo".
- **FR-002**: La acción "Migrar como Nuevo" MUST crear un registro nuevo en SYTIX (Cliente, Proyecto, Recurso/Usuario o Lista de Tareas según el tipo de entidad) usando los datos disponibles de Teamwork como valores iniciales, y MUST aplicar las mismas reglas de validación que ya rigen la creación manual de ese tipo de registro en su pantalla correspondiente.
- **FR-003**: Al confirmar "Migrar como Nuevo" con éxito, el sistema MUST vincular automáticamente la fila de homologación al registro recién creado, dejándola en estado "Migrado".
- **FR-004**: Una fila ya vinculada a un registro de SYTIX (por automapeo, homologación manual o migración) MUST impedir volver a ejecutar "Migrar como Nuevo" sobre ella, para evitar registros duplicados.
- **FR-005**: La tabla de Homologación de Entidades filtrada por Proyectos MUST mostrar una columna "Cliente Asociado" con el nombre del Cliente/Empresa de Teamwork dueño de cada proyecto, resuelto contra la homologación de Empresas cuando exista.
- **FR-006**: Si la Empresa de Teamwork de un Proyecto todavía no está homologada ni migrada, el sistema MUST señalarlo explícitamente en la columna "Cliente Asociado" y MUST deshabilitar la acción "Migrar como Nuevo" de ese Proyecto hasta que se resuelva.
- **FR-007**: La tabla de Homologación de Entidades filtrada por Listas de Tareas MUST mostrar las columnas "Cliente" y "Proyecto" a las que pertenece cada lista en Teamwork, con la misma regla de bloqueo del FR-006 aplicada al Proyecto.
- **FR-008**: La tabla de Homologación de Entidades filtrada por Personal MUST mostrar una columna "Correo Electrónico" con el email traído de Teamwork.
- **FR-009**: Antes de confirmar "Migrar como Nuevo" sobre una fila de Personal, el sistema MUST exigir la selección de un Rol (Admin, Coordinador, QM, Resolutor o Usuario/cliente) para la cuenta que se va a crear.
- **FR-010**: Si el Rol elegido es "Usuario/cliente", el sistema MUST exigir además la asociación a un Cliente de SYTIX antes de permitir confirmar la creación.
- **FR-011**: Si el correo traído de Teamwork ya pertenece a una cuenta existente en SYTIX, el sistema MUST rechazar la acción "Migrar como Nuevo" para esa fila con un mensaje que oriente a usar "Homologar" en su lugar, sin crear una cuenta duplicada.
- **FR-012**: El sistema MUST persistir el ID original de Teamwork (`teamwork_user_id` u homólogo por tipo de entidad) en el registro de SYTIX resultante de una migración, de forma reutilizable por futuras sincronizaciones para automapear por ID externo.
- **FR-013**: La tabla de Homologación de Entidades MUST distinguir visualmente (badge o etiqueta de estado) entre filas "Pendiente" (sin vínculo), "Homologado" (vinculada a un registro existente, manual o por automapeo) y "Migrado" (vinculada a un registro creado desde esta pantalla).
- **FR-014**: Re-sincronizar un catálogo cuyas filas ya están "Homologado" o "Migrado" MUST conservar su vínculo y estado existentes, sin ofrecerlas de nuevo como pendientes ni sobrescribir su `sytix_id`.

### Key Entities *(include if feature involves data)*

- **Homologación de Entidad (`teamwork_entity_mappings`, ya existente)**: registro que vincula una entidad de Teamwork (Empresa/Proyecto/Persona/Lista de Tareas) con su equivalente en SYTIX. Se amplía conceptualmente con un estado que distingue si el vínculo se originó por automapeo/homologación manual o por creación de un registro nuevo ("Migrado"), y con el contexto jerárquico necesario para mostrarlo (Empresa dueña de un Proyecto; Empresa y Proyecto dueños de una Lista de Tareas).
- **Registro migrado en SYTIX (Cliente, Proyecto, Recurso/Usuario o Lista de Tareas)**: registro creado a partir de los datos de Teamwork vía "Migrar como Nuevo", que conserva el ID externo de Teamwork para trazabilidad y automapeo futuro, sujeto a las mismas reglas de validación y de rol/permiso que su creación manual ya tiene.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un Coordinador puede migrar una entidad de Teamwork sin equivalente previo en SYTIX (Cliente, Proyecto, Persona o Lista de Tareas) sin salir de la pantalla de Integración Teamwork ni volver a introducir manualmente los datos que ya trae Teamwork.
- **SC-002**: Frente a dos proyectos o listas de tareas homónimos de clientes distintos, el usuario identifica correctamente a cuál pertenece cada fila el 100% de las veces, sin necesidad de consultar otra pantalla.
- **SC-003**: Ninguna migración de Personal crea una cuenta duplicada cuando el correo de Teamwork ya existe en SYTIX.
- **SC-004**: Después de sincronizar el mismo catálogo dos veces seguidas, el número de filas "Migrado" u "Homologado" no cambia si no hubo intervención manual entre medio (cero regresiones a "Pendiente").

## Assumptions

- Los catálogos de SYTIX destino (Clientes, Proyectos, Recursos/Usuarios, Listas de Tareas) y sus reglas de validación de creación ya existen y no se modifican; esta funcionalidad solo los invoca para crear un registro nuevo con datos precargados de Teamwork.
- El listado de Roles asignables al migrar Personal es el mismo catálogo de roles internos/externos ya usado en el resto de SYTIX (Admin, Coordinador, QM, Resolutor, Usuario/cliente); no se agregan roles nuevos.
- La relación jerárquica Empresa→Proyecto→Lista de Tareas de Teamwork se obtiene ampliando la sincronización ya existente para capturar los IDs de la empresa/proyecto dueños de cada elemento (dato que la API v3 de Teamwork ya expone junto al resto de campos actualmente consumidos), sin agregar un endpoint ni una dependencia nueva.
- Los permisos ya existentes `teamwork_integration:manage`/`operate` (spec 042) siguen siendo el único control de acceso para esta pantalla; no se agregan permisos nuevos para distinguir "Homologar" de "Migrar como Nuevo".
- Los IDs externos de trazabilidad (`teamwork_user_id` y homólogos) se agregan como columnas aditivas en las tablas de destino ya existentes (Recursos/Usuarios, Clientes, Proyectos, Listas de Tareas), sin introducir una tabla de auditoría nueva más allá de la ya existente `teamwork_entity_mappings`.
