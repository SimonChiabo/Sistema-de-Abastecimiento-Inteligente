import gspread
from oauth2client.service_account import ServiceAccountCredentials
from core.db_handler import Session, OrderHistory, update_history_fulfillment, OrderBuffer
from datetime import datetime

def sync_reception_tab():
    """Distribuye los registros SENT del historial a las pestañas RECEPCION de cada local."""
    print("--- Sincronizando Pestañas RECEPCION (Distribuidas) ---")
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    
    # Discovery de Locales
    all_files = client.list_spreadsheet_files()
    local_files = [f for f in all_files if f['name'].startswith("SAI_Local_")]
    
    session = Session()
    try:
        # Traer todos los SENT del historial
        sent_history = session.query(OrderHistory).filter(OrderHistory.fulfillment_status == 'SENT').all()
        
        for entry in local_files:
            local_name = entry['name']
            local_id = entry['id']
            
            # Filtrar registros que pertenecen a este local
            local_orders = [h for h in sent_history if h.centro_costo == local_name]
            
            if not local_orders:
                continue
                
            print(f"   Inyectando {len(local_orders)} pedidos en {local_name}...")
            
            try:
                sh = client.open_by_key(local_id)
                ws = sh.worksheet("RECEPCION")
                
                # Encabezados (ID_Hist, SKU, Prod, Cant_Ped, Cant_Rec, Estado, Notas)
                headers = ["ID_HISTORIAL", "SKU_ID", "Producto", "Cant_Pedida", "Cant_Recibida", "Estado_Articulo", "Notas"]
                ws.clear()
                ws.append_row(headers)
                
                rows = []
                for h in local_orders:
                    rows.append([
                        h.id, h.sku_id, "", h.cantidad, h.cantidad, "OK", ""
                    ])
                
                ws.append_rows(rows)
                ws.format('A1:G1', {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.1, 'green': 0.5, 'blue': 0.1}})
                
            except Exception as e:
                print(f"      ERROR en {local_name}: {e}")
                
        print("OK: Sincronización descentralizada completa.")
    finally:
        session.close()

def process_reception_feedback():
    """Recolecta el feedback de RECEPCION desde cada local y actualiza la base de datos central."""
    print("--- Procesando Feedback de Recepción (Multi-Local) ---")
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    
    all_files = client.list_spreadsheet_files()
    local_files = [f for f in all_files if f['name'].startswith("SAI_Local_")]
    
    for entry in local_files:
        local_name = entry['name']
        try:
            sh = client.open_by_key(entry['id'])
            ws = sh.worksheet("RECEPCION")
            data = ws.get_all_records()
            
            if not data: continue
            
            for row in data:
                h_id = row['ID_HISTORIAL']
                # Validar que sea un registro procesable
                if not h_id or str(h_id).strip() == "": continue
                
                cant_pedida = float(row['Cant_Pedida'])
                cant_rec = float(row['Cant_Recibida'])
                estado = str(row['Estado_Articulo']).upper()
                notas = row['Notas']
                
                status = "COMPLETE"
                if estado == "CANCELADO" or estado == "RECHAZADO":
                    status = "CANCELLED"
                elif cant_rec < cant_pedida:
                    status = "PARTIAL"
                
                success = update_history_fulfillment(h_id, cant_rec, status, f"[{estado}] {notas}")
                if success:
                    # Limpiar la fila del local o marcarla como procesada
                    # Como Senior Engineer, por ahora lo dejamos registrado para el siguiente sync total
                    pass

            print(f"   Feedback procesado para {local_name}.")
            
        except Exception as e:
            print(f"   ERROR leyendo feedback de {local_name}: {e}")

if __name__ == "__main__":
    sync_reception_tab()
