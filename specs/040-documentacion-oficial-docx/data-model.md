# Data Model: Generación y Actualización de Documentación Oficial (3 Documentos .docx)

Esta feature no introduce entidades de datos persistentes (no hay tabla, migración ni modelo de
aplicación nuevo). Lo que sigue es el **modelo de contenido** que el script `docs/generate_docs.py`
construye en memoria antes de volcarlo a cada `.docx` — útil para que la Fase 2 (`tasks.md`) pueda
dividir el trabajo por entidad de contenido en vez de por archivo binario completo.

## Entidad: `DocumentSpec`

Representa uno de los 3 documentos a generar.

| Campo | Tipo | Descripción |
|---|---|---|
| `output_path` | `Path` | Ruta final dentro de `docs/`, ej. `docs/Manual_de_Usuario.docx` |
| `title` | `str` | Título de portada/heading 1 del documento |
| `sections` | `list[Section]` | Secciones de nivel superior, en orden |

Instancias: `manual_usuario`, `codigo_fuente`, `descripcion_ejecutiva` (una por documento pedido en
`spec.md`).

## Entidad: `Section`

Unidad de contenido con heading propio dentro de un documento.

| Campo | Tipo | Descripción |
|---|---|---|
| `heading` | `str` | Texto del encabezado (Heading 1 o 2 según nivel) |
| `level` | `int` | Nivel de heading de Word (1 = sección principal, 2 = subsección) |
| `paragraphs` | `list[str]` | Párrafos de texto plano de la sección |
| `bullet_items` | `list[str]` \| `None` | Lista con viñetas, si aplica (ej. requisitos previos) |
| `table` | `Table` \| `None` | Tabla nativa de Word, si la sección la requiere (ej. variables de entorno) |
| `code_blocks` | `list[CodeBlock]` \| `None` | Fragmentos de código, solo en el documento de Código Fuente |
| `source_refs` | `list[str]` | Rutas de archivo del repositorio que alimentaron esta sección (trazabilidad, ver `research.md` Decisión 6) |

**Validación**: `paragraphs` o `bullet_items` o `table` o `code_blocks` debe tener al menos un elemento
no vacío — una `Section` sin contenido es inválida (no se escribe un heading huérfano).

## Entidad: `CodeBlock`

Fragmento de código representativo (solo usado por `Codigo_Fuente_y_Documentacion.docx`).

| Campo | Tipo | Descripción |
|---|---|---|
| `layer` | `str` | Una de: `Backend`, `Frontend`, `Lógica de SLA`, `Helpers` (FR-008) |
| `source_file` | `str` | Ruta relativa del archivo real de origen (ej. `backend/domain/services/sla_service.py`) |
| `snippet` | `str` | Código fuente extraído tal cual (sin reformatear), acotado a la parte representativa |
| `explanation` | `str` | Nota breve (1-3 frases) de qué hace el fragmento y por qué es representativo |

**Validación**: `source_file` debe existir en el repositorio al momento de generación; si no existe
(edge case de `spec.md`), esa entrada se omite con una nota en consola en vez de fallar la generación
completa (FR consistente con el Edge Case "fuente no existe").

## Entidad: `ComponentCatalogEntry`

Fila del catálogo de componentes/módulos (`Codigo_Fuente_y_Documentacion.docx`, FR-007).

| Campo | Tipo | Descripción |
|---|---|---|
| `category` | `str` | Modelo, Ruta/Controlador, Migración, Middleware, Componente de interfaz |
| `name` | `str` | Nombre del archivo o clase/componente |
| `path` | `str` | Ruta relativa en el repositorio |
| `purpose` | `str` | Descripción de una frase de su propósito |

## Entidad: `WordCountTarget` (solo Descripción Ejecutiva)

| Campo | Tipo | Descripción |
|---|---|---|
| `min_words` | `int` | 400 (FR-009 / SC-004) |
| `max_words` | `int` | 600 (FR-009 / SC-004) |
| `actual_words` | `int` | Calculado al final de generar el documento, contando palabras de todos los `paragraphs` |

**Validación**: el script imprime en consola `actual_words` al finalizar la generación de
`Descripcion_del_Software.docx` para que el usuario verifique manualmente contra el rango (no se aborta
la generación si está fuera de rango — es una advertencia, no un error duro).

## Relaciones

```
DocumentSpec 1 ──< N Section
Section 1 ──< N CodeBlock          (solo en el DocumentSpec "codigo_fuente")
DocumentSpec "codigo_fuente" 1 ──< N ComponentCatalogEntry
DocumentSpec "descripcion_ejecutiva" 1 ── 1 WordCountTarget
```

No hay transiciones de estado (no es una FSM) ni relaciones con entidades de la aplicación
(`Ticket`, `User`, etc.) — este modelo vive únicamente dentro de la ejecución del script, no se
persiste en base de datos.
