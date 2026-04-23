"""
mailer.py — Orquestador de despacho SAI v2.0.
Consolida pedidos pendientes por proveedor, genera OCs HTML y las archiva.
"""
import json
import logging
import os
import argparse
from datetime import datetime

from dotenv import load_dotenv
from jinja2 import Template

from core.auth import obtener_cliente_gsheets, obtener_spreadsheet_maestro
from core.db_handler import OrderBuffer, OrderStatus, Session, archive_orders
from core.log_config import configurar_logging
from core.reception import sync_reception_tab

load_dotenv()

logger = logging.getLogger(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; }
        .header { background-color: #2c3e50; color: white; padding: 20px; border-top-left-radius: 5px; border-top-right-radius: 5px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #f2f2f2; font-weight: bold; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        .text-right { text-align: right; }
        .footer { margin-top: 30px; font-size: 0.85em; color: #7f8c8d; border-top: 1px solid #eee; padding-top: 10px; }
        .total-row { font-weight: bold; background-color: #ecf0f1 !important; }
    </style>
</head>
<body>
    <div class="header">
        <h2>Orden de Compra - SAI</h2>
        <p>Proveedor: {{ prov_nombre }} | Fecha Despacho: {{ fecha }}</p>
    </div>

    <table>
        <thead>
            <tr>
                <th>Producto</th>
                <th>Presentación</th>
                <th class="text-right">Cant. Total</th>
                <th class="text-right">Precio Unit.</th>
                <th class="text-right">Subtotal</th>
            </tr>
        </thead>
        <tbody>
            {% for item in items %}
            <tr>
                <td>{{ item.nombre }}</td>
                <td>{{ item.presentacion }}</td>
                <td class="text-right">{{ item.cantidad }}</td>
                <td class="text-right">${{ "{:,.2f}".format(item.precio_unit) }}</td>
                <td class="text-right">${{ "{:,.2f}".format(item.subtotal) }}</td>
            </tr>
            {% endfor %}
            <tr class="total-row">
                <td colspan="4" class="text-right">TOTAL ESTIMADO:</td>
                <td class="text-right">${{ "{:,.2f}".format(total_orden) }}</td>
            </tr>
        </tbody>
    </table>

    <div class="footer">
        <p>Este pedido consolida todos los requerimientos pendientes hasta la hora de corte.</p>
        <p>Identificador de Transacción: {{ trx_id }}</p>
    </div>
</body>
</html>
"""


def _obtener_datos_maestros() -> tuple[dict, dict]:
    """Obtiene los datos maestros de Google Sheets."""
    sh = obtener_spreadsheet_maestro()

    registros_sku = sh.worksheet("MASTER_SKU").get_all_records()
    registros_prov = sh.worksheet("MASTER_PROV").get_all_records()

    mapa_sku = {str(r["SKU_ID"]).strip(): r for r in registros_sku}
    mapa_prov = {str(r["Proveedor_ID"]).strip(): r for r in registros_prov}

    return mapa_sku, mapa_prov


def _debe_procesar_proveedor(datos_prov: dict) -> bool:
    """
    Determina si un proveedor debe procesarse hoy según su frecuencia y hora de corte.
    """
    frecuencia = str(datos_prov.get("Frecuencia", "DIARIO")).upper()
    ahora = datetime.now()

    # 1. Validación de día (calendario)
    if frecuencia == "PROGRAMADO":
        dias_str = str(datos_prov.get("Dias_Programados", "[]"))
        try:
            dias_programados = json.loads(dias_str)
            if ahora.weekday() not in dias_programados:
                return False
        except (json.JSONDecodeError, ValueError):
            return False

    # 2. Validación de hora límite
    hora_limite_str = str(datos_prov.get("Hora_Limite", "20:00")).strip()
    try:
        hora_actual = ahora.time()
        hora_limite = datetime.strptime(hora_limite_str, "%H:%M").time()
        if hora_actual < hora_limite:
            return False
    except ValueError:
        pass

    return True


def run_mailer(modo_manual: bool = False) -> None:
    """Orquesta la consolidación de pedidos y generación de órdenes de compra HTML."""
    logger.info("Orquestador de despacho SAI v2.0: %s", datetime.now().strftime("%H:%M"))
    if modo_manual:
        logger.info("MODO MANUAL ACTIVADO: Se omitirán validaciones de horario y frecuencia.")

    try:
        mapa_sku, mapa_prov = _obtener_datos_maestros()
    except Exception as error:
        logger.error("Error al obtener maestros: %s", error)
        return

    session = Session()
    try:
        pedidos_pendientes = (
            session.query(OrderBuffer)
            .filter(OrderBuffer.status == OrderStatus.PENDING)
            .all()
        )

        if not pedidos_pendientes:
            logger.info("No hay pedidos pendientes en buffer.")
            return

        # --- FASE 1: Consolidación por proveedor y SKU ---
        mapa_consolidado: dict = {}

        for pedido in pedidos_pendientes:
            prov_id = pedido.proveedor_id
            if not prov_id or prov_id not in mapa_prov:
                continue

            if not modo_manual and not _debe_procesar_proveedor(mapa_prov[prov_id]):
                continue

            if prov_id not in mapa_consolidado:
                mapa_consolidado[prov_id] = {}

            sku_id = pedido.sku_id
            if sku_id not in mapa_consolidado[prov_id]:
                info_sku = mapa_sku.get(sku_id, {})

                precio_raw = info_sku.get("Precio_Ref", 0)
                try:
                    precio_unit = float(
                        str(precio_raw).replace("$", "").replace(",", "").strip()
                    )
                except (ValueError, TypeError):
                    precio_unit = 0.0

                mapa_consolidado[prov_id][sku_id] = {
                    "nombre": info_sku.get("Nombre", "N/A"),
                    "presentacion": info_sku.get("Presentación", "N/A"),
                    "cantidad": 0.0,
                    "precio_unit": precio_unit,
                    "db_refs": [],
                }

            mapa_consolidado[prov_id][sku_id]["cantidad"] += pedido.cantidad
            mapa_consolidado[prov_id][sku_id]["db_refs"].append(pedido)

        # --- FASE 2: Generación de OCs ---
        if not os.path.exists("outbox"):
            os.makedirs("outbox")

        template = Template(HTML_TEMPLATE)
        fecha_archivo = datetime.now().strftime("%Y%m%d")
        contador_procesados = 0

        for prov_id, datos_skus in mapa_consolidado.items():
            items_html = []
            total_orden = 0.0
            todos_los_pedidos_db = []

            for sku_id, datos in datos_skus.items():
                datos["subtotal"] = datos["cantidad"] * datos["precio_unit"]
                total_orden += datos["subtotal"]
                items_html.append(datos)
                todos_los_pedidos_db.extend(datos["db_refs"])

            if not items_html:
                continue

            nombre_prov = mapa_prov[prov_id]["Nombre"]
            nombre_archivo = f"outbox/{fecha_archivo}_{prov_id}_Consolidado.html"

            logger.info("Despachando OC: %s | Items: %d", nombre_prov, len(items_html))

            contenido_html = template.render(
                prov_nombre=nombre_prov,
                fecha=datetime.now().strftime("%d/%m/%Y"),
                items=items_html,
                total_orden=total_orden,
                trx_id=f"SAI-{fecha_archivo}-{prov_id}",
            )

            with open(nombre_archivo, "w", encoding="utf-8") as f:
                f.write(contenido_html)

            # Marcar registros como SENT
            for pedido_db in todos_los_pedidos_db:
                pedido_db.status = OrderStatus.SENT

            session.commit()

            # Archivar pedidos al historial
            precios_sku = {s_id: d["precio_unit"] for s_id, d in datos_skus.items()}
            archive_orders(prov_id, nombre_archivo, sku_prices=precios_sku)

            contador_procesados += 1

        # Actualizar pestaña de recepción con los nuevos pedidos
        sync_reception_tab()

        logger.info(
            "Ciclo terminado. %d OCs generadas y archivadas.", contador_procesados
        )

    except Exception as error:
        session.rollback()
        logger.error("Error crítico en mailer: %s", error)
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Orquestador de Despacho SAI")
    parser.add_argument(
        "--manual", 
        action="store_true", 
        help="Fuerza el despacho de pedidos ignorando horarios y frecuencias (Modo Demo)"
    )
    args = parser.parse_args()

    configurar_logging()
    run_mailer(modo_manual=args.manual)
