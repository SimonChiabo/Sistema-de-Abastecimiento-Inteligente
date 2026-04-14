import gspread
from oauth2client.service_account import ServiceAccountCredentials

def enhance_local_template():
    print("--- [UX] Mejorando Inteligencia de SAI_Local_Template ---")
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        template_name = "SAI_Local_Template"
        sh = client.open(template_name)
        ws_pedidos = sh.worksheet("PEDIDOS")
        print(f"OK: Spreadsheet '{template_name}' abierto.")

        # 1. Preparar Fórmulas en Columnas A y D (Filas 2 a 51)
        # Col A (SKU_ID): Busca Nombre (Col B) en I y devuelve ID (Col H)
        # Col D (Precio): Busca Nombre (Col B) en I y devuelve Precio (Col M)
        print("Insertando formulas de busqueda inteligente...")
        
        # Generar listas de formulas
        formulas_a = [[f'=IF(B{i}="", "", XLOOKUP(B{i}, I:I, H:H))'] for i in range(2, 52)]
        formulas_d = [[f'=IF(B{i}="", "", XLOOKUP(B{i}, I:I, M:M))'] for i in range(2, 52)]
        
        ws_pedidos.update(range_name='A2:A51', values=formulas_a, value_input_option='USER_ENTERED')
        ws_pedidos.update(range_name='D2:D51', values=formulas_d, value_input_option='USER_ENTERED')
        
        # 2. Configurar Dropdown en Columna B (Filas 2 a 51) desde rango I2:I100
        print("Configurando validacion de datos (Dropdown)...")
        
        requests = []
        
        # Request para el Dropdown
        requests.append({
            "setDataValidation": {
                "range": {
                    "sheetId": ws_pedidos.id,
                    "startRowIndex": 1,
                    "endRowIndex": 51,
                    "startColumnIndex": 1, # Columna B
                    "endColumnIndex": 2
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_RANGE",
                        "values": [{"userEnteredValue": "=I2:I100"}]
                    },
                    "showCustomUi": True
                }
            }
        })
        
        # 3. Ocultar columnas H a M (Indices 7 a 12)
        print("Ocultando columnas de referencia (H:M)...")
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": ws_pedidos.id,
                    "dimension": "COLUMNS",
                    "startIndex": 7,
                    "endIndex": 13
                },
                "properties": {
                    "hiddenByUser": True
                },
                "fields": "hiddenByUser"
            }
        })
        
        # 4. Protección de Columnas A y D
        # Nota: La protección requiere permisos específicos y a veces falla si el bot no es el dueño absoluto,
        # pero intentaremos marcar el rango como protegido para 'todos excepto editores'.
        print("Aplicando proteccion de columnas A y D...")
        requests.append({
            "addProtectedRange": {
                "protectedRange": {
                    "range": {
                        "sheetId": ws_pedidos.id,
                        "startColumnIndex": 0, # Columna A
                        "endColumnIndex": 1
                    },
                    "description": "Proteccion SKU_ID",
                    "warningOnly": True # Usar warning para facilitar UX inicial
                }
            }
        })
        requests.append({
            "addProtectedRange": {
                "protectedRange": {
                    "range": {
                        "sheetId": ws_pedidos.id,
                        "startColumnIndex": 3, # Columna D
                        "endColumnIndex": 4
                    },
                    "description": "Proteccion Precio",
                    "warningOnly": True
                }
            }
        })

        sh.batch_update({"requests": requests})
        
        print("\n--- ✅ Optimizacion Mobile Completada ---")
        print(f"URL: https://docs.google.com/spreadsheets/d/{sh.id}")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    enhance_local_template()
