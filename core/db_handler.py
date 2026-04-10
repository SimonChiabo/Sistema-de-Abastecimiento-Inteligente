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

if __name__ == "__main__":
    # Prueba rápida de inicialización y lógica
    print("Iniciando prueba de db_handler...")
    add_to_buffer("SKU-TEST-01", 10.0, "LOCAL_01")
    add_to_buffer("SKU-TEST-01", 5.0, "LOCAL_01")
