"""Genera/actualiza los 3 documentos oficiales .docx de docs/ (spec 040).

Uso:
    python docs/generate_docs.py

Lee el repositorio (solo lectura) para construir el contenido de cada documento; solo escribe
dentro de docs/ (los 3 .docx). No modifica lógica de negocio ni ejecuta la suite de pruebas
(Principio VII de .specify/memory/constitution.md).
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.shared import Pt

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"


# ---------------------------------------------------------------------------
# Modelo de contenido (specs/040-documentacion-oficial-docx/data-model.md)
# ---------------------------------------------------------------------------

@dataclass
class CodeBlock:
    layer: str
    source_file: str
    snippet: str
    explanation: str


@dataclass
class Section:
    heading: str
    level: int = 1
    paragraphs: list[str] = field(default_factory=list)
    bullet_items: list[str] | None = None
    table: list[list[str]] | None = None  # primera fila = encabezados
    code_blocks: list[CodeBlock] | None = None
    source_refs: list[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        return bool(self.paragraphs or self.bullet_items or self.table or self.code_blocks)


@dataclass
class DocumentSpec:
    output_path: Path
    title: str
    sections: list[Section] = field(default_factory=list)


@dataclass
class WordCountTarget:
    min_words: int
    max_words: int
    actual_words: int = 0


# ---------------------------------------------------------------------------
# Helpers de lectura del repositorio (T006)
# ---------------------------------------------------------------------------

def read_file_snippet(path: Path, start: int | None = None, end: int | None = None) -> str | None:
    """Líneas [start, end] (1-indexado, inclusive) de `path`. `None` si el archivo no existe."""
    if not path.exists():
        print(f"  [aviso] fuente no encontrada, se omite: {path}")
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    start = 1 if start is None else start
    end = len(lines) if end is None else end
    return "\n".join(lines[start - 1:end])


def directory_tree(root: Path, entries: dict[str, str]) -> list[str]:
    """Líneas de árbol para las subcarpetas listadas en `entries` (ruta relativa a `root` ->
    propósito), sin recorrer archivos individuales."""
    lines = [f"{root.relative_to(REPO_ROOT)}/"]
    for rel, purpose in entries.items():
        lines.append(f"  {rel}/  —  {purpose}")
    return lines


def extract_env_var_names(compose_text: str) -> list[str]:
    """Nombres de variable referenciados como ${VAR...} en docker-compose.yml (sin valores)."""
    return sorted(set(re.findall(r"\$\{([A-Z0-9_]+)(?::[-?][^}]*)?\}", compose_text)))


def module_docstring_summary(path: Path) -> str:
    """Primera línea del docstring de módulo de un archivo Python, o cadena vacía si no hay."""
    text = path.read_text(encoding="utf-8")
    match = re.search(r'"""(.*?)"""', text, re.DOTALL)
    if not match:
        return ""
    lines = [line.strip() for line in match.group(1).strip().splitlines() if line.strip()]
    return lines[0] if lines else ""


# ---------------------------------------------------------------------------
# Render y guardado (T004, T005)
# ---------------------------------------------------------------------------

def render_document(spec: DocumentSpec) -> Document:
    document = Document()
    document.add_heading(spec.title, level=0)
    for section in spec.sections:
        if not section.is_valid():
            continue
        document.add_heading(section.heading, level=section.level)
        for paragraph in section.paragraphs:
            document.add_paragraph(paragraph)
        if section.bullet_items:
            for item in section.bullet_items:
                document.add_paragraph(item, style="List Bullet")
        if section.table:
            rows = section.table
            table = document.add_table(rows=1, cols=len(rows[0]))
            table.style = "Light Grid Accent 1"
            for cell, text in zip(table.rows[0].cells, rows[0]):
                cell.text = text
            for row_values in rows[1:]:
                row_cells = table.add_row().cells
                for cell, text in zip(row_cells, row_values):
                    cell.text = text
        if section.code_blocks:
            for block in section.code_blocks:
                label_run = document.add_paragraph().add_run(f"{block.layer} — {block.source_file}")
                label_run.bold = True
                code_run = document.add_paragraph(style="No Spacing").add_run(block.snippet)
                code_run.font.name = "Consolas"
                code_run.font.size = Pt(9)
                explanation_run = document.add_paragraph().add_run(block.explanation)
                explanation_run.italic = True
        if section.source_refs:
            note_run = document.add_paragraph().add_run("Fuente: " + ", ".join(section.source_refs))
            note_run.italic = True
    return document


def save_document_safely(document: Document, output_path: Path) -> bool:
    try:
        document.save(output_path)
    except PermissionError:
        print(
            f"  [ERROR] No se pudo escribir {output_path.name}: el archivo parece estar abierto "
            f"(ej. en Word). Ciérralo y vuelve a ejecutar el script."
        )
        return False
    print(f"  OK: {output_path.relative_to(REPO_ROOT)}")
    return True


def count_words(spec: DocumentSpec) -> WordCountTarget:
    chunks: list[str] = []
    for section in spec.sections:
        chunks.extend(section.paragraphs)
        if section.bullet_items:
            chunks.extend(section.bullet_items)
    total = sum(len(chunk.split()) for chunk in chunks)
    return WordCountTarget(min_words=400, max_words=600, actual_words=total)


# ---------------------------------------------------------------------------
# Documento 1: Manual de Usuario (US1, T007-T010)
# ---------------------------------------------------------------------------

def build_architecture_section() -> Section:
    compose_path = REPO_ROOT / "docker-compose.yml"
    compose_text = compose_path.read_text(encoding="utf-8") if compose_path.exists() else ""
    services = re.findall(r"^  (\w+):\s*$", compose_text, re.MULTILINE)
    paragraphs = [
        "SYTIX sigue una arquitectura de 3 capas con dependencia unidireccional (Principio II de "
        "la constitución del proyecto): Capa 1 - Dominio (backend/domain, sin dependencias "
        "externas: FSM de tickets con python-transitions, entidades, motor de SLA), Capa 2 - "
        "Infraestructura (backend/infra, repositorios SQLAlchemy) y Capa 3 - Presentación "
        "(backend/api con Flask-RESTX/Swagger, y frontend/src con React 19 + TypeScript + Ant "
        "Design 5).",
        f"El stack se orquesta con Docker Compose ({len(services)} servicios definidos en "
        f"docker-compose.yml: {', '.join(services) if services else 'ver docker-compose.yml'}): "
        "'postgres' (PostgreSQL 16 con Row Level Security habilitado en tablas con datos "
        "sensibles), 'backend' (API Flask), 'frontend' (Vite/React), 'redis' (broker de Celery) "
        "y 'worker' (Celery, tareas asíncronas: notificaciones, timers de SLA, correo).",
        "El motor de SLA (backend/domain/services/sla_service.py) calcula tiempo consumido y "
        "disponibilidad en horas hábiles reales, respetando el calendario y la zona horaria de "
        "cada recurso (ej. America/Bogota para Aris, America/Guayaquil para Vaxthera) en vez de "
        "wall-clock puro; pausa el conteo en estados como 'Pendiente de Usuario' y congela el "
        "resultado de cada fase (Contacto, Ejecución) al transicionar de estado.",
        "El envío de correo (bienvenida, reseteo de contraseña, notificaciones) usa SMTP "
        "configurado por variables de entorno (SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD/"
        "SMTP_FROM), reutilizado por el mismo mecanismo de token con expiración de 30 minutos en "
        "ambos flujos.",
    ]
    return Section(
        heading="Arquitectura del Sistema",
        level=1,
        paragraphs=paragraphs,
        source_refs=[
            ".specify/memory/constitution.md",
            "docker-compose.yml",
            "backend/domain/services/sla_service.py",
        ],
    )


def build_installation_sections() -> list[Section]:
    compose_path = REPO_ROOT / "docker-compose.yml"
    compose_text = compose_path.read_text(encoding="utf-8") if compose_path.exists() else ""
    env_vars = extract_env_var_names(compose_text)

    requirements_path = REPO_ROOT / "backend" / "requirements.txt"
    requirements = (
        requirements_path.read_text(encoding="utf-8").splitlines()
        if requirements_path.exists() else []
    )
    requirement_names = [r.split("==")[0] for r in requirements if r.strip()]

    package_json_path = REPO_ROOT / "frontend" / "package.json"
    scripts: dict[str, str] = {}
    if package_json_path.exists():
        scripts = json.loads(package_json_path.read_text(encoding="utf-8")).get("scripts", {})

    seed_dir = REPO_ROOT / "backend" / "scripts"
    seed_scripts = sorted(p.name for p in seed_dir.glob("seed_*.py")) if seed_dir.exists() else []

    intro = Section(
        heading="Guía de Instalación y Despliegue Paso a Paso",
        level=1,
        paragraphs=[
            "Pasos para levantar el ambiente completo (backend, frontend, base de datos, cola de "
            "tareas) desde cero."
        ],
    )
    prereqs = Section(
        heading="Requisitos previos",
        level=2,
        bullet_items=[
            "Docker y Docker Compose (ruta recomendada, evita instalar Python/Node localmente).",
            "Alternativa sin Docker: Python 3.12+, Node.js 20+ con pnpm, PostgreSQL 16, Redis 7.",
        ],
    )
    env_section = Section(
        heading="Variables de entorno",
        level=2,
        paragraphs=[
            f"{len(env_vars)} variables referenciadas en docker-compose.yml (solo nombres — los "
            "valores reales viven en `.env`/`.env.prod`/`.env.test`, nunca commiteados al "
            "repositorio):"
        ],
        bullet_items=list(env_vars),
        source_refs=["docker-compose.yml"],
    )
    steps_section = Section(
        heading="Comandos de instalación, migraciones y despliegue",
        level=2,
        bullet_items=[
            "1. Copiar la plantilla de entorno correspondiente y completar valores reales: "
            "`.env.example` → `.env` (desarrollo); `.env.prod.example` → `.env.prod`; "
            "`.env.test.example` → `.env.test` (stacks aislados Test/Producción).",
            "2. Backend: `pip install -r backend/requirements.txt` "
            f"({len(requirement_names)} dependencias, entre ellas "
            f"{', '.join(requirement_names[:6])}...).",
            "3. Frontend: `pnpm install` dentro de `frontend/` (gestor de paquetes obligatorio "
            "del proyecto — prohibido npm/yarn).",
            "4. Migraciones de base de datos: `alembic upgrade head` (configuración en "
            "`backend/alembic.ini`).",
            "5. Datos semilla (opcionales, idempotentes): "
            + (", ".join(seed_scripts) if seed_scripts else "ver backend/scripts/seed_*.py") + ".",
            f"6. Frontend en desarrollo: `pnpm run dev` ({scripts.get('dev', 'vite')}); build de "
            f"producción: `pnpm run build` ({scripts.get('build', 'tsc -b && vite build')}).",
            "7. Despliegue con Docker Compose: `docker compose up -d` desde la raíz del "
            "repositorio; los ambientes aislados de Test/Producción usan `-p sywork_test` / "
            "`-p sywork_prod` sobre el mismo docker-compose.yml parametrizado por variables.",
        ],
        source_refs=[
            "backend/requirements.txt", "frontend/package.json", "backend/alembic.ini",
            "backend/scripts/",
        ],
    )
    return [intro, prereqs, env_section, steps_section]


_MODULES = [
    ("Kanban", "KanbanPage.tsx",
     "Tablero visual de tickets/tareas por estado, con arrastrar y soltar "
     "(@hello-pangea/dnd), ordenado por urgencia de SLA dentro de cada columna."),
    ("Tickets", "TicketsPage.tsx",
     "Listado paginado y filtrable de tickets, creación con cascada Cliente → Proyecto → "
     "Encargado, y ordenamiento configurable (urgencia, prioridad, estado, fecha, código)."),
    ("Tareas y Subtareas", "MyTasksPage.tsx",
     "Vista de tareas asignadas al usuario actual (Resolutor), organizadas en Listas de Tareas "
     "con Subtareas anidadas que heredan Skills y Nivel de escalamiento de la Tarea padre."),
    ("Registro de Tiempos", "WorkSessionsPage.tsx",
     "Registro diario de tiempo por recurso (cronómetro manual o entrada retroactiva), con "
     "clasificación automática 'fuera de jornada' según el calendario laboral del recurso."),
    ("RRHH y Calendarios", "CalendarPage.tsx",
     "Calendario de equipo superpuesto (mes/semana/día), franjas horarias por país, festivos "
     "sincronizados por API pública y ausencias/vacaciones con doble aprobación (Jefe directo + "
     "rol RRHH)."),
    ("Reportes", "ReportsPage.tsx",
     "Grid interactivo con columnas mostrables/ocultables/reordenables, filtros combinables, "
     "agregaciones (suma/promedio/conteo) sobre todo el conjunto filtrado, exportación a Excel y "
     "Vistas Personalizadas guardadas por usuario."),
]


def build_operation_sections() -> list[Section]:
    sections = [
        Section(
            heading="Manual de Usabilidad y Operación",
            level=1,
            paragraphs=[
                "Guía de uso por módulo, una subsección por cada área principal de la aplicación:"
            ],
        )
    ]
    pages_dir = REPO_ROOT / "frontend" / "src" / "pages"
    for module_name, page_file, description in _MODULES:
        exists = (pages_dir / page_file).exists()
        note = "" if exists else " (pantalla no encontrada al generar este documento)"
        sections.append(Section(
            heading=module_name,
            level=2,
            paragraphs=[description + note],
            bullet_items=[f"Pantalla: frontend/src/pages/{page_file}"],
            source_refs=[f"frontend/src/pages/{page_file}"],
        ))
    return sections


def build_manual_usuario_from_scratch() -> DocumentSpec:
    """Fallback usado solo si docs/Manual_de_Usuario.docx todavía no existe (ej. clon nuevo del
    repositorio). Genera una versión mínima razonable, sin las capturas de pantalla reales ni
    los diagramas curados a mano que sí tiene la versión histórica del manual."""
    sections: list[Section] = [build_architecture_section()]
    sections.extend(build_installation_sections())
    sections.extend(build_operation_sections())
    return DocumentSpec(
        output_path=DOCS_DIR / "Manual_de_Usuario.docx",
        title="Manual de Usuario — SYTIX",
        sections=sections,
    )


def _style_by_name(document: Document, name: str):
    """Busca un estilo por su nombre de UI (`.name`), evitando el lookup por nombre interno de
    python-docx (`document.styles[name]`), que falla en documentos generados con Pandoc cuyo
    styles.xml usa nombres internos en minúscula distintos del nombre traducido que expone
    `.name` — ver research.md, corrección post-entrega de spec 040."""
    for style in document.styles:
        if style.name == name:
            return style
    return None


def update_or_create_manual_usuario() -> bool:
    """Actualiza in-place `docs/Manual_de_Usuario.docx` si ya existe: preserva toda la
    narrativa curada a mano, los diagramas y las capturas de pantalla reales (validados contra
    la app en Docker en la sesión de spec 025), y solo agrega/refresca la sección "Guía de
    Instalación y Despliegue Paso a Paso" (el hueco real que pedía spec.md). Si el archivo no
    existe todavía, cae al fallback `build_manual_usuario_from_scratch()`.

    Corrección post-entrega (spec 040): la primera versión de este script regeneraba el Manual
    completo desde cero y así destruía 27 capturas de pantalla reales y ~250 párrafos de
    contenido curado que ningún script puede recrear — ver quickstart.md para el detalle.
    """
    output_path = DOCS_DIR / "Manual_de_Usuario.docx"
    if not output_path.exists():
        spec = build_manual_usuario_from_scratch()
        return save_document_safely(render_document(spec), spec.output_path)

    document = Document(output_path)
    heading_text = "Guía de Instalación y Despliegue Paso a Paso"
    fallback_anchor_text = "2. Diagramas de Flujo y Procesos"

    heading1_style = _style_by_name(document, "Heading 1")
    heading2_style = _style_by_name(document, "Heading 2")
    bullet_style = (
        _style_by_name(document, "List Bullet") or _style_by_name(document, "List Paragraph")
    )

    paragraphs = list(document.paragraphs)
    start_idx = next((i for i, p in enumerate(paragraphs) if p.text.strip() == heading_text), None)
    if start_idx is not None:
        # Ya existe una versión de esta sección (ejecución previa del script): se borra para
        # reemplazarla con contenido fresco, sin duplicar ni acumular.
        end_idx = start_idx + 1
        while end_idx < len(paragraphs):
            style_name = paragraphs[end_idx].style.name if paragraphs[end_idx].style else ""
            if style_name == "Heading 1":
                break
            end_idx += 1
        anchor = paragraphs[end_idx] if end_idx < len(paragraphs) else None
        for stale_paragraph in paragraphs[start_idx:end_idx]:
            stale_paragraph._element.getparent().remove(stale_paragraph._element)
    else:
        anchor = next((p for p in paragraphs if p.text.strip() == fallback_anchor_text), None)

    if anchor is not None:
        def add(text: str, style=None):
            return anchor.insert_paragraph_before(text, style=style)
    else:
        def add(text: str, style=None):
            return document.add_paragraph(text, style=style)

    # La Arquitectura y la Operación por módulo ya existen en la versión histórica del manual
    # (curadas a mano, con capturas reales) — no se tocan, solo se agrega/refresca Instalación.
    for section in build_installation_sections():
        add(section.heading, style=heading1_style if section.level == 1 else heading2_style)
        for paragraph_text in section.paragraphs:
            add(paragraph_text)
        for item in section.bullet_items or []:
            add(item, style=bullet_style)

    return save_document_safely(document, output_path)


# ---------------------------------------------------------------------------
# Documento 2: Documentación del Código Fuente (US2, T011-T014)
# ---------------------------------------------------------------------------

_STRUCTURE_ENTRIES = {
    "backend/domain": (
        "Capa 1 - Dominio puro: FSM de tickets, motor de SLA, entidades. Sin imports de "
        "Flask/SQLAlchemy."
    ),
    "backend/infra": "Capa 2 - Infraestructura: repositorios SQLAlchemy, modelos, migraciones.",
    "backend/api": "Capa 3 - Presentación backend: rutas Flask-RESTX, middlewares, Swagger.",
    "frontend/src/components": (
        "Componentes de interfaz 'tontos' (Ant Design): reciben props y renderizan, sin lógica "
        "de negocio."
    ),
    "frontend/src/services": (
        "Lógica de llamadas a la API (Axios) — único lugar permitido para lógica de negocio "
        "del frontend."
    ),
    "frontend/src/store": "Estado global con Zustand.",
    "frontend/src/types": "Interfaces TypeScript compartidas.",
    "frontend/src/pages": "Vistas completas, una por módulo de la aplicación.",
}


def build_estructura_section() -> Section:
    tree_backend = directory_tree(REPO_ROOT / "backend", {
        "domain": _STRUCTURE_ENTRIES["backend/domain"],
        "infra": _STRUCTURE_ENTRIES["backend/infra"],
        "api": _STRUCTURE_ENTRIES["backend/api"],
    })
    tree_frontend = directory_tree(REPO_ROOT / "frontend" / "src", {
        "components": _STRUCTURE_ENTRIES["frontend/src/components"],
        "services": _STRUCTURE_ENTRIES["frontend/src/services"],
        "store": _STRUCTURE_ENTRIES["frontend/src/store"],
        "types": _STRUCTURE_ENTRIES["frontend/src/types"],
        "pages": _STRUCTURE_ENTRIES["frontend/src/pages"],
    })
    missing = [rel for rel in _STRUCTURE_ENTRIES if not (REPO_ROOT / rel).exists()]
    paragraphs = [
        "Estructura de directorios (Principio II — Clean Architecture de 3 capas, "
        "constitution.md):"
    ]
    if missing:
        paragraphs.append("Nota: no se encontraron al generar este documento: " + ", ".join(missing))
    return Section(
        heading="Estructura General del Proyecto",
        level=1,
        paragraphs=paragraphs,
        bullet_items=tree_backend + tree_frontend,
        source_refs=list(_STRUCTURE_ENTRIES.keys()),
    )


_COMPONENT_FOLDER_PURPOSE = {
    "calendar": "Calendario de equipo, festivos, ausencias/vacaciones.",
    "clients": "Maestro de Clientes y sus Accesos/Portafolio de software.",
    "common": "Componentes compartidos (layout, wrappers genéricos de Ant Design).",
    "projects": "Maestro de Proyectos y Listas de Tareas.",
    "reports": "Grid interactivo de Reportes (columnas, filtros, agregaciones).",
    "resources": "Maestro de Recursos/Skills y su calendario laboral.",
    "roles": "Gestión de Roles y Permisos (RBAC).",
    "sla": "Reglas de SLA configurables por Proyecto/Prioridad.",
    "tickets": "Tarjetas, Kanban, comentarios y detalle de Ticket/Tarea.",
    "users": "Gestión de Usuarios internos y Usuario/cliente.",
    "worksessions": "Registro de tiempo (Work Sessions) y su historial.",
}


def build_catalogo_componentes() -> Section:
    rows: list[list[str]] = [["Categoría", "Nombre", "Ruta", "Propósito"]]

    models_dir = REPO_ROOT / "backend" / "infra" / "models"
    for path in sorted(models_dir.glob("*_model.py")) if models_dir.exists() else []:
        purpose = module_docstring_summary(path) or "Modelo SQLAlchemy."
        rows.append(["Modelo", path.name, str(path.relative_to(REPO_ROOT)), purpose])

    routes_dir = REPO_ROOT / "backend" / "api" / "routes"
    for path in sorted(routes_dir.glob("*.py")) if routes_dir.exists() else []:
        if path.name in ("__init__.py", "_shared.py"):
            continue
        purpose = module_docstring_summary(path) or f"Rutas Flask-RESTX de {path.stem}."
        rows.append(["Ruta/Controlador", path.name, str(path.relative_to(REPO_ROOT)), purpose])

    migrations_dir = REPO_ROOT / "backend" / "infra" / "migrations" / "versions"
    migration_count = len(list(migrations_dir.glob("*.py"))) if migrations_dir.exists() else 0
    rows.append([
        "Migración", f"{migration_count} archivos",
        "backend/infra/migrations/versions/",
        "Historial incremental de cambios de esquema (Alembic), aplicado con "
        "`alembic upgrade head`.",
    ])

    middleware_dir = REPO_ROOT / "backend" / "api" / "middleware"
    for path in sorted(middleware_dir.glob("*.py")) if middleware_dir.exists() else []:
        if path.name == "__init__.py":
            continue
        purpose = module_docstring_summary(path) or f"Middleware de {path.stem}."
        rows.append(["Middleware", path.name, str(path.relative_to(REPO_ROOT)), purpose])

    components_dir = REPO_ROOT / "frontend" / "src" / "components"
    if components_dir.exists():
        for folder in sorted(p.name for p in components_dir.iterdir() if p.is_dir()):
            purpose = _COMPONENT_FOLDER_PURPOSE.get(folder, "Componentes de interfaz del módulo.")
            rows.append([
                "Componente de interfaz", folder, f"frontend/src/components/{folder}/", purpose,
            ])

    return Section(
        heading="Catálogo de Componentes y Módulos",
        level=1,
        paragraphs=[f"{len(rows) - 1} componentes catalogados, agrupados por categoría."],
        table=rows,
        source_refs=[
            "backend/infra/models/", "backend/api/routes/",
            "backend/infra/migrations/versions/", "backend/api/middleware/",
            "frontend/src/components/",
        ],
    )


def build_codigo_representativo() -> Section:
    # Contenido COMPLETO de cada archivo (no fragmentos) — decisión del usuario tras revisar la
    # primera versión: "solo debe copiar y pegar el codigo fuente".
    candidates = [
        (
            "Backend",
            REPO_ROOT / "backend" / "api" / "routes" / "tickets.py",
            "Rutas Flask-RESTX de /api/tickets completas: CRUD, transición de estado FSM, "
            "asignación (Triage Push, endpoint independiente de la UI — Principio VI AI-Native), "
            "reasignación y comentarios.",
        ),
        (
            "Lógica de SLA",
            REPO_ROOT / "backend" / "domain" / "services" / "sla_service.py",
            "Motor de SLA completo (Capa 1 - Dominio, sin dependencias externas): cálculo de "
            "disponibilidad en horas hábiles, pausa/reanudación por estado, congelamiento de "
            "fases (Contacto/Ejecución) en las transiciones de estado.",
        ),
        (
            "Frontend",
            REPO_ROOT / "frontend" / "src" / "services" / "slaService.ts",
            "Servicio de API para reglas de SLA — toda llamada HTTP del frontend vive en "
            "frontend/src/services/, nunca directamente en un componente.",
        ),
        (
            "Helpers",
            REPO_ROOT / "frontend" / "src" / "types" / "workSession.ts",
            "Tipos e interfaces de Work Session más sus helpers de formato (incluye "
            "formatDuration(): minutos → '1h 30m'/'45m' para el resumen diario de Registro de "
            "Tiempos).",
        ),
    ]
    blocks: list[CodeBlock] = []
    source_refs = [str(path.relative_to(REPO_ROOT)) for _, path, _ in candidates]
    for layer, path, explanation in candidates:
        snippet = read_file_snippet(path)
        if snippet is None:
            continue
        blocks.append(CodeBlock(
            layer=layer,
            source_file=str(path.relative_to(REPO_ROOT)),
            snippet=snippet,
            explanation=explanation,
        ))
    return Section(
        heading="Código Fuente Representativo",
        level=1,
        paragraphs=[
            "Un fragmento por capa, tal como existe en el repositorio al momento de generar este "
            "documento (sin reformatear):"
        ],
        code_blocks=blocks,
        source_refs=source_refs,
    )


def build_codigo_fuente() -> DocumentSpec:
    sections = [
        build_estructura_section(),
        build_catalogo_componentes(),
        build_codigo_representativo(),
    ]
    return DocumentSpec(
        output_path=DOCS_DIR / "Codigo_Fuente_y_Documentacion.docx",
        title="Documentación del Código Fuente — SYTIX",
        sections=sections,
    )


# ---------------------------------------------------------------------------
# Documento 3: Descripción Ejecutiva del Software (US3, T015-T017)
# ---------------------------------------------------------------------------

def build_descripcion_ejecutiva() -> DocumentSpec:
    section = Section(
        heading="SYTIX — Systems | Innovation | Xcellence",
        level=1,
        paragraphs=[
            "SYTIX — Systems | Innovation | Xcellence — es una plataforma integral de "
            "gestión de tickets, mesa de ayuda y control de tiempos, diseñada para equipos de "
            "soporte y consultoría que operan proyectos de TI para múltiples clientes. Su nombre "
            "resume el propósito del producto: sistemas que funcionan con innovación y "
            "excelencia operativa, de principio a fin del ciclo de vida de una solicitud de "
            "soporte.",

            "El propósito central de SYTIX es dar a las áreas de soporte y a sus clientes una "
            "única fuente de verdad sobre el estado de cada ticket o tarea: quién lo atiende, en "
            "qué fase del proceso está, cuánto tiempo se le ha dedicado y si se está cumpliendo "
            "el acuerdo de nivel de servicio (SLA) pactado. En vez de coordinar por hojas de "
            "cálculo, correos sueltos o canales de chat dispersos, cada organización cliente y "
            "cada proyecto tienen su propio espacio dentro de la plataforma, con su calendario, "
            "su SLA y su equipo asignado.",

            "Entre sus características principales, SYTIX ofrece gestión de clientes y "
            "proyectos con soporte nativo para zonas horarias distintas — cada cliente "
            "puede operar en su propio huso horario sin que eso afecte el cálculo de plazos —; "
            "un flujo de asignación en cascada que va de Cliente a Proyecto y de ahí al "
            "Encargado o resolutor correcto, reduciendo errores de enrutamiento; un calendario "
            "de equipo que superpone la disponibilidad de todos los recursos junto con festivos, "
            "vacaciones y permisos gestionados por el módulo de Recursos Humanos, con doble "
            "aprobación de jefe directo y RRHH; un módulo de Reportes dinámicos e interactivos, "
            "donde cualquier usuario autorizado arma su propia vista con las columnas, filtros y "
            "agregaciones que necesita, sin depender de un desarrollador para generar cada "
            "informe; y un motor de SLA que corre exclusivamente en horas hábiles reales — "
            "pausándose automáticamente fuera de la jornada laboral, en festivos o mientras el "
            "ticket espera respuesta del cliente — en lugar de contar tiempo de reloj "
            "corrido, que penalizaría injustamente al equipo de soporte.",

            "El valor agregado de SYTIX está en la precisión y la confianza que aporta a la "
            "relación entre el proveedor de soporte y sus clientes. La trazabilidad del tiempo "
            "es exacta al minuto, con cada registro asociado a un ticket, un recurso y una nota "
            "explicativa, lo que permite facturar, auditar y mejorar procesos con datos reales "
            "en vez de estimaciones. La interfaz, construida sobre un sistema de diseño "
            "consistente, está optimizada para que Coordinadores, Resolutores, personal de RRHH "
            "y Usuarios/Clientes encuentren justo la información que su rol necesita, sin ruido "
            "ni pantallas sobrecargadas — cada perfil ve un menú y un conjunto de acciones "
            "ajustado a sus permisos. Esta diferenciación de roles no es solo una capa de "
            "seguridad: es lo que permite que un cliente externo siga el avance de sus propios "
            "tickets con total transparencia, mientras el equipo interno mantiene control total "
            "sobre la operación, la asignación de carga de trabajo y el cumplimiento de SLA.",

            "En conjunto, SYTIX convierte la operación de soporte en un proceso medible y "
            "gobernado por reglas claras, en lugar de coordinación informal. Eso se traduce en "
            "menos tickets perdidos, tiempos de respuesta más predecibles, reportes de gestión "
            "listos para presentar a cualquier cliente, y una base sólida para seguir "
            "incorporando automatización — incluyendo, a futuro, asistencia de "
            "inteligencia artificial en la asignación y priorización de tickets — sin "
            "necesidad de rediseñar la plataforma desde cero.",
        ],
        source_refs=["specs/040-documentacion-oficial-docx/spec.md"],
    )
    return DocumentSpec(
        output_path=DOCS_DIR / "Descripcion_del_Software.docx",
        title="Descripción Ejecutiva del Software — SYTIX",
        sections=[section],
    )


# ---------------------------------------------------------------------------
# Orquestación (T018)
# ---------------------------------------------------------------------------

def _generate(build_fn, label: str) -> tuple[bool, DocumentSpec]:
    print(label)
    spec = build_fn()
    document = render_document(spec)
    ok = save_document_safely(document, spec.output_path)
    return ok, spec


def main() -> int:
    print("Generando documentación oficial (docs/generate_docs.py)...\n")
    exit_code = 0

    print("1/3 Manual de Usuario")
    if not update_or_create_manual_usuario():
        exit_code = 1

    ok, _ = _generate(build_codigo_fuente, "2/3 Documentación de Código Fuente")
    if not ok:
        exit_code = 1

    ok, descripcion_spec = _generate(build_descripcion_ejecutiva, "3/3 Descripción Ejecutiva")
    if ok:
        word_count = count_words(descripcion_spec)
        in_range = word_count.min_words <= word_count.actual_words <= word_count.max_words
        status = "OK" if in_range else "ADVERTENCIA"
        print(
            f"  Conteo de palabras: {word_count.actual_words} "
            f"(rango esperado {word_count.min_words}-{word_count.max_words}) [{status}]"
        )
    else:
        exit_code = 1

    print("\nListo." if exit_code == 0 else "\nCompletado con errores — revisar mensajes arriba.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
