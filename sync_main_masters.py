"""
sync_main_masters.py — Escribe los datos maestros actualizados
(proveedores y SKUs) en el spreadsheet central de Google Sheets.
"""
import logging

from core.auth import obtener_spreadsheet_maestro

logger = logging.getLogger(__name__)


def update_main_masters() -> None:
    """Actualiza MASTER_PROV y MASTER_SKU en el spreadsheet principal."""
    logger.info("Actualizando maestros en spreadsheet principal...")

    try:
        sh = obtener_spreadsheet_maestro()
    except Exception as error:
        logger.error("No se pudo conectar al spreadsheet maestro: %s", error)
        return

    # 1. Actualizar MASTER_PROV
    logger.info("Actualizando MASTER_PROV...")
    ws_prov = sh.worksheet("MASTER_PROV")
    ws_prov.clear()

    encabezados_prov = ["Proveedor_ID", "Nombre", "Email", "Frecuencia", "Hora_Limite", "Dias_Programados"]
    datos_prov = [
        ["PROV-DEMO-01", "Distribuidora Global Carnicos",    "carnicos@demo.sai", "DIARIO", "18:00", "[0,1,2,3,4,5,6]"],
        ["PROV-DEMO-02", "Panificadora Industrial",          "pan@demo.sai",      "DIARIO", "18:00", "[0,1,2,3,4,5,6]"],
        ["PROV-DEMO-03", "Proveedor de Bebidas y Bodega",    "bebidas@demo.sai",  "DIARIO", "18:00", "[0,1,2,3,4,5,6]"],
        ["PROV-DEMO-04", "Suministros de Higiene Profesional","higiene@demo.sai", "DIARIO", "18:00", "[0,1,2,3,4,5,6]"],
    ]
    ws_prov.append_row(encabezados_prov)
    ws_prov.append_rows(datos_prov)
    logger.info("%d proveedores escritos.", len(datos_prov))

    # 2. Actualizar MASTER_SKU
    logger.info("Actualizando MASTER_SKU...")
    ws_sku = sh.worksheet("MASTER_SKU")
    ws_sku.clear()

    encabezados_sku = ["SKU_ID", "Nombre", "Categoría", "Presentación", "Proveedor_ID", "Precio_Ref"]
    datos_sku = [
        ["SKU-CAR-01", "Costillar Premium",      "Carnes",      "Por kg",        "PROV-DEMO-01", 15.50],
        ["SKU-CAR-02", "Lomo Vacuno",            "Carnes",      "Por kg",        "PROV-DEMO-01", 22.00],
        ["SKU-CAR-03", "Chorizo de Campo",       "Carnes",      "Pack 1kg",      "PROV-DEMO-01",  8.00],
        ["SKU-PAN-01", "Pan Baguette",           "Panificados", "Unidad",        "PROV-DEMO-02",  1.20],
        ["SKU-PAN-02", "Pan de Campo",           "Panificados", "Unidad",        "PROV-DEMO-02",  2.50],
        ["SKU-BEB-01", "Vino Malbec",            "Bebidas",     "Botella 750ml", "PROV-DEMO-03", 12.00],
        ["SKU-BEB-02", "Agua Mineral",           "Bebidas",     "Bidon 5L",      "PROV-DEMO-03",  0.80],
        ["SKU-BEB-03", "Cerveza Artesanal",      "Bebidas",     "Lata 473ml",    "PROV-DEMO-03",  4.50],
        ["SKU-HIG-01", "Detergente Industrial",  "Limpieza",    "Bidon 5L",      "PROV-DEMO-04",  8.50],
        ["SKU-HIG-02", "Desinfectante",          "Limpieza",    "Botella 1L",    "PROV-DEMO-04",  5.00],
    ]
    ws_sku.append_row(encabezados_sku)
    ws_sku.append_rows(datos_sku)
    logger.info("%d productos escritos.", len(datos_sku))

    # 3. Formateo de headers
    for ws in [ws_prov, ws_sku]:
        ws.format(
            "A1:Z1",
            {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                "horizontalAlignment": "CENTER",
            },
        )

    logger.info("Sincronización de maestros completada.")


if __name__ == "__main__":
    from core.log_config import configurar_logging
    configurar_logging()
    update_main_masters()
