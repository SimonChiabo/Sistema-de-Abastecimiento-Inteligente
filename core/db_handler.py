from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import enum

Base = declarative_base()
DB_URL = "sqlite:///sai_local.db"
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)

class OrderStatus(enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    LATE = "LATE"

class OrderBuffer(Base):
    __tablename__ = "order_buffer"
    
    id = Column(Integer, primary_key=True)
    sku_id = Column(String, nullable=False)
    centro_costo = Column(String, nullable=False)
    cantidad = Column(Float, nullable=False)
    proveedor_id = Column(String)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING)
    fecha_registro = Column(DateTime, default=datetime.utcnow)
    fecha_despacho_esperada = Column(DateTime)

class OrderHistory(Base):
    __tablename__ = "order_history"
    
    id = Column(Integer, primary_key=True)
    sku_id = Column(String, nullable=False)
    centro_costo = Column(String, nullable=False)
    cantidad = Column(Float, nullable=False)
    proveedor_id = Column(String)
    fecha_registro = Column(DateTime)
    fecha_archivo = Column(DateTime, default=datetime.utcnow)
    precio_compra_final = Column(Float)
    total_linea = Column(Float)
    archivo_adjunto_path = Column(String)
    fulfillment_status = Column(String, default="SENT") # SENT, COMPLETE, PARTIAL, CANCELLED
    received_quantity = Column(Float)
    incident_notes = Column(String)

# Inicializar Base de Datos
Base.metadata.create_all(engine)

def add_to_buffer(sku_id, cantidad, centro_costo, proveedor_id=None, fecha_despacho=None):
    """
    Agrega un pedido al buffer. Si ya existe uno PENDING para el mismo SKU y Centro de Costo,
    se acumula la cantidad.
    """
    session = Session()
    try:
        existing_order = session.query(OrderBuffer).filter(
            OrderBuffer.sku_id == sku_id,
            OrderBuffer.centro_costo == centro_costo,
            OrderBuffer.status == OrderStatus.PENDING
        ).first()

        if existing_order:
            existing_order.cantidad += cantidad
            print(f"DEBUG: Consolidando {cantidad} a SKU {sku_id} en {centro_costo}. Nueva cant: {existing_order.cantidad}")
        else:
            new_order = OrderBuffer(
                sku_id=sku_id,
                cantidad=cantidad,
                centro_costo=centro_costo,
                proveedor_id=proveedor_id,
                fecha_despacho_esperada=fecha_despacho
            )
            session.add(new_order)
            print(f"DEBUG: Nuevo registro en buffer para SKU {sku_id} en {centro_costo}.")

        session.commit()
    except Exception as e:
        session.rollback()
        print(f"ERROR en db_handler.add_to_buffer: {e}")
    finally:
        session.close()

def archive_orders(provider_id, file_path, sku_prices=None):
    """
    Mueve pedidos SENT al historial y los elimina del buffer activo.
    Calcula totales financieros basados en sku_prices {sku_id: precio}.
    """
    session = Session()
    try:
        sent_orders = session.query(OrderBuffer).filter(
            OrderBuffer.proveedor_id == provider_id,
            OrderBuffer.status == OrderStatus.SENT
        ).all()

        for order in sent_orders:
            precio = sku_prices.get(order.sku_id, 0.0) if sku_prices else 0.0
            history_entry = OrderHistory(
                sku_id=order.sku_id,
                centro_costo=order.centro_costo,
                cantidad=order.cantidad,
                proveedor_id=order.proveedor_id,
                fecha_registro=order.fecha_registro,
                precio_compra_final=precio,
                total_linea=order.cantidad * precio,
                archivo_adjunto_path=file_path,
                received_quantity=order.cantidad,
                fulfillment_status="SENT"
            )
            session.add(history_entry)
            session.delete(order)
        
        session.commit()
        print(f"ARCHIVE: {len(sent_orders)} registros movidos al historial para {provider_id}.")
    except Exception as e:
        session.rollback()
        print(f"ERROR en archiving: {e}")
    finally:
        session.close()

def update_history_fulfillment(history_id, received_qty, status, notes=None):
    """Actualiza un registro histórico con la realidad de la recepción."""
    session = Session()
    try:
        entry = session.query(OrderHistory).filter(OrderHistory.id == history_id).first()
        if entry:
            entry.received_quantity = received_qty
            entry.fulfillment_status = status
            if notes: entry.incident_notes = notes
            session.commit()
            return True
    except Exception as e:
        session.rollback()
        print(f"ERROR actualizando historia: {e}")
    finally:
        session.close()
    return False

if __name__ == "__main__":
    # Prueba rápida de inicialización y lógica
    print("Iniciando prueba de db_handler...")
    add_to_buffer("SKU-TEST-01", 10.0, "LOCAL_01")
    add_to_buffer("SKU-TEST-01", 5.0, "LOCAL_01")
