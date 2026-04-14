import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
from core.db_handler import add_to_buffer, Session, OrderBuffer, OrderStatus
from core.reception import process_reception_feedback
from warehouse_sync import sync_to_warehouse

def get_accumulated_from_db(sku_id, centro_costo):
    """Obtiene la cantidad total acumulada para un SKU en estado PENDING."""
    session = Session()
    try:
        order = session.query(OrderBuffer).filter(
            OrderBuffer.sku_id == sku_id,
            OrderBuffer.centro_costo == centro_costo,
            OrderBuffer.status == OrderStatus.PENDING
        ).first()
        return order.cantidad if order else 0
    finally:
        session.close()

def run_orchestrator():
    print(f"--- [MAIN] Iniciando Ciclo SAI Multi-Local: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    # 1. Conexión y Descubrimiento de Locales
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        # Cargar Maestros (Hub Central)
        sh_master = client.open("SAI - Sistema de Abastecimiento")
        skus = sh_master.worksheet("MASTER_SKU").get_all_records()
        provs = sh_master.worksheet("MASTER_PROV").get_all_records()
        
        sku_to_prov = {str(r['SKU_ID']).strip(): str(r['Proveedor_ID']).strip() for r in skus}
        prov_deadlines = {str(r['Proveedor_ID']).strip(): str(r['Hora_Limite']).strip() for r in provs}
        
        # Escaneo dinámico de Spreadsheets de Locales
        all_files = client.list_spreadsheet_files()
        local_files = [f for f in all_files if f['name'].startswith("SAI_Local_")]
        print(f"OK: Se encontraron {len(local_files)} locales para procesar.")
        
    except Exception as e:
        print(f"CRITICAL ERROR: No se pudo conectar al ecosistema. {e}")
        return

    # 2. Procesar cada Local
    for entry in local_files:
        local_name = entry['name']
        print(f"\n>> Procesando Local: {local_name}")
        
        try:
            sh_local = client.open_by_key(entry['id'])
            ws_pedidos = sh_local.worksheet("PEDIDOS")
            
            # Leer pedidos (Layout: SKU, Prod, Cant, Prec, Conf, Log)
            rows = ws_pedidos.get_all_values()
            if len(rows) < 2: continue
            
            data_rows = rows[1:]
            
            for index, row in enumerate(data_rows, start=2):
                try:
                    sku_id = str(row[0]).strip()
                    cantidad_str = str(row[2]).strip()
                    confirmado = str(row[4]).upper() == "TRUE"
                    
                    if not confirmado or not sku_id or not cantidad_str or cantidad_str == "":
                        continue
                    
                    print(f"   [SKU: {sku_id}] Cant: {cantidad_str}")
                    cantidad = float(cantidad_str.replace(',', '.'))
                    
                    # Logica de Horarios
                    prov_id = sku_to_prov.get(sku_id)
                    hora_limite_str = prov_deadlines.get(prov_id, "23:59")
                    
                    now_time = datetime.now().time()
                    limit_time = datetime.strptime(hora_limite_str, "%H:%M").time()
                    
                    status = OrderStatus.PENDING
                    log_msg = f"OK {datetime.now().strftime('%H:%M')}"
                    
                    if now_time > limit_time:
                        status = OrderStatus.LATE
                        log_msg = f"LATE ({hora_limite_str})"

                    # Registrar en DB Local
                    add_to_buffer(sku_id, cantidad, local_name, proveedor_id=prov_id)
                    
                    # Feedback al Local Sheet
                    new_accumulated = get_accumulated_from_db(sku_id, local_name)
                    updates = [
                        {'range': f'C{index}', 'values': [['']]},           # Limpiar Cantidad
                        {'range': f'E{index}', 'values': [[False]]},        # Desmarcar Checkbox
                        {'range': f'F{index}', 'values': [[log_msg]]}         # Log Status
                    ]
                    ws_pedidos.batch_update(updates)
                    
                except Exception as row_error:
                    print(f"      Err en fila {index}: {row_error}")
                    
        except Exception as local_error:
            print(f"   ERROR CRITICO en local {local_name}: {local_error}")

    # 3. Procesar conciliación distribuida
    process_reception_feedback()

    # 4. Sincronizar Data Warehouse
    sync_to_warehouse()

    print("\n--- Ciclo SAI Multi-Local Finalizado ---")

if __name__ == "__main__":
    run_orchestrator()
