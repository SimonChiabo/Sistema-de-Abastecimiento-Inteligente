"""
core/log_config.py — Configuración centralizada de logging para SAI.
Importar y llamar a configurar_logging() al inicio de cada script ejecutable
(main.py, mailer.py, audit_job.py, etc.)
"""
import logging
import os
from datetime import datetime


def configurar_logging(nivel: int = logging.INFO) -> None:
    """
    Configura el sistema de logging para consola y archivo diario.
    Si ya hay handlers registrados, no añade duplicados.

    Args:
        nivel: Nivel de logging (logging.DEBUG, logging.INFO, etc.)
    """
    # Crear directorio de logs si no existe
    os.makedirs("logs", exist_ok=True)

    formato = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(nivel)

    # Evitar handlers duplicados si se llama más de una vez
    if root_logger.handlers:
        return

    # Handler de consola
    handler_consola = logging.StreamHandler()
    handler_consola.setFormatter(formato)
    root_logger.addHandler(handler_consola)

    # Handler de archivo (un archivo por día)
    fecha = datetime.now().strftime("%Y-%m-%d")
    handler_archivo = logging.FileHandler(
        f"logs/sai_{fecha}.log", encoding="utf-8"
    )
    handler_archivo.setFormatter(formato)
    root_logger.addHandler(handler_archivo)
