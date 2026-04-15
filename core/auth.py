"""
core/auth.py — Módulo centralizado de autenticación para Google Sheets.
Todos los módulos del proyecto importan de aquí.
No crear credenciales ni clientes gspread en ningún otro lugar.
"""
import functools
import logging
import os
import time

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def reintentar_en_error_api(max_intentos: int = 3, espera_base: int = 5):
    """
    Decorador que reintenta una función si falla por error de la API de Google Sheets.

    Usa backoff exponencial: 5s → 10s → 20s (con max_intentos=3, espera_base=5).
    Solo reintenta en `gspread.exceptions.APIError`. Los errores de lógica
    (FileNotFoundError, SpreadsheetNotFound, etc.) se propagan inmediatamente.

    Args:
        max_intentos: Número máximo de intentos antes de relanzar la excepción.
        espera_base: Segundos base para el backoff exponencial.
    """
    def decorador(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for intento in range(1, max_intentos + 1):
                try:
                    return func(*args, **kwargs)
                except gspread.exceptions.APIError as error:
                    if intento == max_intentos:
                        logger.error(
                            "Fallo definitivo en '%s' tras %d intentos: %s",
                            func.__name__, max_intentos, error,
                        )
                        raise
                    espera = espera_base * (2 ** (intento - 1))
                    logger.warning(
                        "Error de API en '%s' (intento %d/%d). "
                        "Reintentando en %ds... Error: %s",
                        func.__name__, intento, max_intentos, espera, error,
                    )
                    time.sleep(espera)
        return wrapper
    return decorador


@reintentar_en_error_api()
def obtener_cliente_gsheets() -> gspread.Client:
    """
    Crea y retorna un cliente gspread autenticado con la cuenta de servicio.

    Lee la ruta al archivo de credenciales desde la variable de entorno
    CREDENTIALS_PATH (por defecto: 'credentials.json').

    Returns:
        gspread.Client: Cliente autenticado y listo para usar.

    Raises:
        FileNotFoundError: Si el archivo de credenciales no existe.
        gspread.exceptions.APIError: Si la autenticación falla por error de API
            (se reintentará automáticamente hasta max_intentos).
    """
    ruta_credenciales = os.getenv("CREDENTIALS_PATH", "credentials.json")

    if not os.path.exists(ruta_credenciales):
        mensaje = (
            f"Archivo de credenciales no encontrado en: '{ruta_credenciales}'. "
            "Verificar variable CREDENTIALS_PATH en .env."
        )
        logger.error(mensaje)
        raise FileNotFoundError(mensaje)

    try:
        credenciales = Credentials.from_service_account_file(
            ruta_credenciales, scopes=SCOPES
        )
        cliente = gspread.authorize(credenciales)
        logger.info("Autenticación con Google Sheets exitosa.")
        return cliente
    except gspread.exceptions.APIError:
        raise  # El decorador se encarga del retry
    except Exception as error:
        logger.error("Fallo en la autenticación con Google Sheets: %s", error)
        raise


@reintentar_en_error_api()
def obtener_spreadsheet_maestro() -> gspread.Spreadsheet:
    """
    Retorna el spreadsheet maestro de SAI abierto y listo para usar.

    Lee el nombre del spreadsheet desde la variable de entorno
    MASTER_SPREADSHEET_NAME.

    Returns:
        gspread.Spreadsheet: El spreadsheet maestro abierto.

    Raises:
        gspread.SpreadsheetNotFound: Si el spreadsheet no existe o no tiene acceso.
        gspread.exceptions.APIError: Si falla por error de API
            (se reintentará automáticamente hasta max_intentos).
    """
    nombre_maestro = os.getenv(
        "MASTER_SPREADSHEET_NAME", "SAI - Sistema de Abastecimiento"
    )
    cliente = obtener_cliente_gsheets()

    try:
        spreadsheet = cliente.open(nombre_maestro)
        logger.info("Spreadsheet maestro '%s' abierto correctamente.", nombre_maestro)
        return spreadsheet
    except gspread.SpreadsheetNotFound:
        logger.error(
            "Spreadsheet maestro '%s' no encontrado. "
            "Verificar nombre en MASTER_SPREADSHEET_NAME y permisos de la cuenta de servicio.",
            nombre_maestro,
        )
        raise
    except gspread.exceptions.APIError:
        raise  # El decorador se encarga del retry
    except Exception as error:
        logger.error(
            "Error al abrir spreadsheet maestro '%s': %s", nombre_maestro, error
        )
        raise
