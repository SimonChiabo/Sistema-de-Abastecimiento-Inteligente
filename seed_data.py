import gspread
from oauth2client.service_account import ServiceAccountCredentials

def seed_and_format():
    print("--- Iniciando Carga de Datos y Formateo UX ---")
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        sh = client.open("SAI - Sistema de Abastecimiento")
        print(f"OK: Spreadsheet abierto (ID: {sh.id})")
    except Exception as e:
        print(f"ERROR: No se pudo abrir el archivo. {e}")
        return

    # --- Tarea 1: MASTER_PROV ---
    print("Poblando MASTER_PROV...")
    ws_prov = sh.worksheet("MASTER_PROV")
    prov_data = [
        ["PROV-001", "La Panadería", "panaderia_test@example.com", "DIARIO", "20:00", "[]"],
        ["PROV-002", "Distribuidora Lácteos", "lacteos_test@example.com", "PROGRAMADO", "18:00", "[0, 3]"]
    ]
    ws_prov.append_rows(prov_data)

    # --- Tarea 2: MASTER_SKU ---
    print("Poblando MASTER_SKU...")
    ws_sku = sh.worksheet("MASTER_SKU")
    sku_data = [
        ["SKU-PAN-01", "Pan de Molde", "Panificados", "Bolsa 500g", "PROV-001", 2.50],
        ["SKU-LAC-01", "Leche Entera", "Lácteos", "Pack 12L", "PROV-002", 15.00],
        ["SKU-LAC-02", "Yogur Natural", "Lácteos", "Pack 6u", "PROV-002", 8.00]
    ]
    ws_sku.append_rows(sku_data)

    # --- Tarea 3: LOCAL_01 ---
    print("Poblando LOCAL_01...")
    ws_local = sh.worksheet("LOCAL_01")
    local_data = [
        ["SKU-PAN-01", "Pan de Molde"],
        ["SKU-LAC-01", "Leche Entera"],
        ["SKU-LAC-02", "Yogur Natural"]
    ]
    ws_local.append_rows(local_data)

    # --- Tarea 4: Formateo Avanzado (Batch Update) ---
    print("Aplicando formatos técnicos...")
    
    # IDs de las hojas para las requests
    prov_id = ws_prov.id
    sku_id = ws_sku.id
    local_id = ws_local.id

    requests = [
        # 1. Checkbox en LOCAL_01 Columna D (index 3) para filas de datos (2 a 100)
        {
            "setDataValidation": {
                "range": {
                    "sheetId": local_id,
                    "startRowIndex": 1,
                    "endRowIndex": 100,
                    "startColumnIndex": 3,
                    "endColumnIndex": 4
                },
                "rule": {
                    "condition": {"type": "BOOLEAN"},
                    "showCustomUi": True
                }
            }
        },
        # 2. Formato Moneda en MASTER_SKU Columna F (index 5)
        {
            "repeatCell": {
                "range": {
                    "sheetId": sku_id,
                    "startRowIndex": 1,
                    "endRowIndex": 100,
                    "startColumnIndex": 5,
                    "endColumnIndex": 6
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00"}
                    }
                },
                "fields": "userEnteredFormat.numberFormat"
            }
        },
        # 3. Ajuste de ancho de columnas automático para todas las hojas
        { "autoResizeDimensions": { "dimensions": { "sheetId": prov_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 6 } } },
        { "autoResizeDimensions": { "dimensions": { "sheetId": sku_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 6 } } },
        { "autoResizeDimensions": { "dimensions": { "sheetId": local_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 5 } } }
    ]

    try:
        sh.batch_update({"requests": requests})
        print("OK: Formatos aplicados exitosamente.")
    except Exception as e:
        print(f"ERROR en batch_update: {e}")

    print("\nPROCESO COMPLETO. El Sheet está listo para auditoría.")

if __name__ == "__main__":
    seed_and_format()
