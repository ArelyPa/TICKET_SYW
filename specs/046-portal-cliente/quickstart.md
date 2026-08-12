# Quickstart: Validación del Portal de Cliente

Prerrequisitos: stack Docker ya levantado (`sywork_backend`/`sywork_frontend`/`sywork_db`), al menos un Cliente sembrado con Usuario/cliente activo (p. ej. Aris, `Eliseon@aris.ming.com`, ver `docs/credenciales_dev.txt`) y un Ticket de ese Cliente con historial mixto de comentarios internos/externos.

## 1. Login diferenciado (US1, FR-001/002/003)

1. Abrir `/login`. Confirmar que la pestaña "Equipo / Empleados" está seleccionada por defecto y usa el mismo estilo (`AuthLayout`) ya vigente.
2. Cambiar a "Portal de Clientes / Colaboradores"; loguear con una cuenta interna (`@sywork.net`, p. ej. `coordinador`) → esperar `401` (enforcement estricto).
3. Loguear con `Eliseon@aris.ming.com` en la pestaña "Portal de Clientes / Colaboradores" → acceso exitoso.
4. Repetir el paso 3 pero en la pestaña "Equipo / Empleados" → esperar `401`.

## 2. Aislamiento por Cliente (US2, FR-004/005)

1. Logueado como el Usuario/cliente de Aris, abrir el listado de Tickets/Tareas: confirmar que **todos** los registros mostrados pertenecen a Aris, incluidos los creados por otro contacto de Aris (no solo los propios).
2. Con las DevTools, intentar `GET /api/tickets?client_id=<uuid-de-otro-cliente>` usando el JWT de este usuario → confirmar que la respuesta sigue acotada a Aris (el `client_id` de la query se ignora/reemplaza).
3. Abrir el listado de Proyectos → confirmar que solo aparecen los de Aris.

## 3. Comentarios internos ocultos (US3, FR-006/007)

1. Como Coordinador, sobre un Ticket de Aris, registrar un comentario `comentario_interno` (o cualquier tipo interno) y otro `confirmacion_atencion` (externo).
2. Loguear como el Usuario/cliente de Aris y abrir el detalle de ese Ticket → confirmar que el comentario interno **no aparece en absoluto** en la respuesta de `GET /api/tickets/{id}` (verificar en Network, no solo visualmente).
3. Volver a loguear como Coordinador → confirmar que el historial completo (interno + externo) sigue visible, sin cambios.

## 4. Responder una "Solicitud de información" (US4, FR-009/010/011/012)

1. Como Resolutor asignado al Ticket, registrar un comentario `solicitud_informacion` → el ticket pasa a `PENDIENTE DE USUARIO`.
2. Loguear como el Usuario/cliente de Aris y abrir el detalle del Ticket → confirmar que aparece la caja de respuesta.
3. Enviar una respuesta → confirmar `201`, nuevo comentario `respuesta_usuario` visible en el historial, y que el Ticket pasa a `EN EJECUCIÓN`.
4. Loguear de nuevo como el Resolutor asignado → confirmar que recibió la notificación "El usuario respondió en el ticket ...".
5. Repetir el paso 2 sobre un Ticket que NO esté en `PENDIENTE DE USUARIO` → confirmar que la caja de respuesta no aparece.

## 5. Sin creación de Tareas / campos avanzados (US5, FR-008)

1. Como Usuario/cliente, confirmar que el alta simplificada de Ticket (solo título/descripción) sigue funcionando sin fricción.
2. Confirmar que no existe ninguna acción "Crear Tarea" visible para este rol.
3. Intentar `POST /api/tickets` con `record_type_id` de Tarea usando el JWT de este usuario → esperar rechazo.

## 6. Centro de notificaciones y filtro "Asignado a mí" (US6, FR-013/014)

1. Provocar un cambio de estado o un comentario público sobre un Ticket de Aris → confirmar que aparece en el centro de notificaciones del Usuario/cliente.
2. En el listado de Tickets y en el de Tareas, activar "Asignado a mí" → confirmar que la lista se acota a los registros donde el usuario es creador o `client_contact_id`, para ambos tipos de registro.

## Verificación de no-regresión (roles internos)

Repetir rápidamente los pasos 1-3 logueado como Coordinador/QM/Resolutor/Admin y confirmar: sin pestaña de enforcement bloqueante entre ellos y "Equipo / Empleados", listado global sin acotar por Cliente (según su permiso ya existente), historial de comentarios completo.

## Pruebas automatizadas (alcance de esta sesión)

`pytest` acotado a los archivos tocados (`test_auth.py`, `test_tickets_crud.py`/`test_comments*.py` según corresponda, `test_notification_service.py` si aplica) — **máximo 5 registros de prueba por test**, prohibido correr la suite completa (Principio VII + instrucción explícita del usuario). `tsc -b` para verificar tipos del frontend.
