from analytics_export import export_to_csv
from core.notifier import send_audit_report
from core.db_handler import Session, OrderHistory
from datetime import datetime

def calculate_metrics():
    """Calcula las métricas clave del historial para el resumen del correo."""
    session = Session()
    try:
        data = session.query(OrderHistory).all()
        total_orders = len(data)
        total_amount = sum(h.total_linea for h in data)
        pending_conciliation = len([h for h in data if h.fulfillment_status == 'SENT'])
        
        return {
            'total_orders': total_orders,
            'total_amount': total_amount,
            'pending_conciliation': pending_conciliation
        }
    finally:
        session.close()

def run_production_audit():
    print(f"--- Iniciando Proceso Productivo de Auditoría: {datetime.now()} ---")
    
    filename = "SAI_Analitica_Global.csv"
    
    # 1. Exportar datos a CSV
    count = export_to_csv(filename)
    
    if count > 0:
        # 2. Calcular Métricas para el resumen ejecutivo
        metrics = calculate_metrics()
        
        # 3. Enviar correo con reporte y métricas
        success = send_audit_report(filename, metrics)
        
        if success:
            print("EJECUCIÓN PRODUCTIVA EXITOSA: Todo en orden.")
    else:
        print("No se registran datos en el historial para procesar.")

if __name__ == "__main__":
    run_production_audit()
