"""
demo_injector.py — Inyector de datos de demostración 'white-label'.
Limpia las tablas y genera 50 transacciones realistas con proveedores DEMO.
"""
import logging
import random
from datetime import datetime, timedelta

from core.db_handler import MasterProv, MasterSku, OrderBuffer, OrderHistory, Session
from core.log_config import configurar_logging

logger = logging.getLogger(__name__)


def inject_demo_data() -> None:
    """Limpia la base de datos e inyecta datos de demostración."""
    logger.info("Iniciando inyección de datos demo 'white-label'...")
    session = Session()
    try:
        # Paso 1: Limpieza
        logger.info("Limpiando tablas actuales...")
        session.query(OrderHistory).delete()
        session.query(MasterProv).delete()
        session.query(OrderBuffer).delete()

        # Paso 2: Configuración de maestros demo
        logger.info("Configurando proveedores demo...")
        proveedores = [
            ("PROV-DEMO-01", "Distribuidora Global Carnicos",      "carnicos@demo.sai"),
            ("PROV-DEMO-02", "Panificadora Industrial",            "pan@demo.sai"),
            ("PROV-DEMO-03", "Proveedor de Bebidas y Bodega",      "bebidas@demo.sai"),
            ("PROV-DEMO-04", "Suministros de Higiene Profesional", "higiene@demo.sai"),
        ]

        for p_id, p_nombre, p_email in proveedores:
            session.add(
                MasterProv(
                    proveedor_id=p_id,
                    nombre=p_nombre,
                    email=p_email,
                    frecuencia="DIARIO",
                    hora_limite="18:00",
                    dias_programados="[0,1,2,3,4,5,6]",
                )
            )

        # Registrar SKUs en el maestro local también
        productos_por_prov = {
            "PROV-DEMO-01": [
                ("SKU-CAR-01", "Costillar Premium", "Carnes", "Por kg", 15.5),
                ("SKU-CAR-02", "Lomo Vacuno", "Carnes", "Por kg", 22.0),
                ("SKU-CAR-03", "Chorizo de Campo", "Carnes", "Pack 1kg", 8.0),
            ],
            "PROV-DEMO-02": [
                ("SKU-PAN-01", "Pan Baguette", "Panificados", "Unidad", 1.2),
                ("SKU-PAN-02", "Pan de Campo", "Panificados", "Unidad", 2.5),
            ],
            "PROV-DEMO-03": [
                ("SKU-BEB-01", "Vino Malbec", "Bebidas", "Botella 750ml", 12.0),
                ("SKU-BEB-02", "Agua Mineral", "Bebidas", "Bidon 5L", 0.8),
                ("SKU-BEB-03", "Cerveza Artesanal", "Bebidas", "Lata 473ml", 4.5),
            ],
            "PROV-DEMO-04": [
                ("SKU-HIG-01", "Detergente Industrial", "Limpieza", "Bidon 5L", 8.5),
                ("SKU-HIG-02", "Desinfectante", "Limpieza", "Botella 1L", 5.0),
            ],
        }

        for prov_id, lista_skus in productos_por_prov.items():
            for sku_id, nombre, categoria, presentacion, precio in lista_skus:
                session.add(
                    MasterSku(
                        sku_id=sku_id,
                        nombre=nombre,
                        categoria=categoria,
                        presentacion=presentacion,
                        proveedor_id=prov_id,
                        precio_ref=precio,
                    )
                )

        # Tabla plana para selección aleatoria en transacciones
        productos_demo = {
            "PROV-DEMO-01": [("SKU-CAR-01", 15.5), ("SKU-CAR-02", 22.0)],
            "PROV-DEMO-02": [("SKU-PAN-01", 1.2), ("SKU-PAN-02", 2.5)],
            "PROV-DEMO-03": [("SKU-BEB-01", 12.0), ("SKU-BEB-02", 0.8)],
            "PROV-DEMO-04": [("SKU-HIG-01", 8.5), ("SKU-HIG-02", 5.0)],
        }

        # Paso 3: Generación de 50 transacciones realistas
        logger.info("Generando 50 transacciones realistas...")

        locales = [
            ("Local Centro", 0.40),
            ("Local Alta Montana (Logistica Compleja)", 0.30),
            ("Local Estacional", 0.30),
        ]
        pool_locales = []
        for nombre_local, pct in locales:
            pool_locales.extend([nombre_local] * int(pct * 100))

        estatuses = ["COMPLETE"] * 42 + ["PARTIAL"] * 5 + ["CANCELLED"] * 3
        random.shuffle(estatuses)

        ahora = datetime.now()

        for i in range(50):
            estatus = estatuses[i]
            local = random.choice(pool_locales)
            prov_id = random.choice(list(productos_demo.keys()))
            sku_id, precio_ref = random.choice(productos_demo[prov_id])

            cant_pedida = round(random.uniform(10, 100), 2)
            dias_atras = random.randint(0, 30)
            fecha_pedido = ahora - timedelta(days=dias_atras, hours=random.randint(0, 12))
            fecha_archivo = fecha_pedido + timedelta(hours=random.randint(2, 24))

            if estatus == "COMPLETE":
                cant_recibida = cant_pedida
                incidencia = ""
            elif estatus == "PARTIAL":
                cant_recibida = round(cant_pedida * random.uniform(0.5, 0.9), 2)
                incidencia = "Faltante de stock en origen."
            else:  # CANCELLED
                cant_recibida = 0
                incidencia = "Transporte no pudo llegar por clima/paro."

            session.add(
                OrderHistory(
                    sku_id=sku_id,
                    centro_costo=local,
                    cantidad=cant_pedida,
                    proveedor_id=prov_id,
                    fecha_registro=fecha_pedido,
                    fecha_archivo=fecha_archivo,
                    precio_compra_final=precio_ref,
                    total_linea=round(cant_pedida * precio_ref, 2),
                    received_quantity=cant_recibida,
                    fulfillment_status=estatus,
                    incident_notes=incidencia,
                )
            )

        session.commit()
        logger.info("50 registros inyectados y maestros configurados correctamente.")

    except Exception as error:
        session.rollback()
        logger.error("Error en inyección de datos demo: %s", error)
    finally:
        session.close()


if __name__ == "__main__":
    configurar_logging()
    inject_demo_data()
