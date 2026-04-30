"""
core/reception.py — Sincronización de pestañas RECEPCION y procesamiento
de feedback de locales hacia la base de datos central.
"""
import logging
import os

from dotenv import load_dotenv

from core.auth import obtener_cliente_gsheets
from core.db_handler import OrderHistory, Session, update_history_fulfillment, resolve_claim

load_dotenv()

logger = logging.getLogger(__name__)

PREFIJO_LOCAL = os.getenv("LOCAL_PREFIX", "SAI_Local_")


def sync_reception_tab() -> None:
    """Distribuye los registros SENT del historial a las pestañas RECEPCION de cada local."""
    logger.info("Sincronizando pestañas RECEPCION (distribuidas)...")
    cliente = obtener_cliente_gsheets()

    # Discovery de locales
    todos_los_archivos = cliente.list_spreadsheet_files()
    archivos_locales = [f for f in todos_los_archivos if f["name"].startswith(PREFIJO_LOCAL)]

    session = Session()
    try:
        historial_enviado = (
            session.query(OrderHistory)
            .filter(OrderHistory.fulfillment_status == "SENT")
            .all()
        )

        for entrada in archivos_locales:
            nombre_local = entrada["name"]
            id_local = entrada["id"]

            pedidos_local = [h for h in historial_enviado if h.centro_costo == nombre_local]

            if not pedidos_local:
                continue

            logger.info("Inyectando %d pedidos en %s...", len(pedidos_local), nombre_local)

            try:
                sh = cliente.open_by_key(id_local)
                ws = sh.worksheet("RECEPCION")

                # Col H = "Procesado" (vacío al inyectar = pendiente de procesar)
                encabezados = [
                    "ID_HISTORIAL", "SKU_ID", "Producto",
                    "Cant_Pedida", "Cant_Recibida", "Estado_Articulo", "Notas", "Procesado",
                ]
                ws.clear()
                ws.append_row(encabezados)

                filas = [
                    [h.id, h.sku_id, "", h.cantidad, "", "", "", ""]
                    for h in pedidos_local
                ]
                ws.append_rows(filas)
                ws.format(
                    "A1:H1",
                    {
                        "textFormat": {"bold": True},
                        "backgroundColor": {"red": 0.1, "green": 0.5, "blue": 0.1},
                    },
                )

            except Exception as error:
                logger.error("Error en %s: %s", nombre_local, error)

        logger.info("Sincronización descentralizada completada.")
    finally:
        session.close()


def process_reception_feedback() -> None:
    """Recolecta el feedback de RECEPCION desde cada local y actualiza la base de datos central.

    Las filas con columna 'Procesado' == 'SI' se saltan para evitar reprocesamiento.
    Cuando una fila se procesa con éxito, se escribe 'SI' en la columna H.
    """
    logger.info("Procesando feedback de recepción (multi-local)...")
    cliente = obtener_cliente_gsheets()

    todos_los_archivos = cliente.list_spreadsheet_files()
    archivos_locales = [f for f in todos_los_archivos if f["name"].startswith(PREFIJO_LOCAL)]

    for entrada in archivos_locales:
        nombre_local = entrada["name"]
        try:
            sh = cliente.open_by_key(entrada["id"])
            ws = sh.worksheet("RECEPCION")
            datos = ws.get_all_records()

            if not datos:
                continue

            filas_procesadas = 0
            filas_para_borrar = []

            # start=2: fila 1 = encabezados, filas de datos comienzan en fila 2
            for indice_fila, fila in enumerate(datos, start=2):
                # Saltar filas ya procesadas en ciclos anteriores
                procesado = str(fila.get("Procesado", "")).strip().upper()
                if procesado == "SI":
                    filas_para_borrar.append(indice_fila)
                    continue

                id_historial = fila.get("ID_HISTORIAL")
                if not id_historial or str(id_historial).strip() == "":
                    continue

                try:
                    raw_recibida = str(fila.get("Cant_Recibida", "")).strip()
                    raw_estado = str(fila.get("Estado_Articulo", "")).strip().upper()

                    # Si el operario no ha llenado los campos, saltamos esta fila
                    if not raw_recibida or not raw_estado:
                         continue

                    cant_pedida = float(fila["Cant_Pedida"])
                    cant_recibida = float(raw_recibida)
                    estado = raw_estado
                    notas = fila.get("Notas", "")

                    if estado in ("CANCELADO", "RECHAZADO"):
                        estatus = "CANCELLED"
                    elif estado in ("DAÑADO", "FALTANTE") or cant_recibida < cant_pedida:
                        estatus = "PENDING_RECTIFICATION"
                    else:
                        estatus = "COMPLETE"

                    exito = update_history_fulfillment(
                        id_historial, cant_recibida, estatus, f"[{estado}] {notas}"
                    )

                    if exito:
                        # Marcar fila como procesada
                        ws.update_cell(indice_fila, 8, "SI")
                        filas_para_borrar.append(indice_fila)
                        filas_procesadas += 1
                        logger.info(
                            "Fila %d marcada como procesada (ID_HISTORIAL: %s).",
                            indice_fila, id_historial,
                        )
                        
                        if estatus == "PENDING_RECTIFICATION":
                            cant_faltante = cant_pedida - cant_recibida
                            try:
                                ws_reclamos = sh.worksheet("RECLAMOS")
                                ws_reclamos.append_row([
                                    id_historial, fila.get("SKU_ID"), fila.get("Producto"),
                                    cant_pedida, cant_faltante, f"[{estado}] {notas}",
                                    "ESPERANDO_MERCADERIA", ""
                                ])
                                logger.info("  Reclamo inyectado en RECLAMOS para %s", id_historial)
                            except Exception as e_reclamo:
                                logger.error("  No se pudo inyectar reclamo: %s", e_reclamo)

                except (ValueError, KeyError) as error_fila:
                    logger.warning(
                        "Error en fila %d de %s: %s", indice_fila, nombre_local, error_fila
                    )

            # Limpieza de filas procesadas (de abajo hacia arriba)
            if filas_para_borrar:
                for idx in sorted(filas_para_borrar, reverse=True):
                    ws.delete_rows(idx)
                logger.info("  Borradas %d filas procesadas de RECEPCION en %s", len(filas_para_borrar), nombre_local)

            logger.info(
                "Feedback procesado para %s: %d filas nuevas.",
                nombre_local, filas_procesadas,
            )

        except Exception as error:
            logger.error("Error leyendo feedback de %s: %s", nombre_local, error)

def process_claims_feedback() -> None:
    """Recolecta la resolución de la pestaña RECLAMOS y actualiza la BD."""
    logger.info("Procesando resoluciones de reclamos (multi-local)...")
    cliente = obtener_cliente_gsheets()
    todos_los_archivos = cliente.list_spreadsheet_files()
    archivos_locales = [f for f in todos_los_archivos if f["name"].startswith(PREFIJO_LOCAL)]

    for entrada in archivos_locales:
        nombre_local = entrada["name"]
        try:
            sh = cliente.open_by_key(entrada["id"])
            try:
                ws_reclamos = sh.worksheet("RECLAMOS")
            except Exception:
                continue

            datos = ws_reclamos.get_all_records()
            if not datos:
                continue
            
            filas_para_borrar = []
            
            for indice_fila, fila in enumerate(datos, start=2):
                procesado = str(fila.get("Procesado", "")).strip().upper()
                if procesado == "SI":
                    filas_para_borrar.append(indice_fila)
                    continue
                
                accion = str(fila.get("Accion_Resolucion", "")).strip().upper()
                if accion in ("RESUELTO_ENTREGADO", "CANCELADO_SIN_STOCK"):
                    id_historial = fila.get("ID_HISTORIAL")
                    if id_historial:
                        exito = resolve_claim(id_historial, accion)
                        if exito:
                            ws_reclamos.update_cell(indice_fila, 8, "SI")
                            filas_para_borrar.append(indice_fila)
                            logger.info("  Reclamo resuelto %s: %s", id_historial, accion)
            
            # Limpiar filas procesadas de abajo hacia arriba para evitar desfasaje de índices
            if filas_para_borrar:
                for idx in sorted(filas_para_borrar, reverse=True):
                    ws_reclamos.delete_rows(idx)
                logger.info("  Borradas %d filas procesadas de RECLAMOS en %s", len(filas_para_borrar), nombre_local)

        except Exception as e:
            logger.error("Error procesando reclamos en %s: %s", nombre_local, e)

if __name__ == "__main__":
    sync_reception_tab()
