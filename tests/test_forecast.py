"""
Tests del modelo de proyeccion de pedidos y del motor de backtesting.

core/forecast.py y core/backtest.py no importan nada del proyecto ni tocan la
base, asi que estos tests corren sin infraestructura.
"""

from datetime import date, timedelta

import pytest

from core.backtest import simular
from core.forecast import (
    consumo_esperado_en_lead_time,
    desvio_estandar,
    factores_por_dia_semana,
    lead_time_por_dias_programados,
    promedio_movil,
    punto_de_reorden,
    stock_de_seguridad,
    sugerencia_de_pedido,
)
from core.politicas import PoliticaEstacionalConSeguridad, PoliticaPromedioPlano


# ---------------------------------------------------------------------------
# Consumo base
# ---------------------------------------------------------------------------

def test_promedio_movil_solo_mira_la_ventana():
    """El consumo viejo no informa sobre el actual: la ventana lo descarta."""
    consumos = [100.0] * 10 + [10.0] * 5
    assert promedio_movil(consumos, ventana=5) == 10.0


def test_promedio_movil_con_menos_datos_que_la_ventana():
    assert promedio_movil([10.0, 20.0], ventana=28) == 15.0


def test_promedio_movil_sin_datos():
    assert promedio_movil([], ventana=7) == 0.0


def test_desvio_distingue_consumo_estable_de_erratico():
    """
    El promedio no alcanza para dimensionar el colchon: dos series con la
    misma media pueden necesitar inventarios muy distintos.
    """
    estable = [10.0] * 10
    erratico = [0.0, 20.0] * 5
    assert promedio_movil(estable) == promedio_movil(erratico) == 10.0
    assert desvio_estandar(estable) == 0.0
    assert desvio_estandar(erratico) > 9.0


# ---------------------------------------------------------------------------
# Estacionalidad
# ---------------------------------------------------------------------------

def test_factores_detectan_el_fin_de_semana():
    """Un local que vende el doble los sabados debe dar factor ~2 ese dia."""
    serie = []
    inicio = date(2025, 1, 6)  # lunes
    for semana in range(6):
        for offset in range(7):
            dia = inicio + timedelta(days=semana * 7 + offset)
            serie.append((dia, 20.0 if dia.weekday() == 5 else 10.0))

    factores = factores_por_dia_semana(serie)
    assert factores[5] > factores[0]
    assert factores[5] == pytest.approx(20.0 / (80.0 / 7), rel=1e-6)


def test_factores_ignoran_dias_con_un_solo_dato():
    """Con una sola observacion no hay estacionalidad, hay ruido."""
    serie = [(date(2025, 1, 6), 10.0), (date(2025, 1, 7), 500.0)]
    factores = factores_por_dia_semana(serie, minimo_observaciones=2)
    assert factores[1] == 1.0


def test_factores_neutros_si_no_hay_datos():
    assert factores_por_dia_semana([]) == {d: 1.0 for d in range(7)}


def test_el_lead_time_atraviesa_los_dias_fuertes():
    """
    Un pedido del jueves con entrega el domingo cruza el fin de semana. Aplanar
    el consumo sub-dimensiona justo el pedido que mas importa.
    """
    factores = {0: 0.7, 1: 0.7, 2: 0.7, 3: 1.0, 4: 1.5, 5: 2.0, 6: 1.4}
    jueves = date(2025, 1, 9)

    con_estacionalidad = consumo_esperado_en_lead_time(
        10.0, 3, dia_inicial=jueves, factores=factores
    )
    plano = consumo_esperado_en_lead_time(10.0, 3)

    assert con_estacionalidad == pytest.approx(10.0 * (1.0 + 1.5 + 2.0))
    assert con_estacionalidad > plano


# ---------------------------------------------------------------------------
# Stock de seguridad
# ---------------------------------------------------------------------------

def test_stock_de_seguridad_escala_con_la_raiz_del_lead_time():
    """
    Con la raiz y no con el lead time entero: los desvios diarios se compensan
    parcialmente. Multiplicar por el lead time completo sobre-dimensiona el
    colchon y encarece el inventario sin mejorar el servicio.
    """
    uno = stock_de_seguridad(10.0, 1)
    cuatro = stock_de_seguridad(10.0, 4)
    assert cuatro == pytest.approx(uno * 2.0)


def test_sin_variabilidad_no_hace_falta_colchon():
    assert stock_de_seguridad(0.0, 5) == 0.0


def test_mayor_nivel_de_servicio_exige_mas_colchon():
    assert stock_de_seguridad(10.0, 4, 0.99) > stock_de_seguridad(10.0, 4, 0.90)


def test_nivel_de_servicio_no_tabulado_falla():
    with pytest.raises(ValueError):
        stock_de_seguridad(10.0, 4, nivel_servicio=0.87)


# ---------------------------------------------------------------------------
# Sugerencia de pedido
# ---------------------------------------------------------------------------

def test_sugerencia_descuenta_lo_que_ya_viene_en_camino():
    """
    El error mas caro de un sistema de reposicion: volver a pedir algo que ya
    esta en camino porque el stock todavia se ve bajo. Con un lead time de tres
    dias, olvidar este descuento genera tres pedidos del mismo faltante.
    """
    punto = punto_de_reorden(100.0, 20.0)  # 120

    sin_pendiente = sugerencia_de_pedido(punto, stock_actual=30.0)
    con_pendiente = sugerencia_de_pedido(punto, stock_actual=30.0, pendiente_recepcion=50.0)

    assert sin_pendiente == 90.0
    assert con_pendiente == 40.0


def test_no_sugiere_pedidos_negativos():
    """Con stock de sobra la sugerencia es cero, no un numero negativo."""
    assert sugerencia_de_pedido(50.0, stock_actual=200.0) == 0.0


def test_no_sugiere_nada_si_lo_pendiente_ya_cubre():
    assert sugerencia_de_pedido(100.0, stock_actual=10.0, pendiente_recepcion=95.0) == 0.0


# ---------------------------------------------------------------------------
# Lead time derivado del calendario del proveedor
# ---------------------------------------------------------------------------

def test_lead_time_hasta_la_proxima_entrega_programada():
    """Proveedor que entrega martes (1) y viernes (4); hoy es miercoles (2)."""
    miercoles = date(2025, 1, 8)
    assert lead_time_por_dias_programados([1, 4], miercoles) == 2


def test_lead_time_cruza_la_semana():
    """Hoy sabado (5), el proveedor solo entrega lunes (0): faltan 2 dias."""
    sabado = date(2025, 1, 11)
    assert lead_time_por_dias_programados([0], sabado) == 2


def test_lead_time_sin_calendario_asume_un_dia():
    assert lead_time_por_dias_programados([], date(2025, 1, 8)) == 1


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def _serie_constante(dias: int, consumo: float) -> list[tuple[date, float]]:
    inicio = date(2025, 1, 6)
    return [(inicio + timedelta(days=d), consumo) for d in range(dias)]


def test_el_backtest_no_mide_el_periodo_de_calentamiento():
    """
    Sin calentamiento se compara una politica con historial contra una sin
    historial, y el resultado no significa nada.
    """
    serie = _serie_constante(50, 10.0)
    r = simular(serie, PoliticaPromedioPlano(2), lead_time_dias=2,
                dias_de_calentamiento=20)
    assert r.dias_simulados == 30


def test_sin_stock_ni_reposicion_todo_es_quiebre():
    """Control de cordura del simulador."""
    class NuncaPide:
        nombre = "no repone"

        def cuanto_pedir(self, historial, dia, stock_actual, pendiente_recepcion):
            return 0.0

    serie = _serie_constante(40, 10.0)
    r = simular(serie, NuncaPide(), lead_time_dias=1, stock_inicial=0.0,
                dias_de_calentamiento=10)
    assert r.dias_con_quiebre == r.dias_simulados == 30
    assert r.tasa_de_servicio == 0.0


def test_el_pedido_tarda_el_lead_time_en_llegar():
    """Lo pedido hoy no puede consumirse hoy."""
    class PideCienElPrimerDia:
        nombre = "pide una vez"

        def __init__(self):
            self.pedido = False

        def cuanto_pedir(self, historial, dia, stock_actual, pendiente_recepcion):
            if not self.pedido:
                self.pedido = True
                return 100.0
            return 0.0

    serie = _serie_constante(10, 10.0)
    r = simular(serie, PideCienElPrimerDia(), lead_time_dias=3,
                stock_inicial=0.0, dias_de_calentamiento=0)
    # Dias 0, 1 y 2 sin stock; llega el dia 3.
    assert r.dias_con_quiebre == 3


def test_la_politica_con_colchon_sirve_mas_que_la_plana():
    """
    Con consumo variable, el modelo debe sostener mejor servicio. Es la
    afirmacion central del modulo y por eso se verifica, no se asume.
    """
    import random

    rng = random.Random(7)
    inicio = date(2025, 1, 6)
    factores = [0.7, 0.8, 0.9, 1.1, 1.5, 1.8, 1.2]
    serie = [
        (inicio + timedelta(days=d),
         max(0.0, 20.0 * factores[(inicio + timedelta(days=d)).weekday()] * rng.gauss(1.0, 0.25)))
        for d in range(180)
    ]

    plana = simular(serie, PoliticaPromedioPlano(3), 3, dias_de_calentamiento=28)
    modelo = simular(serie, PoliticaEstacionalConSeguridad(3), 3, dias_de_calentamiento=28)

    assert modelo.tasa_de_servicio > plana.tasa_de_servicio
    assert modelo.stock_promedio > plana.stock_promedio, (
        "el mejor servicio se paga con inventario: si no, algo esta mal medido"
    )
