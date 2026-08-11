# Research: Generación y Actualización de Documentación Oficial (3 Documentos .docx)

## Decisión 1 — Librería de generación: `python-docx`

**Decision**: Usar `python-docx` (Python) en vez de `docx` (Node.js).

**Rationale**: El pedido del usuario deja ambas opciones abiertas pero pide explícitamente que sea
"un script... que genere los documentos de forma automatizada" para evitar corrupción del `.docx`.
`python-docx` ya está instalado en el entorno de esta sesión (v1.2.0, verificado con
`pip show python-docx`), el proyecto backend ya es Python, y el equipo ya tiene scripts standalone en
`backend/scripts/*.py` con el mismo patrón de "script idempotente, sin tocar la app en runtime"
(ej. `seed_clients_aris_vaxthera.py`, `seed_dev_users.py`). Usar Node.js (`docx`) exigiría instalar una
dependencia nueva en un entorno donde Node ya se usa solo para el frontend (`pnpm`), mezclando gobernanza
de paquetes sin necesidad.

**Alternatives considered**:
- `docx` (Node.js): descartado por no tener antecedente instalado en el entorno y por no alinearse con
  el patrón de scripts standalone ya existente en `backend/scripts/`.
- Editar el `.docx` existente in-place con `python-docx.Document(path_existente)` y solo hacer
  find-and-replace de texto: descartado — `python-docx` no soporta bien reflow de texto largo dentro de
  runs existentes sin romper el formato original, y el pedido es "actualizar o regenerarlo" con
  secciones nuevas completas, no un parche puntual.

## Decisión 2 — Estrategia de regeneración: reemplazo completo, no edición incremental

**Decision**: El script construye cada documento desde cero con `docx.Document()` (plantilla en blanco)
y lo guarda sobre la ruta final (`docs/Manual_de_Usuario.docx`, etc.), reemplazando cualquier versión
previa en el mismo path.

**Rationale**: Garantiza idempotencia (edge case de `spec.md`: "el script se ejecuta más de una vez en
la misma sesión" no debe duplicar contenido) y evita el riesgo de corrupción de abrir-y-mutar un binario
`.docx` existente con estructura desconocida (el `Manual_de_Usuario.docx` actual en `docs/` no fue
generado por este script). Ya existe precedente de este patrón de backup manual en el propio repositorio
(`docs/Manual_de_Usuario.backup-20260721.docx`), confirmando que reemplazos completos ya son la práctica
aceptada para este archivo.

**Alternatives considered**: Cargar el `.docx` existente y hacer *append*/reemplazo de secciones por
nombre de heading — descartado por complejidad y fragilidad frente al beneficio marginal (el documento
ya tiene una fuente Markdown paralela, `docs/Manual_de_Usuario.md`, que sirve de borrador editable).

## Decisión 3 — Sin `contracts/`

**Decision**: No se genera el directorio `contracts/` de la Fase 1.

**Rationale**: `contracts/` documenta interfaces que el proyecto expone a otros sistemas o usuarios
(endpoints REST, esquemas CLI, etc.). Este script es una herramienta interna de un solo comando
(`python docs/generate_docs.py`, sin argumentos ni flags de comportamiento variable) que no es consumida
por ningún otro sistema ni expone una interfaz pública — es análogo a los scripts `seed_*.py` ya
existentes en el repo, que tampoco tienen contrato documentado.

**Alternatives considered**: Documentar un "contrato" mínimo del CLI (nombre de script, exit codes) —
descartado por no aportar valor: no hay consumidores externos del script más allá de quien lo ejecuta
manualmente en esta sesión.

## Decisión 4 — Manejo de archivo de destino bloqueado (ej. abierto en Word)

**Decision**: El script intenta `document.save(path)` dentro de un `try/except PermissionError`. Si
falla, imprime un mensaje accionable ("cierra `<archivo>` en Word e intenta de nuevo") y termina con
código de salida distinto de cero, sin dejar un archivo parcialmente escrito.

**Rationale**: En Windows, cuando Word tiene un `.docx` abierto crea un lock file `~$<nombre>.docx` en el
mismo directorio con permisos de escritura exclusivos sobre el original; un intento de
`open(path, "wb")` (lo que hace `python-docx` internamente) lanza `PermissionError` en ese caso. Se
confirmó en este repo la existencia de `docs/~$nual_de_Usuario.docx` (archivo de lock, ~162 bytes,
fecha 2026-08-03) — evidencia de que este escenario ya ocurrió antes con este mismo archivo. Capturar la
excepción real evita la doble complejidad/carrera de intentar detectar el lock file de antemano (el
archivo `~$` puede quedar huérfano tras un cierre anómalo de Word sin que el documento esté realmente
bloqueado).

**Alternatives considered**: Verificar antes de escribir si existe `~$<nombre>.docx` en el directorio y
abortar si está presente — descartado porque ese archivo puede ser un residuo obsoleto (como el ya
encontrado en el repo) y bloquearía la generación sin necesidad real.

## Decisión 5 — `python-docx` como herramienta de `docs/`, no como dependencia de la app

**Decision**: Se agrega `docs/requirements-docs.txt` (nuevo, con `python-docx==1.2.0`) exclusivamente
para este script. No se modifica `backend/requirements.txt` ni `frontend/package.json`.

**Rationale**: El Principio V de la constitución ("Zero Dependencias No Aprobadas") gobierna las
dependencias de la aplicación (`package.json`/`requirements.txt` del backend/frontend en ejecución). Un
script de generación de documentación que corre fuera del runtime de la app y vive enteramente en
`docs/` no es parte de ese stack gobernado; documentarlo con su propio archivo de pin dentro de `docs/`
da reproducibilidad sin activar el gate de aprobación de dependencias de la aplicación (que ya está
fuera de alcance de esta sesión de documentación).

**Alternatives considered**: No fijar versión en ningún archivo (asumir que `python-docx` ya está
instalado) — descartado porque reduce la reproducibilidad del script para quien lo ejecute en el futuro
sin ese paquete ya presente.

## Decisión 6 — Fuentes de contenido por sección (mapeo documento → repositorio)

**Decision**:

| Sección del documento | Fuente en el repositorio |
|---|---|
| Manual → Arquitectura del Sistema | `.specify/memory/constitution.md` (Stack Tecnológico), estructura real de `backend/` y `frontend/src/`, `docker-compose.yml` (servicios: app, api, db, redis) |
| Manual → Instalación y Despliegue | `docker-compose.yml`, `.env.example` / `.env.prod.example` / `.env.test.example` (solo nombres de variable), `backend/requirements.txt`, `frontend/package.json` (comandos `pnpm install`), migraciones Alembic (`backend/`), scripts `seed_*.py` |
| Manual → Operación por módulo | `frontend/src/pages/*Page.tsx` (una página por módulo: Kanban, Tickets, Mis Tareas, Registro de Tiempos, RRHH/Calendario, Reportes) y `docs/Manual_de_Usuario.md` existente como borrador de referencia |
| Código Fuente → Estructura general | Árbol real de `backend/{domain,infra,api}` y `frontend/src/{components,services,store,types,pages}` (Principio II de la constitución) |
| Código Fuente → Catálogo de componentes | Modelos (`backend/infra`), rutas (`backend/api/routes/*.py`), migraciones (`backend/` Alembic), middlewares de auth (JWT), componentes principales de `frontend/src/components/` |
| Código Fuente → Código representativo | Backend: un endpoint de `backend/api/routes/tickets.py`; Lógica de SLA: `backend/domain/services/sla_service.py` / `backend/domain/entities/sla_rule.py`; Frontend: un servicio de `frontend/src/services/`; Helpers: una utilidad de fecha/formato (`date-fns` wrapper) |
| Descripción Ejecutiva | `spec.md` de esta feature (ya redactado con nombre, propósito, características, valor agregado provistos por el usuario) + branding SYTIX ya vigente en `AuthLayout.tsx`/`DashboardPage.tsx` (spec 039) |

**Rationale**: Ancla cada sección a una fuente verificable en el repositorio actual, cumpliendo FR-013
("el contenido... DEBE reflejar el estado actual verificado del código") y evitando contenido genérico.

**Alternatives considered**: Redactar las secciones desde el conocimiento general del dominio sin anclar
a rutas de archivo concretas — descartado porque no sería verificable ni se mantendría sincronizado con
el código real.

## Unknowns resueltos

No quedaron `NEEDS CLARIFICATION` en el Technical Context del plan — todas las decisiones anteriores
resuelven las variables técnicas (lenguaje, dependencia, estrategia de escritura, manejo de errores,
alcance de contrato) usando el propio repositorio como fuente.
