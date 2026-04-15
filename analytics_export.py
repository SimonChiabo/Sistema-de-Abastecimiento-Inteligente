"""
analytics_export.py — Exportador de análitica histórica a CSV para Power BI.
"""
import csv
import logging
from datetime import datetime

from core.db_handler import MasterProv, MasterSku, OrderHistory, Session

logger = logging.getLogger(__name__)


def export_to_csv(filename: str = "SAI_Analitica_Global.csv") -> int:
    """
    Exporta toda la tabla de historial a un CSV estructurado para Power BI.

    Args:
        filename: Ruta del archivo CSV de salida.

    Returns:
        Cantidad de registros exportados. 0 si no hay datos o hay error.
    """
    logger.info("Generando export de analítica: %s", filename)
    session = Session()
    try:
        resultados = (
            session.query(OrderHistory, MasterProv.nombre, MasterSku.nombre)
            .outerjoin(MasterProv, OrderHistory.proveedor_id == MasterProv.proveedor_id)
            .outerjoin(MasterSku, OrderHistory.sku_id == MasterSku.sku_id)
            .all()
        )

        if not resultados:
            logger.info("No hay datos históricos para exportar.")
            return 0

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "ID", "SKU_ID", "SKU_Nombre", "Centro_Costo", "Cant_Pedida",
                "Cant_Recibida", "Proveedor_ID", "Proveedor_Nombre", "Fecha_Pedido",
                "Fecha_Archivo", "Precio_Unit", "Total_Linea", "Status_Cumplimiento", "Notas",
            ])

            for h, nombre_prov, nombre_sku in resultados:
                writer.writerow([
                    h.id, h.sku_id,
                    nombre_sku or "SKU Desconocido",
                    h.centro_costo, h.cantidad, h.received_quantity,
                    h.proveedor_id,
                    nombre_prov or "Proveedor Desconocido",
                    h.fecha_registro.strftime("%Y-%m-%d %H:%M") if h.fecha_registro else "",
                    h.fecha_archivo.strftime("%Y-%m-%d %H:%M") if h.fecha_archivo else "",
                    h.precio_compra_final, h.total_linea,
                    h.fulfillment_status, h.incident_notes or "",
                ])

        logger.info("%d registros exportados a %s.", len(resultados), filename)
        return len(resultados)

    except Exception as error:
        logger.error("Error en export a CSV: %s", error)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    from core.log_config import configurar_logging
    configurar_logging()
    export_to_csv()
