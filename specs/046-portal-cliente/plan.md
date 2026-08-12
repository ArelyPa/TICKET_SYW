# Implementation Plan: Portal de Cliente (Login Diferenciado, Aislamiento por Cliente, Comentarios Públicos y Respuesta a Solicitud de Información)

**Branch**: `046-portal-cliente` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/046-portal-cliente/spec.md`

## Summary

Cierra la "Fase 8" ya anticipada en el modelo de datos (`comment.py`: *"external = visible al cliente (Portal, Fase 8)"*; `ticket_fsm.py`: ciclo `solicitud_informacion`→`pendiente_usuario`→`respuesta_usuario`→`en_ejecucion` ya completo) exponiéndola al rol `Usuario/cliente`: (1) Login con 2 pestañas y enforcement estricto de rol; (2) `tickets:view_own` pasa de `created_by = usuario actual` a `client_id = Cliente del usuario` (ámbito de empresa completa, decidido con el usuario); (3) los comentarios `visibility = internal` se excluyen a nivel de API para este rol; (4) se habilita al Usuario/cliente a registrar el comentario `respuesta_usuario` (hoy bloqueado en `comment_service.validate` y sin permiso de ruta) reutilizando sin cambios la transición FSM y la notificación `user_replied` al resolutor, ambas ya implementadas y ya cableadas en `POST /<ticket_id>/comments`; más Centro de Notificaciones (reutiliza `NotificationService`/`GET /api/notifications`) y filtro "Asignado a mí" para Tickets/Tareas del Usuario/cliente. Se conserva sin cambios el alta simplificada de Ticket ya existente para este rol (autoservicio, spec 010/033); solo se retira creación de Tareas y campos avanzados de perfil interno.

## Technical Context

**Language/Version**: Python 3.12 (Flask) backend · TypeScript 5 strict (React 19) frontend — sin cambio, stack ya vigente.

**Primary Dependencies**: Flask-RESTX, SQLAlchemy + Alembic, `python-transitions` (backend, reutilizados sin cambios) · Ant Design 5 (`Tabs`/`Segmented`, ya en uso desde spec 045), Zustand, `date-fns`, Axios (frontend, reutilizados sin cambios). **Cero dependencias nuevas** (Principio V).

**Storage**: PostgreSQL 16 — **sin migración de esquema nueva** salvo 1 fila aditiva de permiso (`tickets:respond_client`, ver Data Model); todos los demás datos que la feature necesita (`role.name`, `client_contact.client_id`, `comment.comment_type`/`visibility`, `ticket.status`) ya existen.

**Testing**: `pytest` acotado a los archivos tocados, **máximo 5 registros de prueba por test** (instrucción explícita del usuario, más estricta que el "5 a 10" del Principio VII) — prohibido correr la suite completa. `tsc -b` para verificación de tipos frontend.

**Target Platform**: Stack Docker Compose on-premise ya vigente (Flask API + PostgreSQL + React/Vite servidos vía Nginx/dev server) — sin cambios de infraestructura.

**Project Type**: Web (monorepo `backend/` + `frontend/` ya existente).

**Performance Goals**: N/A — reutiliza los mismos endpoints/índices ya existentes (`GET /api/tickets` por `client_id`, ya indexado desde Fase 1); sin nuevo patrón de acceso a datos que requiera índices adicionales.

**Constraints**: Alcance de código restringido explícitamente (instrucción del usuario) a: pantalla de Login, middleware/guardia de permisos de `Usuario/cliente`, componentes de comentarios, y el filtro de visibilidad por cliente en tickets — **prohibido modificar controladores centrales fuera de este rol** (p. ej. no se toca la lógica de Coordinador/QM/Resolutor en los mismos archivos más allá de lo estrictamente necesario para no romper su comportamiento).

**Scale/Scope**: Mismo volumen ya sembrado (Clientes Aris/Vaxthera + Usuario/cliente reales) — sin cambio de escala.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación |
|-----------|------------|
| I. API-First y Dominio Primero | PASS — el único cambio de regla de negocio real (quién puede disparar `respuesta_usuario`) vive en `comment_service.validate` (Capa 1, puro); el enforcement de pestaña de Login es autenticación de ruta (Capa 3), no lógica de negocio. |
| II. Clean Architecture (3 capas) | PASS — reutiliza Capa 1 (`comment_service`, `ticket_fsm`), Capa 2 (`ticket_repo`, `client_contact_repo`), Capa 3 (`api/routes/auth.py`, `api/routes/tickets.py`, `frontend/src/pages|components`). Ninguna capa nueva. |
| III. Tipado Estricto | PASS — TS `strict` se mantiene; nuevos campos (`login_mode`, filtro "Asignado a mí" del cliente) tipados en `frontend/src/types/`. |
| IV. Seguridad en Profundidad | PASS con nota — el aislamiento por Cliente (US2) se refuerza en la capa de aplicación (repositorio + ruta), igual que el resto de scoping por rol ya existente en este proyecto (`tickets:view_own`/`view_assigned`); la RLS de PostgreSQL sigue siendo deliberadamente permisiva (migración 012, decisión ya tomada y documentada en specs previas) — no se modifica RLS en esta feature, mismo criterio que spec 038 US1. |
| V. Gobernanza de Librerías | PASS — cero dependencias nuevas; reutiliza `Tabs`/`Segmented` de Ant Design 5 ya aprobado y en uso. |
| VI. AI-Native | PASS — reutiliza tipos de comentario ya estructurados (`comment_type`); no se introduce texto libre como disparador. |
| VII. Alcance de Sesión y Testing Ultra-Limitado | PASS — alcance de código acotado explícitamente por el usuario (ver Constraints); pruebas ≤5 registros por test; prohibido correr la suite completa. |

No hay violaciones que requieran registrarse en Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/046-portal-cliente/
├── plan.md              # Este archivo
├── research.md          # Fase 0
├── data-model.md         # Fase 1
├── quickstart.md         # Fase 1
├── contracts/            # Fase 1
│   └── api-changes.md
└── tasks.md              # Fase 2 (/speckit-tasks, no generado por /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── domain/
│   └── services/
│       └── comment_service.py        # MODIFICAR: permitir respuesta_usuario desde Usuario/cliente
├── infra/
│   └── repositories/
│       ├── ticket_repo.py            # MODIFICAR: list_paginated — ámbito por client_id + narrowing "asignado a mí"
│       ├── client_contact_repo.py    # REUTILIZAR sin cambios (get_by_user_id ya existe)
│       └── role_repo.py              # REUTILIZAR sin cambios (list_permissions_for_role)
├── api/
│   ├── middleware/
│   │   └── rbac.py                   # REUTILIZAR sin cambios (current_user_has, require_permission)
│   └── routes/
│       ├── auth.py                   # MODIFICAR: enforcement de login_mode vs rol
│       └── tickets.py                # MODIFICAR: scoping de GET list, filtrado de comentarios internal
│                                      #   en _ticket_detail, gate de POST /comments para respuesta_usuario
└── infra/migrations/versions/
    └── 057_tickets_respond_client_permission.py   # NUEVA: permiso tickets:respond_client → Usuario/cliente

frontend/
├── src/
│   ├── pages/
│   │   ├── LoginPage.tsx             # MODIFICAR: pestañas Equipo/Portal
│   │   ├── TicketsPage.tsx           # MODIFICAR: ocultar creación de Tarea/campos avanzados, filtro "Asignado a mí"
│   │   └── MyTasksPage.tsx           # MODIFICAR: habilitar filtro "Asignado a mí" también para Usuario/cliente
│   ├── components/
│   │   ├── common/
│   │   │   ├── AuthLayout.tsx        # REUTILIZAR sin cambios de identidad visual
│   │   │   └── NotificationBell.tsx  # REUTILIZAR sin cambios (ya genérico por evento)
│   │   └── tickets/
│   │       ├── CommentThread.tsx     # MODIFICAR: caja de respuesta cuando status=pendiente_usuario
│   │       └── CommentComposer.tsx   # REUTILIZAR/EXTENDER para el tipo respuesta_usuario
│   ├── services/
│   │   ├── authService.ts            # MODIFICAR: enviar login_mode
│   │   └── ticketService.ts          # MODIFICAR: nuevo parámetro de filtro "asignado a mí" (cliente)
│   └── types/
│       └── auth.ts                   # MODIFICAR: tipo LoginMode
└── tests/                            # sin suite E2E nueva fuera del alcance de esta sesión
```

**Structure Decision**: Se mantiene la estructura de monorepo web (`backend/` + `frontend/`) ya vigente en todo el proyecto — ninguna carpeta ni capa nueva. Todos los archivos listados como "MODIFICAR" ya existen; el único artefacto nuevo es una migración de Alembic aditiva (1 fila de permiso) y, del lado de tests, los archivos de prueba específicos de los módulos tocados.

## Complexity Tracking

*Sin violaciones de la Constitution Check — tabla no aplica.*
