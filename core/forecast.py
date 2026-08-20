"""
core/forecast.py
Modelo de proyeccion de pedidos. Funciones puras: sin red, sin base de datos,
sin reloj propio. No importa nada del resto del proyecto a proposito, para que
se pueda testear y razonar de forma aislada.

El modelo responde una sola pregunta: cuanto conviene pedir hoy de un SKU en un
local, dado lo que se consumio antes y cuanto tarda el proveedor en entregar.

    consumo base   ->  promedio movil de los ultimos N dias
    estacionalidad ->  factor por dia de semana (critico en hosteleria)
    incertidumbre  ->  stock de seguridad = z * desvio * raiz(lead time)
    punto de pedido->  consumo esperado durante el lead time + stock de seguridad
    sugerencia     ->  punto de pedido - stock actual - pendiente de recepcion
"""

from __future__ import annotations

import math
from datetime import date
from typing import Iterable, Mapping, Sequence

# Valores de z para niveles de servicio habituales. Se tabulan en vez de
# depender de scipy: el proyecto no tiene esa dependencia y son cuatro numeros.
_Z_POR_NIVEL_SERVICIO = {
    0.90: 1.2816,
    0.95: 1.6449,
    0.975: 1.9600,
    0.99: 2.3263,
}

NIVEL_SERVICIO_POR_DEFECTO = 0.95
VENTANA_POR_DEFECTO = 28


def promedio_movil(consumos: Sequence[float], ventana: int = VENTANA_POR_DEFECTO) -> float:
    """
    Consumo diario promedio sobre los ultimos `ventana` dias.

    Una ventana movil y no el promedio historico completo: en hosteleria el
    consumo de hace seis meses no informa sobre el de esta semana.
    """
    if ventana <= 0:
        raise ValueError("La ventana debe ser mayor que cero.")
    if not consumos:
        return 0.0
    recientes = list(consumos)[-ventana:]
    return sum(recientes) / len(recientes)


def desvio_estandar(consumos: Sequence[float], ventana: int = VENTANA_POR_DEFECTO) -> float:
    """
    Desvio estandar muestral del consumo en la ventana.

    Mide cuan erratico es el consumo. Es lo que separa un SKU predecible de uno
    que necesita colchon: el promedio no distingue entre vender 10 todos los
    dias y vender 0 o 20 dia por medio.
    """
    recientes = list(consumos)[-ventana:] if consumos else []
    if len(recientes) < 2:
        return 0.0
    media = sum(recientes) / len(recientes)
    varianza = sum((x - media) ** 2 for x in recientes) / (len(recientes) - 1)
    return math.sqrt(varianza)


def factores_por_dia_semana(
    serie: Iterable[tuple[date, float]],
    minimo_observaciones: int = 2,
) -> dict[int, float]:
    """
    Factor multiplicativo de consumo por dia de semana (0 = lunes).

    Un restaurante no consume lo mismo un martes que un sabado. El factor
    normaliza cada dia contra el promedio general: 1.4 significa "los sabados se
    consume un 40% mas que un dia promedio".

    Los dias con menos de `minimo_observaciones` registros quedan en 1.0: con un
    solo dato no hay estacionalidad, hay ruido.

    Returns:
        Diccionario con los 7 dias. Si no hay datos suficientes, todos en 1.0.
    """
    por_dia: dict[int, list[float]] = {d: [] for d in range(7)}
    for fecha, cantidad in serie:
        por_dia[fecha.weekday()].append(cantidad)

    todos = [c for valores in por_dia.values() for c in valores]
    if not todos:
        return {d: 1.0 for d in range(7)}

    media_general = sum(todos) / len(todos)
    if media_general == 0:
        return {d: 1.0 for d in range(7)}

    factores = {}
    for dia, valores in por_dia.items():
        if len(valores) < minimo_observaciones:
            factores[dia] = 1.0
        else:
            factores[dia] = (sum(valores) / len(valores)) / media_general
    return factores


def consumo_esperado_en_lead_time(
    consumo_base: float,
    lead_time_dias: int,
    dia_inicial: date | None = None,
    factores: Mapping[int, float] | None = None,
) -> float:
    """
    Consumo previsto entre que se emite el pedido y que llega.

    Si hay factores estacionales y una fecha de inicio, suma dia por dia
    aplicando el factor de cada uno; si no, multiplica el consumo base por el
    lead time. La diferencia importa: un pedido emitido un jueves con entrega el
    lunes atraviesa el fin de semana, que es justo cuando mas se consume.
    """
    if lead_time_dias <= 0:
        return 0.0
    if factores is None or dia_inicial is None:
        return consumo_base * lead_time_dias

    from datetime import timedelta

    total = 0.0
    for offset in range(lead_time_dias):
        dia = dia_inicial + timedelta(days=offset)
        total += consumo_base * factores.get(dia.weekday(), 1.0)
    return total


def stock_de_seguridad(
    desvio_diario: float,
    lead_time_dias: int,
    nivel_servicio: float = NIVEL_SERVICIO_POR_DEFECTO,
) -> float:
    """
    Colchon para absorber la variabilidad del consumo durante el lead time.

    Formula: z * desvio_diario * raiz(lead_time).

    La raiz --- y no el lead time completo --- porque los desvios diarios se
    compensan parcialmente entre si: dos dias malos seguidos son menos probables
    que un dia malo. Multiplicar por el lead time entero sobre-dimensiona el
    colchon y encarece el inventario sin mejorar el servicio.

    Raises:
        ValueError: si el nivel de servicio no esta tabulado.
    """
    if lead_time_dias <= 0:
        return 0.0
    if nivel_servicio not in _Z_POR_NIVEL_SERVICIO:
        raise ValueError(
            f"Nivel de servicio {nivel_servicio} no tabulado. "
            f"Disponibles: {sorted(_Z_POR_NIVEL_SERVICIO)}"
        )
    z = _Z_POR_NIVEL_SERVICIO[nivel_servicio]
    return z * desvio_diario * math.sqrt(lead_time_dias)


def punto_de_reorden(consumo_en_lead_time: float, stock_seguridad: float) -> float:
    """Nivel de stock por debajo del cual conviene emitir el pedido."""
    return consumo_en_lead_time + stock_seguridad


def sugerencia_de_pedido(
    punto_reorden: float,
    stock_actual: float,
    pendiente_recepcion: float = 0.0,
) -> float:
    """
    Cuanto pedir hoy. Nunca negativo.

    `pendiente_recepcion` es lo ya pedido que todavia no llego. Restarlo es lo
    que evita el error mas caro de un sistema de reposicion: volver a pedir algo
    que ya viene en camino porque el stock todavia se ve bajo. Sin ese termino,
    un lead time de tres dias genera tres pedidos del mismo faltante.
    """
    faltante = punto_reorden - stock_actual - pendiente_recepcion
    return max(0.0, faltante)


def lead_time_por_dias_programados(
    dias_programados: Sequence[int],
    dia_actual: date,
) -> int:
    """
    Lead time por defecto derivado del calendario de entrega del proveedor.

    MASTER_PROV guarda `dias_programados` (que dias entrega) pero **no** guarda
    un lead time real. Los dias hasta la proxima entrega programada son una cota
    inferior util para que el modelo corra sin configuracion adicional: si el
    proveedor entrega martes y viernes, un pedido del miercoles no puede llegar
    antes del viernes.

    No es una medicion del tiempo que el proveedor efectivamente tarda. Cablear
    un lead time observado en MASTER_PROV es el paso pendiente.

    Returns:
        Dias hasta la proxima entrega (minimo 1). Si no hay dias programados,
        asume 1.
    """
    if not dias_programados:
        return 1
    validos = sorted({d for d in dias_programados if 0 <= d <= 6})
    if not validos:
        return 1
    hoy = dia_actual.weekday()
    for offset in range(1, 8):
        if (hoy + offset) % 7 in validos:
            return offset
    return 1
