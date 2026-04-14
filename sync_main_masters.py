import gspread
from oauth2client.service_account import ServiceAccountCredentials

def update_main_masters():
    print("--- Actualizando Maestros en Spreadsheet Principal ---")
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        sh = client.open("SAI - Sistema de Abastecimiento")
        print(f"OK: Conectado a {sh.title}")
    except Exception as e:
        print(f"ERROR: No se pudo conectar. {e}")
        return

    # 1. Actualizar MASTER_PROV
    print("Actualizando MASTER_PROV...")
    ws_prov = sh.worksheet("MASTER_PROV")
    ws_prov.clear()
    
    prov_headers = ["Proveedor_ID", "Nombre", "Email", "Frecuencia", "Hora_Limite", "Dias_Programados"]
    prov_data = [
        ["PROV-DEMO-01", "Distribuidora Global Carnicos", "carnicos@demo.sai", "DIARIO", "18:00", "[0,1,2,3,4,5,6]"],
        ["PROV-DEMO-02", "Panificadora Industrial", "pan@demo.sai", "DIARIO", "18:00", "[0,1,2,3,4,5,6]"],
        ["PROV-DEMO-03", "Proveedor de Bebidas y Bodega", "bebidas@demo.sai", "DIARIO", "18:00", "[0,1,2,3,4,5,6]"],
        ["PROV-DEMO-04", "Suministros de Higiene Profesional", "higiene@demo.sai", "DIARIO", "18:00", "[0,1,2,3,4,5,6]"]
    ]
    ws_prov.append_row(prov_headers)
    ws_prov.append_rows(prov_data)
    print(f"   Done: {len(prov_data)} proveedores.")

    # 2. Actualizar MASTER_SKU
    print("Actualizando MASTER_SKU...")
    ws_sku = sh.worksheet("MASTER_SKU")
    ws_sku.clear()
    
    sku_headers = ["SKU_ID", "Nombre", "Categoría", "Presentación", "Proveedor_ID", "Precio_Ref"]
    sku_data = [
        ["SKU-CAR-01", "Costillar Premium", "Carnes", "Por kg", "PROV-DEMO-01", 15.50],
        ["SKU-CAR-02", "Lomo Vacuno", "Carnes", "Por kg", "PROV-DEMO-01", 22.00],
        ["SKU-CAR-03", "Chorizo de Campo", "Carnes", "Pack 1kg", "PROV-DEMO-01", 8.00],
        ["SKU-PAN-01", "Pan Baguette", "Panificados", "Unidad", "PROV-DEMO-02", 1.20],
        ["SKU-PAN-02", "Pan de Campo", "Panificados", "Unidad", "PROV-DEMO-02", 2.50],
        ["SKU-BEB-01", "Vino Malbec", "Bebidas", "Botella 750ml", "PROV-DEMO-03", 12.00],
        ["SKU-BEB-02", "Agua Mineral", "Bebidas", "Bidon 5L", "PROV-DEMO-03", 0.80],
        ["SKU-BEB-03", "Cerveza Artesanal", "Bebidas", "Lata 473ml", "PROV-DEMO-03", 4.50],
        ["SKU-HIG-01", "Detergente Industrial", "Limpieza", "Bidon 5L", "PROV-DEMO-04", 8.50],
        ["SKU-HIG-02", "Desinfectante", "Limpieza", "Botella 1L", "PROV-DEMO-04", 5.00]
    ]
    ws_sku.append_row(sku_headers)
    ws_sku.append_rows(sku_data)
    print(f"   Done: {len(sku_data)} productos.")

    # 3. Formateo (opcional pero profesional)
    # Reutilizamos lógica de formateo basica
    for ws in [ws_prov, ws_sku]:
        ws.format('A1:Z1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9},
            'horizontalAlignment': 'CENTER'
        })

    print("\n--- Sincronizacion de Maestros Completada ---")

if __name__ == "__main__":
    update_main_masters()
