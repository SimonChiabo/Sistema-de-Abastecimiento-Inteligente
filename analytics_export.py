import csv
from core.db_handler import Session, OrderHistory
from datetime import datetime

def export_to_csv(filename="SAI_Analitica_Global.csv"):
    """
    Exporta toda la tabla de historial a un CSV estructurado para Power BI.
    Retorna el conteo de registros exportados.
    """
    print(f"--- Generando Export de Analítica: {filename} ---")
    session = Session()
    try:
        data = session.query(OrderHistory).all()
        if not data:
            print("No hay datos históricos para exportar.")
            return 0
            
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Encabezados
            writer.writerow([
                "ID", "SKU_ID", "Centro_Costo", "Cant_Pedida", "Cant_Recibida", 
                "Proveedor_ID", "Fecha_Pedido", "Fecha_Archivo", "Precio_Unit", 
                "Total_Linea", "Status_Cumplimiento", "Notas"
            ])
            
            for h in data:
                writer.writerow([
                    h.id, h.sku_id, h.centro_costo, h.cantidad, h.received_quantity,
                    h.proveedor_id, h.fecha_registro.strftime("%Y-%m-%d %H:%M"),
                    h.fecha_archivo.strftime("%Y-%m-%d %H:%M"), h.precio_compra_final,
                    h.total_linea, h.fulfillment_status, h.incident_notes or ""
                ])
                
        print(f"OK: {len(data)} registros exportados.")
        return len(data)
    except Exception as e:
        print(f"ERROR en export: {e}")
        return 0
    finally:
        session.close()

if __name__ == "__main__":
    export_to_csv()
