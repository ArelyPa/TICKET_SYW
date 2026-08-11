import logging
import os
from flask import Flask
from flask_restx import Api, Resource
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


APP_ENV_LABELS = {"development": "DESARROLLO", "test": "TEST", "production": "PRODUCCIÓN"}


def create_app() -> Flask:
    app = Flask(__name__)
    app_env = os.environ.get("APP_ENV", "development")
    app_env_label = APP_ENV_LABELS.get(app_env, app_env.upper())
    app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET", "change-me-in-production")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 3600 * 8

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    JWTManager(app)

    # Devuelve la conexión de PostgreSQL al pool al final de CADA request
    # (la sesión es request-scoped; sin esto el pool se agota bajo carga).
    from backend.infra.database import close_db
    app.teardown_appcontext(close_db)

    # spec 013: contrato estándar de error {success, message, code} en TODA
    # respuesta >= 400, sin modificar los returns de las rutas.
    from backend.api.errors import register_error_handling
    register_error_handling(app)

    api = Api(
        app,
        version="1.0",
        title=f"SYTIX API — Ambiente: {app_env_label}",
        description=(
            "API para el sistema de tickets de soporte SYTIX.\n\n"
            "**Seguridad (Fase 1)**: TODAS las rutas exigen JWT Bearer + permiso módulo/acción "
            "del rol del usuario. Rutas públicas: `/api/auth/login`, `/api/auth/google` y `/health/`."
        ),
        authorizations={
            "Bearer": {"type": "apiKey", "in": "header", "name": "Authorization",
                       "description": "Formato: Bearer {token}"},
        },
        security="Bearer",
        doc="/swagger",
    )

    # ── Auth (login provisional + Google OAuth2 + /me) ─────────────────────────
    from backend.api.routes.auth import ns as ns_auth
    api.add_namespace(ns_auth)

    # ── Maestros — namespaces con Swagger completo ────────────────────────────
    from backend.api.routes.clients import ns as ns_clients
    from backend.api.routes.projects import ns as ns_projects
    from backend.api.routes.resources import ns as ns_resources
    from backend.api.routes.users import ns as ns_users
    from backend.api.routes.roles import ns as ns_roles
    from backend.api.routes.permissions import ns as ns_permissions

    api.add_namespace(ns_clients)
    api.add_namespace(ns_projects)
    api.add_namespace(ns_resources)
    api.add_namespace(ns_users)
    api.add_namespace(ns_roles)
    api.add_namespace(ns_permissions)

    # ── Fase 1 — Tickets ──────────────────────────────────────────────────────
    from backend.api.routes.tickets import ns as ns_tickets
    from backend.api.routes.catalogs import ns as ns_catalogs
    from backend.api.routes.notifications import ns as ns_notifications
    from backend.api.routes.assignment_panel import ns as ns_panel

    api.add_namespace(ns_tickets)
    api.add_namespace(ns_catalogs)
    api.add_namespace(ns_notifications)
    api.add_namespace(ns_panel)

    # ── Fase 2 — Registro diario de tiempos ────────────────────────────────────
    from backend.api.routes.work_sessions import ns as ns_work_sessions

    api.add_namespace(ns_work_sessions)

    # ── Fase 2.1 — Rol Usuario/cliente (client_contacts) ─────────────────────────────
    from backend.api.routes.client_contacts import ns as ns_client_contacts

    api.add_namespace(ns_client_contacts)

    # ── spec 009 — Listas de tareas ─────────────────────────────────────────────
    from backend.api.routes.task_lists import ns_project_lists, ns as ns_task_lists

    api.add_namespace(ns_project_lists)
    api.add_namespace(ns_task_lists)

    # ── spec 010 — Personal del Proyecto y subgrupos "Equipo" ───────────────────
    from backend.api.routes.project_members import ns_project_members, ns_teams as ns_project_teams

    api.add_namespace(ns_project_members)
    api.add_namespace(ns_project_teams)

    # ── spec 012 — Cronómetro manual de tiempo (provisional) ───────────────────
    from backend.api.routes.timer import ns as ns_timer

    api.add_namespace(ns_timer)

    # ── spec 014 — SLAs por Proyecto y Prioridad (Fase 4) ──────────────────────
    from backend.api.routes.sla_rules import ns as ns_sla_rules

    api.add_namespace(ns_sla_rules)

    # ── spec 020 — Fase 5: calendarios, festivos, horario laboral, ausencias y
    #    disponibilidad (esta sesión: solo Historia 1, disponibilidad) ─────────
    from backend.api.routes.calendar import ns as ns_calendar

    api.add_namespace(ns_calendar)

    # ── spec 034 — Módulo de Reportes Dinámicos ────────────────────────────────
    from backend.api.routes.reports import ns as ns_reports

    api.add_namespace(ns_reports)

    # ── spec 041 — Importación de tareas de Teamwork ────────────────────────────
    from backend.api.routes.ticket_imports import ns as ns_ticket_imports

    api.add_namespace(ns_ticket_imports)

    # ── spec 042 — Integración API Teamwork v3 e Importador de Tiempos ─────────
    from backend.api.routes.teamwork_integration import ns as ns_teamwork_integration
    from backend.api.routes.time_imports import ns as ns_time_imports

    api.add_namespace(ns_teamwork_integration)
    api.add_namespace(ns_time_imports)  # T025/T026 — implementado en Phase 4 (US2)

    # ── spec 045 — Centro Independiente de Importación de Tareas y Subtareas ──
    from backend.api.routes.teamwork_task_imports import ns as ns_teamwork_task_imports

    api.add_namespace(ns_teamwork_task_imports)

    # ── Health ────────────────────────────────────────────────────────────────
    ns_health = api.namespace("health", description="Estado del servicio y conectividad de DB")

    @ns_health.route("/")
    class Health(Resource):
        @ns_health.doc("health_check")
        @ns_health.response(200, "Servicio operativo")
        @ns_health.response(503, "Servicio degradado (DB no disponible)")
        def get(self):
            """Verificar estado del backend y conexión a PostgreSQL"""
            from backend.infra.database import get_db
            from sqlalchemy import text
            try:
                db = get_db()
                result = db.execute(text("SELECT version(), current_database(), now()")).fetchone()
                return {
                    "status": "ok",
                    "service": "sywork-backend",
                    "database": {
                        "connected": True,
                        "name": result[1],
                        "server_time": str(result[2]),
                        "version": result[0].split(",")[0],
                    },
                }
            except Exception:
                logger.exception("Health check failed: database unreachable")
                return {
                    "status": "degraded",
                    "service": "sywork-backend",
                    "database": {"connected": False, "error": "No se pudo conectar a la base de datos"},
                }, 503

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
