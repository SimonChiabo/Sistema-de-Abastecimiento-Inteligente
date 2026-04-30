"""
main.py — Orquestador principal del ciclo SAI Multi-Local.
Lee pedidos de cada spreadsheet local, los consolida en SQLite,
procesa el feedback de recepción y sincroniza el warehouse.
"""
import logging
import os
import argparse

from dotenv import load_dotenv

from core.auth import obtener_cliente_gsheets, obtener_spreadsheet_maestro
from core.db_handler import OrderBuffer, OrderStatus, Session, add_to_buffer
from core.log_config import configurar_logging
from core.reception import process_reception_feedback, process_claims_feedback

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


def run_orchestrator(modo_manual: bool = False) -> None:
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

            encabezados = filas[0]
            actualizaciones_batch = []

            for indice, fila in enumerate(filas[1:], start=2):
                try:
                    sku_id = str(fila[0]).strip()
                    if not sku_id:
                        continue

                    cantidad_str = str(fila[2]).strip()
                    confirmado = str(fila[4]).upper() == "TRUE"

                    # 1. Si hay un pedido nuevo, lo procesamos
                    if confirmado:
                        if cantidad_str:
                            logger.info("  [NUEVO PEDIDO - SKU: %s] Cantidad: %s", sku_id, cantidad_str)
                            cantidad = float(cantidad_str.replace(",", "."))

                            # Lógica de horarios
                            prov_id = sku_a_prov.get(sku_id)
                            hora_limite_str = hora_limite_prov.get(prov_id, "23:59")
                            ahora = dt.now().time()
                            hora_limite = dt.strptime(hora_limite_str, "%H:%M").time()

                            estatus = OrderStatus.PENDING
                            mensaje_log = f"OK {dt.now().strftime('%H:%M')}"

                            if not modo_manual and ahora > hora_limite:
                                estatus = OrderStatus.LATE
                                mensaje_log = f"LATE ({hora_limite_str})"

                            if modo_manual:
                                mensaje_log = f"MANUAL {dt.now().strftime('%H:%M')}"

                            # Registrar en DB local
                            add_to_buffer(sku_id, cantidad, nombre_local, proveedor_id=prov_id, status=estatus)
                            
                            # Preparar limpieza de cantidad y log
                            actualizaciones_batch.append({"range": f"C{indice}", "values": [[""]]})
                            actualizaciones_batch.append({"range": f"F{indice}", "values": [[mensaje_log]]})

                        # SIEMPRE reseteamos el checkbox si estaba marcado, para limpiar la UI
                        actualizaciones_batch.append({"range": f"E{indice}", "values": [[False]]})

                    # 2. SIEMPRE actualizamos el acumulado (Columna D) para reflejar la realidad de la DB
                    acumulado_real = _obtener_acumulado_de_db(sku_id, nombre_local)
                    actualizaciones_batch.append({"range": f"D{indice}", "values": [[acumulado_real if acumulado_real > 0 else ""]]})

                    # 3. Si no hay nada acumulado, limpiamos también el LOG para resetear la UI
                    if acumulado_real == 0:
                        actualizaciones_batch.append({"range": f"F{indice}", "values": [[""]]})

                except Exception as error_fila:
                    logger.warning("Error en fila %d: %s", indice, error_fila)

            # Ejecutar todas las actualizaciones de este local en un solo viaje
            if actualizaciones_batch:
                ws_pedidos.batch_update(actualizaciones_batch)

        except Exception as error_local:
            logger.error("Error crítico en local %s: %s", nombre_local, error_local)

    # 3. Procesar conciliación distribuida
    process_reception_feedback()
    process_claims_feedback()

    # 4. Sincronizar data warehouse (solo si está habilitado en .env)
    if os.getenv("WAREHOUSE_SYNC_ENABLED", "false").lower() == "true":
        from warehouse_sync import sync_to_warehouse
        sync_to_warehouse()
    else:
        logger.info("Warehouse sync desactivado (WAREHOUSE_SYNC_ENABLED=false).")

    logger.info("Ciclo SAI Multi-Local finalizado.")
    
    if modo_manual:
        from core.notifier import send_generic_email
        destinatario_demo = os.getenv("ADMIN_EMAIL", "simonchiabo@gmail.com")
        logger.info("  [DEMO] Enviando confirmación de captura a %s...", destinatario_demo)
        send_generic_email(
            subject="DEMO SAI: Captura de Pedidos Exitosa",
            body="""
            <h3>¡El ciclo de captura ha finalizado!</h3>
            <p>Los pedidos de los locales han sido procesados y consolidados en la base de datos central.</p>
            <p><strong>Próximo paso:</strong> Ejecutar el despachador (mailer) para generar las Órdenes de Compra.</p>
            """,
            to_email=destinatario_demo,
            is_html=True
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Orquestador SAI Multi-Local")
    parser.add_argument(
        "--manual", 
        action="store_true", 
        help="Levanta los pedidos ignorando la restricción de horario (Modo Demo)"
    )
    args = parser.parse_args()

    configurar_logging()
    run_orchestrator(modo_manual=args.manual)
