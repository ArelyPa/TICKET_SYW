# Implementation Plan: Matriz de Estados de Sincronización, Acciones Masivas Ampliadas, Extracción Enriquecida de Datos y Centro Independiente de Importación de Tareas (Teamwork API v3)

**Branch**: `045-matriz-estados-importador` | **Date**: 2026-08-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/045-matriz-estados-importador/spec.md`

## Summary

Amplía el integrador de Teamwork (spec 042-044) en 4 frentes: (1) reemplaza el badge derivado de 3 estados
(`_migration_status` hoy vive en la Capa 3, `teamwork_integration.py:161-168`) por una matriz de 4 estados
explícitos — agrega una columna persistida `is_discarded` a `teamwork_entity_mappings` para el estado
`Inactivo` (no derivable de `sytix_id`/`match_method` como los otros 3) y mueve la derivación a una función
pura de Capa 1 en `entity_mapping_service.py`, con pestañas de filtro client-side en el único `Table` ya
existente de `TeamworkIntegrationPage.tsx`; (2) extiende a Empresas, Proyectos y Listas de Tareas el patrón de
Acciones Masivas ya construido para Personal en spec 044 — generaliza `POST .../entity-mappings/bulk-create-new`
para aceptar cualquier `entity_type` (reutilizando sin cambios el dispatcher `_CREATE_NEW_HANDLERS` ya usado por
el endpoint individual) y agrega `POST .../entity-mappings/bulk-discard`/`bulk-reactivate`; (3) agrega una
columna `teamwork_metadata` (JSONB) a la misma tabla para guardar los campos ampliados de la API v3 (País/
Dirección/Dominio/Teléfono en Empresas; Cargo/Zona horaria en Personal; descripción/estado en Proyectos y
Listas), extendiendo `_fetch_entity()` en `teamwork_connection_client.py`; (4) agrega un módulo nuevo e
independiente — ruta `backend/api/routes/teamwork_task_imports.py` + servicio puro
`teamwork_task_import_service.py` + página `TeamworkTaskImporterPage.tsx` — con filtros Cliente/Proyecto(s)/
fecha/Lista de Tareas opcional, prevalidación diagnóstica (`ready`/`blocked` con motivo y enlace) y ejecución
por lotes, reutilizando `classify_task` de `teamwork_task_migration_service.py` (spec 044, sin modificarlo) y
`TicketRepository.upsert_from_import` (spec 041, sin modificarlo) — sin reemplazar `POST .../sync/tasks` ya
existente. Una migración nueva (`056`), cero dependencias nuevas, cero permisos nuevos (ver research.md).

## Technical Context

**Language/Version**: Python 3.12 (Flask) + TypeScript strict (React 19)

**Primary Dependencies**: Flask-RESTX, SQLAlchemy — backend; Ant Design 5, `date-fns` (rango de fechas del
importador vía 2 `<input type="date">` nativos, no `DatePicker.RangePicker` — `dayjs` resultó no resoluble
como import directo bajo pnpm estricto, ver research.md Decisión 6 corregida durante la implementación), Axios
— frontend. Sin dependencias nuevas.

**Storage**: PostgreSQL 16 — extiende `teamwork_entity_mappings` (migraciones 054/055) con 2 columnas nuevas
nullable/con default (`is_discarded`, `teamwork_metadata`), migración `056`. Reutiliza sin cambios `tickets`
(migración 053, `external_reference_id`/`url`) para la creación de Tickets/Tareas del nuevo importador.

**Testing**: `pytest` acotado a `backend/tests/api/test_teamwork_integration.py` (tests tocados/extendidos) +
`backend/tests/api/test_teamwork_task_imports.py` (nuevo) + `backend/tests/domain/test_entity_mapping_service.py`
(nuevo, estado de 4 valores) — lote ≤10 registros mock por test (Principio VII), sin correr la suite completa.
`tsc -b` sin errores como criterio de aceptación frontend (sin suite E2E automatizada nueva).

**Target Platform**: Web app on-premise (Docker Compose), mismo entorno que el resto del proyecto.

**Project Type**: Web application (backend Flask + frontend React) — extiende el namespace existente
`teamwork_integration` y agrega un namespace nuevo `teamwork_task_imports` bajo el mismo path base
`/api/teamwork-integration/task-imports`.

**Performance Goals**: N/A explícito — el nuevo endpoint de prevalidación reutiliza `fetch_tasks()` (ya trae
todo el sitio en memoria, spec 044) y filtra/clasifica en Python; sin objetivo de latencia distinto al ya
aceptado para `POST /sync/tasks`.

**Constraints**: Alcance de código restringido a (a) el namespace `teamwork_integration` ya existente
(ruta/repo/modelo/entidad/servicio de dominio/cliente de conexión), (b) el nuevo módulo de importación
(`teamwork_task_imports.py` + `teamwork_task_import_service.py` + `TeamworkTaskImporterPage.tsx` + su service/
tipos) y (c) los campos de estado de sincronización de la tabla `teamwork_entity_mappings` — instrucción
explícita de esta sesión. **Ningún** archivo de `tickets.py`, `clients.py`, `projects.py`, `task_lists.py`,
`users.py`, `resources.py`, `client_contacts.py`, `ticket_imports.py`, `teamwork_api_client.py`,
`teamwork_import_service.py` ni `teamwork_task_migration_service.py` se modifica — solo se invocan sin cambios
sus funciones/repos ya existentes (mismo criterio de aislamiento ya aplicado en specs 043/044). A diferencia de
spec 044, esta feature **no** toca ninguna pantalla principal de SYTIX fuera del integrador — sin desviación
que justificar en Complexity Tracking.

**Scale/Scope**: 4 User Stories, 1 migración de BD, 5 endpoints backend nuevos + 3 endpoints existentes
extendidos (sin romper contrato), 1 página nueva + 1 página extendida en frontend.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación |
|-----------|------------|
| I. API-First y Dominio Primero | PASA. La derivación de estado (`entity_mapping_service.derive_sync_status`) y la clasificación de diagnóstico (`teamwork_task_import_service.classify_task_for_import`) son Capa 1 pura, sin Flask/SQLAlchemy. Los 5 endpoints nuevos se documentan en `contracts/api.md` antes de implementar. |
| II. Clean Architecture 3 Capas | PASA. Capa 1: `entity_mapping_service.py` (extendido, puro), `teamwork_task_import_service.py` (nuevo, puro, reutiliza `classify_task` por import). Capa 2: `teamwork_connection_client.py` (extendido: metadata por tipo), `teamwork_integration_repo.py` (extendido: `set_discarded`, `get_teamwork_ids_for_sytix`, `upsert_from_sync` con `metadata`). Capa 3: `teamwork_integration.py` (endpoints de estado/bulk extendidos) + `teamwork_task_imports.py` (namespace nuevo) + páginas React. |
| III. Tipado Estricto | PASA. Nuevos tipos TS en `teamworkIntegration.ts` (`TeamworkSyncStatus` de 4 valores, `teamwork_metadata`) y `teamworkTaskImport.ts` (nuevo); type hints en todas las funciones Python nuevas/tocadas. Sin `any`. |
| IV. Seguridad en Profundidad | PASA. Mismo JWT + mismo permiso `teamwork_integration:operate` en los 5 endpoints nuevos — sin secretos nuevos, sin exponer token/URL de Teamwork. |
| V. Gobernanza de Librerías | PASA. Cero dependencias nuevas en `package.json`/`requirements.txt` — el rango de fechas usa `<input type="date">` nativo + `date-fns` ya aprobado, no `dayjs` (research.md Decisión 6, corregida durante la implementación tras verificar que `dayjs` no es resoluble como import directo bajo pnpm estricto). |
| VI. AI-Native | N/A directo — no toca el FSM de tickets ni el flujo de asignación; los Tickets creados por el nuevo importador reutilizan sin cambios `TicketRepository.upsert_from_import` (mismos campos estructurados ya definidos). |
| VII. Alcance de Sesión / Testing Ultra-Limitado | PASA sin desviación. Alcance 100% contenido en el namespace `teamwork_integration` + el nuevo módulo de importación (a diferencia de spec 044, que tuvo que justificar tocar 5 pantallas ajenas). Tests nuevos ≤10 registros por test, sin correr la suite completa. |

**Resultado**: PASA sin desviaciones — Complexity Tracking queda vacío.

## Project Structure

### Documentation (this feature)

```text
specs/045-matriz-estados-importador/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── api.md            # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit-tasks — no creado por /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── infra/
│   ├── migrations/versions/
│   │   └── 056_entity_mapping_status_metadata.py   # NUEVO — is_discarded, teamwork_metadata
│   ├── models/
│   │   └── teamwork_integration_model.py            # + is_discarded (Boolean), teamwork_metadata (JSONB)
│   ├── repositories/
│   │   └── teamwork_integration_repo.py              # + set_discarded, get_teamwork_ids_for_sytix; upsert_from_sync(+metadata)
│   └── importers/
│       └── teamwork_connection_client.py              # _fetch_entity: + metadata por tipo; fetch_tasks: + created_at/due_date
├── domain/
│   ├── entities/
│   │   └── teamwork_integration.py                    # EntityMapping: + is_discarded, teamwork_metadata
│   └── services/
│       ├── entity_mapping_service.py                  # + derive_sync_status (Capa 1, reemplaza _migration_status de la ruta)
│       └── teamwork_task_import_service.py             # NUEVO — Capa 1 pura, filtra por fecha + clasifica ready/blocked con motivo
├── api/routes/
│   ├── teamwork_integration.py                         # + bulk-discard, bulk-reactivate; bulk-create-new generalizado a 4 tipos
│   └── teamwork_task_imports.py                        # NUEVO — namespace independiente, preview + confirm
└── tests/
    ├── api/
    │   ├── test_teamwork_integration.py                # tests tocados/extendidos, ≤10 registros
    │   └── test_teamwork_task_imports.py                # NUEVO, ≤10 registros
    └── domain/
        └── test_entity_mapping_service.py               # NUEVO — derive_sync_status, 4 estados

frontend/src/
├── pages/
│   ├── TeamworkIntegrationPage.tsx        # + pestañas de estado, checkboxes en los 4 catálogos, botón "Inactivar/Descartar", columnas de metadata
│   └── TeamworkTaskImporterPage.tsx        # NUEVO — wizard Cliente/Proyecto(s)/fecha/Lista → prevalidación → ejecución por lotes
├── services/
│   ├── teamworkIntegrationService.ts       # + bulkDiscard, bulkReactivate; bulkCreateNew ya genérico de tipo
│   └── teamworkTaskImportService.ts        # NUEVO — preview, confirm
├── types/
│   ├── teamworkIntegration.ts              # TeamworkMigrationStatus → 4 valores; + teamwork_metadata, tipos bulk discard/reactivate
│   └── teamworkTaskImport.ts               # NUEVO — filtros, fila de diagnóstico, resultado de confirm
├── config/
│   └── navigation.tsx                      # + entrada "Importador de Tareas y Subtareas"
└── App.tsx                                  # + ruta `integraciones/teamwork/importador-tareas`
```

**Structure Decision**: Web application ya existente (`backend/` Flask + `frontend/` React). Esta feature no
agrega proyectos ni capas nuevas — extiende el namespace `teamwork_integration` (spec 042) y agrega un segundo
namespace hermano (`teamwork_task_imports`) para el módulo de importación, siguiendo el mismo patrón
preview→confirm ya usado por `ticket_imports.py`/`time_imports.py` (spec 041/042) pero como archivo físicamente
independiente, sin tocar ninguno de esos dos.

## Complexity Tracking

*Sin violaciones — tabla vacía. Ver Constitution Check.*

## Post-Design Constitution Re-check

Sin cambios respecto al gate inicial tras completar Phase 0/1 — la migración `056` es aditiva (2 columnas
nullable/con default, sin tabla nueva), ningún endpoint nuevo requiere excepción, y el alcance de archivos
tocados se mantiene 100% dentro de lo autorizado por esta sesión (namespace `teamwork_integration` + nuevo
módulo de importación), sin ninguna pantalla ajena tocada.
