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
<html lang="es">
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #2563eb;
            --primary-dark: #1e40af;
            --bg: #f8fafc;
            --text: #0f172a;
            --text-light: #64748b;
            --white: #ffffff;
            --border: #e2e8f0;
        }
        body { 
            font-family: 'Inter', system-ui, -apple-system, sans-serif; 
            color: var(--text); 
            background-color: var(--bg);
            margin: 0;
            padding: 40px;
            line-height: 1.5;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: var(--white);
            border-radius: 16px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
            overflow: hidden;
            border: 1px solid var(--border);
        }
        .header { 
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%); 
            color: var(--white); 
            padding: 40px; 
            position: relative;
        }
        .header h2 { margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.025em; }
        .header p { margin: 10px 0 0; opacity: 0.8; font-weight: 300; }
        .badge {
            display: inline-block;
            padding: 4px 12px;
            background: rgba(255,255,255,0.1);
            border-radius: 20px;
            font-size: 12px;
            margin-top: 15px;
        }
        .content { padding: 40px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th { 
            text-align: left; 
            padding: 12px 16px; 
            font-size: 12px; 
            text-transform: uppercase; 
            color: var(--text-light);
            border-bottom: 2px solid var(--border);
            font-weight: 600;
        }
        td { padding: 16px; border-bottom: 1px solid var(--border); }
        .item-row:hover { background-color: #f1f5f9; }
        .sku-name { font-weight: 600; color: var(--text); display: block; }
        .sku-presentation { font-size: 13px; color: var(--text-light); }
        .text-right { text-align: right; }
        .qty-badge {
            background: #f1f5f9;
            padding: 4px 8px;
            border-radius: 6px;
            font-weight: 600;
            color: var(--primary);
        }
        .local-breakdown {
            font-size: 11px;
            color: var(--text-light);
            margin-top: 8px;
            padding-left: 20px;
            border-left: 2px solid var(--primary);
            list-style: none;
            padding: 0 0 0 12px;
        }
        .local-item { margin-bottom: 2px; }
        .footer { 
            background: #f8fafc;
            padding: 30px 40px; 
            font-size: 13px; 
            color: var(--text-light); 
            border-top: 1px solid var(--border); 
        }
        .total-card {
            margin-top: 30px;
            padding: 24px;
            background: #f1f5f9;
            border-radius: 12px;
            text-align: right;
        }
        .total-label { font-size: 14px; color: var(--text-light); display: block; }
        .total-amount { font-size: 32px; font-weight: 700; color: var(--text); }
        .timestamp { font-size: 11px; opacity: 0.6; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="timestamp">CONFIRMACIÓN DE PEDIDO</div>
            <h2>{{ prov_nombre }}</h2>
            <p>Orden de Compra Consolidada</p>
            <div class="badge">Fecha de Despacho: {{ fecha }}</div>
        </div>

        <div class="content">
            <table>
                <thead>
                    <tr>
                        <th>Producto / Desglose por Local</th>
                        <th class="text-right">Cantidad</th>
                        <th class="text-right">P. Unitario</th>
                        <th class="text-right">Subtotal</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in items %}
                    <tr class="item-row">
                        <td>
                            <span class="sku-name">{{ item.nombre }}</span>
                            <span class="sku-presentation">{{ item.presentacion }}</span>
                            
                            <ul class="local-breakdown">
                                {% for local, qty in item.desglose.items() %}
                                <li class="local-item">
                                    <strong>{{ local }}:</strong> {{ qty }}
                                </li>
                                {% endfor %}
                            </ul>
                        </td>
                        <td class="text-right">
                            <span class="qty-badge">{{ item.cantidad }}</span>
                        </td>
                        <td class="text-right">${{ "{:,.2f}".format(item.precio_unit) }}</td>
                        <td class="text-right" style="font-weight: 600;">${{ "{:,.2f}".format(item.subtotal) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

            <div class="total-card">
                <span class="total-label">VALOR TOTAL ESTIMADO</span>
                <span class="total-amount">${{ "{:,.2f}".format(total_orden) }}</span>
            </div>
        </div>

        <div class="footer">
            <p><strong>Nota importante:</strong> Esta orden consolida los requerimientos de múltiples sucursales a través del sistema SAI. Por favor, asegúrese de etiquetar cada bulto según el desglose adjunto si es posible.</p>
            <p style="margin-top: 10px;">ID de Transacción: <code>{{ trx_id }}</code></p>
        </div>
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
                    "desglose": {},  # Nuevo campo para agrupar por local
                }

            mapa_consolidado[prov_id][sku_id]["cantidad"] += pedido.cantidad
            
            # Registrar desglose por local
            local_name = str(pedido.centro_costo).strip()
            mapa_consolidado[prov_id][sku_id]["desglose"][local_name] = (
                mapa_consolidado[prov_id][sku_id]["desglose"].get(local_name, 0.0) + pedido.cantidad
            )
            
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
