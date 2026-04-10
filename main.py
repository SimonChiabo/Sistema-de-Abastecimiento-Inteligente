import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
from core.db_handler import add_to_buffer, Session, OrderBuffer, OrderStatus

def get_accumulated_from_db(sku_id, centro_costo):
    """Obtiene la cantidad total acumulada para un SKU en estado PENDING."""
    session = Session()
    try:
        order = session.query(OrderBuffer).filter(
            OrderBuffer.sku_id == sku_id,
            OrderBuffer.centro_costo == centro_costo,
            OrderBuffer.status == OrderStatus.PENDING
        ).first()
        return order.cantidad if order else 0
    finally:
        session.close()

def run_orchestrator():
    print(f"--- Iniciando Ciclo SAI: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    # 1. Conexión a Sheets
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        sh = client.open("SAI - Sistema de Abastecimiento")
        
        ws_sku = sh.worksheet("MASTER_SKU")
        ws_prov = sh.worksheet("MASTER_PROV")
        ws_local = sh.worksheet("LOCAL_01")
        
        # Cargar mapeos de referencia
        skus = ws_sku.get_all_records()
        provs = ws_prov.get_all_records()
        
        # Diccionarios de búsqueda rápida
        # SKU_ID -> Proveedor_ID
        sku_to_prov = {str(r['SKU_ID']).strip(): str(r['Proveedor_ID']).strip() for r in skus}
        # Proveedor_ID -> Hora_Limite
        prov_deadlines = {str(r['Proveedor_ID']).strip(): str(r['Hora_Limite']).strip() for r in provs}
        
    except Exception as e:
        print(f"CRITICAL ERROR: No se pudo conectar a Google Sheets. {e}")
        return

    # 2. Leer LOCAL_01
    try:
        # Obtenemos todos los valores incluyendo encabezados
        rows = ws_local.get_all_values()
        headers = rows[0]
        data_rows = rows[1:] # Saltar headers
    except Exception as e:
        print(f"ERROR: No se pudo leer LOCAL_01. {e}")
        return

    # Iterar sobre las filas (usamos enumeración para saber el número de fila en el Sheet)
    for index, row in enumerate(data_rows, start=2): # Comienza en fila 2 del Sheet
        try:
            # Layout: A:SKU, B:Prod, C:Cant, D:Acum, E:Conf, F:Log
            sku_id = str(row[0]).strip()
            cantidad_str = str(row[2]).strip()
            confirmado = str(row[4]).upper() == "TRUE"
            
            if not confirmado or not sku_id or not cantidad_str:
                continue
            
            print(f"Procesando SKU: {sku_id}...")
            cantidad = float(cantidad_str.replace(',', '.'))
            
            # 3. Lógica de Proveedor y Horario
            prov_id = sku_to_prov.get(sku_id)
            hora_limite_str = prov_deadlines.get(prov_id, "23:59") # Default a fin de día si no existe
            
            # Comparación de Horas
            now_time = datetime.now().time()
            limit_time = datetime.strptime(hora_limite_str, "%H:%M").time()
            
            status = OrderStatus.PENDING
            log_msg = f"✅ Registrado {datetime.now().strftime('%H:%M')}"
            
            if now_time > limit_time:
                status = OrderStatus.LATE
                log_msg = f"⚠️ LATE: Pasó límite {hora_limite_str}"
                print(f"   Aviso: Pedido fuera de hora para proveedor {prov_id}.")

            # 4. Guardar en Base de Datos Local
            # Nota: add_to_buffer necesita ajustes para recibir status si queremos marcar LATE
            # O simplemente lo registramos. Por ahora usamos la función base.
            add_to_buffer(sku_id, cantidad, "LOCAL_01", proveedor_id=prov_id)
            
            # 5. Feedback Loop a Google Sheets
            new_accumulated = get_accumulated_from_db(sku_id, "LOCAL_01")
            
            # Actualización Batch para esta fila específica
            # Columnas: C: Cantidad, D: Acumulado, E: Confirmar, F: Log
            # Indices: [2, 3, 4, 5]
            updates = [
                {'range': f'C{index}', 'values': [['']]},           # Limpiar Cantidad
                {'range': f'D{index}', 'values': [[new_accumulated]]}, # Actualizar Acumulado
                {'range': f'E{index}', 'values': [[False]]},        # Desmarcar Checkbox
                {'range': f'F{index}', 'values': [[log_msg]]}         # Log Status
            ]
            ws_local.batch_update(updates)
            
            print(f"   Fila {index} procesada con éxito.")
            
        except Exception as e:
            print(f"   ERROR procesando fila {index} (SKU: {sku_id}): {e}")
            ws_local.update_acell(f'F{index}', f"❌ Error: {str(e)[:20]}")

    print("--- Ciclo SAI Finalizado ---")

if __name__ == "__main__":
    run_orchestrator()
