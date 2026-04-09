import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

def setup_sai_infrastructure():
    print("--- Configurando Infraestructura SAI en Spreadsheet existente ---")
    
    # Configuración de autenticación
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        print("OK: Autenticación exitosa.")
    except Exception as e:
        print(f"ERROR: Autenticación: {e}")
        return

    # 1. Abrir el Spreadsheet (debe estar compartido con el bot)
    spreadsheet_name = "SAI - Sistema de Abastecimiento"
    try:
        print(f"Abriendo Spreadsheet: {spreadsheet_name}...")
        sh = client.open(spreadsheet_name)
        print(f"OK: Spreadsheet encontrado con ID: {sh.id}")
    except gspread.SpreadsheetNotFound:
        print(f"ERROR: No se encontró el archivo '{spreadsheet_name}'.")
        print("Asegúrate de haberlo compartido con el bot y que el nombre sea EXACTO.")
        return
    except Exception as e:
        print(f"ERROR al abrir: {e}")
        return

    # 2. Configurar pestañas y encabezados
    sheets_config = {
        "MASTER_SKU": ["SKU_ID", "Nombre", "Categoría", "Presentación", "Proveedor_ID", "Precio_Ref"],
        "MASTER_PROV": ["Proveedor_ID", "Nombre", "Email", "Frecuencia", "Hora_Limite", "Dias_Programados"],
        "LOCAL_01": ["SKU_ID", "Producto", "Cantidad", "Confirmar", "Estado Log"]
    }

    # Obtener lista de pestañas existentes para no duplicar si hay errores
    existing_worksheets = [ws.title for ws in sh.worksheets()]

    for sheet_name, headers in sheets_config.items():
        print(f"Configurando pestaña: {sheet_name}...")
        try:
            if sheet_name in existing_worksheets:
                worksheet = sh.worksheet(sheet_name)
                print(f"   Pestaña ya existe. Limpiando...")
                worksheet.clear()
            else:
                # Si es la primera y no se llama MASTER_SKU, renombramos la default (Hoja 1 o Sheet1)
                if sheet_name == "MASTER_SKU" and len(existing_worksheets) == 1:
                    worksheet = sh.get_worksheet(0)
                    worksheet.update_title(sheet_name)
                    worksheet.clear()
                else:
                    worksheet = sh.add_worksheet(title=sheet_name, rows="100", cols="20")
            
            # Insertar encabezados
            worksheet.append_row(headers)
            
            # Formatear encabezados (Negrita y fondo gris claro)
            worksheet.format('A1:Z1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9},
                'horizontalAlignment': 'CENTER'
            })
            
            # Ajustar anchos opcionalmente si gspread lo permite de forma fácil
            # (En el futuro podemos usar batch_update para esto)
            
            print(f"   Done.")
        except Exception as e:
            print(f"   ERROR en {sheet_name}: {e}")

    # 3. Eliminar "Hoja 1" o "Sheet1" si quedó colgada
    try:
        if "Hoja 1" in [ws.title for ws in sh.worksheets()] and "MASTER_SKU" in [ws.title for ws in sh.worksheets()]:
            sh.del_worksheet(sh.worksheet("Hoja 1"))
        if "Sheet1" in [ws.title for ws in sh.worksheets()] and "MASTER_SKU" in [ws.title for ws in sh.worksheets()]:
            sh.del_worksheet(sh.worksheet("Sheet1"))
    except:
        pass

    print("\n" + "="*40)
    print(f"INFRAESTRUCTURA DESPLEGADA EXITOSAMENTE")
    print(f"ID del Spreadsheet: {sh.id}")
    print(f"URL: https://docs.google.com/spreadsheets/d/{sh.id}")
    print("="*40)

if __name__ == "__main__":
    setup_sai_infrastructure()
