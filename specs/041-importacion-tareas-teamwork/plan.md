# Implementation Plan: Migración e Importación de Tareas desde Teamwork (API v3 / Excel) con Trazabilidad y Asignación a Coordinador

**Branch**: `041-importacion-tareas-teamwork` | **Date**: 2026-08-09 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/041-importacion-tareas-teamwork/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Módulo de migración de tareas desde Teamwork hacia SYTIX con dos vías de entrada (carga
Excel/CSV y sincronización API v3, ambas con vista previa obligatoria antes de confirmar),
trazabilidad cruzada vía dos campos nuevos en `tickets` (`external_reference_id`/
`external_reference_url`, visibles como enlace en el detalle), y ampliación de la asignación de
Tickets/Tareas para admitir usuarios con rol Coordinador además de Resolutor — reutilizando el
patrón ya probado de "candidatos por rol + Recurso aprovisionado perezosamente" que spec 033
introdujo para QM. Alcance de código deliberadamente acotado (instrucción explícita de esta
sesión) a: la migración de los dos campos de referencia (+ el permiso `ticket_imports:run`), el
servicio de importación (parser Excel/CSV + cliente API v3 + mapeo de dominio), y las reglas de
asignación de Coordinador.

## Technical Context

**Language/Version**: Python 3.12 (backend, Flask) + TypeScript 5 / React 19 (frontend) — stack
ya establecido, sin cambios.

**Primary Dependencies**: `openpyxl` (ya en `requirements.txt`, spec 034) para `.xlsx`; módulo
estándar `csv` para `.csv`; `requests` (ya en `requirements.txt`) para el cliente API v3 de
Teamwork. Frontend: Ant Design `Upload`/`Table` (ya en uso). **Sin dependencias nuevas**
(Principio V).

**Storage**: PostgreSQL 16 (ya existente) — 2 columnas nuevas en `tickets`, sin tablas nuevas
(ver research.md Decisión 1-3).

**Testing**: `pytest` (backend, acotado a los archivos tocados, máx 5-10 filas por test —
Principio VII); `tsc -b` (frontend, sin suite E2E nueva en esta sesión).

**Target Platform**: Backend Flask en Docker (Linux), frontend Vite/React servido vía Docker —
sin cambios de infraestructura.

**Project Type**: Web application (backend Flask + frontend React), ya existente.

**Performance Goals**: La vista previa de un archivo de cientos de filas (uso real esperado, no
el fixture de prueba de esta sesión) debe renderizarse en la tabla del frontend sin bloquear la
UI — sin requisito numérico adicional al resto de la aplicación.

**Constraints**: Ningún dato se inserta en `tickets` hasta la confirmación explícita del usuario
(FR-004). Reimportar el mismo `external_reference_id` actualiza en vez de duplicar (FR-009).
Solo Admin/Coordinador pueden importar (permiso `ticket_imports:run`).

**Scale/Scope**: Volumen esperado de un reporte de Teamwork típico (cientos de filas por carga),
sin paginación de servidor para la vista previa (research.md Decisión 2).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. API-First y Dominio Primero**: PASS. El endpoint de importación (`ticket_imports`) y los
  endpoints de asignación (`/assign`, `/reassign`, `/coordinador-candidates`) se documentan en
  Swagger (Flask-RESTX) antes de implementarse (ver `contracts/api.md`). La lógica de mapeo vive
  en `backend/domain/services/teamwork_import_service.py` (Capa 1, sin imports externos).
- **II. Clean Architecture - Tres Capas**: PASS. Ver research.md Decisión 5 — Capa 1 (mapeo puro),
  Capa 2 (`backend/infra/importers/`, parser de archivo + cliente HTTP de Teamwork), Capa 3
  (`backend/api/routes/ticket_imports.py`).
- **III. Tipado Estricto**: PASS. Sin `any` nuevo en TypeScript; type hints en el servicio de
  dominio y en el parser/cliente de Capa 2.
- **IV. Seguridad en Profundidad**: PASS. Sin credenciales de Teamwork expuestas al frontend — el
  token/dominio de la API v3 vive solo en configuración de servidor (variable de entorno del
  backend, igual que el resto de secretos). `ticket_imports:run` gatea ambos endpoints nuevos.
  RLS de `tickets` (migración 012) no cambia — las columnas nuevas no son sensibles.
- **V. Gobernanza de Librerías**: PASS. Cero dependencias nuevas — ver Technical Context.
- **VI. AI-Native**: PASS. Los endpoints de importación son independientes de la UI (puede
  invocarlos un futuro proceso automatizado); `/assign` sigue siendo agnóstico al caller.
- **VII. Alcance de Sesión / Testing Ultra-Limitado**: PASS por diseño — ver Summary. Ningún test
  de importación insertará más de 5-10 filas; no se corre la suite completa.

No hay violaciones que registrar en Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/041-importacion-tareas-teamwork/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── api.md            # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── infra/
│   ├── migrations/versions/
│   │   └── 053_ticket_external_reference.py   # nuevo: 2 columnas + permiso ticket_imports:run
│   ├── models/ticket_model.py                 # editado: 2 columnas nuevas
│   ├── importers/                             # nuevo (Capa 2)
│   │   ├── teamwork_file_parser.py             # nuevo: .xlsx/.csv -> filas dict homologadas
│   │   └── teamwork_api_client.py              # nuevo: API v3 Teamwork -> filas dict homologadas
│   └── repositories/
│       └── ticket_repo.py                      # editado: upsert por external_reference_id, campos en _ticket_detail
├── domain/
│   └── services/
│       ├── teamwork_import_service.py          # nuevo (Capa 1): mapeo/validación puro
│       └── assignment_service.py               # editado: ASSIGN_MODE_REQUIRED_ROLE["resolver"] admite Coordinador
├── domain/services/reassignment_service.py      # sin cambios de lógica (ya agnóstico al rol)
└── api/routes/
    ├── ticket_imports.py                        # nuevo (Capa 3): namespace ticket_imports
    └── tickets.py                                # editado: /coordinador-candidates, resolución de assignee en /assign y /reassign, campos externos en _ticket_detail

frontend/src/
├── pages/
│   └── TicketImportsPage.tsx                    # nuevo: carga archivo/API v3 + vista previa + confirmar
├── services/
│   └── ticketImportService.ts                   # nuevo: llamadas a /api/ticket-imports/*
├── components/tickets/
│   ├── useResourceCandidates.ts                  # editado: agrega candidatos Coordinador
│   ├── ResourceCandidateGrid.tsx                 # editado: etiqueta de rol por candidato
│   └── TicketDetailPage.tsx                      # editado: insignia/enlace de Teamwork
└── config/navigation.tsx                         # editado: nuevo ítem "Importación de Tareas"
```

**Structure Decision**: Se extiende la estructura de tres capas ya existente (`backend/domain` /
`backend/infra` / `backend/api`) con un subpaquete nuevo `backend/infra/importers/` (Capa 2,
adaptadores de origen externo — mismo rol que `backend/infra/repositories/` pero para fuentes no
transaccionales) y un servicio de dominio nuevo en `backend/domain/services/`. No se crean
proyectos ni carpetas de nivel superior nuevas; el frontend sigue el patrón ya establecido
`pages/` + `services/` + `components/`.

## Complexity Tracking

> Sin violaciones que justificar — tabla omitida (Constitution Check en PASS).
