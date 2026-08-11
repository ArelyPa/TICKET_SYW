# Implementation Plan: Operaciones Masivas, Paginación de Sincronización y Migración de Tareas/Subtareas (Teamwork API v3)

**Branch**: `044-sync-masivo-tareas` | **Date**: 2026-08-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/044-sync-masivo-tareas/spec.md`

## Summary

Amplía el integrador de Teamwork (spec 042/043) en 5 frentes: (1) corrige la sincronización incompleta de
catálogos — la API v3 de Teamwork limita cada respuesta a un tope propio del servidor sin importar el
`pageSize` pedido, y hoy solo se pide una página — agregando recorrido real de páginas, y expone la Compañía
de origen de cada Persona reutilizando la columna `parent_teamwork_id` ya existente; (2) agrega acciones
masivas (filtro por correo + migración masiva de Rol+Cliente) sobre Personal, reutilizando sin cambios la
función de creación individual `_create_new_person` ya probada; (3) enriquece los selectores de homologación
de Proyectos/Listas de Tareas con el formato `Cliente - Proyecto`; (4) fija la paginación de tabla a 15 filas y
agrega un distintivo de trazabilidad visible tanto en el integrador como en las 5 pantallas principales de
SYTIX afectadas; (5) migra masivamente Tareas/Subtareas desde `GET /projects/api/v3/tasks.json`, resolviendo
Cliente/Proyecto/Lista/Usuario vía las homologaciones ya existentes y reutilizando sin modificar
`TicketRepository.upsert_from_import` (spec 041) para crear/actualizar los Tickets con hipervínculo de origen.
Cero migraciones de base de datos nuevas, cero dependencias nuevas, cero permisos nuevos (ver research.md).

## Technical Context

**Language/Version**: Python 3.12 (Flask) + TypeScript strict (React 19)

**Primary Dependencies**: Flask-RESTX, SQLAlchemy, `requests` (ya aprobados) — backend; Ant Design 5, Axios —
frontend. Sin dependencias nuevas.

**Storage**: PostgreSQL 16 — reutiliza `teamwork_entity_mappings` (migraciones 054/055) y `tickets`
(`external_reference_id`/`url`, migración 053). Sin migración nueva.

**Testing**: `pytest` (backend, acotado a `backend/tests/api/test_teamwork_integration.py`, lote ≤10 registros,
Principio VII) — sin `tsc -b` roto como criterio de aceptación frontend.

**Target Platform**: Web app on-premise (Docker Compose), mismo entorno que el resto del proyecto.

**Project Type**: Web application (backend Flask + frontend React), extensión del namespace existente
`teamwork_integration`.

**Performance Goals**: N/A explícito — el recorrido de páginas de Teamwork debe completar una sincronización
de ~250-300 registros en el mismo orden de tiempo que hoy toma una sola página (llamadas HTTP adicionales
secuenciales, sin paralelismo, dado que Teamwork no documenta un límite de rate conocido en este entorno).

**Constraints**: Alcance de código restringido al namespace `teamwork_integration` (ruta/repo/modelo/cliente
de conexión) + `TeamworkIntegrationPage.tsx`/su service/tipos, más las 5 pantallas principales de SYTIX
estrictamente para el badge de trazabilidad (ver Complexity Tracking) — ningún archivo de
`tickets.py`/`clients.py`/`projects.py`/`task_lists.py`/`users.py`/`resources.py`/`client_contacts.py`/
`ticket_imports.py`/`teamwork_api_client.py`/`teamwork_import_service.py` se modifica, solo se invocan sus
repos/servicios ya existentes sin cambios (instrucción explícita de esta sesión).

**Scale/Scope**: 5 User Stories, 3 endpoints backend nuevos + 2 endpoints existentes con fix interno, ~6
archivos de frontend tocados (1 reescrito en profundidad + 5 con una columna adicional).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación |
|-----------|------------|
| I. API-First y Dominio Primero | PASA. La clasificación de Tareas (`teamwork_task_migration_service.py`) es Capa 1 pura, sin Flask/SQLAlchemy. Los 3 endpoints nuevos se documentan en `contracts/api.md` antes de implementar. |
| II. Clean Architecture 3 Capas | PASA. Capa 1: `teamwork_task_migration_service.py` (nuevo, puro). Capa 2: `teamwork_connection_client.py` (extendido: `_fetch_all_pages`, `fetch_tasks`), `teamwork_integration_repo.py` (sin cambios de esquema, posible método de lectura agregado). Capa 3: `teamwork_integration.py` (3 rutas nuevas) + páginas React. |
| III. Tipado Estricto | PASA. Nuevos tipos TS en `teamworkIntegration.ts` (`TeamworkBulkCreateNewResult`, `TeamworkMigratedRefs`, etc.); type hints en las funciones Python nuevas. Sin `any`. |
| IV. Seguridad en Profundidad | PASA. Mismo JWT + mismo permiso `teamwork_integration:operate` en los 3 endpoints nuevos — sin secretos nuevos, sin exponer token/URL de Teamwork en las respuestas nuevas (`migrated-refs` solo expone UUIDs de SYTIX ya visibles en sus propias pantallas). |
| V. Gobernanza de Librerías | PASA. Cero dependencias nuevas (research.md § Resumen de impacto). |
| VI. AI-Native | N/A directo — no toca el FSM de tickets ni el flujo de asignación; los Tickets creados por migración de Tareas usan los mismos campos estructurados ya definidos (skills, tipo de registro), sin excepción. |
| VII. Alcance de Sesión / Testing Ultra-Limitado | PASA con una desviación documentada — ver Complexity Tracking. Tests nuevos acotados a `test_teamwork_integration.py`, ≤10 registros por test, sin correr la suite completa. |

**Resultado**: PASA con 1 desviación documentada (alcance de archivos tocados fuera del namespace estricto,
para el badge de trazabilidad) — ver Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/044-sync-masivo-tareas/
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
│   └── importers/
│       └── teamwork_connection_client.py   # + _fetch_all_pages, fetch_tasks; fix _fetch_entity (person: parent_id)
├── infra/repositories/
│   └── teamwork_integration_repo.py        # + método de lectura para migrated-refs (sin cambio de esquema)
├── domain/services/
│   └── teamwork_task_migration_service.py  # NUEVO — Capa 1 pura, clasifica Tarea/Subtarea ready|skipped
├── api/routes/
│   └── teamwork_integration.py             # + bulk-create-new, migrated-refs, sync/tasks; fix _resolve_parent_context (person)
└── tests/api/
    └── test_teamwork_integration.py        # tests nuevos/tocados, ≤10 registros por test

frontend/src/
├── pages/
│   ├── TeamworkIntegrationPage.tsx         # bulk actions, filtros, paginación 15, selects Cliente-Proyecto
│   ├── ClientsPage.tsx                     # + badge trazabilidad (columna adicional, solo lectura)
│   ├── ProjectsPage.tsx                    # + badge trazabilidad
│   ├── ProjectListsPage.tsx                # + badge trazabilidad
│   ├── TeamPage.tsx                        # + badge trazabilidad
│   └── ClientContactsPage.tsx              # + badge trazabilidad
├── services/
│   └── teamworkIntegrationService.ts       # + bulkCreateNew, getMigratedRefs, syncTasks
└── types/
    └── teamworkIntegration.ts              # + tipos nuevos (bulk result, migrated refs)
```

**Structure Decision**: Web application ya existente (`backend/` Flask + `frontend/` React). Esta feature no
agrega proyectos ni capas nuevas — extiende el namespace `teamwork_integration` ya creado en spec 042 y toca,
de forma mínima y aditiva (una columna de solo lectura cada una), 5 pantallas principales de SYTIX para
cumplir FR-012/013.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| Se tocan 5 archivos fuera del namespace `teamwork_integration` (`ClientsPage.tsx`, `ProjectsPage.tsx`, `ProjectListsPage.tsx`, `TeamPage.tsx`, `ClientContactsPage.tsx`), aunque las directrices de esta sesión piden "modificar únicamente los componentes de UI del integrador" | FR-012/FR-013 del propio spec.md (ya validado, sin `[NEEDS CLARIFICATION]`) exigen explícitamente que el badge de trazabilidad sea visible "tanto en las pantallas del integrador como en sus respectivas pantallas principales dentro de SYTIX" — es un requisito de negocio, no una ampliación de alcance decidida en el plan. | Omitir el badge en las pantallas principales incumpliría FR-012/013 y dejaría US5 sin implementar. El cambio en cada archivo se limita a una columna/`Tag` de solo lectura consumiendo el nuevo endpoint `GET /migrated-refs` — no toca lógica de negocio, formularios, ni contratos existentes de esas pantallas. |

## Post-Design Constitution Re-check

Sin cambios respecto al gate inicial tras completar Phase 0/1 — ningún endpoint nuevo requiere excepción
adicional, ninguna migración de esquema resultó necesaria, y la única desviación (5 pantallas principales
tocadas) sigue acotada a una columna de solo lectura por archivo, ya justificada arriba.
