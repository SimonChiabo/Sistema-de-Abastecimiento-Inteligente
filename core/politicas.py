"""
core/politicas.py
Politicas de reposicion evaluables con core/backtest.py.

Se implementan dos para poder comparar: la que aproxima lo que hace un operario
con una planilla (promedio plano, sin colchon) y la del modelo (estacionalidad
por dia de semana + stock de seguridad). El valor del ejercicio esta en la
comparacion, no en cualquiera de las dos por separado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from core.forecast import (
    NIVEL_SERVICIO_POR_DEFECTO,
    VENTANA_POR_DEFECTO,
    consumo_esperado_en_lead_time,
    desvio_estandar,
    factores_por_dia_semana,
    promedio_movil,
    punto_de_reorden,
    stock_de_seguridad,
    sugerencia_de_pedido,
)


@dataclass
class PoliticaPromedioPlano:
    """
    Linea de base: pedir para cubrir el consumo promedio durante el lead time.

    Es la aproximacion de lo que hace alguien con una planilla y buen criterio:
    mira el promedio de las ultimas semanas y repone contra eso. No modela la
    estacionalidad ni deja colchon para la variabilidad.
    """

    lead_time_dias: int
    ventana: int = VENTANA_POR_DEFECTO
    nombre: str = "Promedio plano (linea de base)"

    def cuanto_pedir(
        self,
        historial: Sequence[tuple[date, float]],
        dia: date,
        stock_actual: float,
        pendiente_recepcion: float,
    ) -> float:
        consumos = [c for _, c in historial]
        base = promedio_movil(consumos, self.ventana)
        objetivo = punto_de_reorden(
            consumo_esperado_en_lead_time(base, self.lead_time_dias),
            stock_seguridad=0.0,
        )
        return sugerencia_de_pedido(objetivo, stock_actual, pendiente_recepcion)


@dataclass
class PoliticaPromedioConSeguridad:
    """
    Promedio plano MAS stock de seguridad, sin modelar estacionalidad.

    Existe para separar dos efectos que de otro modo se confunden. Comparar
    solo "promedio plano sin colchon" contra "estacional con colchon" atribuye
    a la estacionalidad una mejora que en buena parte viene del colchon. Esta
    politica es la linea de base honesta: cualquier diferencia contra ella si
    es merito de modelar el dia de semana.
    """

    lead_time_dias: int
    ventana: int = VENTANA_POR_DEFECTO
    nivel_servicio: float = NIVEL_SERVICIO_POR_DEFECTO
    nombre: str = "Promedio + stock de seguridad"

    def cuanto_pedir(
        self,
        historial: Sequence[tuple[date, float]],
        dia: date,
        stock_actual: float,
        pendiente_recepcion: float,
    ) -> float:
        consumos = [c for _, c in historial]
        base = promedio_movil(consumos, self.ventana)
        colchon = stock_de_seguridad(
            desvio_estandar(consumos, self.ventana),
            self.lead_time_dias,
            self.nivel_servicio,
        )
        objetivo = punto_de_reorden(
            consumo_esperado_en_lead_time(base, self.lead_time_dias), colchon
        )
        return sugerencia_de_pedido(objetivo, stock_actual, pendiente_recepcion)


@dataclass
class PoliticaEstacionalConSeguridad:
    """
    El modelo: promedio movil ajustado por dia de semana, mas stock de
    seguridad dimensionado por la variabilidad observada y el lead time.
    """

    lead_time_dias: int
    ventana: int = VENTANA_POR_DEFECTO
    nivel_servicio: float = NIVEL_SERVICIO_POR_DEFECTO
    nombre: str = "Estacional + stock de seguridad"

    def cuanto_pedir(
        self,
        historial: Sequence[tuple[date, float]],
        dia: date,
        stock_actual: float,
        pendiente_recepcion: float,
    ) -> float:
        consumos = [c for _, c in historial]
        base = promedio_movil(consumos, self.ventana)
        factores = factores_por_dia_semana(list(historial)[-self.ventana:])

        esperado = consumo_esperado_en_lead_time(
            base, self.lead_time_dias, dia_inicial=dia, factores=factores
        )
        colchon = stock_de_seguridad(
            desvio_estandar(consumos, self.ventana),
            self.lead_time_dias,
            self.nivel_servicio,
        )
        objetivo = punto_de_reorden(esperado, colchon)
        return sugerencia_de_pedido(objetivo, stock_actual, pendiente_recepcion)
