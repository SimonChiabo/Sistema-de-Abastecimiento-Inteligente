"""
main.py — Orquestador principal del ciclo SAI Multi-Local.
Lee pedidos de cada spreadsheet local, los consolida en SQLite,
procesa el feedback de recepción y sincroniza el warehouse.
"""
import logging
import os

from dotenv import load_dotenv

from core.auth import obtener_cliente_gsheets, obtener_spreadsheet_maestro
from core.db_handler import OrderBuffer, OrderStatus, Session, add_to_buffer
from core.log_config import configurar_logging
from core.reception import process_reception_feedback

load_dotenv()

logger = logging.getLogger(__name__)

PREFIJO_LOCAL = os.getenv("LOCAL_PREFIX", "SAI_Local_")


def _obtener_acumulado_de_db(sku_id: str, centro_costo: str) -> float:
    """Obtiene la cantidad total acumulada para un SKU en estado PENDING."""
    session = Session()
    try:
        pedido = (
            session.query(OrderBuffer)
            .filter(
                OrderBuffer.sku_id == sku_id,
                OrderBuffer.centro_costo == centro_costo,
                OrderBuffer.status == OrderStatus.PENDING,
            )
            .first()
        )
        return pedido.cantidad if pedido else 0
    finally:
        session.close()


def run_orchestrator() -> None:
    """Ejecuta el ciclo completo SAI: lectura de pedidos → buffer → feedback → warehouse."""
    from datetime import datetime

    logger.info(
        "Iniciando ciclo SAI Multi-Local: %s",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    # 1. Conexión y descubrimiento de locales
    try:
        cliente = obtener_cliente_gsheets()
        sh_maestro = obtener_spreadsheet_maestro()

        skus = sh_maestro.worksheet("MASTER_SKU").get_all_records()
        proveedores = sh_maestro.worksheet("MASTER_PROV").get_all_records()

        sku_a_prov = {str(r["SKU_ID"]).strip(): str(r["Proveedor_ID"]).strip() for r in skus}
        hora_limite_prov = {
            str(r["Proveedor_ID"]).strip(): str(r["Hora_Limite"]).strip()
            for r in proveedores
        }

        todos_los_archivos = cliente.list_spreadsheet_files()
        archivos_locales = [f for f in todos_los_archivos if f["name"].startswith(PREFIJO_LOCAL)]
        logger.info("Se encontraron %d locales para procesar.", len(archivos_locales))

    except Exception as error:
        logger.error("Error crítico: no se pudo conectar al ecosistema. %s", error)
        return

    # 2. Procesar cada local
    from datetime import datetime as dt

    for entrada in archivos_locales:
        nombre_local = entrada["name"]
        logger.info("Procesando local: %s", nombre_local)

        try:
            sh_local = cliente.open_by_key(entrada["id"])
            ws_pedidos = sh_local.worksheet("PEDIDOS")

            filas = ws_pedidos.get_all_values()
            if len(filas) < 2:
                continue

            for indice, fila in enumerate(filas[1:], start=2):
                try:
                    sku_id = str(fila[0]).strip()
                    cantidad_str = str(fila[2]).strip()
                    confirmado = str(fila[4]).upper() == "TRUE"

                    if not confirmado or not sku_id or not cantidad_str:
                        continue

                    logger.info("  [SKU: %s] Cantidad: %s", sku_id, cantidad_str)
                    cantidad = float(cantidad_str.replace(",", "."))

                    # Lógica de horarios
                    prov_id = sku_a_prov.get(sku_id)
                    hora_limite_str = hora_limite_prov.get(prov_id, "23:59")

                    ahora = dt.now().time()
                    hora_limite = dt.strptime(hora_limite_str, "%H:%M").time()

                    estatus = OrderStatus.PENDING
                    mensaje_log = f"OK {dt.now().strftime('%H:%M')}"

                    if ahora > hora_limite:
                        estatus = OrderStatus.LATE
                        mensaje_log = f"LATE ({hora_limite_str})"

                    # Registrar en DB local
                    add_to_buffer(sku_id, cantidad, nombre_local, proveedor_id=prov_id)

                    # Feedback al local sheet
                    acumulado = _obtener_acumulado_de_db(sku_id, nombre_local)
                    actualizaciones = [
                        {"range": f"C{indice}", "values": [[""]]},
                        {"range": f"D{indice}", "values": [[acumulado]]},
                        {"range": f"E{indice}", "values": [[False]]},
                        {"range": f"F{indice}", "values": [[mensaje_log]]},
                    ]
                    ws_pedidos.batch_update(actualizaciones)

                except Exception as error_fila:
                    logger.warning("Error en fila %d: %s", indice, error_fila)

        except Exception as error_local:
            logger.error("Error crítico en local %s: %s", nombre_local, error_local)

    # 3. Procesar conciliación distribuida
    process_reception_feedback()

    # 4. Sincronizar data warehouse (solo si está habilitado en .env)
    if os.getenv("WAREHOUSE_SYNC_ENABLED", "false").lower() == "true":
        from warehouse_sync import sync_to_warehouse
        sync_to_warehouse()
    else:
        logger.info("Warehouse sync desactivado (WAREHOUSE_SYNC_ENABLED=false).")

    logger.info("Ciclo SAI Multi-Local finalizado.")


if __name__ == "__main__":
    configurar_logging()
    run_orchestrator()
