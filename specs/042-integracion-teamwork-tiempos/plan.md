# Implementation Plan: Integración API Teamwork v3, Homologación de Catálogos e Importador de Tiempos Mensuales

**Branch**: `042-integracion-teamwork-tiempos` | **Date**: 2026-08-09 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/042-integracion-teamwork-tiempos/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Pantalla de Administración para configurar y probar una conexión a la API v3 de Teamwork
(credenciales guardadas en BD, no por variable de entorno), sincronizar 4 catálogos
(Empresas/Proyectos/Personal/Listas de Tareas) hacia una tabla de homologación con automapeo por
correo/ID externo/nombre y corrección manual, y un importador de reportes mensuales de tiempos
(CSV/Excel) con el mismo patrón preview→confirm sin persistencia intermedia ya usado en spec 041,
que resuelve cada fila contra los catálogos homologados y ofrece homologar/crear (solo
Recurso/Cliente)/omitir para las filas en conflicto antes de confirmar la carga como `WorkSession`.
Alcance de sesión restringido a tablas/modelos nuevos, la vista de administración de la API y el
servicio parser de tiempos — sin tocar el importador de tareas de spec 041 (Principio VII).

## Technical Context

**Language/Version**: Python 3.12 (backend, Flask) + TypeScript 5 strict / React 19 (frontend) —
mismo stack ya aprobado por la constitución, sin cambios.

**Primary Dependencies**: Flask-RESTX, SQLAlchemy + Alembic, `requests` (ya usado por
`teamwork_api_client.py`, spec 041), `openpyxl`/`csv` (ya usado por `teamwork_file_parser.py`,
spec 034/041) para el backend; Ant Design 5, Axios, Zustand para el frontend. **Sin dependencias
nuevas** (Principio V) — reutiliza exactamente el mismo stack que spec 041.

**Storage**: PostgreSQL 16. 3 tablas nuevas (`teamwork_integration_configs`,
`teamwork_entity_mappings`, `time_import_batches`) + 1 columna aditiva en `work_sessions`
(`external_time_id`) — ver data-model.md.

**Testing**: pytest (backend, acotado a los archivos nuevos de esta sesión, máximo 5-10 registros
por test, prohibido correr la suite completa — Principio VII / instrucción explícita del usuario).
Sin pruebas de frontend nuevas (el proyecto no tiene suite de frontend establecida).

**Target Platform**: Servidor Linux on-premise vía Docker Compose (backend) + navegador (frontend
SPA) — sin cambio de plataforma.

**Project Type**: Web application (backend Flask + frontend React), mismo patrón que el resto del
repositorio.

**Performance Goals**: Sin requisito de rendimiento distinto al resto de la app — ver SC-002
(prevalidar hasta 200 filas en <30s), acorde al volumen ya manejado por spec 041.

**Constraints**: Alcance de código restringido por Principio VII/instrucción de esta sesión: solo
tablas/modelos de credenciales y referencias externas, la vista de administración de la API y el
servicio parser de tiempos — prohibido refactorizar `ticket_imports.py`/`teamwork_api_client.py`/
`teamwork_file_parser.py`/`teamwork_import_service.py` de spec 041 o cualquier otro módulo fuera
de este alcance. Sin smoke-test contra una cuenta real de Teamwork (sin credenciales en este
entorno, igual que spec 041).

**Scale/Scope**: 1 pantalla de configuración + 1 vista de homologación (posiblemente como tab de
la misma pantalla) + 1 pantalla de importación de tiempos; 4 endpoints de catálogo/homologación +
2 endpoints de importación + 3 de configuración/prueba de conexión.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. API-First y Dominio Primero**: PASS. `time_import_service.py` (clasificación de filas) y
  la lógica de automapeo de homologación son Capa 1 pura (sin imports de Flask/SQLAlchemy/
  `requests`/`openpyxl`), igual que `teamwork_import_service.py` de spec 041. Contratos Swagger
  documentados en `contracts/api.md` antes de implementar (Flask-RESTX genera el schema real).
- **II. Clean Architecture - Tres Capas**: PASS. Capa 1 (`backend/domain/entities/`,
  `backend/domain/services/time_import_service.py`, `entity_mapping_service.py`) sin
  dependencias externas; Capa 2 (`backend/infra/importers/teamwork_connection_client.py`,
  `teamwork_time_file_parser.py`, `backend/infra/repositories/teamwork_integration_repo.py`)
  implementa acceso a la API externa y a BD; Capa 3 (`backend/api/routes/teamwork_integration.py`,
  `time_imports.py`, páginas React nuevas) solo orquesta/renderiza.
- **III. Tipado Estricto**: PASS. Type hints en servicios/repositorios nuevos de Python;
  interfaces TypeScript nuevas (`teamworkIntegration.ts`, `timeImport.ts`) sin `any`.
- **IV. Seguridad en Profundidad**: PASS. El token de Teamwork se cifra en BD con el mismo
  mecanismo app-level ya usado para `client_access` (`_encrypt`/`_decrypt`,
  `backend/infra/models/client_model.py`) — nunca se devuelve en texto plano por la API
  (`GET /config` solo expone `has_token`). RLS no aplica (tablas de configuración/homologación no
  son datos de cliente por fila, son de administración global) — mismo criterio ya usado para
  otras tablas de catálogo/configuración del sistema.
- **V. Gobernanza de Librerías**: PASS. Cero dependencias nuevas — ver Technical Context.
- **VI. AI-Native**: N/A directo — este módulo es de integración/importación administrativa, no
  de acciones del Coordinador sobre tickets. `WorkSession` creado por el importador usa los mismos
  campos estructurados (`resource_id`, `ticket_id`, `duration_minutes`, `note`) que el registro de
  tiempo manual ya "AI-ready" de fases anteriores — sin cambio de forma.
- **VII. Alcance de Sesión / Testing Ultra-Limitado**: PASS por diseño — ver Constraints arriba y
  quickstart.md § "Verificación de alcance". Ningún archivo de spec 041 se modifica.

**Resultado**: Sin violaciones. Tabla de Complexity Tracking no aplica (vacía).

## Constitution Check (post-Phase 1)

Re-evaluado tras research.md/data-model.md/contracts: sin cambios respecto al check inicial. La
Decisión 3 de research.md (una sola tabla `teamwork_entity_mappings` en vez de 4) y la Decisión 4
(auto-creación limitada a Recurso/Cliente) reducen superficie de código frente al diseño inicial,
reforzando el cumplimiento de Principio VII. PASS.

## Project Structure

### Documentation (this feature)

```text
specs/042-integracion-teamwork-tiempos/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── api.md           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── domain/
│   ├── entities/
│   │   └── teamwork_integration.py        # NUEVO: TeamworkIntegrationConfig, EntityMapping (Capa 1)
│   └── services/
│       ├── time_import_service.py         # NUEVO: clasificación pura de filas del reporte de tiempos
│       └── entity_mapping_service.py      # NUEVO: automapeo puro (correo/ID externo/nombre exacto)
├── infra/
│   ├── importers/
│   │   ├── teamwork_connection_client.py  # NUEVO: cliente API v3 con credenciales de BD (test-connection + sync catálogos)
│   │   └── teamwork_time_file_parser.py   # NUEVO: parser Excel/CSV del reporte de tiempos mensual
│   ├── models/
│   │   └── teamwork_integration_model.py  # NUEVO: modelos SQLAlchemy de las 3 tablas nuevas
│   ├── repositories/
│   │   └── teamwork_integration_repo.py   # NUEVO: config (singleton), homologaciones, batches de auditoría
│   └── migrations/versions/
│       └── 054_teamwork_integration_time_imports.py  # NUEVO
├── api/routes/
│   ├── teamwork_integration.py            # NUEVO: namespace config/test-connection/sync/homologación
│   └── time_imports.py                    # NUEVO: namespace preview/confirm de tiempos
└── tests/
    ├── domain/
    │   ├── test_time_import_service.py            # NUEVO (≤10 registros)
    │   └── test_entity_mapping_service.py         # NUEVO (≤10 registros)
    ├── infra/
    │   ├── test_teamwork_connection_client.py     # NUEVO (mocks, ≤10 registros)
    │   └── test_teamwork_time_file_parser.py      # NUEVO (≤10 filas de fixture)
    └── api/
        ├── test_teamwork_integration.py           # NUEVO (≤10 registros)
        └── test_time_imports.py                   # NUEVO (≤10 registros)

frontend/src/
├── pages/
│   ├── TeamworkIntegrationPage.tsx        # NUEVO: config + probar conexión + sincronizar catálogos + tab de homologación
│   └── TimeImportsPage.tsx                # NUEVO: carga de archivo + resumen de validación + resolución de conflictos + confirmar
├── services/
│   ├── teamworkIntegrationService.ts      # NUEVO
│   └── timeImportService.ts               # NUEVO
├── types/
│   ├── teamworkIntegration.ts             # NUEVO
│   └── timeImport.ts                      # NUEVO
├── config/navigation.tsx                  # MODIFICADO (aditivo): entradas de menú nuevas, gateadas por permiso
└── App.tsx                                # MODIFICADO (aditivo): rutas nuevas
```

**Structure Decision**: Aplicación web ya existente (backend Flask + frontend React, Clean
Architecture de 3 capas) — esta feature agrega módulos nuevos siguiendo exactamente la misma
estructura de directorios que spec 041 (`teamwork_api_client.py`/`teamwork_file_parser.py` en
`infra/importers/`, servicio puro en `domain/services/`, namespace propio en `api/routes/`), sin
crear ningún directorio nuevo de alto nivel. Ningún archivo de spec 041 se modifica (research.md
Decisión 1); `frontend/src/config/navigation.tsx` y `App.tsx` son los únicos archivos
preexistentes tocados, de forma estrictamente aditiva (registro de rutas/menú).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Sin violaciones — tabla no aplica.
