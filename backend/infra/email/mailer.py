import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def _send(message) -> None:
    """Conexión/autenticación SMTP compartida por variables de entorno (SMTP_HOST, SMTP_PORT,
    SMTP_USER, SMTP_PASSWORD) — mismo mecanismo para ambos correos de este módulo."""
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        if user and password:
            server.login(user, password)
        server.send_message(message)


def send_password_reset_email(to_email: str, token: str) -> None:
    """Envía el correo de recuperación de contraseña vía SMTP (stdlib, sin dependencia nueva).

    Configuración por variables de entorno: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    SMTP_FROM, FRONTEND_URL. Envío síncrono — ver plan.md § Complexity Tracking sobre por qué
    esta fase no usa Celery/Redis para esto.
    """
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    reset_link = f"{frontend_url}/reset-password?token={token}"

    body = (
        "Recibimos una solicitud para restablecer tu contraseña de SYTIX.\n\n"
        f"Si fuiste tú, sigue este enlace (válido por 30 minutos):\n{reset_link}\n\n"
        "Si no solicitaste esto, puedes ignorar este correo."
    )
    message = MIMEText(body)
    message["Subject"] = "Restablecer tu contraseña — SYTIX"
    message["From"] = os.environ.get("SMTP_FROM", "no-reply@sywork.net")
    message["To"] = to_email
    _send(message)


_WELCOME_EMAIL_TEMPLATE = """\
<!DOCTYPE html>
<html lang="es">
<body style="margin:0;padding:0;background:#f4f5f7;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" width="480" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:8px;overflow:hidden;">
        <tr><td style="background:#1f2937;padding:20px 32px;">
          <span style="color:#ffffff;font-size:18px;font-weight:700;">SYTIX</span>
        </td></tr>
        <tr><td style="padding:32px;">
          <h1 style="font-size:20px;color:#111827;margin:0 0 16px;">¡Bienvenido/a, {{ name }}!</h1>
          <p style="font-size:14px;color:#374151;line-height:1.5;">
            Se creó una cuenta para vos en SYTIX. Estos son tus datos de acceso iniciales:
          </p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:16px 0;width:100%;">
            <tr><td style="padding:8px 12px;background:#f9fafb;border-radius:6px;">
              <div style="font-size:12px;color:#6b7280;">URL de acceso</div>
              <div style="font-size:14px;color:#111827;"><a href="{{ login_url }}" style="color:#2563eb;">{{ login_url }}</a></div>
            </td></tr>
            <tr><td style="height:8px;"></td></tr>
            <tr><td style="padding:8px 12px;background:#f9fafb;border-radius:6px;">
              <div style="font-size:12px;color:#6b7280;">Contraseña temporal</div>
              <div style="font-size:16px;color:#111827;font-family:monospace;">{{ temp_password }}</div>
            </td></tr>
          </table>
          <p style="font-size:14px;color:#374151;line-height:1.5;">
            Por seguridad, te recomendamos cambiarla antes de iniciar sesión usando este enlace
            (válido por 30 minutos):
          </p>
          <p style="text-align:center;margin:20px 0;">
            <a href="{{ reset_link }}"
               style="background:#2563eb;color:#ffffff;padding:10px 24px;border-radius:6px;
                      text-decoration:none;font-size:14px;font-weight:600;display:inline-block;">
              Cambiar contraseña
            </a>
          </p>
          <p style="font-size:12px;color:#9ca3af;line-height:1.5;margin-top:24px;">
            Este es un mensaje automático — no respondas a este correo. Tus datos se usan
            exclusivamente para gestionar tu acceso a SYTIX.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def send_welcome_email(to_email: str, name: str, temp_password: str, reset_link: str) -> None:
    """Correo de bienvenida HTML al crear una cuenta con "Notificar al Usuario" (spec 038, US5).

    Reutiliza el mismo mecanismo SMTP que `send_password_reset_email` — `reset_link` ya trae el
    token de un solo uso y expiración de 30 min generados por `AuthService.generate_reset_token`
    (spec 003), la misma pieza usada por "¿Olvidaste tu contraseña?". Plantilla renderizada con
    Jinja2 (ya viene con Flask, Principio V — sin dependencia nueva).
    """
    from jinja2 import Template

    login_url = os.environ.get("FRONTEND_URL", "http://localhost:5173") + "/login"
    html = Template(_WELCOME_EMAIL_TEMPLATE).render(
        name=name, login_url=login_url, temp_password=temp_password, reset_link=reset_link,
    )

    message = MIMEMultipart("alternative")
    message["Subject"] = "Bienvenido/a a SYTIX"
    message["From"] = os.environ.get("SMTP_FROM", "no-reply@sywork.net")
    message["To"] = to_email
    message.attach(MIMEText(
        f"Bienvenido/a a SYTIX.\n\nURL de acceso: {login_url}\n"
        f"Contraseña temporal: {temp_password}\n\n"
        f"Cambiala antes de 30 minutos en: {reset_link}",
        "plain",
    ))
    message.attach(MIMEText(html, "html"))
    _send(message)
