"""Autenticación: login provisional, Google OAuth2 y `/me`.

Documentado como Namespace de Flask-RESTX (antes era un Blueprint plano, invisible
en /swagger) para que aparezca en la documentación interactiva junto al resto de la
API, siguiendo /api-design-principles ("Documentation: Use OpenAPI/Swagger for
interactive docs"). Rutas públicas (sin JWT): /login y /google — son el punto de
entrada para obtenerlo. /me sí lo exige.
"""
import logging
import os

from flask import g, request
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import create_access_token
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from backend.api.routes._shared import error_model, server_error
from backend.infra.repositories.user_repo import UserRepository
from backend.infra.repositories.role_repo import RoleRepository
from backend.infra.database import get_db
from backend.domain.entities.user import USUARIO_CLIENTE_ROLE_NAME
from backend.domain.services.auth_service import AuthService
from backend.infra.email.mailer import send_password_reset_email

ns = Namespace("auth", description="Login provisional, Google OAuth2 y sesión actual", path="/api/auth")
_logger = logging.getLogger(__name__)

ALLOWED_DOMAIN = "sywork.net"
_auth_svc = AuthService()

# spec 046 (FR-003): enforcement estricto de pestaña de Login vs. rol de la cuenta. `login_mode`
# es opcional — si se omite, el login funciona igual que antes de esta feature (sin enforcement).
_LOGIN_MODE_ROLES = {
    "team": {"Admin", "Coordinador", "QM", "Resolutor"},
    "client_portal": {USUARIO_CLIENTE_ROLE_NAME},
}

# ── Swagger models ────────────────────────────────────────────────────────────

_error = error_model(ns, "AuthError")

_permission_out = ns.model("AuthPermission", {
    "module": fields.String(description="Módulo del permiso", example="tickets"),
    "action": fields.String(description="Acción", example="view"),
})

_role_out = ns.model("AuthRole", {
    "id": fields.String(description="UUID del rol"),
    "name": fields.String(description="Nombre del rol", example="Coordinador"),
})

_user_out = ns.model("AuthUser", {
    "id": fields.String(description="UUID del usuario"),
    "email": fields.String(description="Email @sywork.net"),
    "username": fields.String(description="Nombre de usuario"),
    "role": fields.Nested(_role_out),
    "permissions": fields.List(fields.Nested(_permission_out), description="Permisos efectivos del rol"),
})

_login_input = ns.model("LoginInput", {
    "username_or_email": fields.String(required=True, description="Username o email @sywork.net", example="coordinador"),
    "password": fields.String(required=True, description="Contraseña"),
    "login_mode": fields.String(description="'team' (Admin/Coordinador/QM/Resolutor) o "
                                "'client_portal' (Usuario/cliente) — spec 046 FR-003. Opcional: "
                                "si se omite, no se valida el rol contra la pestaña de origen.",
                                enum=["team", "client_portal"]),
})

_forgot_password_input = ns.model("ForgotPasswordInput", {
    "email": fields.String(required=True, description="Email @sywork.net de la cuenta"),
})

_message_out = ns.model("MessageResponse", {
    "message": fields.String(description="Mensaje genérico de resultado"),
})

_reset_password_input = ns.model("ResetPasswordInput", {
    "token": fields.String(required=True, description="Token recibido por correo"),
    "new_password": fields.String(required=True, description="Nueva contraseña"),
})

_google_input = ns.model("GoogleLoginInput", {
    "id_token": fields.String(required=True, description="ID token emitido por Google Identity Services"),
})

_auth_response = ns.model("AuthResponse", {
    "access_token": fields.String(description="JWT Bearer, expira en 8 horas"),
    "user": fields.Nested(_user_out),
})

_me_response = ns.model("MeResponse", {
    "user": fields.Nested(_user_out),
})


def _user_payload(user, db) -> dict:
    permissions = RoleRepository(db).list_permissions_for_role(user.role.id)
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "role": {"id": str(user.role.id), "name": user.role.name},
        "permissions": [{"module": p.module, "action": p.action} for p in permissions],
    }


# ── Rutas ─────────────────────────────────────────────────────────────────────

@ns.route("/login")
class AuthLogin(Resource):
    @ns.doc("login", security=None)
    @ns.expect(_login_input, validate=False)
    @ns.response(200, "Login exitoso", _auth_response)
    @ns.response(400, "Faltan credenciales", _error)
    @ns.response(401, "Usuario o contraseña incorrectos, o cuenta inactiva", _error)
    def post(self):
        """Login provisional por usuario/contraseña. Coexiste con /google, no lo reemplaza (ruta pública)."""
        data = request.get_json(silent=True) or {}
        identifier = (data.get("username_or_email") or "").strip()
        password = data.get("password") or ""
        login_mode = data.get("login_mode")
        if not identifier or not password:
            return {"error": "validation_error", "message": "username_or_email y password son requeridos"}, 400

        try:
            db = get_db()
            repo = UserRepository(db)
            user = repo.get_by_username_or_email(identifier)
            if not user or not user.active or not _auth_svc.verify_password(password, user.password_hash):
                return {"error": "unauthorized", "message": "Usuario o contraseña incorrectos"}, 401
            if login_mode in _LOGIN_MODE_ROLES and user.role.name not in _LOGIN_MODE_ROLES[login_mode]:
                # Mismo mensaje genérico que credenciales inválidas: no confirma si la cuenta
                # existe ni su rol (FR-003).
                return {"error": "unauthorized", "message": "Usuario o contraseña incorrectos"}, 401

            repo.update_last_login(user.id)
            token = create_access_token(identity=str(user.id), additional_claims={"role": user.role.name})
            return {"access_token": token, "user": _user_payload(user, db)}, 200
        except Exception:
            return server_error()


@ns.route("/google")
class AuthGoogle(Resource):
    @ns.doc("google_login", security=None)
    @ns.expect(_google_input, validate=False)
    @ns.response(200, "Login exitoso", _auth_response)
    @ns.response(400, "id_token faltante", _error)
    @ns.response(401, "Token inválido, dominio no permitido o usuario inexistente/inactivo", _error)
    def post(self):
        """Login vía Google OAuth2, restringido al dominio @sywork.net (ruta pública).

        No auto-crea usuarios: el email debe corresponder a una cuenta ya existente,
        dada de alta por un Admin (FR-018b).
        """
        data = request.get_json(silent=True) or {}
        id_token_str = data.get("id_token")
        if not id_token_str:
            return {"error": "bad_request", "message": "id_token requerido"}, 400

        try:
            idinfo = id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                os.environ.get("GOOGLE_CLIENT_ID"),
            )
        except ValueError:
            return {"error": "unauthorized", "message": "Acceso denegado"}, 401

        email: str = idinfo.get("email", "")
        domain = email.split("@")[-1] if "@" in email else ""
        if domain != ALLOWED_DOMAIN:
            return {"error": "unauthorized", "message": "Acceso denegado"}, 401

        google_sub: str = idinfo["sub"]
        try:
            db = get_db()
            repo = UserRepository(db)

            user = repo.get_by_google_sub(google_sub) or repo.get_by_email(email)
            if user is None or not user.active:
                return {"error": "unauthorized", "message": "Acceso denegado"}, 401

            repo.update_last_login(user.id)
            token = create_access_token(identity=str(user.id), additional_claims={"role": user.role.name})
            return {"access_token": token, "user": _user_payload(user, db)}, 200
        except Exception:
            return server_error()


_FORGOT_PASSWORD_MESSAGE = "Si el correo está registrado, recibirás un enlace para restablecer tu contraseña."


@ns.route("/forgot-password")
class AuthForgotPassword(Resource):
    @ns.doc("forgot_password", security=None)
    @ns.expect(_forgot_password_input, validate=False)
    @ns.response(200, "Solicitud procesada (mensaje genérico, exista o no la cuenta)", _message_out)
    @ns.response(400, "Falta el email", _error)
    def post(self):
        """Solicitar recuperación de contraseña por email (ruta pública, FR-009).

        Responde siempre el mismo mensaje genérico, exista o no la cuenta, para no revelar
        qué correos están registrados (FR-009 spec 003).
        """
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        if not email:
            return {"error": "validation_error", "message": "El campo 'email' es requerido"}, 400

        db = get_db()
        repo = UserRepository(db)
        user = repo.get_by_email(email)
        if user and user.active:
            token, expires_at = _auth_svc.generate_reset_token()
            repo.set_reset_token(user.id, token, expires_at)
            try:
                send_password_reset_email(user.email, token)
            except Exception:
                # No se revela al usuario si el envío falló (mismo mensaje genérico),
                # pero queda registrado en el log del backend para poder diagnosticarlo.
                _logger.exception("Fallo al enviar el correo de recuperación a %s", user.email)

        return {"message": _FORGOT_PASSWORD_MESSAGE}, 200


@ns.route("/reset-password")
class AuthResetPassword(Resource):
    @ns.doc("reset_password", security=None)
    @ns.expect(_reset_password_input, validate=False)
    @ns.response(200, "Contraseña actualizada correctamente", _message_out)
    @ns.response(400, "Token inválido, expirado, ya usado, o cuenta inactiva", _error)
    def post(self):
        """Completar la recuperación de contraseña con el token recibido por correo (ruta pública)."""
        data = request.get_json(silent=True) or {}
        token = data.get("token") or ""
        new_password = data.get("new_password") or ""
        if not token or not new_password:
            return {"error": "validation_error", "message": "token y new_password son requeridos"}, 400

        db = get_db()
        repo = UserRepository(db)
        user = repo.get_by_reset_token(token)
        if not _auth_svc.is_reset_token_valid(user, token):
            return {"error": "invalid_token", "message": "El enlace no es válido o ya expiró"}, 400

        repo.set_password(user.id, _auth_svc.hash_password(new_password))
        repo.clear_reset_token(user.id)
        return {"message": "Contraseña actualizada correctamente"}, 200


@ns.route("/me")
class AuthMe(Resource):
    @ns.doc("get_current_user")
    @ns.response(200, "Usuario autenticado", _me_response)
    @ns.response(401, "No autenticado, token inválido o cuenta desactivada", _error)
    def get(self):
        """Obtener el usuario y permisos de la sesión actual a partir del JWT."""
        from backend.api.middleware.auth import jwt_required_active

        @jwt_required_active
        def _inner():
            db = get_db()
            return {"user": _user_payload(g.current_user, db)}, 200

        try:
            return _inner()
        except Exception:
            # Token ausente/inválido: flask-restx convertiría la excepción de
            # flask-jwt-extended en 500 en vez de dejarla a JWTManager (FR-023).
            return {"error": "unauthorized", "message": "Acceso denegado"}, 401
