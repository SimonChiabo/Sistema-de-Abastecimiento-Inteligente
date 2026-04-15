"""
audit_job.py — Job de auditoría productiva.
Exporta el historial a CSV, calcula métricas y envía el reporte por email.
"""
import logging
from datetime import datetime

from analytics_export import export_to_csv
from core.db_handler import OrderHistory, Session
from core.log_config import configurar_logging
from core.notifier import send_audit_report

logger = logging.getLogger(__name__)


def _calcular_metricas() -> dict:
    """Calcula las métricas clave del historial para el resumen del correo."""
    session = Session()
    try:
        datos = session.query(OrderHistory).all()
        total_ordenes = len(datos)
        monto_total = sum(h.total_linea for h in datos if h.total_linea)
        pendientes_conciliacion = len(
            [h for h in datos if h.fulfillment_status == "SENT"]
        )
        return {
            "total_orders": total_ordenes,
            "total_amount": monto_total,
            "pending_conciliation": pendientes_conciliacion,
        }
    finally:
        session.close()


def run_production_audit() -> None:
    """Ejecuta el ciclo completo de auditoría: exportar → calcular → notificar."""
    logger.info("Iniciando proceso productivo de auditoría: %s", datetime.now())

    nombre_archivo = "SAI_Analitica_Global.csv"

    # 1. Exportar datos a CSV
    cantidad = export_to_csv(nombre_archivo)

    if cantidad > 0:
        # 2. Calcular métricas para el resumen ejecutivo
        metricas = _calcular_metricas()

        # 3. Enviar correo con reporte y métricas
        exito = send_audit_report(nombre_archivo, metricas)

        if exito:
            logger.info("Ejecución productiva exitosa. Todo en orden.")
    else:
        logger.warning("No se registran datos en el historial para procesar.")


if __name__ == "__main__":
    configurar_logging()
    run_production_audit()
