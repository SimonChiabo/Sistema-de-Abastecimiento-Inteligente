import gspread
from oauth2client.service_account import ServiceAccountCredentials
from core.db_handler import Session, OrderHistory
from datetime import datetime

def sync_to_warehouse():
    print("--- Sincronizando Data Warehouse (BI) ---")
    
    # ID proporcionado por el arquitecto
    WAREHOUSE_ID = "1q0-FbUQnid2kYvlj9UYLQMnxi_frLN7hsy2cfHD4T00"
    
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        sh = client.open_by_key(WAREHOUSE_ID)
        print(f"OK: Conectado al Warehouse {sh.title}")
    except Exception as e:
        print(f"ERROR: No se pudo conectar al Warehouse. {e}")
        print("Asegúrate de que sai-bot esté compartido como editor en el nuevo ID.")
        return

    # 1. Preparar Pestaña Maestro
    sheet_name = "HOJA_MAESTRA_BI"
    try:
        ws = sh.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows="1000", cols="15")
        print(f"Pestaña {sheet_name} creada.")

    ws.clear()
    
    # Encabezados
    headers = [
        "ID", "SKU_ID", "Centro_Costo", "Cant_Pedida", "Cant_Recibida", 
        "Proveedor_ID", "Fecha_Pedido", "Fecha_Archivo", "Precio_Unit", 
        "Total_Linea", "Status_Cumplimiento", "Notas"
    ]
    ws.append_row(headers)
    ws.format('A1:Z1', {
        'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
        'backgroundColor': {'red': 0.1, 'green': 0.1, 'blue': 0.1},
        'horizontalAlignment': 'CENTER'
    })

    # 2. Extraer datos de SQLite
    session = Session()
    try:
        history = session.query(OrderHistory).all()
        if not history:
            print("No hay datos históricos para sincronizar.")
            return

        rows = []
        for h in history:
            rows.append([
                h.id,
                h.sku_id,
                h.centro_costo,
                h.cantidad,
                h.received_quantity,
                h.proveedor_id,
                h.fecha_registro.strftime("%Y-%m-%d"),
                h.fecha_archivo.strftime("%Y-%m-%d"),
                h.precio_compra_final,
                h.total_linea,
                h.fulfillment_status,
                h.incident_notes or ""
            ])
        
        # 3. Inyección Masiva
        ws.append_rows(rows, value_input_option='RAW')
        print(f"OK: {len(rows)} registros inyectados en el Warehouse.")
        
    except Exception as e:
        print(f"ERROR en inyección: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    sync_to_warehouse()
