"""
warehouse_sync.py — Sincronización del historial de pedidos al Data Warehouse BI.
El ID del spreadsheet destino se lee desde WAREHOUSE_SPREADSHEET_ID en .env.
"""
import logging
import os

from dotenv import load_dotenv

from core.auth import obtener_cliente_gsheets
from core.db_handler import MasterProv, MasterSku, OrderHistory, Session

load_dotenv()

logger = logging.getLogger(__name__)


def sync_to_warehouse() -> None:
    """Vuelca todo el historial de OrderHistory al spreadsheet de BI con JOINs de nombres."""
    # Verificar si la sincronización está habilitada
    habilitado = os.getenv("WAREHOUSE_SYNC_ENABLED", "false").lower()
    if habilitado != "true":
        logger.info("Sincronización de warehouse deshabilitada (WAREHOUSE_SYNC_ENABLED=false).")
        return

    id_warehouse = os.getenv("WAREHOUSE_SPREADSHEET_ID")
    if not id_warehouse:
        logger.warning(
            "WAREHOUSE_SPREADSHEET_ID no configurado en .env. "
            "Sincronización de warehouse omitida."
        )
        return

    logger.info("Sincronizando data warehouse (BI)...")

    try:
        cliente = obtener_cliente_gsheets()
        sh = cliente.open_by_key(id_warehouse)
        logger.info("Conectado al warehouse: %s", sh.title)
    except Exception as error:
        logger.error("No se pudo conectar al warehouse: %s", error)
        return

    # Preparar pestaña maestra
    nombre_hoja = "HOJA_MAESTRA_BI"
    try:
        ws = sh.worksheet(nombre_hoja)
    except Exception:
        ws = sh.add_worksheet(title=nombre_hoja, rows="1000", cols="15")
        logger.info("Pestaña '%s' creada.", nombre_hoja)

    ws.clear()

    encabezados = [
        "ID", "SKU_ID", "SKU_Nombre", "Centro_Costo", "Cant_Pedida", "Cant_Recibida",
        "Proveedor_ID", "Proveedor_Nombre", "Fecha_Pedido", "Fecha_Archivo",
        "Precio_Unit", "Total_Linea", "Status_Cumplimiento", "Notas",
    ]
    ws.append_row(encabezados)
    ws.format(
        "A1:Z1",
        {
            "textFormat": {
                "bold": True,
                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            },
            "backgroundColor": {"red": 0.1, "green": 0.1, "blue": 0.1},
            "horizontalAlignment": "CENTER",
        },
    )

    # Extraer datos de SQLite con JOINs
    session = Session()
    try:
        resultados = (
            session.query(OrderHistory, MasterProv.nombre, MasterSku.nombre)
            .outerjoin(MasterProv, OrderHistory.proveedor_id == MasterProv.proveedor_id)
            .outerjoin(MasterSku, OrderHistory.sku_id == MasterSku.sku_id)
            .all()
        )

        if not resultados:
            logger.info("No hay datos históricos para sincronizar.")
            return

        filas = []
        for h, nombre_prov, nombre_sku in resultados:
            filas.append([
                h.id,
                h.sku_id,
                nombre_sku or "SKU Desconocido",
                h.centro_costo,
                h.cantidad,
                h.received_quantity,
                h.proveedor_id,
                nombre_prov or "Proveedor Desconocido",
                h.fecha_registro.strftime("%Y-%m-%d") if h.fecha_registro else "",
                h.fecha_archivo.strftime("%Y-%m-%d") if h.fecha_archivo else "",
                h.precio_compra_final,
                h.total_linea,
                h.fulfillment_status,
                h.incident_notes or "",
            ])

        ws.append_rows(filas, value_input_option="RAW")
        logger.info("%d registros inyectados en el warehouse.", len(filas))

    except Exception as error:
        logger.error("Error en inyección al warehouse: %s", error)
    finally:
        session.close()


if __name__ == "__main__":
    from core.log_config import configurar_logging
    configurar_logging()
    sync_to_warehouse()
