"""
test_mail.py — Script de diagnóstico para verificar la integración SMTP.
Envía un correo de prueba al administrador para confirmar que el stack de correo funciona.
"""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

from core.log_config import configurar_logging

load_dotenv()

logger = logging.getLogger(__name__)


def test_smtp_connection() -> None:
    """Realiza un handshake SMTP completo y envía un correo de prueba."""
    logger.info("Verificando configuración SMTP...")

    servidor_smtp = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    puerto_smtp = int(os.getenv("SMTP_PORT", 587))
    usuario_smtp = os.getenv("SMTP_USER")
    contrasena_smtp = os.getenv("SMTP_PASS")
    destinatario = os.getenv("ADMIN_EMAIL", "simonchiabo@gmail.com")

    if not usuario_smtp or not contrasena_smtp:
        logger.error("Faltan SMTP_USER o SMTP_PASS en el archivo .env.")
        return

    logger.info(
        "Intentando handshake con %s:%d usando cuenta %s...",
        servidor_smtp, puerto_smtp, usuario_smtp,
    )

    msg = MIMEMultipart()
    msg["From"] = usuario_smtp
    msg["To"] = destinatario
    msg["Subject"] = "SAI: Test de Conexión Exitoso"
    cuerpo = (
        "Si estás leyendo esto, la integración SMTP está operativa. "
        "El sistema SAI puede enviar notificaciones."
    )
    msg.attach(MIMEText(cuerpo, "plain"))

    try:
        servidor = smtplib.SMTP(servidor_smtp, puerto_smtp)
        servidor.set_debuglevel(1)
        servidor.starttls()

        logger.info("Autenticando...")
        servidor.login(usuario_smtp, contrasena_smtp)

        logger.info("Enviando correo de prueba a %s...", destinatario)
        servidor.sendmail(usuario_smtp, destinatario, msg.as_string())
        servidor.quit()

        logger.info("CONEXIÓN EXITOSA: El correo fue enviado a %s.", destinatario)

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Error de autenticación: usuario o contraseña incorrectos. "
            "Si usas Gmail, asegúrate de usar una 'Contraseña de Aplicación'."
        )
    except smtplib.SMTPConnectError:
        logger.error("Error de conexión: no se pudo conectar al servidor SMTP.")
    except Exception as error:
        logger.error("Error inesperado en SMTP: %s", error)


if __name__ == "__main__":
    configurar_logging()
    test_smtp_connection()
