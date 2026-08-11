# Feature Specification: Generación y Actualización de Documentación Oficial (3 Documentos .docx)

**Feature Branch**: `040-documentacion-oficial-docx`

**Created**: 2026-08-05

**Status**: Draft

**Input**: User description: "Generación y Actualización de Documentación Oficial (3 Documentos .docx): (1) actualizar/regenerar `docs/Manual_de_Usuario.docx` con Arquitectura del Sistema, Guía de Instalación y Despliegue Paso a Paso, y Manual de Usabilidad y Operación por módulo; (2) crear `docs/Codigo_Fuente_y_Documentacion.docx` con estructura del proyecto, catálogo de componentes/módulos y código fuente representativo por capa; (3) crear `docs/Descripcion_del_Software.docx`, documento ejecutivo de ~500 palabras sobre SYTIX. Los tres documentos deben generarse mediante un script automatizado (python-docx o docx de Node.js) para evitar corrupción del archivo. Alcance restringido a lectura del código para documentarlo y ejecución del script generador en `docs/`; prohibido modificar lógica de negocio y prohibido correr la suite de pruebas."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manual de Usuario actualizado (Priority: P1)

Como stakeholder de negocio, consultor UAT o nuevo integrante del equipo, quiero abrir `docs/Manual_de_Usuario.docx` y encontrar en un solo documento la arquitectura del sistema, los pasos exactos para instalar/desplegar el ambiente, y una guía de uso módulo por módulo (Kanban, Tickets, Tareas/Subtareas, Registro de Tiempos, RRHH/Calendarios, Reportes), reflejando el estado actual de la aplicación (incluye el rebranding a SYTIX y las features más recientes ya implementadas).

**Why this priority**: Es el documento de mayor consumo — lo usan tanto usuarios finales/UAT como cualquiera que necesite levantar el ambiente desde cero. Sin esto actualizado, el resto de la documentación pierde valor práctico inmediato.

**Independent Test**: Abrir el `.docx` generado en Microsoft Word (o Word Online) sin errores de "contenido no legible", y verificar que contiene las tres secciones clave (Arquitectura, Instalación/Despliegue, Operación por módulo) con contenido específico del proyecto (no placeholders).

**Acceptance Scenarios**:

1. **Given** el repositorio actual del proyecto (backend Flask + frontend React/Vite + PostgreSQL + Docker), **When** se ejecuta el script generador, **Then** `docs/Manual_de_Usuario.docx` se crea/actualiza con una sección de Arquitectura que nombra explícitamente Frontend, Backend, Base de Datos, servicio de correo, motor de SLA y manejo de zonas horarias.
2. **Given** el `docker-compose.yml` y los archivos `.env.example` existentes en el repositorio, **When** se genera el manual, **Then** la sección de Instalación y Despliegue incluye requisitos previos, variables de entorno, comandos de instalación de dependencias, ejecución de migraciones/seeders y arranque vía Docker Compose, en orden ejecutable paso a paso.
3. **Given** los módulos ya implementados de la aplicación (Kanban, Tickets, Tareas/Subtareas, Registro de Tiempos, RRHH/Calendarios, Reportes), **When** se genera el manual, **Then** cada módulo tiene su propia guía de uso paso a paso dentro del documento.
4. **Given** que ya existe un `docs/Manual_de_Usuario.docx` previo, **When** se re-ejecuta el script, **Then** el archivo resultante reemplaza limpiamente al anterior sin dejar el archivo corrupto o parcialmente escrito.

---

### User Story 2 - Documentación técnica del código fuente (Priority: P2)

Como desarrollador nuevo en el proyecto o auditor técnico, quiero un documento (`docs/Codigo_Fuente_y_Documentacion.docx`) que me muestre la estructura de carpetas, el catálogo de componentes/módulos principales (modelos, controladores, migraciones, middlewares, componentes de interfaz) y fragmentos de código representativos de cada capa, para entender rápidamente cómo está organizado el software sin tener que leer todo el repositorio.

**Why this priority**: Acelera el onboarding técnico y sirve de referencia de arquitectura, pero depende de que el Manual de Usuario (US1) ya exprese el panorama general primero.

**Independent Test**: Abrir el `.docx` generado y confirmar que incluye un árbol de directorios navegable, una lista de componentes/módulos con su propósito, y al menos un bloque de código por capa (Backend, Frontend, Lógica de SLA, Helpers) con formato de código monoespaciado y una nota explicativa breve.

**Acceptance Scenarios**:

1. **Given** la estructura real de carpetas del repositorio (`backend/domain`, `backend/infra`, `backend/api`, `frontend/src/{components,services,store,types,pages}`), **When** se genera el documento, **Then** incluye un árbol de directorios con el propósito de cada carpeta principal.
2. **Given** los archivos de modelos, migraciones (Alembic), middlewares y componentes React principales existentes en el repositorio, **When** se genera el documento, **Then** el catálogo de componentes describe cada uno con una frase de propósito.
3. **Given** el motor de SLA (`backend/domain`), un endpoint representativo de la API, un servicio del frontend y un helper, **When** se genera el documento, **Then** se incluyen los fragmentos de código correspondientes en bloques formateados con comentario explicativo de qué hace cada fragmento.

---

### User Story 3 - Descripción ejecutiva del software (Priority: P3)

Como responsable comercial o directivo que necesita presentar SYTIX a un tercero (cliente potencial, socio, auditor), quiero un documento corto y ejecutivo (`docs/Descripcion_del_Software.docx`, ~500 palabras) que resuma qué es la plataforma, su propósito de negocio, sus características principales y su valor agregado, sin detalle técnico.

**Why this priority**: Es el documento más liviano de producir y el de menor dependencia técnica, pero de menor uso operativo diario frente a US1/US2 — por eso queda en tercer lugar aunque sea rápido de completar.

**Independent Test**: Abrir el `.docx` generado, confirmar una extensión aproximada de 500 palabras (rango aceptable ±20%) y que cubre los 4 puntos pedidos: nombre/significado de SYTIX, propósito de negocio, características principales y valor agregado, en lenguaje no técnico.

**Acceptance Scenarios**:

1. **Given** el nombre "SYTIX" y su eslogan "Systems | Innovation | Xcellence" ya usados en el producto (login/branding), **When** se genera el documento, **Then** el documento abre presentando ese nombre y significado.
2. **Given** las capacidades ya implementadas del sistema (gestión de clientes/proyectos multi-zona horaria, asignación en cascada, calendario de equipo, RRHH/ausencias, reportes dinámicos, motor de SLA en horas hábiles), **When** se genera el documento, **Then** la sección de características principales las menciona sin lenguaje técnico de implementación.
3. **Given** el documento generado, **When** se cuenta su extensión, **Then** el conteo de palabras del cuerpo del documento está entre 400 y 600 palabras.

---

### Edge Cases

- ¿Qué ocurre si `docs/Manual_de_Usuario.docx` está abierto/bloqueado por otro proceso (ej. Word abierto) al momento de ejecutar el script? El script debe fallar con un mensaje claro en consola en vez de generar un archivo corrupto o silenciosamente no escribir nada.
- ¿Qué ocurre si el script se ejecuta más de una vez en la misma sesión? Cada ejecución debe regenerar el documento completo de forma idempotente (mismo resultado final), no ir acumulando contenido duplicado.
- ¿Qué ocurre si una sección fuente (por ejemplo, un archivo `.env.example` o un módulo esperado) no existe en el repositorio al momento de generar el documento? El script debe omitir esa fuente puntual con una nota o valor razonable en vez de fallar por completo la generación de los tres documentos.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE proveer un script automatizado (Python con `python-docx`, o Node.js con `docx`) que genere/actualice los tres documentos `.docx` de forma programática, sin edición manual del binario `.docx`.
- **FR-002**: El script DEBE regenerar `docs/Manual_de_Usuario.docx` completo, reemplazando el contenido existente, con al menos las secciones: Arquitectura del Sistema, Guía de Instalación y Despliegue Paso a Paso, y Manual de Usabilidad y Operación por módulo.
- **FR-003**: La sección de Arquitectura del Sistema DEBE describir Frontend, Backend, Base de Datos, servicio de correo, motor de SLA y manejo de zonas horarias, en términos consistentes con el estado real del código del repositorio.
- **FR-004**: La sección de Instalación y Despliegue DEBE listar requisitos previos, variables de entorno relevantes (sin exponer valores secretos reales), comandos de instalación de dependencias, ejecución de migraciones y seeders, y el procedimiento de despliegue vía Docker/Docker Compose, en orden ejecutable.
- **FR-005**: La sección de Manual de Usabilidad y Operación DEBE cubrir, como mínimo, los módulos Kanban, Tickets, Tareas/Subtareas, Registro de Tiempos, RRHH/Calendarios y Reportes, con pasos de uso para cada uno.
- **FR-006**: El sistema DEBE generar `docs/Codigo_Fuente_y_Documentacion.docx` con un árbol de la estructura general de directorios del proyecto y el propósito de cada carpeta principal.
- **FR-007**: `docs/Codigo_Fuente_y_Documentacion.docx` DEBE incluir un catálogo de componentes y módulos (modelos, controladores/rutas, migraciones, middlewares, componentes de interfaz principales) con una descripción breve de cada uno.
- **FR-008**: `docs/Codigo_Fuente_y_Documentacion.docx` DEBE incluir fragmentos de código representativos de cada capa (Backend, Frontend, Lógica de SLA, Helpers), en bloques con formato de código monoespaciado y una nota explicativa de su funcionamiento.
- **FR-009**: El sistema DEBE generar `docs/Descripcion_del_Software.docx`, un documento ejecutivo de aproximadamente 500 palabras (rango aceptable 400-600) que cubra: nombre y significado de SYTIX, propósito de negocio, características principales y valor agregado, en lenguaje no técnico.
- **FR-010**: El script generador NO DEBE modificar ningún archivo de lógica de negocio de la aplicación (backend/frontend fuera de `docs/`); su alcance de escritura se limita a los tres archivos `.docx` (y el propio script) dentro de `docs/`.
- **FR-011**: La ejecución del script y de esta sesión de documentación NO DEBE invocar la suite de pruebas unitarias del proyecto.
- **FR-012**: Cada documento generado DEBE poder abrirse en Microsoft Word (u otro lector `.docx` estándar) sin advertencias de contenido dañado o ilegible.
- **FR-013**: El contenido de los tres documentos DEBE reflejar el estado actual verificado del código del repositorio (arquitectura, módulos, estructura de carpetas) en el momento de la generación, en vez de contenido genérico o desactualizado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Los tres archivos `docs/Manual_de_Usuario.docx`, `docs/Codigo_Fuente_y_Documentacion.docx` y `docs/Descripcion_del_Software.docx` existen tras la ejecución del script y se abren sin errores de corrupción en un lector `.docx` estándar.
- **SC-002**: El Manual de Usuario contiene, de forma verificable por inspección, las tres secciones clave solicitadas (Arquitectura, Instalación/Despliegue, Operación por módulo) cubriendo los 6 módulos listados.
- **SC-003**: La Documentación del Código Fuente contiene el árbol de directorios, el catálogo de componentes y al menos un fragmento de código por cada una de las 4 capas solicitadas (Backend, Frontend, Lógica de SLA, Helpers).
- **SC-004**: La Descripción Ejecutiva tiene una extensión entre 400 y 600 palabras y cubre los 4 puntos solicitados (nombre/significado, propósito de negocio, características, valor agregado).
- **SC-005**: Ningún archivo fuera de `docs/` resulta modificado como consecuencia de esta sesión de documentación (verificable con `git status` / `git diff`).
- **SC-006**: La suite de pruebas unitarias del proyecto no se ejecuta en ningún momento de esta sesión.

## Assumptions

- El script generador se guarda dentro de `docs/` (por ejemplo `docs/generate_docs.py`) para quedar disponible como herramienta reutilizable en futuras actualizaciones de estos mismos documentos.
- Se usa `python-docx` como librería preferida (Python ya es el lenguaje del backend del proyecto), salvo que no esté disponible en el entorno, en cuyo caso se evalúa la alternativa Node.js (`docx`) sin cambiar el alcance ni las secciones pedidas.
- Los tres documentos se redactan en español, consistente con el resto de la documentación del repositorio (`specs/`, `UAT/`, `docs/Manual_de_Usuario.md` existente).
- El contenido de cada documento se basa en el estado del código y specs ya mergeados/commiteados del repositorio al momento de generación; no se espera ni se documenta trabajo pendiente de commit como si ya estuviera entregado.
- No se generan diagramas embebidos obligatorios (imágenes); se permite texto estructurado, árboles en texto y tablas nativas de Word para representar arquitectura y estructura de carpetas.
- Los tres documentos son un artefacto de documentación, no una migración de datos ni un cambio de comportamiento de la aplicación — por lo tanto no requieren pruebas automatizadas nuevas ni migraciones de base de datos.
- El archivo `docs/Manual_de_Usuario.md` (Markdown, spec 025) puede seguir existiendo en paralelo como fuente/borrador; esta feature no lo elimina, solo genera/actualiza la versión oficial `.docx`.
