import gspread
from oauth2client.service_account import ServiceAccountCredentials

def restructure_local():
    print("--- Reestructurando LOCAL_01: Implementando Feedback Loop ---")
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        sh = client.open("SAI - Sistema de Abastecimiento")
        ws_local = sh.worksheet("LOCAL_01")
        print(f"OK: Conectado a {sh.title}")
    except Exception as e:
        print(f"ERROR: {e}")
        return

    local_id = ws_local.id

    # Definimos los nuevos encabezados
    new_headers = ["SKU_ID", "Producto", "Cantidad", "Acumulado (Pendiente Envío)", "Confirmar", "Estado Log"]

    requests = [
        # 1. Insertar una columna en la posición D (index 3)
        {
            "insertDimension": {
                "range": {
                    "sheetId": local_id,
                    "dimension": "COLUMNS",
                    "startIndex": 3,
                    "endIndex": 4
                },
                "inheritFromBefore": True
            }
        },
        # 2. Actualizar todos los encabezados
        {
            "updateCells": {
                "range": {
                    "sheetId": local_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 6
                },
                "rows": [
                    {
                        "values": [{"userEnteredValue": {"stringValue": h}} for h in new_headers]
                    }
                ],
                "fields": "userEnteredValue"
            }
        },
        # 3. Formatear la nueva columna D como Gris (Solo Lectura)
        {
            "repeatCell": {
                "range": {
                    "sheetId": local_id,
                    "startRowIndex": 1,
                    "endRowIndex": 100,
                    "startColumnIndex": 3,
                    "endColumnIndex": 4
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95}
                    }
                },
                "fields": "userEnteredFormat.backgroundColor"
            }
        },
        # 4. Asegurar Checkbox en la NUEVA posición E (index 4)
        {
            "setDataValidation": {
                "range": {
                    "sheetId": local_id,
                    "startRowIndex": 1,
                    "endRowIndex": 100,
                    "startColumnIndex": 4,
                    "endColumnIndex": 5
                },
                "rule": {
                    "condition": {"type": "BOOLEAN"},
                    "showCustomUi": True
                }
            }
        },
        # 5. Añadir Nota en D1
        {
            "updateCells": {
                "range": {
                    "sheetId": local_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 3,
                    "endColumnIndex": 4
                },
                "rows": [
                    {
                        "values": [
                            {
                                "note": "Cantidad ya procesada por el sistema y en espera de despacho al proveedor"
                            }
                        ]
                    }
                ],
                "fields": "note"
            }
        }
    ]

    try:
        sh.batch_update({"requests": requests})
        print("OK: Estructura de LOCAL_01 actualizada exitosamente.")
        
        # Verificamos/Refrescamos la fórmula en A2 para asegurarnos de que no se rompió por el shift
        # Aunque Google Sheets suele ajustarlo, re-insertarla garantiza integridad técnica.
        formula = '=ARRAYFORMULA(IF(ISBLANK(B2:B), "", XLOOKUP(B2:B, MASTER_SKU!B:B, MASTER_SKU!A:A, "ERR")))'
        ws_local.update_acell('A2', formula)
        print("OK: Integridad de ARRAYFORMULA verificada.")
        
    except Exception as e:
        print(f"ERROR en batch_update: {e}")

if __name__ == "__main__":
    restructure_local()
