import gspread
from oauth2client.service_account import ServiceAccountCredentials

def restructure_local_template():
    print("--- [ARCH] Re-estructurando SAI_Local_Template (Capas) ---")
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        template_sh = client.open("SAI_Local_Template")
        master_sh = client.open("SAI - Sistema de Abastecimiento")
        master_id = master_sh.id
        print(f"OK: Template ID: {template_sh.id}")

        # 1. Capa de Datos (_DB_INTERNAL)
        print("Configurando Capa de Datos (_DB_INTERNAL)...")
        try:
            ws_db = template_sh.worksheet("_DB_INTERNAL")
            ws_db.clear()
        except gspread.WorksheetNotFound:
            ws_db = template_sh.add_worksheet(title="_DB_INTERNAL", rows="100", cols="10")
        
        import_formula = f'=IMPORTRANGE("{master_id}", "MASTER_SKU!A1:F100")'
        ws_db.update_acell('A1', import_formula)

        # 2. Capa de Interfaz (PEDIDOS)
        print("Re-configurando Capa de Interfaz (PEDIDOS)...")
        ws_pedidos = template_sh.worksheet("PEDIDOS")
        ws_pedidos.clear()
        ws_pedidos.append_row(["SKU_ID", "Producto", "Cantidad", "Pedidos Acumulados", "Confirmar", "Log"])
        
        # Formulas XLOOKUP (Filas 2 a 100)
        # Col A (SKU_ID): Busca B en _DB_INTERNAL Col B, devuelve _DB_INTERNAL Col A
        # (Column D will be updated by the bot, no initial formula)
        formulas_a = [[f'=IF(B{i}="", "", XLOOKUP(B{i}, _DB_INTERNAL!B:B, _DB_INTERNAL!A:A))'] for i in range(2, 101)]
        
        ws_pedidos.update(range_name='A2:A101', values=formulas_a, value_input_option='USER_ENTERED')
        
        # 3. Capa de Inventario (STOCK)
        print("Configurando Capa de Inventario (STOCK)...")
        try:
            ws_stock = template_sh.worksheet("STOCK")
            ws_stock.clear()
        except gspread.WorksheetNotFound:
            ws_stock = template_sh.add_worksheet(title="STOCK", rows="100", cols="10")
        
        ws_stock.append_row(["SKU_ID", "Producto", "Stock_Fisico", "Notas"])
        
        # Referencias directas a _DB_INTERNAL
        ref_a = [[f'=_DB_INTERNAL!A{i}'] for i in range(2, 101)]
        ref_b = [[f'=_DB_INTERNAL!B{i}'] for i in range(2, 101)]
        ws_stock.update(range_name='A2:A101', values=ref_a, value_input_option='USER_ENTERED')
        ws_stock.update(range_name='B2:B101', values=ref_b, value_input_option='USER_ENTERED')

        # 4. Capa de Calidad (RECEPCION)
        print("Configurando Capa de Calidad (RECEPCION)...")
        try:
            ws_rec = template_sh.worksheet("RECEPCION")
            ws_rec.clear()
        except gspread.WorksheetNotFound:
            ws_rec = template_sh.add_worksheet(title="RECEPCION", rows="100", cols="15")
        ws_rec.append_row(["ID_Pedido", "SKU_ID", "Producto", "Cant_Pedida", "Cant_Recibida", "Estado_Articulo", "Notas"])

        # 5. Seguridad y UX
        print("Aplicando caps de seguridad y UX...")
        requests = [
            # Ocultar _DB_INTERNAL
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": ws_db.id,
                        "hidden": True
                    },
                    "fields": "hidden"
                }
            },
            # Dropdown en PEDIDOS B2:B100 desde _DB_INTERNAL!B2:B100
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": ws_pedidos.id,
                        "startRowIndex": 1,
                        "endRowIndex": 100,
                        "startColumnIndex": 1,
                        "endColumnIndex": 2
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_RANGE",
                            "values": [{"userEnteredValue": "=_DB_INTERNAL!$B$2:$B$100"}]
                        },
                        "showCustomUi": True
                    }
                }
            },
            # Checkbox en PEDIDOS E2:E100 (Confirmar)
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": ws_pedidos.id,
                        "startRowIndex": 1,
                        "endRowIndex": 100,
                        "startColumnIndex": 4, # Columna E
                        "endColumnIndex": 5
                    },
                    "rule": {
                        "condition": {"type": "BOOLEAN"},
                        "showCustomUi": True
                    }
                }
            }
        ]
        
        # Formateo de Headers (Azul oscuro para todos)
        for ws in [ws_pedidos, ws_stock, ws_rec]:
            ws.format('A1:Z1', {
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
                'backgroundColor': {'red': 0, 'green': 0.2, 'blue': 0.5},
                'horizontalAlignment': 'CENTER'
            })

        template_sh.batch_update({"requests": requests})
        print("\n--- ✅ Re-estructuracion Arquitectonica Completada ---")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    restructure_local_template()
