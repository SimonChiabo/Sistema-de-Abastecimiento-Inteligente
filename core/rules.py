"""
core/rules.py
Reglas de negocio puras: sin red, sin base de datos, sin reloj propio.

Se extraen del orquestador para que puedan testearse y para que la regla quede
escrita en un solo lugar. Todo lo que dependa del entorno (la hora actual, la
fila del Sheet) se recibe como argumento.
"""

from datetime import datetime, time
from typing import Optional

from core.db_handler import OrderStatus

HORA_LIMITE_POR_DEFECTO = "23:59"


def determinar_estado_pedido(
    ahora: time,
    hora_limite_str: Optional[str] = None,
    modo_manual: bool = False,
) -> tuple[OrderStatus, str]:
    """
    Decide si un pedido entra en el ciclo actual o queda para el siguiente.

    Cada proveedor tiene su propio horario de corte. Un pedido cargado después
    de esa hora no se pierde ni se cuela en una orden ya cerrada: queda LATE y
    entra en el ciclo siguiente.

    Args:
        ahora:           Hora de carga del pedido.
        hora_limite_str: Corte del proveedor en formato "HH:MM". Si es None o
                         vacío se usa 23:59, es decir, no hay corte efectivo.
        modo_manual:     El flag --manual de demostración saltea el corte.

    Returns:
        (estado, mensaje_log) — el mensaje es el que se escribe en la columna F
        del Sheet del local.

    Raises:
        ValueError: si hora_limite_str no respeta el formato "HH:MM". El
            orquestador captura por fila, así que una celda mal cargada en el
            maestro afecta a ese pedido y no al ciclo completo.
    """
    limite_str = hora_limite_str or HORA_LIMITE_POR_DEFECTO
    hora_limite = datetime.strptime(limite_str, "%H:%M").time()

    if modo_manual:
        return OrderStatus.PENDING, f"MANUAL {ahora.strftime('%H:%M')}"

    if ahora > hora_limite:
        return OrderStatus.LATE, f"LATE ({limite_str})"

    return OrderStatus.PENDING, f"OK {ahora.strftime('%H:%M')}"


def calcular_fill_rate(cantidad_pedida: float, cantidad_recibida: float) -> Optional[float]:
    """
    Proporción de lo pedido que el proveedor efectivamente entregó.

    Es la métrica que mide al proveedor, no al inventario: el inventario refleja
    lo que llegó, el fill rate refleja la diferencia entre lo prometido y lo
    cumplido.

    Returns:
        Valor entre 0.0 y 1.0, o None si no se pidió nada (no hay fill rate
        definido para un pedido de cantidad cero).
    """
    if not cantidad_pedida:
        return None
    return cantidad_recibida / cantidad_pedida
