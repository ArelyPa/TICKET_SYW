# Quickstart: Integración API Teamwork v3, Homologación de Catálogos e Importador de Tiempos
Mensuales

Guía de validación manual end-to-end contra Docker real, sin ejecutar la suite completa de
pruebas (Principio VII).

## Prerrequisitos

- Stack levantado (`docker compose up`), login como Admin (para configurar credenciales) y como
  Coordinador (para operar sincronización/importación).
- Migración `054_teamwork_integration_time_imports` aplicada.
- Un archivo de prueba reducido (5-10 filas) con el formato de reporte de tiempos mensual de
  Teamwork, incluyendo al menos:
  - 1 fila cuyo `Who`/`Company`/`Project`/`Task` ya tengan coincidencia en SYTIX (fila válida).
  - 1 fila con `Who` sin coincidencia (conflicto → se resuelve creando el Recurso).
  - 1 fila con `Project` sin coincidencia (conflicto → se resuelve homologando a un proyecto
    existente).
  - 1 fila que se decide omitir.
  - 1 fila con el mismo `ID` que otra ya confirmada antes (para probar el upsert de FR-013).

## US1 — Configurar y probar conexión

1. Login como Admin → **Administración / Integraciones / Teamwork**.
2. Completar URL del sitio + token + entorno, guardar.
3. `GET /api/teamwork-integration/config` (recargar la pantalla) confirma que `has_token: true` y
   que el token nunca aparece en la respuesta.
4. Presionar "Probar Conexión" con credenciales inválidas → badge de error de autenticación.
   Corregir y repetir → badge de éxito.

## US4 — Sincronizar catálogos

1. Con la conexión en `success`, presionar "Sincronizar Catálogos" para cada uno de los 4 tipos.
2. Verificar `GET /api/teamwork-integration/entity-mappings?entity_type=company` devuelve las
   entidades traídas, con automapeo ya sugerido donde el correo/nombre coincide exactamente.

## US5 — Homologación manual

1. Abrir la tabla de Homologación de Entidades.
2. Para una fila sin automapeo, seleccionar manualmente el registro SYTIX correspondiente y
   guardar (`PUT /api/teamwork-integration/entity-mappings/{id}`).
3. Confirmar que la fila queda con `match_method: "manual"`.

## US2/US3 — Importar tiempos, validar y resolver conflictos

1. Login como Coordinador → pantalla de importación de tiempos, subir el archivo de prueba.
2. `POST /api/time-imports/preview` — confirmar en el resumen el conteo de válidas vs. conflicto
   coincide con lo armado en el archivo de prueba.
3. Resolver cada fila con conflicto: una por homologación manual (selector), una creando el
   Recurso faltante, una omitiéndola.
4. Confirmar la carga (`POST /api/time-imports/confirm`) y verificar:
   - Se crearon `WorkSession` para las filas válidas + resueltas + creadas (no para la omitida).
   - El Recurso creado automáticamente no tiene `user_id` (sin acceso de login).
   - `time_import_batches` tiene una fila nueva con los conteos correctos.
5. Repetir el mismo archivo (o solo la fila con `ID` duplicado) y confirmar que el registro de
   tiempo existente se actualiza en vez de duplicarse (FR-013).

## Verificación de alcance (Principio VII)

- `git diff --stat` tras la implementación NO debe tocar `backend/infra/importers/teamwork_api_client.py`,
  `teamwork_file_parser.py`, `backend/domain/services/teamwork_import_service.py` ni
  `backend/api/routes/ticket_imports.py` (spec 041, fuera de alcance de esta sesión).
- `tsc -b` sin errores tras agregar las páginas/servicios/tipos nuevos del frontend.
