import csv
from core.db_handler import Session, OrderHistory, MasterProv, MasterSku
from datetime import datetime

def export_to_csv(filename="SAI_Analitica_Global.csv"):
    """
    Exporta toda la tabla de historial a un CSV estructurado para Power BI.
    Retorna el conteo de registros exportados.
    """
    print(f"--- Generando Export de Analitica: {filename} ---")
    session = Session()
    try:
        # Realizar JOIN para traer el nombre del proveedor y del SKU
        results = session.query(OrderHistory, MasterProv.nombre, MasterSku.nombre).\
            outerjoin(MasterProv, OrderHistory.proveedor_id == MasterProv.proveedor_id).\
            outerjoin(MasterSku, OrderHistory.sku_id == MasterSku.sku_id).\
            all()
            
        if not results:
            print("No hay datos históricos para exportar.")
            return 0
            
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Encabezados
            writer.writerow([
                "ID", "SKU_ID", "SKU_Nombre", "Centro_Costo", "Cant_Pedida", "Cant_Recibida", 
                "Proveedor_ID", "Proveedor_Nombre", "Fecha_Pedido", "Fecha_Archivo", "Precio_Unit", 
                "Total_Linea", "Status_Cumplimiento", "Notas"
            ])
            
            for h, provider_name, sku_name in results:
                writer.writerow([
                    h.id, h.sku_id, sku_name or "Sku Desconocido", h.centro_costo, h.cantidad, h.received_quantity,
                    h.proveedor_id, provider_name or "Prov Desconocido", h.fecha_registro.strftime("%Y-%m-%d %H:%M") if h.fecha_registro else "",
                    h.fecha_archivo.strftime("%Y-%m-%d %H:%M") if h.fecha_archivo else "", h.precio_compra_final,
                    h.total_linea, h.fulfillment_status, h.incident_notes or ""
                ])
                
        print(f"OK: {len(results)} registros exportados.")
        return len(results)
    except Exception as e:
        print(f"ERROR en export: {e}")
        return 0
    finally:
        session.close()

if __name__ == "__main__":
    export_to_csv()
