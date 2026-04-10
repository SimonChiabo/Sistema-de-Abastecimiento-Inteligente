import gspread
from oauth2client.service_account import ServiceAccountCredentials

def improve_local_ux():
    print("--- Mejorando UX de LOCAL_01 y Vinculación de Datos ---")
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        sh = client.open("SAI - Sistema de Abastecimiento")
        ws_local = sh.worksheet("LOCAL_01")
        ws_sku = sh.worksheet("MASTER_SKU")
        print(f"OK: Conectado a {sh.title}")
    except Exception as e:
        print(f"ERROR: {e}")
        return

    local_id = ws_local.id
    sku_id = ws_sku.id

    # --- Tarea 2: Automatización de SKU (Fórmula en A2) ---
    print("Insertando ARRAYFORMULA para vinculación automática de SKUs...")
    # Limpiamos la columna A para que la ArrayFormula no choque
    ws_local.update('A2:A100', [[''] for _ in range(99)])
    formula = '=ARRAYFORMULA(IF(ISBLANK(B2:B), "", XLOOKUP(B2:B, MASTER_SKU!B:B, MASTER_SKU!A:A, "ERR")))'
    ws_local.update_acell('A2', formula)

    # --- Tarea 1 & 3: Formatos y Validaciones (Batch Update) ---
    print("Aplicando Batch Update para Dropdowns, Colores y Protección...")
    
    requests = [
        # 1. Dropdown en LOCAL_01!B2:B100 desde MASTER_SKU!B2:B100
        {
            "setDataValidation": {
                "range": {
                    "sheetId": local_id,
                    "startRowIndex": 1,
                    "endRowIndex": 100,
                    "startColumnIndex": 1,
                    "endColumnIndex": 2
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_RANGE",
                        "values": [{"userEnteredValue": "=MASTER_SKU!$B$2:$B$100"}]
                    },
                    "showCustomUi": True,
                    "strict": True
                }
            }
        },
        # 2. Resaltar Columna C (Cantidad) en Amarillo Claro (index 2)
        {
            "repeatCell": {
                "range": {
                    "sheetId": local_id,
                    "startRowIndex": 1,
                    "endRowIndex": 100,
                    "startColumnIndex": 2,
                    "endColumnIndex": 3
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.8}
                    }
                },
                "fields": "userEnteredFormat.backgroundColor"
            }
        },
        # 3. Proteger Columna A (SKU_ID) para evitar borrado de fórmula
        {
            "addProtectedRange": {
                "protectedRange": {
                    "range": {
                        "sheetId": local_id,
                        "startRowIndex": 1,
                        "endRowIndex": 100,
                        "startColumnIndex": 0,
                        "endColumnIndex": 1
                    },
                    "description": "Protección de Columnas de Fórmulas Automáticas",
                    "warningOnly": True # Usamos warning para que el usuario pueda editar si es necesario pero sea avisado
                }
            }
        }
    ]

    try:
        sh.batch_update({"requests": requests})
        print("OK: Lógica de vinculación y UX aplicada.")
    except Exception as e:
        print(f"ERROR en batch_update: {e}")

    print("\nUX ACTUALIZADA. Pruebe seleccionando un producto en la Columna B.")

if __name__ == "__main__":
    improve_local_ux()
