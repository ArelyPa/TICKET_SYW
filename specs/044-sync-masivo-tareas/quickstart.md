# Quickstart — Validación de Operaciones Masivas, Paginación y Migración de Tareas/Subtareas

Prerrequisitos: stack Docker levantado (`docker compose up`), sesión como Admin o Coordinador, configuración
de Teamwork ya guardada con "Probar Conexión" en éxito (spec 042).

## 1. Sincronización completa + Compañía en Personal (US1)

1. Ir a `Maestros > Integración Teamwork`.
2. Sincronizar "Personal". Confirmar que el `synced` reportado por el toast coincide con el total real del
   sitio de Teamwork (si el sitio de prueba tiene <60 personas, forzar el caso con un mock de `requests` en
   un test dirigido — ver contrato de `_fetch_all_pages`).
3. Confirmar que la tabla de Personal muestra la columna "Compañía/Empresa de Origen" con el nombre resuelto
   (o "Sin compañía").

## 2. Migración masiva de Personal por correo (US2)

1. En Personal, escribir un fragmento de correo en el filtro (ej. `@aris.ming.com`).
2. Seleccionar 2-5 filas filtradas con los checkboxes.
3. Abrir "Acciones Masivas", elegir Rol "Usuario/cliente" + Cliente "Aris", confirmar.
4. Verificar `POST /entity-mappings/bulk-create-new` → 200, cada fila queda con `migration_status="created"`
   y aparece en `created[]`; repetir la acción sobre las mismas filas y confirmar que ahora aparecen en
   `skipped[]` con `reason="already_linked"`.

## 3. Selectores enriquecidos y filtros globales (US4)

1. En Proyectos, abrir el selector SYTIX de una fila sin homologar y confirmar el formato `Cliente - Proyecto`.
2. En Listas de Tareas, confirmar el mismo prefijo en las opciones del selector.
3. Aplicar el filtro superior por Cliente en Personal/Proyectos/Listas de Tareas y confirmar que las tres
   pantallas acotan sus filas.

## 4. Paginación fija (parte de FR-010)

1. Con más de 15 filas sincronizadas en cualquier catálogo, confirmar que la tabla muestra exactamente 15 por
   página y un control de paginación (sin selector de tamaño de página).

## 5. Distintivo de trazabilidad (US5)

1. Migrar una Empresa nueva vía "Migrar como Nuevo" (o la acción masiva de Personal).
2. Ir a la pantalla principal de SYTIX correspondiente (Clientes, Proyectos, Listas de Tareas, Equipo, o
   Usuarios/cliente) y confirmar que la fila migrada muestra el badge de trazabilidad; confirmar que un
   registro creado manualmente (sin relación con Teamwork) no lo muestra.

## 6. Migración masiva de Tareas y Subtareas (US3)

Prerrequisito: un lote de prueba de 5 a 10 Tareas/Subtareas de Teamwork cuyo Proyecto/Lista/Persona asignada
ya estén homologados o migrados (usar los pasos 1-2 de este quickstart, o datos ya sembrados de sesiones
anteriores).

1. Ejecutar `POST /api/teamwork-integration/sync/tasks`.
2. Verificar en la respuesta que `created`/`updated` coincide con las filas cuya cadena estaba resuelta, y que
   `skipped` reporta el resto con su motivo.
3. Abrir el Ticket/Tarea creado en SYTIX y confirmar: (a) el hipervínculo sobre el número de ticket abre la
   tarea original de Teamwork, (b) una Subtarea del lote aparece como hija de su Tarea padre.
4. Re-ejecutar el mismo `POST /sync/tasks` sobre el mismo lote y confirmar `updated` en vez de duplicados
   (mismo `ticket_number`/`id` que la primera corrida).

## Pruebas automatizadas (Principio VII — lote máximo 5-10 registros)

```bash
docker compose exec backend pytest backend/tests/api/test_teamwork_integration.py -q
```

No correr la suite completa (`pytest` sin acotar) en ningún momento de esta sesión.
