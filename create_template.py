import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

def configure_local_template():
    print("--- [ARCH] Configurando SAI_Local_Template ---")
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        # 0. Obtener ID del Maestro
        master_sh = client.open("SAI - Sistema de Abastecimiento")
        master_id = master_sh.id
        print(f"Master ID: {master_id}")
        
        # 1. Abrir Template Compartido
        template_name = "SAI_Local_Template"
        try:
            sh = client.open(template_name)
            print(f"OK: Spreadsheet '{template_name}' abierto. ID: {sh.id}")
        except gspread.SpreadsheetNotFound:
            print(f"ERROR: No se encontro '{template_name}'. Asegurate de haberlo compartido con el bot.")
            return

        # 2. Configurar Pestañas
        # a. PEDIDOS
        print("Configurando PEDIDOS...")
        try:
            ws_pedidos = sh.worksheet("PEDIDOS")
            ws_pedidos.clear()
        except gspread.WorksheetNotFound:
            ws_pedidos = sh.add_worksheet(title="PEDIDOS", rows="100", cols="10")
            
        # Encabezados
        ws_pedidos.append_row(["SKU_ID", "Producto (Referencia)", "Cantidad", "Precio Unit", "Confirmar", "Log"])
        
        # Insertar Formula IMPORTRANGE en una zona de referencia (Capa oculta o lateral)
        # Vamos a poner los datos maestros en la columna H:J para que sirvan de validacion
        import_formula = f'=IMPORTRANGE("{master_id}", "MASTER_SKU!A1:F100")'
        ws_pedidos.update_acell('H1', import_formula)
        print("   Referencia vinculada via IMPORTRANGE.")
        
        # b. RECEPCION
        print("Configurando RECEPCION...")
        try:
            ws_rec = sh.worksheet("RECEPCION")
            ws_rec.clear()
        except gspread.WorksheetNotFound:
            ws_rec = sh.add_worksheet(title="RECEPCION", rows="100", cols="15")
        
        ws_rec.append_row(["ID_Pedido", "SKU_ID", "Producto", "Cant_Pedida", "Cant_Recibida", "Estado_Articulo", "Notas"])
        
        # c. STOCK
        print("Configurando STOCK...")
        try:
            ws_stock = sh.worksheet("STOCK")
            ws_stock.clear()
        except gspread.WorksheetNotFound:
            ws_stock = sh.add_worksheet(title="STOCK", rows="100", cols="10")
        
        ws_stock.append_row(["SKU_ID", "Producto", "Stock_Sistema", "Conteo_Fisico", "Diferencia"])
        
        # 3. Formateo y Proteccion
        print("Aplicando estilos corporativos...")
        header_format = {
            'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
            'backgroundColor': {'red': 0.1, 'green': 0.1, 'blue': 0.6}, # Azul oscuro
            'horizontalAlignment': 'CENTER'
        }
        
        for ws_name in ["PEDIDOS", "RECEPCION", "STOCK"]:
            ws = sh.worksheet(ws_name)
            ws.format('A1:G1', header_format)
            
        # 4. Checkbox en PEDIDOS
        print("Añadiendo Checkboxes...")
        requests = [
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
        sh.batch_update({"requests": requests})

        # Eliminar Hoja default si existe
        for name in ["Hoja 1", "Sheet1"]:
            try:
                sh.del_worksheet(sh.worksheet(name))
            except:
                pass
                
        print("\n--- ✅ Template Configurado Exitosamente ---")
        print(f"URL: https://docs.google.com/spreadsheets/d/{sh.id}")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    configure_local_template()
