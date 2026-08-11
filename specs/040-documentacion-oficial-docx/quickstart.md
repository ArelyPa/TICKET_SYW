# Quickstart: Generación y Actualización de Documentación Oficial (3 Documentos .docx)

Guía para ejecutar y validar el script generador una vez implementado. No incluye el código completo del
script (eso vive en `docs/generate_docs.py` y se implementa en la fase de ejecución) — solo cómo correrlo
y cómo comprobar que cumple `spec.md`.

## Prerrequisitos

- Python 3.10+ disponible en el `PATH` (ya verificado en esta sesión: `python --version` → 3.10.6).
- `python-docx` instalado (ya verificado: `pip show python-docx` → 1.2.0). Si no lo estuviera:

```bash
pip install -r docs/requirements-docs.txt
```

- Ningún lector de Word con `docs/Manual_de_Usuario.docx` abierto (evita el `PermissionError` cubierto en
  `research.md` Decisión 4). Cerrar Word antes de ejecutar si estaba abierto.
- Working tree limpio o revisado antes de ejecutar, para poder comparar el `git status` posterior
  (SC-005 exige que solo cambien archivos dentro de `docs/`).

## Ejecutar

Desde la raíz del repositorio:

```bash
python docs/generate_docs.py
```

Salida esperada en consola: una línea por documento generado con su ruta y, para la Descripción
Ejecutiva, el conteo de palabras final (ver `data-model.md` → `WordCountTarget`).

## Validar (End-to-End)

1. **Los tres archivos existen y abren sin error**:

   ```bash
   ls -la docs/Manual_de_Usuario.docx docs/Codigo_Fuente_y_Documentacion.docx docs/Descripcion_del_Software.docx
   ```

   Abrir cada uno en Word / Word Online y confirmar que no aparece el aviso de "contenido no legible"
   (SC-001).

2. **Manual de Usuario cubre las 3 secciones clave** (SC-002): en el documento abierto, verificar que
   existen los encabezados de nivel 1 "Arquitectura del Sistema", "Guía de Instalación y Despliegue" y
   "Manual de Usabilidad y Operación", y que esta última tiene una subsección por cada uno de los 6
   módulos (Kanban, Tickets, Tareas/Subtareas, Registro de Tiempos, RRHH/Calendarios, Reportes).

3. **Documentación de Código Fuente tiene árbol, catálogo y 4 fragmentos de código** (SC-003):
   confirmar un árbol de directorios en texto/monoespaciado, una tabla o lista de componentes, y al
   menos un bloque de código por capa: Backend, Frontend, Lógica de SLA, Helpers.

4. **Descripción Ejecutiva entre 400 y 600 palabras y con los 4 puntos pedidos** (SC-004): usar el
   conteo impreso por el script en el paso "Ejecutar", o verificar manualmente en Word
   (Revisar > Contar palabras) sobre el cuerpo del documento. Confirmar que cubre: nombre/significado de
   SYTIX, propósito de negocio, características principales, valor agregado.

5. **Ningún archivo fuera de `docs/` cambió** (SC-005):

   ```bash
   git status --porcelain | grep -v '^?? docs/\|^ M docs/\|^M  docs/\|^A  docs/'
   ```

   Este comando no debe devolver ninguna línea — cualquier resultado indica una escritura fuera de
   alcance.

6. **Ningún test se ejecutó en la sesión** (SC-006): revisión manual — confirmar que no se invocó
   `pytest`, `npm test`, `pnpm test` ni equivalentes durante la sesión de documentación.

7. **Idempotencia** (Edge Case de `spec.md`): correr `python docs/generate_docs.py` una segunda vez
   seguida y confirmar que los 3 `.docx` se regeneran sin error y sin duplicar contenido (ej. el
   Manual de Usuario no debería duplicar la sección "Arquitectura del Sistema" dos veces).

## Notas

- El `docs/Manual_de_Usuario.docx` existente se reemplaza por completo (ver `research.md` Decisión 2);
  si se quiere conservar una copia previa antes de la primera ejecución, copiarla manualmente
  (ej. `docs/Manual_de_Usuario.backup-<fecha>.docx`, mismo patrón ya usado en el repo).
- `docs/Manual_de_Usuario.md` (Markdown) no se modifica ni se elimina por este script — sigue siendo un
  borrador/fuente en paralelo (`spec.md` § Assumptions).
