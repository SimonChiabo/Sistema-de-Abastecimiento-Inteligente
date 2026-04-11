import gspread
from oauth2client.service_account import ServiceAccountCredentials
from core.db_handler import Session, OrderHistory, update_history_fulfillment, OrderBuffer

def sync_reception_tab():
    """Exporta los últimos registros de OrderHistory al Google Sheet para control manual."""
    print("--- Sincronizando Pestaña CONTROL_RECEPCION ---")
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    sh = client.open("SAI - Sistema de Abastecimiento")
    
    # 1. Crear o preparar pestaña
    try:
        ws = sh.worksheet("CONTROL_RECEPCION")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="CONTROL_RECEPCION", rows="100", cols="10")
        print("Pestaña creada.")

    # Encabezados
    headers = ["ID_HISTORIAL", "Fecha", "Proveedor", "Producto", "Cant_Pedida", "Cant_Recibida", "Anular (Checkbox)", "Notas"]
    ws.clear()
    ws.append_row(headers)
    ws.format('A1:Z1', {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.8, 'green': 0.9, 'blue': 1.0}})

    # 2. Obtener datos de SQL
    session = Session()
    try:
        # Últimos 50 enviados
        history = session.query(OrderHistory).order_by(OrderHistory.fecha_archivo.desc()).limit(50).all()
        
        rows = []
        for h in history:
            rows.append([
                h.id,
                h.fecha_archivo.strftime("%d/%m/%Y"),
                h.proveedor_id,
                h.sku_id,
                h.cantidad,
                h.received_quantity,
                False, # Checkbox Anular
                h.incident_notes or ""
            ])
        
        if rows:
            ws.append_rows(rows)
            
            # Configurar Checkboxes en la columna G (index 6)
            ws.format(f'G2:G{len(rows)+1}', {"backgroundColor": {"red": 1, "green": 0.9, "blue": 0.9}})
            sh.batch_update({
                "requests": [{
                    "setDataValidation": {
                        "range": {
                            "sheetId": ws.id,
                            "startRowIndex": 1,
                            "endRowIndex": len(rows)+1,
                            "startColumnIndex": 6,
                            "endColumnIndex": 7
                        },
                        "rule": {"condition": {"type": "BOOLEAN"}, "showCustomUi": True}
                    }
                }]
            })
        print(f"OK: {len(rows)} registros sincronizados.")
    finally:
        session.close()

def process_reception_feedback():
    """Lee el feedback del usuario en CONTROL_RECEPCION y actualiza la base de datos."""
    print("--- Procesando Feedback de Recepción ---")
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    sh = client.open("SAI - Sistema de Abastecimiento")
    
    try:
        ws = sh.worksheet("CONTROL_RECEPCION")
        data = ws.get_all_records()
        
        for row in data:
            h_id = row['ID_HISTORIAL']
            cant_rec = float(row['Cant_Recibida'])
            anular = str(row['Anular (Checkbox)']).upper() == "TRUE"
            notas = row['Notas']
            
            status = "COMPLETE"
            if anular:
                status = "CANCELLED"
            elif cant_rec < row['Cant_Pedida']:
                status = "PARTIAL"
            
            # Solo actualizar si es una transición válida (antes estaba en SENT)
            # Como Senior Engineer, por ahora lo hacemos simple:
            if h_id:
                success = update_history_fulfillment(h_id, cant_rec, status, notas)
                if success:
                    print(f"   Pedido {h_id} actualizado a {status}.")
                    
        print("OK: Sincronización feedback completa.")
    except Exception as e:
        print(f"ERROR en feedback: {e}")

if __name__ == "__main__":
    sync_reception_tab()
