"""
init_setup.py — Configuración inicial de la infraestructura SAI en el spreadsheet maestro.
Crea las pestañas MASTER_SKU y MASTER_PROV con sus encabezados si no existen.
"""
import logging

import gspread

from core.auth import obtener_spreadsheet_maestro
from core.log_config import configurar_logging

logger = logging.getLogger(__name__)


def setup_sai_infrastructure() -> None:
    """Crea o limpia las pestañas maestras en el spreadsheet central de SAI."""
    logger.info("Configurando infraestructura SAI en spreadsheet existente...")

    try:
        sh = obtener_spreadsheet_maestro()
        logger.info("Spreadsheet maestro encontrado. ID: %s", sh.id)
    except gspread.SpreadsheetNotFound:
        logger.error(
            "Spreadsheet maestro no encontrado. "
            "Asegúrate de haberlo compartido con la cuenta de servicio "
            "y que el nombre en MASTER_SPREADSHEET_NAME sea exacto."
        )
        return
    except Exception as error:
        logger.error("Error al abrir spreadsheet maestro: %s", error)
        return

    # Configuración de pestañas y encabezados
    config_hojas = {
        "MASTER_SKU": ["SKU_ID", "Nombre", "Categoría", "Presentación", "Proveedor_ID", "Precio_Ref"],
        "MASTER_PROV": ["Proveedor_ID", "Nombre", "Email", "Frecuencia", "Hora_Limite", "Dias_Programados"],
    }

    hojas_existentes = [ws.title for ws in sh.worksheets()]

    for nombre_hoja, encabezados in config_hojas.items():
        logger.info("Configurando pestaña: %s...", nombre_hoja)
        try:
            if nombre_hoja in hojas_existentes:
                worksheet = sh.worksheet(nombre_hoja)
                logger.info("  Pestaña ya existe. Limpiando...")
                worksheet.clear()
            else:
                # Si es la primera pestaña, renombrar la default en lugar de añadir
                if nombre_hoja == "MASTER_SKU" and len(hojas_existentes) == 1:
                    worksheet = sh.get_worksheet(0)
                    worksheet.update_title(nombre_hoja)
                    worksheet.clear()
                else:
                    worksheet = sh.add_worksheet(title=nombre_hoja, rows="100", cols="20")

            worksheet.append_row(encabezados)
            worksheet.format(
                "A1:Z1",
                {
                    "textFormat": {"bold": True},
                    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                    "horizontalAlignment": "CENTER",
                },
            )
            logger.info("  Pestaña '%s' lista.", nombre_hoja)

        except Exception as error:
            logger.error("Error en pestaña '%s': %s", nombre_hoja, error)

    # Eliminar hojas default sobrantes
    try:
        titulos_actuales = [ws.title for ws in sh.worksheets()]
        for nombre_default in ["Hoja 1", "Sheet1", "Hoja1"]:
            if nombre_default in titulos_actuales and "MASTER_SKU" in titulos_actuales:
                sh.del_worksheet(sh.worksheet(nombre_default))
                logger.info("Hoja default '%s' eliminada.", nombre_default)
    except Exception:
        pass

    logger.info(
        "Infraestructura desplegada exitosamente. "
        "URL: https://docs.google.com/spreadsheets/d/%s",
        sh.id,
    )


if __name__ == "__main__":
    configurar_logging()
    setup_sai_infrastructure()
