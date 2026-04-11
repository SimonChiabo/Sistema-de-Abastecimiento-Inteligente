import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def send_audit_report(filename, metrics):
    """
    Envía el reporte de auditoría por email con el CSV adjunto y un resumen de métricas.
    metrics = { 'total_orders': int, 'total_amount': float, 'pending_concilation': int }
    """
    print(f"--- Iniciando Envío de Auditoría a Admin ---")
    
    # Configuración desde .env
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASS = os.getenv("SMTP_PASS")
    RECIPIENT = "simonchiabo@gmail.com"

    if not SMTP_USER or not SMTP_PASS:
        print("ERROR: Credenciales SMTP no configuradas en .env. Saltando envío.")
        return False

    # Crear el mensaje
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = RECIPIENT
    msg['Subject'] = f"SAI Audit Report - {datetime.now().strftime('%d/%m/%Y')}"

    body = f"""
    Hola Administrador,
    
    Se ha generado el reporte de auditoría global del sistema SAI.
    
    Resumen Ejecutivo:
    - Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}
    - Total de Órdenes Procesadas: {metrics.get('total_orders')}
    - Monto Total Acumulado: ${metrics.get('total_amount', 0.0):,.2f}
    - Pedidos Pendientes de Conciliación: {metrics.get('pending_conciliation')}
    
    Este archivo está listo para ser importado en Power BI para el análisis de cumplimiento.
    
    Atentamente,
    SAI BOT (Senior Data Engine)
    """
    msg.attach(MIMEText(body, 'plain'))

    # Adjuntar el archivo CSV
    try:
        with open(filename, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {filename}",
        )
        msg.attach(part)
    except Exception as e:
        print(f"ERROR al adjuntar archivo: {e}")
        return False

    # Enviar el correo
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        text = msg.as_string()
        server.sendmail(SMTP_USER, RECIPIENT, text)
        server.quit()
        print(f"OK: Reporte enviado exitosamente a {RECIPIENT}.")
        return True
    except Exception as e:
        print(f"ERROR en el envío SMTP: {e}")
        return False

if __name__ == "__main__":
    # Prueba rápida
    send_audit_report("SAI_Analitica_Global.csv", 0)
