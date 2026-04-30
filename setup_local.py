"""
setup_local.py — Configuración completa de un spreadsheet SAI_Local.
Unifica la funcionalidad de create_template.py, enhance_template.py,
restructure_local.py e improve_ux.py en un único script reproducible.

Uso:
    python setup_local.py                    → configura SAI_Local_Template
    python setup_local.py "SAI_Local_01"    → configura un local específico por nombre
"""
import logging
import os
import sys

import gspread
from dotenv import load_dotenv

from core.auth import obtener_cliente_gsheets, obtener_spreadsheet_maestro
from core.log_config import configurar_logging

load_dotenv()

logger = logging.getLogger(__name__)

# Nombre por defecto del template canónico
NOMBRE_TEMPLATE = "SAI_Local_Template"

# Formato de encabezado corporativo (azul oscuro)
FORMATO_ENCABEZADO = {
    "textFormat": {
        "bold": True,
        "foregroundColor": {"red": 1, "green": 1, "blue": 1},
    },
    "backgroundColor": {"red": 0.0, "green": 0.2, "blue": 0.5},
    "horizontalAlignment": "CENTER",
}


# ---------------------------------------------------------------------------
# PASO 1 — Crear estructura base de pestañas
# ---------------------------------------------------------------------------

def _crear_estructura_base(sh: gspread.Spreadsheet, id_maestro: str) -> dict:
    """
    Crea o limpia las cuatro capas del spreadsheet local:
    _DB_INTERNAL (oculta), PEDIDOS, STOCK, RECEPCION.

    Returns:
        Diccionario con las hojas creadas {nombre: worksheet}.
    """
    logger.info("Paso 1: Creando estructura base de pestañas...")

    def _obtener_o_crear(nombre: str, filas: int = 100, cols: int = 15) -> gspread.Worksheet:
        try:
            ws = sh.worksheet(nombre)
            ws.clear()
            logger.info("  Pestaña '%s' limpiada.", nombre)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=nombre, rows=str(filas), cols=str(cols))
            logger.info("  Pestaña '%s' creada.", nombre)
        return ws

    # Capa de datos interna (sincronizada con IMPORTRANGE desde el maestro)
    ws_db = _obtener_o_crear("_DB_INTERNAL")
    formula_importrange = f'=IMPORTRANGE("{id_maestro}", "MASTER_SKU!A1:F100")'
    ws_db.update_acell("A1", formula_importrange)

    # Capa de interfaz de pedidos
    ws_pedidos = _obtener_o_crear("PEDIDOS")
    ws_pedidos.append_row(["SKU_ID", "Producto", "Cantidad", "Pedidos Acumulados", "Confirmar", "Log"])

    # Fórmulas XLOOKUP en columna A (SKU_ID auto-calculado desde el nombre elegido en B)
    formulas_sku = [
        [f'=IF(B{i}="", "", XLOOKUP(B{i}, _DB_INTERNAL!B:B, _DB_INTERNAL!A:A))']
        for i in range(2, 101)
    ]
    ws_pedidos.update(range_name="A2:A101", values=formulas_sku, value_input_option="USER_ENTERED")

    # Capa de inventario
    ws_stock = _obtener_o_crear("STOCK")
    ws_stock.append_row(["SKU_ID", "Producto", "Stock_Fisico", "Notas"])
    refs_a = [[f"=_DB_INTERNAL!A{i}"] for i in range(2, 101)]
    refs_b = [[f"=_DB_INTERNAL!B{i}"] for i in range(2, 101)]
    ws_stock.update(range_name="A2:A101", values=refs_a, value_input_option="USER_ENTERED")
    ws_stock.update(range_name="B2:B101", values=refs_b, value_input_option="USER_ENTERED")

    # Capa de calidad / recepción
    ws_rec = _obtener_o_crear("RECEPCION")
    ws_rec.append_row(["ID_Pedido", "SKU_ID", "Producto", "Cant_Pedida", "Cant_Recibida", "Estado_Articulo", "Notas"])

    # Capa de reclamos
    ws_reclamos = _obtener_o_crear("RECLAMOS")
    ws_reclamos.append_row(["ID_HISTORIAL", "SKU_ID", "Producto", "Cant_Original_Pedida", "Cant_Faltante", "Notas_Problema", "Accion_Resolucion", "Procesado"])

    # Eliminar hoja default si existe
    for nombre_default in ["Hoja 1", "Sheet1", "Hoja1"]:
        try:
            sh.del_worksheet(sh.worksheet(nombre_default))
            logger.info("  Hoja default '%s' eliminada.", nombre_default)
        except (gspread.WorksheetNotFound, Exception):
            pass

    return {
        "_DB_INTERNAL": ws_db,
        "PEDIDOS": ws_pedidos,
        "STOCK": ws_stock,
        "RECEPCION": ws_rec,
        "RECLAMOS": ws_reclamos,
    }


# ---------------------------------------------------------------------------
# PASO 2 — Aplicar validaciones de datos y seguridad
# ---------------------------------------------------------------------------

def _aplicar_validaciones(sh: gspread.Spreadsheet, hojas: dict) -> None:
    """
    Aplica dropdowns, checkboxes y protecciones de columnas.
    """
    logger.info("Paso 2: Aplicando validaciones de datos y seguridad...")

    ws_pedidos = hojas["PEDIDOS"]
    ws_db = hojas["_DB_INTERNAL"]
    ws_rec = hojas["RECEPCION"]

    requests = [
        # Ocultar _DB_INTERNAL
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": ws_db.id,
                    "hidden": True,
                },
                "fields": "hidden",
            }
        },
        # Dropdown en PEDIDOS!B2:B100 desde _DB_INTERNAL!$B$2:$B$100
        {
            "setDataValidation": {
                "range": {
                    "sheetId": ws_pedidos.id,
                    "startRowIndex": 1, "endRowIndex": 100,
                    "startColumnIndex": 1, "endColumnIndex": 2,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_RANGE",
                        "values": [{"userEnteredValue": "=_DB_INTERNAL!$B$2:$B$100"}],
                    },
                    "showCustomUi": True,
                    "strict": True,
                },
            }
        },
        # Checkbox en PEDIDOS!E2:E100 (Confirmar)
        {
            "setDataValidation": {
                "range": {
                    "sheetId": ws_pedidos.id,
                    "startRowIndex": 1, "endRowIndex": 100,
                    "startColumnIndex": 4, "endColumnIndex": 5,
                },
                "rule": {
                    "condition": {"type": "BOOLEAN"},
                    "showCustomUi": True,
                },
            }
        },
        # Protección de columna A (SKU_ID, auto-calculado)
        {
            "addProtectedRange": {
                "protectedRange": {
                    "range": {
                        "sheetId": ws_pedidos.id,
                        "startRowIndex": 1, "endRowIndex": 100,
                        "startColumnIndex": 0, "endColumnIndex": 1,
                    },
                    "description": "Protección SKU_ID (fórmula automática)",
                    "warningOnly": True,
                }
            }
        },
        # Resaltar columna C (Cantidad) en amarillo claro para guiar al usuario
        {
            "repeatCell": {
                "range": {
                    "sheetId": ws_pedidos.id,
                    "startRowIndex": 1, "endRowIndex": 100,
                    "startColumnIndex": 2, "endColumnIndex": 3,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.8}
                    }
                },
                "fields": "userEnteredFormat.backgroundColor",
            }
        },
        # Dropdown en RECEPCION!F2:F100 (Estado_Articulo)
        {
            "setDataValidation": {
                "range": {
                    "sheetId": ws_rec.id,
                    "startRowIndex": 1, "endRowIndex": 100,
                    "startColumnIndex": 5, "endColumnIndex": 6,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [
                            {"userEnteredValue": "OK"},
                            {"userEnteredValue": "DAÑADO"},
                            {"userEnteredValue": "FALTANTE"},
                            {"userEnteredValue": "RECHAZADO"}
                        ],
                    },
                    "showCustomUi": True,
                    "strict": True,
                },
            }
        },
        # Formato condicional: OK (Verde)
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{"sheetId": ws_rec.id, "startRowIndex": 1, "endRowIndex": 100, "startColumnIndex": 5, "endColumnIndex": 6}],
                    "booleanRule": {
                        "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "OK"}]},
                        "format": {"backgroundColor": {"red": 0.85, "green": 0.93, "blue": 0.83}}
                    }
                },
                "index": 0
            }
        },
        # Formato condicional: DAÑADO / FALTANTE (Amarillo)
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{"sheetId": ws_rec.id, "startRowIndex": 1, "endRowIndex": 100, "startColumnIndex": 5, "endColumnIndex": 6}],
                    "booleanRule": {
                        "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "DAÑADO"}]},
                        "format": {"backgroundColor": {"red": 1.0, "green": 0.9, "blue": 0.6}}
                    }
                },
                "index": 1
            }
        },
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{"sheetId": ws_rec.id, "startRowIndex": 1, "endRowIndex": 100, "startColumnIndex": 5, "endColumnIndex": 6}],
                    "booleanRule": {
                        "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "FALTANTE"}]},
                        "format": {"backgroundColor": {"red": 1.0, "green": 0.9, "blue": 0.6}}
                    }
                },
                "index": 2
            }
        },
        # Formato condicional: RECHAZADO (Rojo)
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{"sheetId": ws_rec.id, "startRowIndex": 1, "endRowIndex": 100, "startColumnIndex": 5, "endColumnIndex": 6}],
                    "booleanRule": {
                        "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "RECHAZADO"}]},
                        "format": {"backgroundColor": {"red": 0.96, "green": 0.8, "blue": 0.8}}
                    }
                },
                "index": 3
            }
        },
        # Fondo gris para columnas de solo lectura en PEDIDOS (A, D, F)
        {
            "repeatCell": {
                "range": {"sheetId": ws_pedidos.id, "startRowIndex": 1, "endRowIndex": 100, "startColumnIndex": 0, "endColumnIndex": 1},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": ws_pedidos.id, "startRowIndex": 1, "endRowIndex": 100, "startColumnIndex": 3, "endColumnIndex": 4},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": ws_pedidos.id, "startRowIndex": 1, "endRowIndex": 100, "startColumnIndex": 5, "endColumnIndex": 6},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        },
        # Fondo gris para columnas de solo lectura en RECEPCION (A a D)
        {
            "repeatCell": {
                "range": {"sheetId": ws_rec.id, "startRowIndex": 1, "endRowIndex": 100, "startColumnIndex": 0, "endColumnIndex": 4},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        },
        # Resaltar columna E (Cant_Recibida) en RECEPCION en amarillo claro para guiar al usuario
        {
            "repeatCell": {
                "range": {"sheetId": ws_rec.id, "startRowIndex": 1, "endRowIndex": 100, "startColumnIndex": 4, "endColumnIndex": 5},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.8}}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        },
        # Validaciones para RECLAMOS (Dropdown)
        {
            "setDataValidation": {
                "range": {
                    "sheetId": hojas["RECLAMOS"].id,
                    "startRowIndex": 1, "endRowIndex": 100,
                    "startColumnIndex": 6, "endColumnIndex": 7,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [
                            {"userEnteredValue": "ESPERANDO_MERCADERIA"},
                            {"userEnteredValue": "RESUELTO_ENTREGADO"},
                            {"userEnteredValue": "CANCELADO_SIN_STOCK"},
                        ],
                    },
                    "showCustomUi": True,
                    "strict": True,
                },
            }
        },
        # Fondo gris A-F en RECLAMOS
        {
            "repeatCell": {
                "range": {"sheetId": hojas["RECLAMOS"].id, "startRowIndex": 1, "endRowIndex": 100, "startColumnIndex": 0, "endColumnIndex": 6},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        },
        # Resaltar amarillo la columna G en RECLAMOS
        {
            "repeatCell": {
                "range": {"sheetId": hojas["RECLAMOS"].id, "startRowIndex": 1, "endRowIndex": 100, "startColumnIndex": 6, "endColumnIndex": 7},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.8}}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        },
    ]

    sh.batch_update({"requests": requests})
    logger.info("  Validaciones aplicadas correctamente.")


# ---------------------------------------------------------------------------
# PASO 3 — Aplicar formato visual corporativo
# ---------------------------------------------------------------------------

def _aplicar_formato_corporativo(hojas: dict) -> None:
    """Aplica el formato de encabezado corporativo a todas las pestañas visibles."""
    logger.info("Paso 3: Aplicando formato corporativo a encabezados...")

    for nombre, ws in hojas.items():
        if nombre == "_DB_INTERNAL":
            continue
        ws.format("A1:Z1", FORMATO_ENCABEZADO)
        logger.info("  Encabezado formateado en '%s'.", nombre)


# ---------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL
# ---------------------------------------------------------------------------

def configurar_local(nombre_local: str = NOMBRE_TEMPLATE) -> None:
    """
    Ejecuta el setup completo de un spreadsheet SAI_Local en orden:
    estructura base → validaciones → formato corporativo.

    Args:
        nombre_local: Nombre exacto del spreadsheet en Google Drive.
    """
    logger.info("Iniciando configuración de local: '%s'", nombre_local)

    try:
        cliente = obtener_cliente_gsheets()
        sh_maestro = obtener_spreadsheet_maestro()
        id_maestro = sh_maestro.id
    except Exception as error:
        logger.error("No se pudo conectar al ecosistema Google: %s", error)
        return

    try:
        sh = cliente.open(nombre_local)
        logger.info("Spreadsheet '%s' abierto. ID: %s", nombre_local, sh.id)
    except gspread.SpreadsheetNotFound:
        logger.error(
            "Spreadsheet '%s' no encontrado. "
            "Asegúrate de haberlo creado y compartido con la cuenta de servicio.",
            nombre_local,
        )
        return
    except Exception as error:
        logger.error("Error al abrir '%s': %s", nombre_local, error)
        return

    try:
        hojas = _crear_estructura_base(sh, id_maestro)
        _aplicar_validaciones(sh, hojas)
        _aplicar_formato_corporativo(hojas)

        logger.info(
            "Configuración de '%s' completada exitosamente. URL: "
            "https://docs.google.com/spreadsheets/d/%s",
            nombre_local, sh.id,
        )
    except Exception as error:
        logger.error("Error durante la configuración de '%s': %s", nombre_local, error)


if __name__ == "__main__":
    configurar_logging()
    nombre = sys.argv[1] if len(sys.argv) > 1 else NOMBRE_TEMPLATE
    configurar_local(nombre)
