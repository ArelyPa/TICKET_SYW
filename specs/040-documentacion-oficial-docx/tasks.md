---

description: "Task list template for feature implementation"
---

# Tasks: Generación y Actualización de Documentación Oficial (3 Documentos .docx)

**Input**: Design documents from `specs/040-documentacion-oficial-docx/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Tests**: No se solicitaron tests automatizados para esta feature (herramienta de documentación, fuera
del dominio de la app; Principio VII prohíbe además correr la suite de pruebas en esta sesión). La
verificación es la ejecución manual descrita en `quickstart.md` (Tarea T019).

**Organization**: Todas las tareas de implementación escriben en el mismo archivo,
`docs/generate_docs.py` (es un script de un solo módulo) — por eso casi ninguna tarea lleva `[P]`: aunque
las historias de usuario son independientemente verificables una vez implementadas, no son
paralelizables *entre sí* a nivel de edición de archivo (evita conflictos de merge en el mismo módulo).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Todo el código de esta feature vive en `docs/` (ver `plan.md` → Project Structure): un único script
`docs/generate_docs.py` y su pin de dependencia `docs/requirements-docs.txt`. Las funciones lo componen
en secciones nombradas por historia de usuario, pero comparten el mismo archivo.

---

## Phase 1: Setup

**Purpose**: Preparar el archivo de dependencia y el esqueleto del script

- [X] T001 [P] Crear `docs/requirements-docs.txt` con el pin `python-docx==1.2.0` (research.md Decisión 5)
- [X] T002 Crear el esqueleto de `docs/generate_docs.py`: imports (`docx`, `pathlib.Path`, `sys`, `dataclasses`), constante `REPO_ROOT = Path(__file__).resolve().parent.parent`, y bloque `if __name__ == "__main__": main()` con `main()` vacío por ahora

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Modelo de contenido y helpers compartidos por las 3 historias de usuario — **ninguna
historia puede implementarse antes de completar esta fase**

**⚠️ CRITICAL**: Bloquea Phase 3, 4 y 5

- [X] T003 Implementar en `docs/generate_docs.py` las dataclasses del modelo de contenido según `data-model.md`: `Section`, `CodeBlock`, `ComponentCatalogEntry`, `DocumentSpec`, `WordCountTarget` (campos y validación de "al menos un campo de contenido no vacío" de `Section`)
- [X] T004 Implementar `render_document(spec: DocumentSpec) -> docx.Document` en `docs/generate_docs.py`: recorre `spec.sections` y escribe heading (nivel 1/2), párrafos, listas con viñetas, tablas y bloques de código monoespaciado (`style='No Spacing'` + fuente `Consolas` por run) según los campos presentes en cada `Section`/`CodeBlock`
- [X] T005 Implementar `save_document_safely(document, output_path: Path) -> bool` en `docs/generate_docs.py`: intenta `document.save(output_path)` dentro de `try/except PermissionError`, imprime mensaje accionable ("cierra `<output_path.name>` en Word e intenta de nuevo") y retorna `False` sin abortar el proceso completo (research.md Decisión 4)
- [X] T006 Implementar helpers de lectura del repositorio en `docs/generate_docs.py`: `read_file_snippet(path: Path, start: int | None, end: int | None) -> str | None` (retorna `None` y loguea a consola si `path` no existe, en vez de lanzar excepción — ver Edge Case de `spec.md`) y `directory_tree(root: Path, max_depth: int) -> str` (árbol en texto plano)

**Checkpoint**: Modelo de contenido y helpers listos — las historias de usuario pueden implementarse en
secuencia (no en paralelo, mismo archivo)

---

## Phase 3: User Story 1 - Manual de Usuario actualizado (Priority: P1) 🎯 MVP

**Goal**: Regenerar `docs/Manual_de_Usuario.docx` completo con Arquitectura del Sistema, Guía de
Instalación y Despliegue, y Operación por los 6 módulos.

**Independent Test**: Ejecutar `python docs/generate_docs.py`, abrir `docs/Manual_de_Usuario.docx` en
Word sin advertencia de corrupción, y confirmar los 3 headings de nivel 1 pedidos con las 6 subsecciones
de módulo dentro de Operación (quickstart.md pasos 1-2).

### Implementation for User Story 1

- [X] T007 [US1] Implementar `build_architecture_section() -> Section` en `docs/generate_docs.py`: lee la tabla "Stack completo aprobado" de `.specify/memory/constitution.md` y los servicios definidos en `docker-compose.yml`, arma párrafos describiendo Frontend/Backend/Base de Datos/servicio de correo/motor de SLA/zonas horarias (FR-003)
- [X] T008 [US1] Implementar `build_installation_section() -> Section` en `docs/generate_docs.py`: lee nombres de variables (no valores) de `.env.example`/`.env.prod.example`/`.env.test.example`, comandos de `backend/requirements.txt`/`frontend/package.json` (`pnpm install`), comando de migraciones Alembic y los scripts `backend/scripts/seed_*.py` existentes, y el bloque `docker compose up` de despliegue, en orden ejecutable paso a paso (FR-004)
- [X] T009 [US1] Implementar `build_operation_section() -> Section` en `docs/generate_docs.py` con una subsección (nivel 2) por cada módulo — Kanban, Tickets, Tareas/Subtareas, Registro de Tiempos, RRHH/Calendarios, Reportes — usando `frontend/src/pages/*Page.tsx` para identificar la pantalla de cada módulo y `docs/Manual_de_Usuario.md` como borrador de referencia para los pasos de uso (FR-005)
- [X] T010 [US1] Implementar `build_manual_usuario() -> DocumentSpec` en `docs/generate_docs.py` combinando T007-T009 en las `sections` del `DocumentSpec` con `output_path=REPO_ROOT / "docs" / "Manual_de_Usuario.docx"`, y llamar `save_document_safely(render_document(build_manual_usuario()), spec.output_path)` desde `main()` (FR-002)

**Checkpoint**: `docs/Manual_de_Usuario.docx` se genera de forma independiente y es funcional por sí solo

---

## Phase 4: User Story 2 - Documentación técnica del código fuente (Priority: P2)

**Goal**: Generar `docs/Codigo_Fuente_y_Documentacion.docx` con árbol de directorios, catálogo de
componentes y código representativo de 4 capas.

**Independent Test**: Ejecutar `python docs/generate_docs.py`, abrir
`docs/Codigo_Fuente_y_Documentacion.docx` y confirmar árbol de directorios, tabla de catálogo y 4 bloques
de código (Backend, Frontend, Lógica de SLA, Helpers) con nota explicativa cada uno (quickstart.md paso
3).

### Implementation for User Story 2

- [X] T011 [US2] Implementar `build_estructura_section() -> Section` en `docs/generate_docs.py` usando `directory_tree()` (T006) sobre `backend/{domain,infra,api}` y `frontend/src/{components,services,store,types,pages}`, con una frase de propósito por carpeta (FR-006)
- [X] T012 [US2] Implementar `build_catalogo_componentes() -> Section` en `docs/generate_docs.py`: recolecta filas `ComponentCatalogEntry` (Modelo, Ruta/Controlador, Migración, Middleware, Componente de interfaz) inspeccionando `backend/infra`, `backend/api/routes/*.py`, migraciones Alembic y `frontend/src/components/`, y las renderiza como tabla nativa de Word vía `render_document` (FR-007)
- [X] T013 [US2] Implementar `build_codigo_representativo() -> Section` en `docs/generate_docs.py` con 4 `CodeBlock` (Backend: `backend/api/routes/tickets.py`; Lógica de SLA: `backend/domain/services/sla_service.py`; Frontend: un servicio de `frontend/src/services/`; Helpers: un helper de fecha/formato), usando `read_file_snippet()` (T006) y omitiendo con nota en consola cualquier `source_file` que no exista (FR-008, data-model.md validación de `CodeBlock`)
- [X] T014 [US2] Implementar `build_codigo_fuente() -> DocumentSpec` en `docs/generate_docs.py` combinando T011-T013 con `output_path=REPO_ROOT / "docs" / "Codigo_Fuente_y_Documentacion.docx"`, y añadir su generación a `main()` junto a la de T010

**Checkpoint**: `docs/Codigo_Fuente_y_Documentacion.docx` se genera de forma independiente, sin afectar el
resultado de User Story 1

---

## Phase 5: User Story 3 - Descripción ejecutiva del software (Priority: P3)

**Goal**: Generar `docs/Descripcion_del_Software.docx`, ~500 palabras, con nombre/significado, propósito
de negocio, características principales y valor agregado de SYTIX.

**Independent Test**: Ejecutar `python docs/generate_docs.py`, abrir
`docs/Descripcion_del_Software.docx`, confirmar los 4 puntos pedidos y un conteo de palabras entre 400 y
600 (quickstart.md paso 4).

### Implementation for User Story 3

- [X] T015 [US3] Implementar `build_descripcion_ejecutiva() -> DocumentSpec` en `docs/generate_docs.py` con las 4 secciones pedidas (Nombre "SYTIX — Systems | Innovation | Xcellence", Propósito de Negocio, Características Principales, Valor Agregado), en lenguaje no técnico, apuntando a ~500 palabras totales (FR-009)
- [X] T016 [US3] Implementar `count_words(spec: DocumentSpec) -> WordCountTarget` en `docs/generate_docs.py` que suma las palabras de todos los `paragraphs`/`bullet_items` de `spec.sections` y arma un `WordCountTarget(min_words=400, max_words=600, actual_words=...)`
- [X] T017 [US3] En `main()` de `docs/generate_docs.py`, guardar `build_descripcion_ejecutiva()` con `save_document_safely()` hacia `docs/Descripcion_del_Software.docx`, luego llamar `count_words()` sobre el mismo spec e imprimir `actual_words` en consola (advertencia, no error, si queda fuera de 400-600) (FR-009, SC-004)

**Checkpoint**: Los 3 documentos se generan de forma independiente entre sí; cada uno puede regenerarse
sin afectar a los otros dos

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Orquestación final y verificación end-to-end

- [X] T018 Implementar `main()` en `docs/generate_docs.py`: invoca secuencialmente `build_manual_usuario()` (T010), `build_codigo_fuente()` (T014) y `build_descripcion_ejecutiva()` (T017/T015), cada una envuelta para que un `PermissionError` de `save_document_safely()` en un documento no impida generar los otros dos, e imprime un resumen final de 3 líneas (una por documento: ruta y estado OK/omitido)
- [X] T019 Ejecutar la validación completa de `specs/040-documentacion-oficial-docx/quickstart.md` sobre `docs/generate_docs.py`: correr el script, verificar SC-001 a SC-004 abriendo los 3 `.docx`, confirmar SC-005 con `git status --porcelain` (solo cambios dentro de `docs/`), confirmar SC-006 (ninguna suite de pruebas ejecutada en la sesión), y re-ejecutar el script una segunda vez para confirmar idempotencia (sin contenido duplicado)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sin dependencias — puede iniciarse de inmediato
- **Foundational (Phase 2)**: Depende de Setup — bloquea las 3 historias de usuario
- **User Stories (Phase 3-5)**: Todas dependen de Foundational; **no son paralelizables entre sí** (mismo
  archivo `docs/generate_docs.py`) pero sí son independientemente verificables una vez implementadas —
  se recomienda el orden de prioridad P1 → P2 → P3
- **Polish (Phase 6)**: Depende de que las 3 historias estén implementadas (T018 las invoca a todas)

### User Story Dependencies

- **User Story 1 (P1)**: Puede iniciarse tras Foundational — sin dependencia de otras historias
- **User Story 2 (P2)**: Puede iniciarse tras Foundational — sin dependencia de US1 más allá de compartir helpers de Phase 2
- **User Story 3 (P3)**: Puede iniciarse tras Foundational — sin dependencia de US1/US2

### Within Each User Story

- T007-T009 (US1), T011-T013 (US2) y T015-T016 (US3) construyen las `Section`/`DocumentSpec` de cada
  historia antes de la tarea de "wiring" final (T010, T014, T017 respectivamente) que llama a
  `save_document_safely()`
- Cada historia queda completa y verificable antes de pasar a la siguiente por prioridad

### Parallel Opportunities

- T001 (`docs/requirements-docs.txt`) es la única tarea verdaderamente paralelizable frente a T002
  (archivo distinto)
- El resto de las tareas edita el mismo archivo (`docs/generate_docs.py`) — se recomienda ejecutarlas en
  secuencia dentro de una misma sesión de edición para evitar conflictos, aunque las historias de usuario
  en sí (Phase 3, 4, 5) son conceptualmente independientes y podrían repartirse entre desarrolladores que
  coordinen los merges de un mismo archivo

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: Setup (T001-T002)
2. Completar Phase 2: Foundational (T003-T006) — crítico, bloquea todo lo demás
3. Completar Phase 3: User Story 1 (T007-T010)
4. **Detenerse y validar**: correr `python docs/generate_docs.py` y confirmar `docs/Manual_de_Usuario.docx` cumple SC-001/SC-002 de forma independiente
5. Continuar con US2/US3 solo si el Manual de Usuario ya es satisfactorio

### Incremental Delivery

1. Setup + Foundational → base lista
2. Agregar User Story 1 → validar independientemente → Manual de Usuario entregable
3. Agregar User Story 2 → validar independientemente → Documentación de Código Fuente entregable
4. Agregar User Story 3 → validar independientemente → Descripción Ejecutiva entregable
5. Phase 6 (T018-T019) cierra la orquestación conjunta y la validación end-to-end de los 3 documentos

---

## Notes

- `[P]` se usa solo en T001 — el resto del trabajo comparte `docs/generate_docs.py` y se hace en
  secuencia.
- `[Story]` etiqueta cada tarea de Phase 3-5 con `US1`/`US2`/`US3` para trazabilidad contra `spec.md`.
- Ninguna tarea de esta lista modifica archivos fuera de `docs/` (Principio VII, FR-010) ni ejecuta la
  suite de pruebas (FR-011) — T019 lo verifica explícitamente al final.
- Confirmar tras cada tarea de escritura (T007-T017) que `docs/generate_docs.py` sigue siendo válido
  Python (ej. `python -m py_compile docs/generate_docs.py`) antes de pasar a la siguiente.
