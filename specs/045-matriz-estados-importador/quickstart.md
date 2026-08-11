# Quickstart — Validación de Matriz de Estados, Acciones Masivas, Extracción Enriquecida e Importador de Tareas

Prerrequisitos: stack Docker levantado (`docker compose up`), sesión como Admin o Coordinador, configuración de
Teamwork ya guardada con "Probar Conexión" en éxito (spec 042), al menos un catálogo (ej. Proyectos) ya
sincronizado con más de 5 filas.

## 1. Matriz de 4 estados y pestañas de filtro (US1)

1. Ir a `Maestros > Integración Teamwork`.
2. Sobre cualquiera de los 4 catálogos, confirmar que aparecen las pestañas `Todos / Pendientes / Homologados /
   Migrados / Inactivos` encima de la tabla.
3. Homologar una fila manualmente y confirmar que pasa a la pestaña "Homologados" con badge azul; migrar otra
   como nueva y confirmar que pasa a "Migrados" con badge verde.
4. Confirmar que la pestaña "Todos" sigue mostrando el total sin filtrar.

## 2. Acciones masivas ampliadas — Migrar e Inactivar (US2)

1. En Proyectos (o Empresas/Listas de Tareas), seleccionar 3 filas Pendientes con checkbox y ejecutar "Migrar
   Masivamente como Nuevos". Confirmar que las 3 pasan a "Migrado" con su registro nuevo creado en SYTIX.
2. Seleccionar otras 2 filas Pendientes y ejecutar "Inactivar / Descartar Seleccionados". Confirmar que pasan a
   la pestaña "Inactivos" sin ningún registro nuevo creado en SYTIX.
3. Repetir la sincronización del mismo catálogo y confirmar que las filas Inactivas siguen apareciendo bajo
   "Inactivos" (no vuelven a "Pendientes").
4. Sobre una fila Inactiva, ejecutar la acción de reactivar y confirmar que vuelve a "Pendientes".
5. Verificar `POST /entity-mappings/bulk-create-new` y `POST /entity-mappings/bulk-discard` → 200, con
   `created`/`updated` y `skipped` reportando el motivo de cada omisión.

## 3. Extracción ampliada de metadatos (US3)

1. Sincronizar el catálogo de Empresas contra un mock/fixture con País, Dirección, Dominio y Teléfono cargados
   en al menos una compañía (Principio VII, ≤10 registros).
2. Confirmar que esos 4 campos se ven en la fila o en su detalle expandible; un campo no informado muestra "No
   informado".
3. Repetir para Personal (Cargo, Zona horaria) y Proyectos/Listas de Tareas (descripción, estado
   activo/archivado).

## 4. Importador de Tareas y Subtareas — filtros y prevalidación (US4)

Prerrequisito: un lote de prueba de 5 a 10 Tareas/Subtareas de Teamwork repartidas entre 2 Clientes/2 meses,
algunas con Proyecto/Lista/Usuario asignado ya homologados y otras no (mock de `requests`, Principio VII).

1. Ir a `Maestros > Importador de Tareas y Subtareas` (pantalla nueva, separada de "Integración Teamwork").
2. Seleccionar un Cliente y uno de sus Proyectos ya homologados; aplicar un rango de un mes.
3. Ejecutar la prevalidación (`POST .../task-imports/preview`) y confirmar que la cantidad de tareas "listas" y
   "bloqueadas" coincide con el subconjunto esperado del fixture, con el motivo de bloqueo de cada bloqueada
   (`project_not_mapped` / `tasklist_not_mapped` / `assignee_not_mapped`).
4. Hacer clic en el enlace de una advertencia bloqueada y confirmar que navega a `Integración Teamwork` con el
   catálogo y la fila correspondiente preseleccionados.
5. Confirmar la importación (`POST .../task-imports/confirm`) y verificar que solo se crean/actualizan las
   tareas marcadas como listas — las bloqueadas no generan Ticket huérfano.
6. Abrir un Ticket/Tarea creado y confirmar el hipervínculo hacia Teamwork y, si corresponde, la relación
   Tarea padre → Subtarea.
7. Re-ejecutar `confirm` sobre el mismo filtro y confirmar `updated` en vez de duplicados.

## Pruebas automatizadas (Principio VII — lote máximo 5-10 registros)

```bash
docker compose exec backend pytest backend/tests/api/test_teamwork_integration.py -q
docker compose exec backend pytest backend/tests/api/test_teamwork_task_imports.py -q
docker compose exec backend pytest backend/tests/domain/test_entity_mapping_service.py -q
```

No correr la suite completa (`pytest` sin acotar) en ningún momento de esta sesión.
