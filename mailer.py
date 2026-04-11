import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from jinja2 import Template
from core.db_handler import Session, OrderBuffer, OrderStatus, archive_orders
from core.reception import sync_reception_tab

def get_masters_data():
    """Obtiene los datos maestros de Google Sheets."""
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    sh = client.open("SAI - Sistema de Abastecimiento")
    
    sku_records = sh.worksheet("MASTER_SKU").get_all_records()
    prov_records = sh.worksheet("MASTER_PROV").get_all_records()
    
    sku_map = {str(r['SKU_ID']).strip(): r for r in sku_records}
    prov_map = {str(r['Proveedor_ID']).strip(): r for r in prov_records}
    
    return sku_map, prov_map

def should_process_provider(prov_data):
    """
    Determina si un proveedor debe procesarse hoy según su frecuencia y hora de corte.
    Como Lead SE, implementamos validación estricta de calendario.
    """
    frecuencia = str(prov_data.get('Frecuencia', 'DIARIO')).upper()
    now = datetime.now()
    
    # 1. Validación de Día (Calendario)
    if frecuencia == 'PROGRAMADO':
        dias_str = str(prov_data.get('Dias_Programados', '[]'))
        try:
            dias_programados = json.loads(dias_str)
            if now.weekday() not in dias_programados:
                return False
        except:
            return False
            
    # 2. Validación de Hora Límite (Disparo de Envío)
    # Solo "disparamos" si ya pasamos la hora límite del proveedor (consolidación diaria)
    hora_limite_str = str(prov_data.get('Hora_Limite', '20:00')).strip()
    try:
        current_time = now.time()
        limit_time = datetime.strptime(hora_limite_str, "%H:%M").time()
        # Nota: En un sistema industrial, aquí decidiríamos si enviar justo a esa hora.
        # Por ahora, permitimos el envío si ya es hora o posterior.
        if current_time < limit_time:
            # Todavía hay tiempo para recibir más pedidos antes del envío total
            return False
    except:
        pass

    return True

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

def run_mailer():
    print(f"--- Orquestador de Despacho SAI v2.0: {datetime.now().strftime('%H:%M')} ---")
    
    try:
        sku_map, prov_map = get_masters_data()
    except Exception as e:
        print(f"ERROR MASTER: {e}")
        return

    session = Session()
    try:
        pending_orders = session.query(OrderBuffer).filter(
            OrderBuffer.status == OrderStatus.PENDING
        ).all()
        
        if not pending_orders:
            print("No hay pedidos pendientes en buffer.")
            return

        # --- FASE 1: CONSOLIDACIÓN POR PROVEEDOR Y SKU ---
        # Estructura: consolidate_map[prov_id][sku_id] = {info, total_qty, db_orders_refs}
        consolidate_map = {}
        
        for order in pending_orders:
            prov_id = order.proveedor_id
            if not prov_id or prov_id not in prov_map:
                continue
            
            # Filtro de Calendario y Hora de Corte
            if not should_process_provider(prov_map[prov_id]):
                continue
            
            if prov_id not in consolidate_map:
                consolidate_map[prov_id] = {}
            
            sku_id = order.sku_id
            if sku_id not in consolidate_map[prov_id]:
                # Obtener info maestra
                p_info = sku_map.get(sku_id, {})
                
                # Gestión de Precios
                p_raw = p_info.get('Precio_Ref', 0)
                try: p_unit = float(str(p_raw).replace('$', '').replace(',', '').strip())
                except: p_unit = 0.0

                consolidate_map[prov_id][sku_id] = {
                    'nombre': p_info.get('Nombre', 'N/A'),
                    'presentacion': p_info.get('Presentación', 'N/A'),
                    'cantidad': 0.0,
                    'precio_unit': p_unit,
                    'db_refs': []
                }
            
            # Sumatoria (Consolidación)
            consolidate_map[prov_id][sku_id]['cantidad'] += order.cantidad
            consolidate_map[prov_id][sku_id]['db_refs'].append(order)

        # --- FASE 2: GENERACIÓN DE OCs ---
        if not os.path.exists('outbox'): os.makedirs('outbox')
        template = Template(HTML_TEMPLATE)
        fecha_file = datetime.now().strftime("%Y%m%d")
        
        processed_count = 0
        for prov_id, skus_data in consolidate_map.items():
            items_for_html = []
            total_orden = 0
            all_db_orders = []
            
            for sku_id, data in skus_data.items():
                data['subtotal'] = data['cantidad'] * data['precio_unit']
                total_orden += data['subtotal']
                items_for_html.append(data)
                all_db_orders.extend(data['db_refs'])
            
            if not items_for_html: continue

            prov_nombre = prov_map[prov_id]['Nombre']
            filename = f"outbox/{fecha_file}_{prov_id}_Consolidado.html"
            
            print(f"Despachando OC: {prov_nombre} | Items: {len(items_for_html)}")
            
            html_content = template.render(
                prov_nombre=prov_nombre,
                fecha=datetime.now().strftime("%d/%m/%Y"),
                items=items_for_html,
                total_orden=total_orden,
                trx_id=f"SAI-{fecha_file}-{prov_id}"
            )
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Marcar registros como SENT (Idempotencia)
            for db_order in all_db_orders:
                db_order.status = OrderStatus.SENT
            
            # Persistir cambio de estatus a SENT primero para poder archivarlos
            session.commit()
            
            # --- Tarea DBA: Archivando pedidos ---
            # Construimos mapa de precios para el histórico
            sku_prices = {s_id: d['precio_unit'] for s_id, d in skus_data.items()}
            archive_orders(prov_id, filename, sku_prices=sku_prices)
            
            processed_count += 1

        # Actualizar la pestaña de recepción con los nuevos pedidos enviados
        sync_reception_tab()

        print(f"Ciclo terminado. {processed_count} OCs generadas y archivadas.")
        
    except Exception as e:
        session.rollback()
        print(f"CRITICAL: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    run_mailer()
