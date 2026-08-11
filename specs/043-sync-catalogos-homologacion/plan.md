# Implementation Plan: Ampliación y Ajustes Finos en la Sincronización de Catálogos de Teamwork (Mapeo, Homologación y Creación Dinámica)

**Branch**: `develp_Jp` (sin rama de feature dedicada — mismo criterio que specs 041/042 en este
repositorio, la spec vive en `specs/043-...` de forma independiente del nombre de la rama) | **Date**: 2026-08-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/043-sync-catalogos-homologacion/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Amplía la pantalla de Homologación de Entidades de la Integración Teamwork (spec 042,
`TeamworkIntegrationPage.tsx`) para que cada fila sin resolver ofrezca dos acciones explícitas —
"Homologar" (vincular a un registro SYTIX existente, ya implementado) y "Migrar como Nuevo" (crear
el registro en SYTIX con los datos de Teamwork, nuevo endpoint `POST .../entity-mappings/{id}/
create-new` que reutiliza sin cambios los repos/servicios de creación ya existentes de
Cliente/Proyecto/Usuario+Recurso/Usuario-cliente/Lista de Tareas) — agrega contexto jerárquico
(Cliente dueño de un Proyecto; Cliente+Proyecto dueños de una Lista de Tareas) y de correo para
Personal, un selector de Rol obligatorio antes de migrar una Persona, y un badge de estado
("Pendiente"/"Homologado"/"Migrado") derivado de `match_method`. Toda la trazabilidad de IDs
externos se apoya en la tabla `teamwork_entity_mappings` ya existente (research.md Decisión 1),
ampliada con 2 columnas aditivas (`parent_teamwork_id`, `teamwork_email`) en una sola migración —
sin tabla nueva, sin tocar `clients`/`projects`/`resources`/`users`/`task_lists`. Alcance de código
acotado al namespace `teamwork_integration` (ruta, repo, modelo, cliente de conexión) y a la
pantalla/servicio/tipos de frontend correspondientes — no se modifica la lógica central de
usuarios ni de proyectos globales, solo se invoca (instrucción explícita de esta sesión).

## Technical Context

**Language/Version**: Python 3.12 (backend, Flask) + TypeScript 5 strict / React 19 (frontend) —
mismo stack ya aprobado por la constitución, sin cambios.

**Primary Dependencies**: Flask-RESTX, SQLAlchemy + Alembic, `requests` (ya usado por
`teamwork_connection_client.py`, spec 042) para el backend; Ant Design 5, Axios para el frontend.
**Sin dependencias nuevas** (Principio V).

**Storage**: PostgreSQL 16. 2 columnas aditivas nuevas (`parent_teamwork_id`, `teamwork_email`)
sobre `teamwork_entity_mappings` (tabla ya existente de spec 042) — ver data-model.md. Ninguna
tabla nueva.

**Testing**: pytest (backend, acotado a los archivos tocados/nuevos de esta sesión, máximo 5-10
registros por test, prohibido correr la suite completa — Principio VII / instrucción explícita del
usuario). Sin pruebas de frontend nuevas (el proyecto no tiene suite de frontend establecida).

**Target Platform**: Servidor Linux on-premise vía Docker Compose (backend) + navegador (frontend
SPA) — sin cambio de plataforma.

**Project Type**: Web application (backend Flask + frontend React), mismo patrón que el resto del
repositorio.

**Performance Goals**: Sin requisito de rendimiento distinto al resto de la app. La resolución de
contexto jerárquico agrega hasta 2 lookups adicionales por fila de Proyecto/Lista de Tareas
(research.md Decisión 2) sobre una tabla sin paginación server-side hoy — volumen ya acotado al de
un catálogo de Teamwork sincronizado (spec 042 no reportó problema de escala).

**Constraints**: Alcance de código restringido por Principio VII/instrucción de esta sesión: solo
la interfaz de la pantalla de Sincronización de Catálogos de Teamwork, las migraciones/modelos para
guardar IDs de referencia externa, y el controlador de importación (`teamwork_integration.py`,
`teamwork_integration_repo.py`, `teamwork_integration_model.py`, `teamwork_connection_client.py`).
Prohibido modificar la lógica central de usuarios ni de proyectos globales — la creación de
registros vía "Migrar como Nuevo" **invoca** `ClientRepository`/`ProjectRepository`/
`UserRepository`/`ResourceRepository`/`ClientContactRepository`/`TaskListRepository` y sus
servicios de validación (`ClientService`/`ProjectService`/`ClientContactService`/
`TaskListService`) tal cual existen hoy, sin tocar esos archivos. Suite de pruebas: prohibido
correr la suite completa; cualquier test nuevo de homologación se limita a 5-10 registros dummy
(instrucción explícita de esta sesión). Sin smoke-test contra una cuenta real de Teamwork para el
campo `parent_id` nuevo en `_fetch_entity` (mismo caso ya documentado en spec 041/042 — verificado
contra la documentación oficial, con fallback a `None` si el payload real no trae el campo
esperado, sin romper la sincronización existente).

**Scale/Scope**: 1 endpoint nuevo (`create-new`) + 1 endpoint nuevo de solo lectura
(`create-new-candidates`) + ampliación de `GET /entity-mappings` (3 campos derivados nuevos en la
respuesta) + ampliación de `POST /sync/<entity_type>` (captura de `parent_id`/`email` sin cambiar
su contrato) sobre el namespace ya existente; 1 migración aditiva; cambios de UI acotados a
`TeamworkIntegrationPage.tsx` (nuevas columnas, nuevo botón/modal por fila, badges) y sus
`service.ts`/`types.ts`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. API-First y Dominio Primero**: PASS. Contrato documentado en `contracts/api.md` antes de
  implementar (Flask-RESTX genera el schema real). El endpoint nuevo `create-new` no contiene
  lógica de negocio propia: delega en los servicios de dominio/repos ya existentes de cada entidad
  destino (research.md Decisión 5) — cero reglas de negocio nuevas en Capa 1.
- **II. Clean Architecture - Tres Capas**: PASS. Capa 1 (`entity_mapping_service.py`, si se toca,
  sigue sin imports de Flask/SQLAlchemy/`requests`) sin cambios de fondo; Capa 2
  (`teamwork_connection_client.py` amplía `_fetch_entity`; `teamwork_integration_repo.py` amplía
  `upsert_from_sync`/agrega `set_created_new_mapping`); Capa 3 (`teamwork_integration.py`) orquesta
  llamando a los repos/servicios de Cliente/Proyecto/Usuario/Recurso/Cliente-contacto/Lista de
  Tareas ya existentes — nunca reimplementa su validación.
- **III. Tipado Estricto**: PASS. Type hints en los métodos de repo ampliados; tipos TypeScript
  nuevos (`migration_status`, `parent_context`, payload de `create-new`) en
  `types/teamworkIntegration.ts`, sin `any`.
- **IV. Seguridad en Profundidad**: PASS. Mismo permiso ya existente
  (`teamwork_integration:operate`) para "Homologar" y "Migrar como Nuevo" — sin credenciales
  nuevas, sin cambio de RLS (la tabla de homologación sigue sin ser dato de cliente por fila).
- **V. Gobernanza de Librerías**: PASS. Cero dependencias nuevas.
- **VI. AI-Native**: N/A directo — módulo de integración/homologación administrativa, no de
  acciones del Coordinador sobre tickets.
- **VII. Alcance de Sesión / Testing Ultra-Limitado**: PASS por diseño — ver Constraints arriba y
  quickstart.md § "Verificación de alcance". Ningún archivo de `clients.py`/`projects.py`/
  `users.py`/`resources.py`/`client_contacts.py`/`task_lists.py` se modifica, solo se invocan sus
  repos/servicios ya existentes desde el namespace de integración.

**Resultado**: Sin violaciones. Tabla de Complexity Tracking no aplica (vacía).

## Constitution Check (post-Phase 1)

Re-evaluado tras research.md/data-model.md/contracts: sin cambios respecto al check inicial. La
Decisión 1 (reutilizar `teamwork_entity_mappings` en vez de agregar `external_id` a 5 tablas
destino) y la Decisión 5 (reutilizar los repos/servicios de creación ya existentes en vez de
reimplementar validación en el endpoint nuevo) reducen aún más la superficie de código tocada
frente al diseño inicial, reforzando Principio VII. PASS.

## Project Structure

### Documentation (this feature)

```text
specs/043-sync-catalogos-homologacion/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
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
│   │   └── teamwork_integration.py        # MODIFICADO (aditivo): EntityMapping gana parent_teamwork_id/teamwork_email
│   └── services/
│       └── entity_mapping_service.py      # Sin cambios de fondo (automapeo puro ya cubre lo necesario)
├── infra/
│   ├── importers/
│   │   └── teamwork_connection_client.py  # MODIFICADO (aditivo): _fetch_entity captura parent_id para project/tasklist
│   ├── models/
│   │   └── teamwork_integration_model.py  # MODIFICADO (aditivo): 2 columnas nuevas en EntityMappingModel
│   ├── repositories/
│   │   └── teamwork_integration_repo.py   # MODIFICADO: upsert_from_sync amplía firma; nuevo set_created_new_mapping; +task_list en _SYTIX_REPO_BY_TYPE
│   └── migrations/versions/
│       └── 055_teamwork_entity_mappings_context.py  # NUEVO
├── api/routes/
│   └── teamwork_integration.py            # MODIFICADO: +GET .../create-new-candidates, +POST .../create-new; GET /entity-mappings enriquecido
└── tests/
    ├── infra/
    │   └── test_teamwork_connection_client.py     # MODIFICADO (mocks, ≤10 registros): parent_id capturado
    └── api/
        └── test_teamwork_integration.py           # MODIFICADO/AMPLIADO (≤10 registros): create-new por tipo de entidad, casos 409

frontend/src/
├── pages/
│   └── TeamworkIntegrationPage.tsx        # MODIFICADO: columnas Cliente Asociado/Correo/Cliente+Proyecto, botón+modal "Migrar como Nuevo", badges de estado
├── services/
│   └── teamworkIntegrationService.ts      # MODIFICADO (aditivo): createNewCandidates(), createNew()
└── types/
    └── teamworkIntegration.ts             # MODIFICADO (aditivo): migration_status, parent_context, CreateNewPayload
```

**Structure Decision**: Aplicación web ya existente (backend Flask + frontend React, Clean
Architecture de 3 capas) — esta feature no agrega directorios ni namespaces nuevos, amplía de
forma aditiva exactamente los mismos archivos que introdujo spec 042 para este módulo. Ningún
archivo de `clients.py`/`projects.py`/`users.py`/`resources.py`/`client_contacts.py`/
`task_lists.py`/`ticket_imports.py`/`time_imports.py` se modifica — solo se invocan sus repos/
servicios ya existentes desde `teamwork_integration.py` (research.md Decisión 5).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Sin violaciones — tabla no aplica.
