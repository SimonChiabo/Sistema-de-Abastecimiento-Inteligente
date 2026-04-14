import random
from datetime import datetime, timedelta
from core.db_handler import Session, OrderHistory, MasterProv, OrderBuffer

def inject_demo_data():
    print("--- [DEP] Iniciando Inyeccion de Datos Demo 'White-Label' ---")
    session = Session()
    try:
        # Paso 1: Limpieza
        print("Paso 1: Limpiando tablas actuales...")
        session.query(OrderHistory).delete()
        session.query(MasterProv).delete()
        session.query(OrderBuffer).delete()
        
        # Paso 2: Configuración de Maestros Demo
        print("Paso 2: Configurando Proveedores Demo...")
        providers = [
            ("PROV-DEMO-01", "Distribuidora Global Carnicos", "carnicos@demo.sai"),
            ("PROV-DEMO-02", "Panificadora Industrial", "pan@demo.sai"),
            ("PROV-DEMO-03", "Proveedor de Bebidas y Bodega", "bebidas@demo.sai"),
            ("PROV-DEMO-04", "Suministros de Higiene Profesional", "higiene@demo.sai"),
        ]
        
        for p_id, p_name, p_email in providers:
            session.add(MasterProv(
                proveedor_id=p_id,
                nombre=p_name,
                email=p_email,
                frecuencia="DIARIO",
                hora_limite="18:00",
                dias_programados="[0,1,2,3,4,5,6]"
            ))
        
        products = {
            "PROV-DEMO-01": [("SKU-CAR-01", "Costillar Premium", 15.5), ("SKU-CAR-02", "Lomo Vacuno", 22.0)],
            "PROV-DEMO-02": [("SKU-PAN-01", "Pan Baguette", 1.2), ("SKU-PAN-02", "Pan de Campo", 2.5)],
            "PROV-DEMO-03": [("SKU-BEB-01", "Vino Malbec", 12.0), ("SKU-BEB-02", "Agua Mineral", 0.8)],
            "PROV-DEMO-04": [("SKU-HIG-01", "Detergente Industrial", 8.5), ("SKU-HIG-02", "Desinfectante", 5.0)],
        }
        
        # Paso 3: Generación de 50 registros
        print("Paso 3: Generando 50 transacciones realistas...")
        
        locales = [
            ('Local Centro', 0.40),
            ('Local Alta Montana (Logistica Compleja)', 0.30),
            ('Local Estacional', 0.30)
        ]
        
        # Preparar lista de locales expandida para random
        locales_pool = []
        for loc, pct in locales:
            locales_pool.extend([loc] * int(pct * 100))
            
        statuses = ["COMPLETE"] * 42 + ["PARTIAL"] * 5 + ["CANCELLED"] * 3
        random.shuffle(statuses)
        
        now = datetime.now()
        
        for i in range(50):
            status = statuses[i]
            local = random.choice(locales_pool)
            prov_id = random.choice(list(products.keys()))
            sku_info = random.choice(products[prov_id])
            
            sku_id = sku_info[0]
            precio_ref = sku_info[2]
            
            # Cantidad y fechas
            cant_pedida = round(random.uniform(10, 100), 2)
            dias_atras = random.randint(0, 30)
            fecha_pedido = now - timedelta(days=dias_atras, hours=random.randint(0, 12))
            fecha_archivo = fecha_pedido + timedelta(hours=random.randint(2, 24))
            
            # Realidad de recepción
            if status == "COMPLETE":
                cant_recibida = cant_pedida
                incident = ""
            elif status == "PARTIAL":
                cant_recibida = round(cant_pedida * random.uniform(0.5, 0.9), 2)
                incident = "Faltante de stock en origen."
            else: # CANCELLED
                cant_recibida = 0
                incident = "Transporte no pudo llegar por clima/paro."
            
            history_entry = OrderHistory(
                sku_id=sku_id,
                centro_costo=local,
                cantidad=cant_pedida,
                proveedor_id=prov_id,
                fecha_registro=fecha_pedido,
                fecha_archivo=fecha_archivo,
                precio_compra_final=precio_ref,
                total_linea=round(cant_pedida * precio_ref, 2),
                received_quantity=cant_recibida,
                fulfillment_status=status,
                incident_notes=incident
            )
            session.add(history_entry)
            
        session.commit()
        print(f"OK: 50 registros inyectados y maestros configurados.")
    except Exception as e:
        session.rollback()
        print(f"❌ ERROR: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    inject_demo_data()
