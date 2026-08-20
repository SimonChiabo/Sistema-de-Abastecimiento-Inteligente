"""
forecast_report.py
Corre el backtest de las politicas de reposicion y muestra la comparacion.

    python forecast_report.py

DATOS SINTETICOS. La serie de consumo se genera con los parametros que el
propio reporte imprime. No es historico real: el objetivo es demostrar el
metodo de evaluacion, no afirmar un resultado obtenido en produccion.

Se evalua sobre DOS series a proposito:

  - Con estacionalidad semanal, que es el caso que el modelo esta pensado para
    aprovechar.
  - Plana, sin estructura por dia de semana.

Mostrar solo la primera seria construir la respuesta dentro del dato: si se
genera consumo con estacionalidad y despues se demuestra que la politica que
modela estacionalidad gana, no se probo nada. La segunda serie es la que dice
cuanto cuesta el modelo cuando la estructura que asume no esta.
"""

import argparse
import random
from datetime import date, timedelta

from core.backtest import ResultadoBacktest, simular
from core.politicas import (
    PoliticaEstacionalConSeguridad,
    PoliticaPromedioConSeguridad,
    PoliticaPromedioPlano,
)

CONSUMO_BASE = 20.0
RUIDO_PCT = 0.25
LEAD_TIME_DIAS = 3
DIAS = 180
CALENTAMIENTO = 28
SEMILLA = 42

# Lunes a domingo. Refleja un local de hosteleria: fin de semana fuerte.
FACTORES_REALES = [0.7, 0.8, 0.9, 1.1, 1.5, 1.8, 1.2]


def generar_serie(dias: int, estacional: bool, semilla: int) -> list[tuple[date, float]]:
    """Serie sintetica de consumo diario. Con o sin estructura por dia."""
    rng = random.Random(semilla)
    inicio = date(2025, 1, 6)  # un lunes
    serie = []
    for offset in range(dias):
        dia = inicio + timedelta(days=offset)
        factor = FACTORES_REALES[dia.weekday()] if estacional else 1.0
        ruido = rng.gauss(1.0, RUIDO_PCT)
        serie.append((dia, max(0.0, CONSUMO_BASE * factor * ruido)))
    return serie


def _fila(r: ResultadoBacktest) -> str:
    return (
        f"  {r.nombre_politica:<34} "
        f"{r.dias_con_quiebre:>7} "
        f"{r.unidades_no_servidas:>12.1f} "
        f"{r.tasa_de_servicio:>10.1%} "
        f"{r.stock_promedio:>13.1f} "
        f"{r.pedidos_emitidos:>9}"
    )


def _comparar(titulo: str, serie: list[tuple[date, float]], lead_time: int) -> None:
    print(f"\n{titulo}")
    print("  " + "-" * 92)
    print(
        f"  {'Politica':<34} {'Quiebres':>7} {'Ud. faltantes':>12} "
        f"{'Servicio':>10} {'Stock prom.':>13} {'Pedidos':>9}"
    )
    print("  " + "-" * 92)

    resultados = [
        simular(serie, PoliticaPromedioPlano(lead_time), lead_time,
                dias_de_calentamiento=CALENTAMIENTO),
        simular(serie, PoliticaPromedioConSeguridad(lead_time), lead_time,
                dias_de_calentamiento=CALENTAMIENTO),
        simular(serie, PoliticaEstacionalConSeguridad(lead_time), lead_time,
                dias_de_calentamiento=CALENTAMIENTO),
    ]
    for r in resultados:
        print(_fila(r))

    sin_colchon, con_colchon, modelo = resultados
    print("  " + "-" * 92)
    print(
        f"  Aporte del stock de seguridad: "
        f"{sin_colchon.dias_con_quiebre - con_colchon.dias_con_quiebre:+d} dias de quiebre evitados, "
        f"{con_colchon.stock_promedio - sin_colchon.stock_promedio:+.1f} ud. de stock"
    )
    print(
        f"  Aporte de la estacionalidad:   "
        f"{con_colchon.dias_con_quiebre - modelo.dias_con_quiebre:+d} dias de quiebre evitados, "
        f"{modelo.stock_promedio - con_colchon.stock_promedio:+.1f} ud. de stock"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[2])
    parser.add_argument("--dias", type=int, default=DIAS)
    parser.add_argument("--lead-time", type=int, default=LEAD_TIME_DIAS)
    parser.add_argument("--semilla", type=int, default=SEMILLA)
    args = parser.parse_args()

    print("=" * 96)
    print("  BACKTEST DE POLITICAS DE REPOSICION --- DATOS SINTETICOS")
    print("=" * 96)
    print(f"  Consumo base            {CONSUMO_BASE:.0f} unidades/dia")
    print(f"  Ruido                   gaussiano, desvio {RUIDO_PCT:.0%}")
    print(f"  Factores por dia (L-D)  {FACTORES_REALES}")
    print(f"  Lead time               {args.lead_time} dias")
    print(f"  Horizonte               {args.dias} dias "
          f"({CALENTAMIENTO} de calentamiento, {args.dias - CALENTAMIENTO} medidos)")
    print(f"  Semilla                 {args.semilla}")

    _comparar(
        "SERIE 1 --- Con estacionalidad semanal (el caso que el modelo asume)",
        generar_serie(args.dias, estacional=True, semilla=args.semilla),
        args.lead_time,
    )
    _comparar(
        "SERIE 2 --- Plana, sin estructura por dia de semana (control)",
        generar_serie(args.dias, estacional=False, semilla=args.semilla),
        args.lead_time,
    )

    print()
    print("  Como leerlo: bajar quiebres es trivial si se acepta cualquier nivel de")
    print("  stock, por eso las dos columnas se leen juntas. Y la comparacion util")
    print("  no es contra el promedio sin colchon --- esa es una linea de base debil")
    print("  que hace quedar bien a cualquier cosa --- sino contra el promedio CON")
    print("  colchon, que es lo que aisla el aporte real de modelar el dia de semana.")
    print()


if __name__ == "__main__":
    main()
