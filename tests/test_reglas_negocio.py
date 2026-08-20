"""
Tests de las reglas de negocio de SAI.

No buscan cobertura: buscan dejar escrita la regla. Cada test documenta una
decision de diseno que un refactor podria romper en silencio.
"""

from datetime import time

import pytest

from core.db_handler import (
    OrderBuffer,
    OrderHistory,
    OrderStatus,
    add_to_buffer,
    archive_orders,
    delete_pending_orders,
    resolve_claim,
    update_history_fulfillment,
)
from core.rules import calcular_fill_rate, determinar_estado_pedido


# ---------------------------------------------------------------------------
# Corte por horario limite del proveedor
# ---------------------------------------------------------------------------

def test_pedido_antes_del_corte_queda_pendiente():
    estado, mensaje = determinar_estado_pedido(time(9, 30), "18:00")
    assert estado == OrderStatus.PENDING
    assert mensaje == "OK 09:30"


def test_pedido_despues_del_corte_queda_late():
    """Un pedido tardio no se pierde ni entra en la orden ya cerrada: espera."""
    estado, mensaje = determinar_estado_pedido(time(19, 15), "18:00")
    assert estado == OrderStatus.LATE
    assert mensaje == "LATE (18:00)"


def test_en_la_hora_exacta_el_pedido_todavia_entra():
    """El corte es "despues de", no "desde": a las 18:00 en punto entra."""
    estado, _ = determinar_estado_pedido(time(18, 0), "18:00")
    assert estado == OrderStatus.PENDING


def test_modo_manual_saltea_el_corte():
    """El flag --manual existe para demostraciones fuera de horario."""
    estado, mensaje = determinar_estado_pedido(time(23, 50), "08:00", modo_manual=True)
    assert estado == OrderStatus.PENDING
    assert mensaje == "MANUAL 23:50"


def test_proveedor_sin_horario_configurado_no_tiene_corte_efectivo():
    """Sin hora_limite en el maestro se asume 23:59, no se bloquea el pedido."""
    estado, _ = determinar_estado_pedido(time(23, 0), None)
    assert estado == OrderStatus.PENDING


def test_horario_mal_cargado_falla_ruidosamente():
    """
    El orquestador captura por fila, asi que una celda mal cargada en el
    maestro afecta a ese pedido y no al ciclo completo. Fallar es preferible
    a asumir un horario por defecto y despachar fuera de termino.
    """
    with pytest.raises(ValueError):
        determinar_estado_pedido(time(10, 0), "6 de la tarde")


# ---------------------------------------------------------------------------
# Consolidacion en el buffer
# ---------------------------------------------------------------------------

def test_consolida_dos_pedidos_del_mismo_sku_y_local(session):
    """Dos cargas del mismo SKU en el mismo local son una sola linea de compra."""
    add_to_buffer("SKU-01", 10.0, "LOCAL_NORTE")
    add_to_buffer("SKU-01", 5.0, "LOCAL_NORTE")

    filas = session.query(OrderBuffer).filter(OrderBuffer.sku_id == "SKU-01").all()
    assert len(filas) == 1
    assert filas[0].cantidad == 15.0


def test_no_consolida_entre_centros_de_costo_distintos(session):
    """La trazabilidad por local es lo que permite imputar el costo."""
    add_to_buffer("SKU-01", 10.0, "LOCAL_NORTE")
    add_to_buffer("SKU-01", 7.0, "LOCAL_SUR")

    filas = session.query(OrderBuffer).filter(OrderBuffer.sku_id == "SKU-01").all()
    assert len(filas) == 2
    assert {f.centro_costo: f.cantidad for f in filas} == {
        "LOCAL_NORTE": 10.0,
        "LOCAL_SUR": 7.0,
    }


def test_no_consolida_sobre_un_pedido_ya_despachado(session):
    """Un pedido SENT ya salio al proveedor: lo nuevo es una linea aparte."""
    add_to_buffer("SKU-01", 10.0, "LOCAL_NORTE", status=OrderStatus.SENT)
    add_to_buffer("SKU-01", 4.0, "LOCAL_NORTE")

    filas = session.query(OrderBuffer).filter(OrderBuffer.sku_id == "SKU-01").all()
    assert len(filas) == 2
    assert sorted(f.cantidad for f in filas) == [4.0, 10.0]


def test_cancelar_borra_pendientes_y_tardios_pero_no_despachados(session):
    """No se puede cancelar lo que el proveedor ya recibio."""
    add_to_buffer("SKU-01", 3.0, "LOCAL_NORTE", status=OrderStatus.PENDING)
    add_to_buffer("SKU-02", 6.0, "LOCAL_NORTE", status=OrderStatus.LATE)
    add_to_buffer("SKU-03", 9.0, "LOCAL_NORTE", status=OrderStatus.SENT)

    assert delete_pending_orders("SKU-01", "LOCAL_NORTE") == 1
    assert delete_pending_orders("SKU-02", "LOCAL_NORTE") == 1
    assert delete_pending_orders("SKU-03", "LOCAL_NORTE") == 0

    restantes = session.query(OrderBuffer).all()
    assert [r.sku_id for r in restantes] == ["SKU-03"]


# ---------------------------------------------------------------------------
# Archivado y verdad financiera
# ---------------------------------------------------------------------------

def test_archivar_calcula_el_total_y_vacia_el_buffer(session):
    add_to_buffer("SKU-01", 10.0, "LOCAL_NORTE", proveedor_id="PROV-01",
                  status=OrderStatus.SENT)

    archive_orders("PROV-01", "outbox/oc.pdf", sku_prices={"SKU-01": 25.0})

    assert session.query(OrderBuffer).count() == 0
    h = session.query(OrderHistory).one()
    assert h.cantidad == 10.0
    assert h.total_linea == 250.0
    assert h.received_quantity == 10.0, "al despachar se asume entrega completa"
    assert h.fulfillment_status == "SENT"


def test_un_faltante_baja_el_total_real_sin_tocar_lo_pedido(session):
    """
    La regla mas importante y la mas facil de romper en un refactor.

    Un reclamo por faltante ajusta la metrica financiera del proveedor
    --- lo que efectivamente hay que pagarle --- pero NO reescribe la cantidad
    pedida. Si un refactor "corrigiera" cantidad para que coincida con lo
    recibido, el fill rate daria 100% siempre y el reclamo desapareceria
    del analisis.
    """
    add_to_buffer("SKU-01", 10.0, "LOCAL_NORTE", proveedor_id="PROV-01",
                  status=OrderStatus.SENT)
    archive_orders("PROV-01", "outbox/oc.pdf", sku_prices={"SKU-01": 25.0})
    h = session.query(OrderHistory).one()

    update_history_fulfillment(h.id, received_qty=6.0, status="PARTIAL",
                               notes="Faltaron 4 unidades")

    session.expire_all()
    h = session.query(OrderHistory).one()

    assert h.cantidad == 10.0, "lo pedido no se reescribe"
    assert h.received_quantity == 6.0, "el inventario refleja lo que llego"
    assert h.total_linea == 250.0, "el compromiso original queda registrado"

    total_real = h.received_quantity * h.precio_compra_final
    assert total_real == 150.0, "se le paga al proveedor lo que entrego"
    assert calcular_fill_rate(h.cantidad, h.received_quantity) == 0.6


def test_reclamo_entregado_restituye_la_cantidad(session):
    """Si el proveedor completa la entrega, el fill rate vuelve a 100%."""
    add_to_buffer("SKU-01", 10.0, "LOCAL_NORTE", proveedor_id="PROV-01",
                  status=OrderStatus.SENT)
    archive_orders("PROV-01", "outbox/oc.pdf", sku_prices={"SKU-01": 25.0})
    h = session.query(OrderHistory).one()
    update_history_fulfillment(h.id, received_qty=6.0, status="PARTIAL")

    resolve_claim(h.id, "RESUELTO_ENTREGADO")

    session.expire_all()
    h = session.query(OrderHistory).one()
    assert h.received_quantity == 10.0
    assert h.fulfillment_status == "COMPLETE_RECTIFIED"
    assert calcular_fill_rate(h.cantidad, h.received_quantity) == 1.0


def test_reclamo_cancelado_deja_el_faltante_registrado(session):
    """
    Si el proveedor no puede reponer, el faltante NO se perdona: la cantidad
    recibida sigue baja y el incumplimiento queda en su metrica.
    """
    add_to_buffer("SKU-01", 10.0, "LOCAL_NORTE", proveedor_id="PROV-01",
                  status=OrderStatus.SENT)
    archive_orders("PROV-01", "outbox/oc.pdf", sku_prices={"SKU-01": 25.0})
    h = session.query(OrderHistory).one()
    update_history_fulfillment(h.id, received_qty=6.0, status="PARTIAL")

    resolve_claim(h.id, "CANCELADO_SIN_STOCK")

    session.expire_all()
    h = session.query(OrderHistory).one()
    assert h.received_quantity == 6.0, "el faltante no se borra al cerrar el reclamo"
    assert h.fulfillment_status == "PARTIAL_CLOSED"
    assert calcular_fill_rate(h.cantidad, h.received_quantity) == 0.6


# ---------------------------------------------------------------------------
# Fill rate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pedido,recibido,esperado", [
    (10.0, 10.0, 1.0),
    (10.0, 0.0, 0.0),
    (8.0, 6.0, 0.75),
    (10.0, 12.0, 1.2),   # sobre-entrega: se registra, no se recorta
])
def test_fill_rate(pedido, recibido, esperado):
    assert calcular_fill_rate(pedido, recibido) == esperado


def test_fill_rate_indefinido_si_no_se_pidio_nada():
    assert calcular_fill_rate(0.0, 0.0) is None
