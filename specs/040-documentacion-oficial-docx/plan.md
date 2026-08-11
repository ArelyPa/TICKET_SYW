# Implementation Plan: Generación y Actualización de Documentación Oficial (3 Documentos .docx)

**Branch**: `040-documentacion-oficial-docx` | **Date**: 2026-08-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/040-documentacion-oficial-docx/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Generar/actualizar de forma automatizada y no destructiva tres documentos `.docx` oficiales en `docs/`
(Manual de Usuario, Documentación de Código Fuente, Descripción Ejecutiva) mediante un único script
Python (`docs/generate_docs.py`) que usa `python-docx` — ya disponible en el entorno (v1.2.0), sin
agregar dependencias al `backend/requirements.txt` ni al `frontend/package.json` (Principio V). El
script solo lee el repositorio (código, specs, `docker-compose.yml`, `.env.example`) para construir el
contenido y solo escribe dentro de `docs/`; no se ejecuta la suite de pruebas ni se toca lógica de
negocio (Principio VII, restricción explícita de esta sesión).

## Technical Context

**Language/Version**: Python 3.10 (intérprete ya presente en el entorno de esta sesión; el proyecto
backend usa Python 3.12 en Docker, pero este script es una herramienta de documentación independiente,
no parte del runtime de la app, por lo que no requiere igualar esa versión).

**Primary Dependencies**: `python-docx` 1.2.0 (ya instalado en el entorno; se referencia con un pin en
`docs/requirements-docs.txt` — archivo nuevo, alcance `docs/`, no toca `backend/requirements.txt`).

**Storage**: N/A — no hay base de datos ni persistencia; el script lee archivos del repositorio en disco
y escribe archivos `.docx` en `docs/`.

**Testing**: N/A — Principio VII prohíbe explícitamente correr la suite de pruebas en esta sesión; no se
agregan tests automatizados para este script (es una herramienta de documentación, no lógica de
dominio). La verificación es manual/funcional vía `quickstart.md` (abrir cada `.docx` y validar
estructura/conteo de palabras).

**Target Platform**: Ejecución local por línea de comandos (`python docs/generate_docs.py`) en la
máquina de desarrollo (Windows, este repo); no depende de Docker ni de un servicio en ejecución.

**Project Type**: Script de documentación de un solo archivo (herramienta interna), fuera del árbol de
capas de la aplicación (`backend/domain`, `backend/infra`, `backend/api`, `frontend/src/`) — no es una
"Opción 1/2/3" de app web, es un generador de artefactos estáticos.

**Performance Goals**: N/A — ejecución manual bajo demanda, no es una ruta de runtime con SLA de
performance.

**Constraints**:
- Solo puede escribir dentro de `docs/` (los 3 `.docx` + `docs/requirements-docs.txt` opcional). Prohibido
  modificar `backend/`, `frontend/`, migraciones o cualquier archivo de lógica de negocio (FR-010).
- Prohibido invocar la suite de pruebas unitaria en esta sesión (FR-011).
- No debe exponer secretos reales (valores de `.env`) en el contenido generado — solo nombres de
  variables y su propósito (FR-004).
- Regeneración idempotente: cada corrida reemplaza el documento completo, sin ir acumulando contenido
  duplicado (Edge Case de spec.md).
- Debe fallar con mensaje claro (no traceback crudo ni archivo corrupto) si el `.docx` de destino está
  bloqueado por otro proceso (ej. abierto en Word) — ver `research.md` Decisión 4.

**Scale/Scope**: 3 documentos `.docx`, generados por una sola invocación de script; ~10-20 secciones en
total repartidas entre los tres documentos.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica a esta feature | Evaluación |
|-----------|------------------------|------------|
| I. API-First y Dominio Primero | No | No se toca el dominio ni se crean endpoints; es un script de documentación fuera de la API. |
| II. Clean Architecture 3 capas | No | El script no vive en `backend/domain`, `backend/infra`, `backend/api` ni `frontend/src`; es una herramienta de `docs/`, no una capa de la app. |
| III. Tipado estricto | Parcial | Se usan type hints en las funciones públicas del script por buena práctica, aunque el gate NON-NEGOTIABLE está definido para el dominio/frontend de la app, no para scripts de documentación. |
| IV. Seguridad en profundidad | Sí | El script NO debe volcar valores reales de `.env`/secretos al `.docx`; solo nombres de variables y su propósito (FR-004, ya reflejado en Technical Context → Constraints). |
| V. Gobernanza de librerías - Zero Dependencias No Aprobadas | Sí | `python-docx` NO se agrega a `backend/requirements.txt` ni a `frontend/package.json` (no es dependencia de la app); se documenta como herramienta de `docs/` vía `docs/requirements-docs.txt`, evitando el gate de aprobación de dependencias de la app. |
| VI. AI-Native | No | No aplica a un generador de documentos estáticos. |
| VII. Alcance de Sesión, Testing Ultra-Limitado y Eficiencia de Tokens | Sí | Escritura confinada a `docs/`; prohibido correr la suite de pruebas (FR-011); sin refactors fuera de alcance. |

**Resultado**: PASS. No hay violaciones que requieran justificación — no se llena Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/040-documentacion-oficial-docx/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command) — modelo de contenido, no de datos persistentes
├── quickstart.md        # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No se genera `contracts/`: este script no expone una interfaz externa (API, CLI con múltiples comandos,
librería reutilizable) — es una herramienta interna de un solo comando sin contrato de consumo por
terceros. Ver `research.md` Decisión 3.

### Source Code (repository root)

```text
docs/                              # Único árbol tocado por esta feature
├── generate_docs.py               # NUEVO — script generador de los 3 documentos (python-docx)
├── requirements-docs.txt          # NUEVO — pin de python-docx para esta herramienta (no toca backend/requirements.txt)
├── Manual_de_Usuario.docx         # REGENERADO por el script (reemplazo completo)
├── Codigo_Fuente_y_Documentacion.docx  # NUEVO — generado por el script
├── Descripcion_del_Software.docx  # NUEVO — generado por el script
└── Manual_de_Usuario.md           # Sin cambios — sigue existiendo como borrador/fuente en paralelo (spec.md § Assumptions)

# Fuera de alcance de escritura (solo lectura, para construir el contenido):
backend/                           # domain/, infra/, api/ — leídos para Arquitectura y Código Fuente representativo
frontend/src/                      # components/, services/, store/, types/, pages/ — leídos igual
docker-compose.yml, .env.example*  # leídos para la Guía de Instalación y Despliegue
specs/                             # leído como fuente de verdad de features/módulos ya implementados
```

**Structure Decision**: Herramienta de documentación de un solo script (`docs/generate_docs.py`),
aislada dentro de `docs/`, que lee (sin modificar) el resto del repositorio como fuente de contenido.
No sigue la estructura Backend/Frontend de Clean Architecture del Principio II porque no es parte de la
aplicación en ejecución — es tooling de documentación, análogo en naturaleza a los scripts ya existentes
en `backend/scripts/seed_*.py` (también fuera del árbol de capas de dominio) pero ubicado en `docs/`
por ser exclusivamente generador de artefactos de documentación, no de datos de aplicación.

## Complexity Tracking

*No aplica — Constitution Check no reportó violaciones.*
