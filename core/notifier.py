"""
core/notifier.py — Envío de reportes de auditoría por email (SMTP).
No usa Google Sheets. Las credenciales se leen desde .env.
"""
import logging
import os
import smtplib
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def send_audit_report(filename: str, metrics: dict) -> bool:
    """
    Envía el reporte de auditoría por email con el CSV adjunto y un resumen de métricas.

    Args:
        filename: Ruta al archivo CSV a adjuntar.
        metrics: Diccionario con claves 'total_orders', 'total_amount', 'pending_conciliation'.

    Returns:
        True si el correo fue enviado exitosamente, False en caso contrario.
    """
    logger.info("Iniciando envío de auditoría al administrador...")

    servidor_smtp = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    puerto_smtp = int(os.getenv("SMTP_PORT", 587))
    usuario_smtp = os.getenv("SMTP_USER")
    contrasena_smtp = os.getenv("SMTP_PASS")
    destinatario = os.getenv("ADMIN_EMAIL", "simonchiabo@gmail.com")

    if not usuario_smtp or not contrasena_smtp:
        logger.error("Credenciales SMTP no configuradas en .env. Saltando envío.")
        return False

    # Construir mensaje
    msg = MIMEMultipart()
    msg["From"] = usuario_smtp
    msg["To"] = destinatario
    msg["Subject"] = f"SAI Audit Report - {datetime.now().strftime('%d/%m/%Y')}"

    cuerpo = f"""
    Hola Administrador,

    Se ha generado el reporte de auditoría global del sistema SAI.

    Resumen Ejecutivo:
    - Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}
    - Total de Órdenes Procesadas: {metrics.get('total_orders')}
    - Monto Total Acumulado: ${metrics.get('total_amount', 0.0):,.2f}
    - Pedidos Pendientes de Conciliación: {metrics.get('pending_conciliation')}

    Este archivo está listo para ser importado en Power BI para el análisis de cumplimiento.

    Atentamente,
    SAI BOT (Motor de Datos)
    """
    msg.attach(MIMEText(cuerpo, "plain"))

    # Adjuntar el archivo CSV
    try:
        with open(filename, "rb") as adjunto:
            parte = MIMEBase("application", "octet-stream")
            parte.set_payload(adjunto.read())
        encoders.encode_base64(parte)
        parte.add_header("Content-Disposition", f"attachment; filename={filename}")
        msg.attach(parte)
    except Exception as error:
        logger.error("Error al adjuntar archivo '%s': %s", filename, error)
        return False

    # Enviar correo
    try:
        servidor = smtplib.SMTP(servidor_smtp, puerto_smtp)
        servidor.starttls()
        servidor.login(usuario_smtp, contrasena_smtp)
        servidor.sendmail(usuario_smtp, destinatario, msg.as_string())
        servidor.quit()
        logger.info("Reporte enviado exitosamente a %s.", destinatario)
        return True
    except Exception as error:
        logger.error("Error en el envío SMTP: %s", error)
        return False


if __name__ == "__main__":
    send_audit_report("SAI_Analitica_Global.csv", {"total_orders": 0})
