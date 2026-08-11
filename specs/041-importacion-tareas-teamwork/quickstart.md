# Quickstart: Migración e Importación de Tareas desde Teamwork

## Prerrequisitos

- Stack Docker corriendo (`docker compose up`, ver README) con `sywork_backend`/`sywork_frontend`.
- Migración `053_ticket_external_reference.py` aplicada (`alembic upgrade head` dentro del
  contenedor backend, o el mecanismo de arranque ya existente que corre migraciones pendientes).
- Sesión iniciada como usuario con rol Coordinador o Admin.
- Usar el fixture de 8 filas ya preparado en
  [`ejemplo-teamwork-tasks.xlsx`](ejemplo-teamwork-tasks.xlsx) (o su equivalente
  [`.csv`](ejemplo-teamwork-tasks.csv)) — derivado de un export real de Teamwork y recortado a
  8 filas (Principio VII, máx. 5-10 filas). Ya incluye: un par padre+hijo dentro del lote (la
  fila padre es sintética, marcada `[EJEMPLO SINTÉTICO]` en el título — ver spec.md § "Ejemplo de
  datos de referencia"), una fila hija con su padre real ausente del lote (caso dominante en la
  práctica), una fila del cliente `Aris` (ya sembrado en SYTIX, pero con Proyecto/Lista que no
  calzan exactamente) y filas de clientes inexistentes en SYTIX (`Cargill`, `Congrupo`,
  `Consorcio Shushufindi S.A.`) — no hace falta armar un archivo de prueba nuevo.

## US1 — Carga masiva Excel/CSV con vista previa

1. Ir a **Maestros → Importación de Tareas** (`/importacion-tareas`).
2. Cargar el archivo de prueba (`Upload` de Ant Design).
3. Verificar: la tabla de vista previa muestra cada fila con su mapeo (Cliente, Proyecto, Lista
   de Tareas, Título, Asignado, Solicitante, Tiempo Estimado en horas, Tarea padre) y la fila con
   datos no resueltos aparece marcada como "Pendiente de revisión" — **nada se inserta todavía**
   (confirmar consultando `GET /api/tickets` antes/después, o el conteo del listado de Tareas).
4. Confirmar la importación. Verificar en la respuesta el resumen `{created, updated, errors}`.
5. Abrir la Tarea recién creada con `Parent task ID`: confirmar que aparece como Subtarea de su
   Tarea padre (Card "Subtareas"/"Tarea Padre", ya existente desde spec 036/037).
6. Repetir la carga del **mismo archivo** una segunda vez: confirmar que el resumen reporta
   `updated` para esas filas y `created: 0` — sin duplicados (`GET /api/tickets` con el mismo
   `external_reference_id` sigue devolviendo un solo registro).

## US2 — Trazabilidad visible en el detalle

1. Abrir el detalle de una de las Tareas importadas.
2. Verificar que aparece el enlace/insignia de Teamwork y que al hacer clic abre
   `external_reference_url` en una pestaña nueva.
3. Abrir el detalle de un Ticket creado directamente en SYTIX (sin importar): confirmar que NO
   aparece ningún elemento de Teamwork.

## US3 — Sincronización por API v3 (si hay credenciales de prueba disponibles)

1. En la misma pantalla de importación, activar "Sincronizar con Teamwork (API v3)".
2. Verificar que el resultado pasa por la misma tabla de vista previa que US1.
3. Si no hay credenciales de prueba disponibles en este entorno, validar al menos el manejo de
   error: con una URL/token inválido configurado, confirmar que el endpoint responde
   `502 teamwork_api_error` sin dejar filas insertadas.

## US4 — Asignación a Coordinador

1. Abrir el Panel de Asignación (o el detalle de un Ticket/Tarea sin asignar) y abrir el selector
   de responsable: confirmar que además de los Resolutores aparece al menos un usuario con rol
   Coordinador.
2. Asignar el Ticket/Tarea a ese Coordinador: confirmar `200 OK` y que el detalle del ticket
   muestra al Coordinador como responsable.
3. Reasignar ese mismo Ticket/Tarea a un Resolutor: confirmar que el historial de reasignación
   registra "Coordinador ➡️ Resolutor" igual que ya lo hace entre Resolutores (spec 023).

## Verificación de alcance (Principio VII)

- No ejecutar la suite completa de `pytest`. Acotar a los archivos nuevos/tocados, ej.:
  `pytest backend/tests/domain/test_teamwork_import_service.py backend/tests/api/test_ticket_imports.py backend/tests/domain/test_assignment_service.py backend/tests/api/test_assign.py`
- Cualquier test de importación debe usar un fixture de máximo 5-10 filas.
