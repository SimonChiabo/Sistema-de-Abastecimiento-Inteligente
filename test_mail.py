import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

def test_smtp_connection():
    print("--- Verificando Configuración DevOps: Test SMTP ---")
    
    # Cargar variables (.env debe existir)
    load_dotenv()
    
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASS = os.getenv("SMTP_PASS")
    RECIPIENT = "simonchiabo@gmail.com"

    if not SMTP_USER or not SMTP_PASS:
        print("ERROR: Faltan SMTP_USER o SMTP_PASS en el archivo .env.")
        return

    print(f"Intentando handshake con {SMTP_SERVER}:{SMTP_PORT} usando {SMTP_USER}...")

    # Configurar el mensaje
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = RECIPIENT
    msg['Subject'] = 'SAI: Test de Conexión Exitoso'
    body = 'Si estás leyendo esto, la integración SMTP está operativa. El sistema SAI puede enviar notificaciones.'
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Iniciar conexión
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.set_debuglevel(1) # Activamos debug para ver el proceso interno
        server.starttls()
        
        # Login
        print("Autenticando...")
        server.login(SMTP_USER, SMTP_PASS)
        
        # Enviar
        print("Enviando correo de prueba...")
        server.sendmail(SMTP_USER, RECIPIENT, msg.as_string())
        server.quit()
        
        print("\n" + "="*40)
        print("CONEXIÓN EXITOSA: El correo fue enviado.")
        print("="*40)
        
    except smtplib.SMTPAuthenticationError:
        print("\n❌ ERROR DE AUTENTICACIÓN: Usuario o contraseña incorrectos.")
        print("Nota: Si usas Gmail, asegúrate de usar una 'Contraseña de Aplicación' y no tu contraseña normal.")
    except smtplib.SMTPConnectError:
        print("\n❌ ERROR DE CONEXIÓN: No se pudo conectar al servidor SMTP.")
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {e}")

if __name__ == "__main__":
    test_smtp_connection()
