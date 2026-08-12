# Feature Specification: Portal de Cliente (Login Diferenciado, Aislamiento por Cliente, Comentarios Públicos y Respuesta a Solicitud de Información)

**Feature Branch**: `046-portal-cliente`

**Created**: 2026-08-12

**Status**: Draft

**Input**: User description: "Implementación del Portal de Cliente (Login Diferenciado, Restricción de Ámbito, Comentarios Públicos y Respuestas de Información) — diferenciar el acceso en el Login para el rol Usuario/cliente, restringir visibilidad de datos e interacciones (aislamiento por cliente, sin creación, comentarios internos ocultos), habilitar el flujo de respuesta a 'Solicitud de información', y agregar Centro de Notificaciones + filtro 'Asignado a mí' para este rol."

## Contexto del sistema existente

Esta feature formaliza y cierra una "Fase 8" ya anticipada en el modelo de datos actual: `backend/domain/entities/comment.py` ya clasifica cada tipo de comentario como `internal`/`external` con el comentario explícito *"external = visible al cliente (Portal, Fase 8)"*, y la máquina de estados (`backend/domain/fsm/ticket_fsm.py`) ya tiene el ciclo `solicitud_informacion` (cualquier fase → `pendiente_usuario`) y `respuesta_usuario` (`pendiente_usuario` → `en_ejecucion`) completamente definido. Lo que falta es exponer y restringir esa capacidad ya modelada al lado del Usuario/cliente. Puntos de partida relevantes:

- El rol `Usuario/cliente` (renombrado de "Encargado" en spec 010/migración 025) ya existe, con permiso `tickets:view_own` que hoy fuerza el listado a `created_by = usuario actual` (no a todo el Cliente/empresa) y `tickets:create` habilitado para alta simplificada ("autoservicio", solo título/descripción, spec 010/033).
- La API (`_ticket_detail` en `backend/api/routes/tickets.py`) ya serializa `visibility` por comentario pero **no filtra** hoy los comentarios `internal` antes de devolverlos — cualquier consumidor autenticado con acceso al ticket ve el historial completo.
- `comment_service.validate()` exige `actor_can_manage` (Coordinador/QM/Admin) o ser el Resolutor asignado para registrar un comentario con trigger de transición — un Usuario/cliente hoy **no puede** registrar `respuesta_usuario`, aunque el tipo y la transición FSM ya existan.
- Ya existe `NotificationService`/`notification_model`/`GET /api/notifications` (usado hoy para eventos de asignación/reasignación) y ya existe un filtro "Asignado a mí" para Resolutor en Tickets/Kanban/Mis Tareas (spec 038 US1).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Acceso diferenciado en el Login (Priority: P1)

Un colaborador de un Cliente (dominio de correo externo) y un empleado interno (`@sywork.net`) llegan a la misma URL de login. Cada uno elige la pestaña correspondiente a su tipo de cuenta ("Equipo / Empleados" o "Portal de Clientes / Colaboradores") y se autentica con las mismas credenciales de siempre, sin cambiar de URL ni de formulario de recuperación de contraseña.

**Why this priority**: Es el punto de entrada de todo lo demás — sin esto no hay forma diferenciada de llegar al Portal.

**Independent Test**: Abrir `/login`, alternar entre ambas pestañas y verificar que el formulario (usuario/correo + contraseña) y el flujo de "¿Olvidaste tu contraseña?" siguen funcionando igual en cualquiera de las dos, con el estilo visual de SYTIX ya vigente (`AuthLayout.tsx`).

**Acceptance Scenarios**:

1. **Given** la pantalla de login, **When** el usuario no interactúa con las pestañas, **Then** se muestra la pestaña "Equipo / Empleados" seleccionada por defecto.
2. **Given** la pestaña "Portal de Clientes / Colaboradores" seleccionada, **When** un Usuario/cliente válido ingresa sus credenciales correctas, **Then** accede normalmente al sistema con su ámbito restringido (User Story 2).
3. **Given** cualquiera de las dos pestañas, **When** las credenciales son incorrectas, **Then** se muestra el mismo mensaje de error ya existente, sin filtrar si el usuario existe o su rol.

---

### User Story 2 - Aislamiento de datos por Cliente (Priority: P1)

Un Usuario/cliente autenticado abre los listados de Tickets, Tareas y Proyectos y solo ve los registros de su propia empresa/cliente — nunca los de otros clientes de SYTIX.

**Why this priority**: Es la garantía de confidencialidad básica del Portal; sin esto, ningún otro punto de la feature es seguro de habilitar.

**Independent Test**: Loguearse como un Usuario/cliente de un Cliente sembrado (p. ej. Aris) y confirmar que `GET /api/tickets`, `GET /api/tasks` (o equivalente) y el listado de Proyectos devuelven exclusivamente registros con `client_id` igual al del Cliente del usuario, incluso ante intentos de manipular filtros/parámetros de la URL.

**Acceptance Scenarios**:

1. **Given** un Usuario/cliente de la empresa Aris, **When** abre el listado de Tickets/Tareas, **Then** solo ve registros cuyo Proyecto pertenece a Aris.
2. **Given** ese mismo listado, **When** intenta forzar por API un filtro de otro `client_id`, **Then** el servidor ignora el filtro y aplica igualmente el aislamiento por su propio Cliente.
3. **Given** el listado de Proyectos, **When** el Usuario/cliente lo abre, **Then** solo ve los Proyectos de su Cliente (y no accede a Maestros administrativos, ya restringido desde spec 038 US1).

---

### User Story 3 - Comentarios internos nunca visibles (Priority: P1)

Un Usuario/cliente abre el detalle de un Ticket/Tarea de su empresa y en el historial de comentarios solo aparecen los tipos marcados como públicos (`external`); los comentarios internos del equipo de soporte (notas de diagnóstico, comentarios internos, etc.) están completamente ausentes — no ocultos por CSS, sino nunca entregados por la API.

**Why this priority**: Es un requisito de confidencialidad tan crítico como el aislamiento por cliente (US2); una fuga aquí expondría diagnóstico interno a un tercero.

**Independent Test**: Con un Ticket que tenga al menos un comentario `comentario_interno`/`asignado`/`pre_analisis`/`termina_analisis`/`descripcion_solucion` (internos) y uno `confirmacion_atencion`/`solicitud_informacion`/`solicitud_cierre`/`respuesta_usuario` (externos), confirmar que la respuesta de la API al Usuario/cliente solo trae los externos — no solo que el frontend los esconda.

**Acceptance Scenarios**:

1. **Given** un Ticket con comentarios internos y externos, **When** un Usuario/cliente autorizado a verlo consulta su detalle, **Then** la respuesta de la API excluye por completo los comentarios `visibility = internal`.
2. **Given** el mismo Ticket, **When** un Coordinador/QM/Admin/Resolutor lo consulta, **Then** ve el historial completo (sin cambios respecto al comportamiento actual).

---

### User Story 4 - Responder una "Solicitud de información" (Priority: P2)

Un resolutor registra un comentario tipo "Solicitud de información" sobre un Ticket de un Cliente (ya deja el ticket en estado `pendiente_usuario`, comportamiento FSM existente). El Usuario/cliente correspondiente ve ese comentario en el historial y se le habilita una caja de respuesta exclusiva para ese caso; al enviarla, el comentario queda adjunto al historial del ticket con su información y el ticket transiciona de vuelta (`pendiente_usuario` → `en_ejecucion`, transición `respuesta_usuario` ya existente en la FSM) notificando al resolutor asignado.

**Why this priority**: Es el valor funcional central del Portal (cerrar el ciclo de comunicación con el cliente), pero depende de que US1-US3 ya limiten correctamente el acceso.

**Independent Test**: Como Coordinador/Resolutor, registrar un comentario `solicitud_informacion` sobre un ticket de un Cliente con Usuario/cliente asociado; loguearse como ese Usuario/cliente, confirmar que aparece la caja de respuesta solo mientras el ticket está en `pendiente_usuario`, enviarla y verificar que el ticket pasa a `en_ejecucion` y el resolutor recibe notificación.

**Acceptance Scenarios**:

1. **Given** un Ticket en estado `pendiente_usuario` por una `solicitud_informacion` dirigida a su empresa, **When** el Usuario/cliente solicitante (o cualquier Usuario/cliente de esa empresa con acceso al ticket) abre el detalle, **Then** ve una caja de respuesta habilitada.
2. **Given** esa caja de respuesta, **When** el Usuario/cliente envía su respuesta, **Then** se crea un comentario tipo `respuesta_usuario` visible en el historial, el ticket transiciona a `en_ejecucion`, y el resolutor asignado recibe una notificación de que la información fue entregada.
3. **Given** un Ticket que NO está en `pendiente_usuario`, **When** el Usuario/cliente ve su detalle, **Then** la caja de respuesta no se muestra (solo lectura de comentarios públicos).

---

### User Story 5 - Solo alta simplificada de Ticket, sin Tareas ni campos avanzados (Priority: P2)

Un Usuario/cliente navega el Portal y conserva la única acción de creación que ya tenía (alta simplificada de Ticket: título + descripción, autoservicio existente); no encuentra ningún botón para crear Tareas, ni ningún campo de creación pensado para perfil interno (Proyecto, Herramienta/Proceso, Skills, asignación manual de resolutor).

**Why this priority**: Es una restricción de UI/permiso puntual, de menor riesgo que el aislamiento de datos, pero forma parte explícita del alcance pedido.

**Independent Test**: Loguearse como Usuario/cliente, confirmar que el alta simplificada de Ticket (solo título/descripción) sigue funcionando sin cambios, que no aparece ninguna acción de "Crear Tarea", y que el endpoint de creación de Tareas la rechaza si se invoca igualmente para esa cuenta.

**Acceptance Scenarios**:

1. **Given** el Usuario/cliente en el listado de Tickets, **When** la pantalla carga, **Then** el botón de alta simplificada de Ticket sigue disponible, sin campos avanzados de perfil interno.
2. **Given** el Usuario/cliente en el listado de Tareas, **When** la pantalla carga, **Then** no hay botón "Crear Tarea" visible.
3. **Given** una llamada directa al endpoint de creación de Tareas con las credenciales de un Usuario/cliente, **When** se invoca, **Then** el servidor la rechaza.

---

### User Story 6 - Centro de notificaciones y filtro "Asignado a mí" (Priority: P3)

Un Usuario/cliente ve, en un centro de notificaciones dentro del Portal, alertas de cambios de estado o nuevos comentarios públicos sobre los Tickets/Tareas de su empresa; y en los listados de Tickets/Tareas puede activar un filtro "Asignado a mí" que muestra solo aquellos donde figura como encargado o solicitante explícito.

**Why this priority**: Mejora de usabilidad sobre una base ya funcional (US1-US5); no bloquea el resto del Portal.

**Independent Test**: Generar un cambio de estado o un comentario público sobre un ticket del Cliente del usuario y confirmar que aparece en su centro de notificaciones; activar el filtro "Asignado a mí" y confirmar que la lista se acota a los tickets/tareas donde es `client_contact_id` o creador.

**Acceptance Scenarios**:

1. **Given** un Ticket de su empresa que cambia de estado o recibe un comentario público, **When** el Usuario/cliente revisa su centro de notificaciones, **Then** ve la alerta correspondiente.
2. **Given** el listado de Tickets o Tareas, **When** el Usuario/cliente activa "Asignado a mí", **Then** la lista se limita a los registros donde es el encargado/solicitante explícito, para ambos tipos de registro sin excepción.

---

### Edge Cases

- Un Usuario/cliente sin ningún Cliente asociado (cuenta mal configurada) intenta entrar al Portal: debe ver una lista vacía o un mensaje claro, nunca un error que exponga datos de otro Cliente.
- Un Ticket cambia de `pendiente_usuario` a otro estado (p. ej. por acción interna) mientras el Usuario/cliente tiene la caja de respuesta abierta sin enviar: al intentar enviar, el sistema debe rechazar la respuesta y refrescar el estado real en pantalla.
- Un mismo Cliente tiene varios Usuario/cliente activos: cualquiera de ellos con acceso al ticket puede ver y responder una `solicitud_informacion`, no solo el `client_contact_id` original del ticket (evita bloquear el flujo si el solicitante original ya no está disponible).
- Un Usuario/cliente desactivado (`active = false`, spec 034) no debe poder autenticarse por ninguna de las dos pestañas de Login.
- Adjuntos en la respuesta del Usuario/cliente deben respetar las mismas validaciones de tipo/tamaño ya vigentes para adjuntos de comentario (spec 017).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: La pantalla de Login MUST ofrecer dos modos de acceso claramente diferenciados — "Equipo / Empleados" y "Portal de Clientes / Colaboradores" — sobre el mismo formulario base (usuario/correo + contraseña) y el mismo mecanismo de autenticación y recuperación de contraseña ya existentes, sin introducir un flujo de login paralelo.
- **FR-002**: El diseño de ambos modos MUST reutilizar los componentes/estilos visuales ya vigentes de SYTIX (`AuthLayout.tsx` y la paleta/tipografía actuales), sin introducir una identidad visual distinta para el Portal.
- **FR-003**: El sistema MUST validar, al autenticar, que el rol de la cuenta coincide con la pestaña de Login elegida — una cuenta interna (Admin/Coordinador/QM/Resolutor) que intenta ingresar por "Portal de Clientes / Colaboradores" MUST ser rechazada, y una cuenta Usuario/cliente que intenta ingresar por "Equipo / Empleados" MUST ser rechazada, ambas con un mensaje que no confirme si la cuenta existe (mismo criterio de no-filtrado ya usado para credenciales inválidas).
- **FR-004**: El sistema MUST permitir al Usuario/cliente ver TODOS los Tickets, Tareas y Proyectos asociados a su propia empresa/Cliente — no solo los que él mismo creó — ampliando el alcance actual de `tickets:view_own` (hoy acotado a `created_by = usuario actual`) a `client_id = Cliente del usuario`.
- **FR-005**: El sistema MUST impedir que un Usuario/cliente acceda (por listado o por consulta directa de un registro) a Tickets, Tareas o Proyectos de un Cliente distinto al suyo, sin importar los parámetros de filtro enviados por el cliente HTTP.
- **FR-006**: El sistema MUST excluir por completo, a nivel de API, los comentarios con `visibility = internal` de cualquier respuesta consumida por un Usuario/cliente — no basta con ocultarlos en el frontend.
- **FR-007**: El sistema MUST seguir devolviendo el historial completo de comentarios (internos y externos) a roles internos (Admin, Coordinador, QM, Resolutor), sin cambios respecto al comportamiento actual.
- **FR-008**: El sistema MUST conservar la alta simplificada de Tickets ya existente para Usuario/cliente (autoservicio, solo título/descripción, `tickets:create`, spec 010/033) sin cambios, y MUST ocultar/deshabilitar para este rol cualquier opción de creación de Tareas y cualquier campo avanzado de creación (Proyecto/Herramienta/Proceso/Skills/asignación manual) que hoy solo esté pensado para perfiles internos.
- **FR-009**: Cuando un comentario tipo "Solicitud de información" (`solicitud_informacion`) queda registrado sobre un Ticket/Tarea de su Cliente y ese registro está en el estado que ese comentario produce (`pendiente_usuario`), el sistema MUST habilitar al Usuario/cliente con acceso al registro una caja de respuesta dedicada.
- **FR-010**: Al enviar esa respuesta, el sistema MUST registrar un comentario público tipo "Respuesta de usuario" (`respuesta_usuario`) autoría del Usuario/cliente, adjuntarlo al historial del Ticket/Tarea, y transicionar el estado según la regla ya existente (`pendiente_usuario` → `en_ejecucion`).
- **FR-011**: Esa transición MUST disparar una notificación al resolutor asignado indicando que la información solicitada fue entregada, reutilizando el mecanismo de notificaciones ya existente.
- **FR-012**: La caja de respuesta a "Solicitud de información" MUST estar ausente/deshabilitada cuando el Ticket/Tarea no está en el estado `pendiente_usuario`.
- **FR-013**: El sistema MUST mostrar al Usuario/cliente un centro de notificaciones con alertas de cambios de estado y nuevos comentarios públicos limitado a los Tickets/Tareas de su propio Cliente.
- **FR-014**: Los listados de Tickets y de Tareas visibles para el Usuario/cliente MUST ofrecer un filtro "Asignado a mí" que acote el listado a los registros donde el usuario figura como creador o como solicitante (`client_contact_id`) explícito, aplicado por igual a Tickets y a Tareas.
- **FR-015**: El sistema MUST mantener sin cambios el comportamiento de Login, aislamiento, comentarios, notificaciones y permisos ya vigente para todos los roles internos (Admin, Coordinador, QM, Resolutor).

### Key Entities

- **Usuario/cliente (rol existente)**: cuenta con dominio de correo externo, vinculada a un Cliente vía `client_contact`; ahora además determina qué pestaña de Login usa y qué ámbito de datos ve en el Portal.
- **Comentario (`Comment`, existente)**: ya tipificado con `comment_type` y `visibility` (`internal`/`external`); esta feature consume esa clasificación para filtrar la entrega al Portal y para habilitar la respuesta del cliente.
- **Ticket/Tarea (existente)**: su `status` (en particular `pendiente_usuario`) determina si la caja de respuesta del Portal está habilitada; su `client_id`/Proyecto determinan el aislamiento por Cliente.
- **Notificación (existente)**: se extiende su alcance de eventos para incluir los relevantes al Usuario/cliente, acotados a su propio Cliente.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de las consultas de listado o detalle realizadas por una cuenta Usuario/cliente devuelven exclusivamente registros de su propio Cliente, verificado contra al menos un intento deliberado de acceder a datos de otro Cliente.
- **SC-002**: El 100% de los comentarios internos de un Ticket quedan ausentes de cualquier respuesta de API consumida por un Usuario/cliente, sin excepción.
- **SC-003**: Un Usuario/cliente puede completar el ciclo "ver solicitud de información → responder → ver el ticket avanzar" sin asistencia del equipo de soporte.
- **SC-004**: Ningún botón ni ruta de creación de Tareas, ni ningún campo de creación de perfil interno, queda accesible (visible o invocable) para una cuenta Usuario/cliente — mientras el alta simplificada de Ticket sigue funcionando sin fricción adicional.
- **SC-005**: Un usuario nuevo distingue en menos de 5 segundos, sin instrucción previa, cuál de las dos pestañas de Login corresponde a su tipo de cuenta.

## Assumptions

- El backend reutiliza sin cambios el mecanismo de autenticación (`/api/auth/login`, JWT) y de recuperación de contraseña ya existentes; la diferenciación de Login es de presentación (más, según se resuelva FR-003, de validación de rol) y no un proveedor de identidad nuevo.
- "Su empresa/cliente" se resuelve siempre a través de `client_contact` → `client_id`, igual que en el resto del sistema (sin introducir una relación nueva usuario↔cliente).
- El Centro de Notificaciones del Portal reutiliza el `NotificationService`/`GET /api/notifications` ya existente, ampliando los tipos de evento que genera notificación y acotando su alcance por Cliente — no se crea un mecanismo de notificación paralelo.
- Cualquier Usuario/cliente activo de la misma empresa (no solo el `client_contact_id` original del ticket) puede ver y responder una "Solicitud de información", en línea con el aislamiento por Cliente (no por contacto individual) pedido en el resto de la feature.
- Fuera de alcance de esta especificación: cambios a la lógica de asignación/reasignación de resolutores, al motor de SLA, y a los catálogos administrativos — el Usuario/cliente sigue sin acceso a Maestros (ya restringido desde spec 038).
