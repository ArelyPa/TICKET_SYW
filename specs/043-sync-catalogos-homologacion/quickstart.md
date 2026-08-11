# Quickstart: Ampliación y Ajustes Finos en la Sincronización de Catálogos de Teamwork

Guía de validación manual end-to-end contra Docker real, sin ejecutar la suite completa de
pruebas (Principio VII). Si se prueba la homologación/migración a nivel de test automatizado,
acotar a un máximo de 5-10 registros dummy por test (directriz explícita de esta sesión).

## Prerrequisitos

- Stack levantado (`docker compose up`), migración `055_teamwork_entity_mappings_context`
  aplicada, login como Coordinador (permiso `teamwork_integration:operate`).
- Configuración de conexión de spec 042 ya guardada y probada con éxito (o repetir esos 2 pasos
  primero — sin cambios en esta feature).
- Datos de prueba en Teamwork (o mockeados en el test de integración) con: al menos 2 Proyectos
  homónimos de Empresas distintas, 1 Persona cuyo correo NO coincide con ningún Recurso/Usuario de
  SYTIX, y 1 Lista de Tareas de un Proyecto ya homologado.

## US1 — Homologar vs. Migrar Nuevo por fila

1. Sincronizar el catálogo de Empresas. Ubicar una fila sin automapeo (`migration_status:
   "pending"`).
2. Elegir "Migrar como Nuevo" → confirmar → verificar que aparece un Cliente nuevo en Maestros >
   Clientes con el nombre exacto de Teamwork, y que la fila queda `migration_status: "created"`.
3. Intentar "Migrar como Nuevo" de nuevo sobre esa misma fila → la acción debe estar deshabilitada
   (ya vinculada, FR-004).
4. Repetir el flujo de migración con un nombre que ya existe como Cliente → confirmar `409
   duplicate_name` sin crear un segundo registro.

## US2 — Contexto de Cliente en Proyectos y Listas de Tareas

1. Sincronizar Proyectos con al menos 2 proyectos homónimos de Empresas distintas (una ya
   homologada, otra sin homologar).
2. Verificar que la columna "Cliente Asociado" muestra el nombre real del Cliente para el proyecto
   de la Empresa ya homologada, y un estado "pendiente de homologar" para el otro — y que "Migrar
   como Nuevo" está deshabilitado en este último (FR-006).
3. Sincronizar Listas de Tareas del proyecto ya resuelto y confirmar que las columnas "Cliente" y
   "Proyecto" muestran ambos nombres correctamente (FR-007).

## US3 — Correo, Rol y creación de cuenta al migrar Personal

1. Sincronizar Personal y confirmar que la columna "Correo" aparece junto al nombre (FR-008).
2. Elegir "Migrar como Nuevo" en una fila sin coincidencia → el modal exige elegir un Rol antes de
   confirmar (FR-009).
3. Elegir el rol "Usuario/cliente" → el modal exige además un Cliente (FR-010) → confirmar y
   verificar que se crea el `ClientContact` asociado al Cliente elegido.
4. Elegir el rol "Resolutor" en otra fila → confirmar y verificar que se crea el Usuario + Recurso
   (mismo patrón de `TeamPage.tsx`), con `full_name`/`email` tomados de Teamwork.
5. Repetir "Migrar como Nuevo" sobre una fila cuyo correo ya pertenece a un usuario existente →
   confirmar `409 email_already_used` y que el mensaje sugiere "Homologar".

## US4 — Trazabilidad visible de IDs externos y estado de migración

1. Con la tabla mostrando filas en los 3 estados (pendiente, homologado manual, migrado), verificar
   que cada una pinta un badge distinto (`migration_status`).
2. Recargar la página → los badges se mantienen.
3. Volver a sincronizar el mismo catálogo → las filas ya "Homologado"/"Migrado" no vuelven a
   "Pendiente" ni cambian de `sytix_id` (FR-014).

## Verificación de alcance (Principio VII)

- `git diff --stat` tras la implementación se limita a: `teamwork_integration.py` (ruta),
  `teamwork_integration_repo.py`, `teamwork_integration_model.py`, `teamwork_connection_client.py`,
  `entity_mapping_service.py` (si aplica), migración `055`, `TeamworkIntegrationPage.tsx`,
  `teamworkIntegrationService.ts`, `types/teamworkIntegration.ts` — sin tocar `ticket_imports.py`,
  `time_imports.py`, ni la lógica central de `users.py`/`clients.py`/`projects.py`/`resources.py`/
  `task_lists.py` (solo se **llaman** sus repos/servicios ya existentes, no se modifican).
- `tsc -b` sin errores tras los cambios de frontend.
