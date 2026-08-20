"""
core/backtest.py
Reproduce una serie de consumo dia por dia aplicando una politica de reposicion
y mide que habria pasado. Funciones puras: sin red, sin base de datos.

Un modelo sin evaluacion es una idea. El backtest es lo que lo convierte en un
resultado, y lo que permite comparar dos politicas sobre exactamente el mismo
consumo.

Se miden SIEMPRE las dos caras del problema, porque optimizar una sola es
trivial y enganoso: pedir de mas elimina los quiebres y dispara el inventario;
pedir de menos vacia el deposito y rompe el servicio. Una politica solo es mejor
si gana en una dimension sin empeorar la otra.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Protocol, Sequence


@dataclass
class ResultadoBacktest:
    """Que habria pasado al aplicar una politica sobre una serie de consumo."""

    nombre_politica: str
    dias_simulados: int
    dias_con_quiebre: int
    unidades_no_servidas: float
    stock_promedio: float
    stock_maximo: float
    pedidos_emitidos: int
    unidades_pedidas: float

    @property
    def tasa_de_servicio(self) -> float:
        """Proporcion de dias sin quiebre."""
        if not self.dias_simulados:
            return 0.0
        return 1.0 - (self.dias_con_quiebre / self.dias_simulados)


class Politica(Protocol):
    """
    Decide cuanto pedir en un dia dado.

    Recibe el historial de consumo hasta ayer (nunca el de hoy: eso seria
    mirar el futuro), la fecha, el stock actual y lo que ya viene en camino.
    """

    nombre: str

    def cuanto_pedir(
        self,
        historial: Sequence[tuple[date, float]],
        dia: date,
        stock_actual: float,
        pendiente_recepcion: float,
    ) -> float:
        ...


@dataclass
class _Llegada:
    dia: date
    cantidad: float


def simular(
    serie: Sequence[tuple[date, float]],
    politica: Politica,
    lead_time_dias: int,
    stock_inicial: float = 0.0,
    dias_de_calentamiento: int = 28,
) -> ResultadoBacktest:
    """
    Corre la politica sobre la serie y devuelve las metricas.

    Orden de cada dia, deliberadamente conservador:
      1. Llega lo que tenia que llegar hoy.
      2. Se consume lo del dia (si no alcanza, se registra el quiebre).
      3. Se decide el pedido con el stock que queda al cierre.

    Args:
        serie: [(fecha, consumo), ...] en orden cronologico.
        politica: la regla a evaluar.
        lead_time_dias: dias entre emitir el pedido y recibirlo.
        stock_inicial: stock al empezar.
        dias_de_calentamiento: dias iniciales que NO se miden, para que la
            politica junte historial. Sin esto se compara una politica con
            datos contra una sin datos, y el resultado no significa nada.

    Returns:
        ResultadoBacktest con las metricas del periodo medido.
    """
    from datetime import timedelta

    stock = float(stock_inicial)
    llegadas: list[_Llegada] = []
    historial: list[tuple[date, float]] = []

    dias_con_quiebre = 0
    unidades_no_servidas = 0.0
    stocks_registrados: list[float] = []
    pedidos_emitidos = 0
    unidades_pedidas = 0.0
    dias_medidos = 0

    for indice, (dia, consumo) in enumerate(serie):
        # 1. Recepcion
        pendientes_restantes = []
        for llegada in llegadas:
            if llegada.dia <= dia:
                stock += llegada.cantidad
            else:
                pendientes_restantes.append(llegada)
        llegadas = pendientes_restantes

        # 2. Consumo
        se_mide = indice >= dias_de_calentamiento
        servido = min(stock, consumo)
        faltante = consumo - servido
        stock -= servido

        if se_mide:
            dias_medidos += 1
            stocks_registrados.append(stock)
            if faltante > 0:
                dias_con_quiebre += 1
                unidades_no_servidas += faltante

        # 3. Decision de pedido, con el historial hasta ayer inclusive
        pendiente = sum(l.cantidad for l in llegadas)
        cantidad = politica.cuanto_pedir(historial, dia, stock, pendiente)
        if cantidad > 0:
            llegadas.append(_Llegada(dia + timedelta(days=lead_time_dias), cantidad))
            if se_mide:
                pedidos_emitidos += 1
                unidades_pedidas += cantidad

        historial.append((dia, consumo))

    return ResultadoBacktest(
        nombre_politica=politica.nombre,
        dias_simulados=dias_medidos,
        dias_con_quiebre=dias_con_quiebre,
        unidades_no_servidas=round(unidades_no_servidas, 2),
        stock_promedio=round(
            sum(stocks_registrados) / len(stocks_registrados), 2
        ) if stocks_registrados else 0.0,
        stock_maximo=round(max(stocks_registrados), 2) if stocks_registrados else 0.0,
        pedidos_emitidos=pedidos_emitidos,
        unidades_pedidas=round(unidades_pedidas, 2),
    )
