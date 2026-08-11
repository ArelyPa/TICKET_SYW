# Feature Specification: Migración e Importación de Tareas desde Teamwork (API v3 / Excel) con Trazabilidad y Asignación a Coordinador

**Feature Branch**: `041-importacion-tareas-teamwork`

**Created**: 2026-08-09

**Status**: Draft

**Input**: User description: "Mapeo y Migración de Tareas de Teamwork (API v3 / Excel) con Campos de Referencia y Permisos de Coordinador — módulo de migración e importación de tareas desde Teamwork hacia SYTIX (Integración por API v3 y Carga Masiva desde Excel/CSV), trazabilidad cruzada (external_reference_id/url), vista previa antes de confirmar, y ampliación de asignación de Tickets/Tareas a usuarios con rol Coordinador además de Resolutor."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Carga masiva de tareas desde Excel/CSV con vista previa (Priority: P1)

Un Coordinador o Admin exporta el reporte estándar de tareas desde Teamwork (Excel/CSV), lo carga en SYTIX y revisa una vista previa del mapeo de cada columna (Cliente, Proyecto, Lista de Tareas, Título, Descripción, fechas, Asignado, Solicitante, Tiempo Estimado, Tarea padre) antes de confirmar la inserción masiva de las Tareas.

**Why this priority**: Es la vía de entrada más simple y de menor riesgo (no depende de credenciales ni disponibilidad de la API externa) y resuelve por sí sola el problema central: migrar el histórico de tareas de Teamwork a SYTIX sin perder datos ni trazabilidad.

**Independent Test**: Se puede probar de forma completa cargando un archivo de ejemplo con 5-10 filas (incluyendo un caso de Tarea padre + Subtarea) y verificando que las Tareas aparecen correctamente creadas en su Cliente/Proyecto/Lista de Tareas con todos los campos mapeados.

**Acceptance Scenarios**:

1. **Given** un Coordinador con un archivo Excel/CSV del reporte estándar de Teamwork, **When** lo carga en la pantalla de importación, **Then** el sistema muestra una vista previa fila por fila con el mapeo de cada columna a su campo SYTIX correspondiente, sin insertar todavía ningún dato.
2. **Given** la vista previa de una carga, **When** el Coordinador confirma la importación, **Then** el sistema crea las Tareas en su Cliente/Proyecto/Lista de Tareas correspondiente, con `external_reference_id` igual al `ID` de Teamwork.
3. **Given** una fila cuyo `Parent task ID` corresponde a otra fila del mismo archivo, **When** se confirma la importación, **Then** la tarea hija queda vinculada como Subtarea de la tarea padre recién creada.
4. **Given** una fila cuyo `Company name` o `Project` no coincide con ningún Cliente/Proyecto existente en SYTIX, **When** se genera la vista previa, **Then** esa fila se marca visualmente como pendiente de resolución y no se inserta hasta que el usuario la resuelva o la excluya.
5. **Given** un archivo que contiene una fila con el mismo `ID` de Teamwork que una Tarea ya importada anteriormente, **When** se confirma la importación, **Then** el sistema actualiza la Tarea existente en vez de crear un duplicado.

---

### User Story 2 - Trazabilidad visible del origen Teamwork en el detalle del Ticket/Tarea (Priority: P2)

Un usuario interno que abre el detalle de un Ticket o Tarea que fue migrado desde Teamwork ve un enlace o insignia identificable que lo lleva directamente a la tarea original en Teamwork, en una pestaña nueva.

**Why this priority**: Es el valor de "trazabilidad cruzada" que el usuario pidió explícitamente; sin este enlace visible, los datos migrados (`external_reference_id`/`external_reference_url`) quedan invisibles para el usuario final aunque ya existan en la base de datos.

**Independent Test**: Se puede probar de forma independiente asignando manualmente los campos de referencia externa a un Ticket/Tarea de prueba y verificando que el enlace aparece y funciona en su detalle, y que un Ticket/Tarea sin esos campos no muestra ningún elemento de Teamwork.

**Acceptance Scenarios**:

1. **Given** una Tarea con `external_reference_id` y `external_reference_url` asignados, **When** un usuario abre su detalle, **Then** ve un enlace/insignia con el icono de Teamwork que, al hacer clic, abre la tarea original en una pestaña nueva.
2. **Given** un Ticket creado directamente en SYTIX (sin origen Teamwork), **When** un usuario abre su detalle, **Then** no se muestra ningún enlace ni insignia de Teamwork.

---

### User Story 3 - Sincronización directa vía API v3 de Teamwork (Priority: P3)

Un Coordinador o Admin, desde la misma pantalla de importación, activa una sincronización directa contra la API v3 de Teamwork para traer la lista de tareas sin necesidad de exportar manualmente un archivo, revisando la misma vista previa antes de confirmar.

**Why this priority**: Automatiza la vía de entrada que hoy depende de un archivo manual, pero solo aporta valor una vez que el flujo de mapeo/vista previa/confirmación ya está probado y funcionando con archivos (US1), por lo que se implementa después.

**Independent Test**: Se puede probar de forma independiente conectando contra un espacio de pruebas de Teamwork (o datos de API simulados) y verificando que el resultado recuperado pasa por la misma vista previa y produce el mismo resultado que una carga por archivo equivalente.

**Acceptance Scenarios**:

1. **Given** un Coordinador en la pantalla de importación, **When** activa la sincronización por API v3, **Then** el sistema consulta `/projects/api/v3/tasks.json` y muestra la misma vista previa de mapeo que la carga por archivo, sin insertar datos todavía.
2. **Given** una sincronización por API v3 en curso, **When** la conexión falla a mitad del proceso, **Then** el sistema conserva las tareas ya obtenidas exitosamente y comunica claramente cuántas quedaron pendientes, sin dejar registros a medio insertar.

---

### User Story 4 - Asignación de Tickets/Tareas a usuarios con rol Coordinador (Priority: P2)

Un Coordinador, al asignar o reasignar un Ticket o Tarea (incluyendo los recién importados desde Teamwork, cuyo `Assigned to` original puede corresponder a alguien con rol Coordinador en SYTIX), puede elegir como responsable tanto a un usuario con rol Resolutor como a uno con rol Coordinador.

**Why this priority**: Sin esto, una parte de las tareas migradas desde Teamwork (las asignadas a quienes hoy son Coordinadores en SYTIX) no se podría mapear correctamente al campo Asignado; es independiente del resto del módulo de importación pero necesaria para que la migración quede completa.

**Independent Test**: Se puede probar de forma independiente, sin importar nada de Teamwork, abriendo el selector de asignación de cualquier Ticket/Tarea existente y verificando que ahora lista también a los usuarios con rol Coordinador.

**Acceptance Scenarios**:

1. **Given** el formulario/panel de asignación de un Ticket o Tarea, **When** un Coordinador abre el selector de responsable, **Then** la lista incluye tanto usuarios con rol Resolutor como usuarios con rol Coordinador.
2. **Given** un Ticket/Tarea asignado a un usuario con rol Coordinador, **When** se reasigna a otro usuario, **Then** el historial de reasignación registra el cambio igual que hoy lo hace entre Resolutores (spec 023).

---

### Edge Cases

- ¿Qué pasa si una fila trae `Parent task ID` que no corresponde a ninguna tarea incluida en el archivo actual ni previamente importada? El sistema la marca en la vista previa como Subtarea sin padre resuelto, y la fila puede importarse igual como tarea de primer nivel.
- ¿Qué pasa si dos filas del mismo archivo comparten el mismo `ID` de Teamwork? Se marca como error de fila en la vista previa y no se inserta duplicado.
- ¿Cómo se maneja una fecha vacía o con formato inválido en `Start date`/`Due date`? El campo queda vacío en SYTIX; la fila se importa igual, sin bloquear el resto del archivo.
- ¿Qué pasa si `Assigned to` o `Created by` no coincide de forma inequívoca con ningún usuario de SYTIX (sin coincidencia, o coincidencia ambigua por nombre repetido)? La fila se marca en la vista previa como pendiente de resolución manual antes de poder confirmarse.
- ¿Qué pasa si se intenta cargar un archivo que no tiene las columnas mínimas esperadas del reporte de Teamwork? El sistema rechaza el archivo completo antes de generar cualquier vista previa, indicando qué columnas faltan.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir a un usuario con rol Coordinador o Admin cargar un archivo Excel/CSV con el reporte estándar de tareas de Teamwork desde una pantalla de administración/herramientas.
- **FR-002**: El sistema DEBE generar y mostrar una vista previa del mapeo de cada fila del archivo a los campos correspondientes en SYTIX (Cliente, Proyecto, Lista de Tareas, Título, Descripción, Fecha de inicio, Vencimiento, Asignado, Solicitante, Tiempo Estimado, referencia externa, Tarea padre) antes de insertar cualquier dato.
- **FR-003**: La vista previa DEBE señalar de forma distinguible las filas cuyo Cliente, Proyecto, Asignado o Solicitante no se pueden resolver automáticamente contra los datos existentes en SYTIX.
- **FR-004**: El sistema NO DEBE insertar en la base de datos ninguna fila de la vista previa hasta que el usuario confirme explícitamente la importación.
- **FR-005**: El sistema DEBE crear automáticamente la Lista de Tareas (`Task list`) dentro del Proyecto correspondiente cuando no exista ya una con ese nombre.
- **FR-006**: El sistema DEBE almacenar el identificador original de Teamwork en `external_reference_id` y construir `external_reference_url` (enlace directo a la tarea en Teamwork) para cada Ticket/Tarea creado o actualizado por una importación.
- **FR-007**: El sistema DEBE vincular automáticamente como Subtarea a toda fila importada cuyo `Parent task ID` corresponda a otra tarea ya existente en SYTIX (importada en el mismo proceso o en uno anterior).
- **FR-008**: El sistema DEBE convertir el `Time estimate` reportado en minutos a horas al poblar el Tiempo Estimado de la Tarea.
- **FR-009**: Si una fila a importar tiene el mismo `external_reference_id` que un Ticket/Tarea ya existente en SYTIX, el sistema DEBE actualizar ese registro existente en vez de crear uno duplicado.
- **FR-010**: El sistema DEBE permitir a un usuario con rol Coordinador o Admin iniciar, bajo demanda, una sincronización de tareas mediante la API v3 de Teamwork (`/projects/api/v3/tasks.json`), aplicando el mismo mapeo de campos y el mismo flujo de vista previa/confirmación que la carga por archivo.
- **FR-011**: En la vista de detalle de un Ticket o Tarea que tenga `external_reference_id` y `external_reference_url` poblados, el sistema DEBE mostrar un enlace o insignia identificable como Teamwork que abra la tarea original en una pestaña nueva del navegador.
- **FR-012**: Un Ticket/Tarea sin `external_reference_id`/`external_reference_url` NO DEBE mostrar ningún elemento de Teamwork en su detalle.
- **FR-013**: El sistema DEBE permitir asignar y reasignar un Ticket o Tarea tanto a usuarios con rol Resolutor como a usuarios con rol Coordinador, en todos los puntos donde hoy la validación solo permite Resolutor.
- **FR-014**: El registro de reasignación existente ("resolutor anterior ➡️ nuevo resolutor", spec 023) DEBE seguir funcionando sin cambios cuando cualquiera de los dos extremos del cambio es un usuario con rol Coordinador.
- **FR-015**: El sistema DEBE dejar constancia consultable de cada proceso de importación (usuario que lo ejecutó, fecha/hora, origen, cantidad de filas creadas, actualizadas y con error).

### Key Entities *(include if feature involves data)*

- **Ticket/Tarea**: entidad existente; se amplía con `external_reference_id` (identificador original en Teamwork) y `external_reference_url` (enlace directo a la tarea original).
- **Registro de importación**: representa una ejecución de carga por archivo o sincronización por API v3 — quién la ejecutó, cuándo, origen (Excel/CSV o API v3) y el resultado (filas creadas, actualizadas, con error).
- **Fila de vista previa**: representación temporal de una fila del archivo/respuesta de API antes de confirmarse, con su estado de resolución (lista para importar, pendiente de resolución manual, error) y los campos SYTIX a los que se mapea.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un Coordinador puede cargar un archivo estándar de Teamwork y obtener la vista previa completa del mapeo de sus filas sin necesidad de soporte técnico externo.
- **SC-002**: El 100% de los Tickets/Tareas creados o actualizados por una importación conservan un enlace funcional y visible a su tarea original en Teamwork.
- **SC-003**: Repetir la misma carga o sincronización dos veces nunca produce Tickets/Tareas duplicados.
- **SC-004**: Las relaciones Tarea padre-Subtarea declaradas en el origen se reconstruyen correctamente en SYTIX siempre que la tarea padre esté incluida en la misma importación o ya exista de una anterior.
- **SC-005**: Un usuario con rol Coordinador puede quedar como responsable de un Ticket/Tarea a través de los mismos flujos de asignación y reasignación que hoy solo admiten Resolutores, sin pasos adicionales ni comportamiento distinto.

## Assumptions

- Reimportar la misma fuente (archivo o sincronización API) usando el mismo `external_reference_id` actualiza el registro ya existente en vez de duplicarlo; no se pidió una política de "crear siempre un registro nuevo".
- La sincronización por API v3 es una acción manual bajo demanda iniciada por un Coordinador/Admin desde la pantalla de importación, no un proceso automático recurrente en segundo plano.
- Solo los roles Coordinador y Admin pueden ejecutar la importación (Excel/CSV o API v3), en línea con el resto de pantallas de administración/herramientas ya existentes en SYTIX.
- Los registros importados desde Teamwork se crean en SYTIX como "Tarea" (no como "Ticket"), dado que las columnas del reporte (`Task list`, `Parent task ID`) corresponden directamente a la jerarquía Proyecto → Lista de Tareas → Tarea → Subtarea ya existente en SYTIX.
- Si `Company name`, `Project`, `Assigned to` o `Created by` no coinciden de forma inequívoca con un registro existente en SYTIX, la fila se marca como pendiente de resolución manual en la vista previa; el sistema no crea Clientes ni Proyectos nuevos de forma automática.
- Las credenciales de conexión a la API v3 de Teamwork (dominio y token) se configuran una única vez por un Admin y se reutilizan en cada sincronización posterior.

## Ejemplo de datos de referencia (validación de columnas real)

El usuario adjuntó un export real de Teamwork (`All Tasks Report - 06 Aug 2026.xlsx`, 85 filas,
15 Clientes/Company distintos) que confirma y complementa lo especificado arriba:

- Las 12 columnas listadas en la sección "Homologación y Mapeo de Datos" existen tal cual en el
  export real, con esos nombres exactos. El archivo real trae además otras columnas (`Status`,
  `Milestone`, `Progress`, `Priority`, `Billable minutes`, `Tags`, `Workflow Stages`, etc.) que
  **no** forman parte del mapeo pedido y se ignoran al importar — fuera de alcance de esta
  feature.
- **Confirma el edge case de `Parent task ID` "huérfano"**: en el export real, de 71 filas con
  `Parent task ID` poblado, **ninguna** tiene a su tarea padre incluida en el mismo archivo (el
  export de Teamwork no arrastra automáticamente la tarea padre de una subtarea filtrada). Es el
  caso dominante, no una excepción — la vista previa debe manejarlo con normalidad (fila
  importada como Tarea de primer nivel, ver Edge Cases).
- **`Time estimate` suele venir en 0** en la práctica: el esfuerzo real muchas veces se registra
  en la columna `Billable minutes` (fuera del mapeo pedido) en vez de `Time estimate`. No cambia
  el requisito (FR-008 sigue mapeando específicamente `Time estimate`), pero se documenta para no
  sorprenderse si muchas Tareas importadas quedan con Tiempo Estimado en 0.
- Ninguna fila del export trae `Assigned to`/`Created by` vacío, pero es esperable que **ninguno**
  de esos nombres coincida con un usuario ya existente en SYTIX (son personas reales de Teamwork,
  no seeded en el entorno de desarrollo) — validando en la práctica el flujo de "pendiente de
  resolución manual" (FR-003) como el camino más frecuente, no el excepcional.
- Un fixture recortado de 8 filas derivado de este export real (Principio VII: máximo 5-10 filas)
  se guardó en [`ejemplo-teamwork-tasks.xlsx`](ejemplo-teamwork-tasks.xlsx) /
  [`.csv`](ejemplo-teamwork-tasks.csv) para usarse como caso de prueba durante `/speckit-tasks` e
  implementación. Incluye: una fila sintética (`ID` sintético, marcada como tal en el título) para
  probar el caso "padre incluido en el lote" ya que ningún par real padre+hijo convive en el
  export original; una fila real hija con su padre real ausente (caso dominante); una fila del
  cliente `Aris` (ya existe en SYTIX, pero con `Project`/`Task list` que no calzan exactamente
  con los ya sembrados — dispara `needs_review` de todas formas); y filas de clientes que no
  existen en SYTIX (`Cargill`, `Congrupo`, `Consorcio Shushufindi S.A.`).
