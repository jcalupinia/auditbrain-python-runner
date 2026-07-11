# backend/app/client_portal/flujo/patrimonio_matriz.py
"""Matriz oficial del Estado de Cambios en el Patrimonio (códigos 99xx).

16 filas de movimiento × 18 columnas de componente + TOTAL, reproduciendo la
hoja "Estado de Evolucion del Patrimonio" del modelo. Los movimientos se derivan
del ESF (saldos por componente año anterior/actual) y del ORI:

  99      SALDO AL FINAL DEL PERÍODO      = 9901 + 9902           (= saldo actual)
  9901    SALDO REEXPRESADO ANTERIOR      = 990101 + 990102 + 990103 (= saldo anterior)
  9902    CAMBIOS DEL AÑO                 = Σ(990201..990210)      (= actual − anterior)
  990101  SALDO DEL PERÍODO ANTERIOR      = saldo anterior por componente
  990201  Aumento (disminución) capital   = cambio de 301/302/303
  990204  Dividendos                      = cambio de 30601 − ORI
  990205  Transferencia de resultados     = cambio de 30701 − resultado del año
  990209  Otros cambios (ORI)             = ORI (en 30601) + cualquier otro residuo
  990210  Resultado Integral del año      = ganancia/pérdida neta del ejercicio (30701/30702)

Validado celda por celda contra SIGMAN.
"""
from __future__ import annotations

from . import catalogos, motor, motor_f101

# Componentes (columnas) en el orden oficial de la hoja.
COMPONENTES = [
    "301", "302", "303", "30401", "30402",
    "30501", "30502", "30503", "30504",
    "30601", "30602", "30603", "30604", "30605", "30606", "30607",
    "30701", "30702",
]
GRUPOS = [
    {"nombre": "", "cols": ["301", "302", "303"]},
    {"nombre": "RESERVAS", "cols": ["30401", "30402"]},
    {"nombre": "OTROS RESULTADOS INTEGRALES", "cols": ["30501", "30502", "30503", "30504"]},
    {"nombre": "RESULTADOS ACUMULADOS",
     "cols": ["30601", "30602", "30603", "30604", "30605", "30606", "30607", "30701", "30702"]},
]
# Filas de movimiento (código 99xx, nombre).
FILAS = [
    ("99", "SALDO AL FINAL DEL PERÍODO"),
    ("9901", "SALDO REEXPRESADO DEL PERIODO INMEDIATO ANTERIOR"),
    ("9902", "CAMBIOS DEL AÑO EN EL PATRIMONIO"),
    ("990101", "SALDO DEL PERÍODO INMEDIATO ANTERIOR"),
    ("990102", "CAMBIOS EN POLÍTICAS CONTABLES"),
    ("990103", "CORRECCIÓN DE ERRORES"),
    ("990201", "Aumento (disminución) de capital social"),
    ("990202", "Aportes para futuras capitalizaciones"),
    ("990203", "Prima por emisión primaria de acciones"),
    ("990204", "Dividendos"),
    ("990205", "Transferencia de resultados a otras cuentas patrimoniales"),
    ("990206", "Realización de la Reserva por Valuación de Activos Financieros"),
    ("990207", "Realización de la Reserva por Valuación de Propiedades, planta y equipo"),
    ("990208", "Realización de la Reserva por Valuación de Activos intangibles"),
    ("990209", "Otros cambios (detallar)"),
    ("990210", "Resultado Integral Total del Año (Ganancia o pérdida del ejercicio)"),
]

_CAPITAL = ("301", "302", "303")
_R = 2


def _r(v) -> float:
    return round(float(v or 0.0), 2)


def matriz_patrimonio(bal_ant: list[dict], bal_act: list[dict]) -> dict:
    """Devuelve la matriz 99xx: columnas, grupos, filas con celdas por componente."""
    est_esf = catalogos.cargar_estructura("esf")
    labels = {n.codigo: n.etiqueta for n in est_esf}
    sa, _ = motor.homologar_balanza(bal_ant)
    sc, _ = motor.homologar_balanza(bal_act)
    ant = motor.totales_por_codigo(est_esf, sa)
    act = motor.totales_por_codigo(est_esf, sc)
    ori = _r(motor_f101.ori_del_periodo(bal_ant, bal_act))

    prior = {c: _r(ant.get(c, 0.0)) for c in COMPONENTES}
    final = {c: _r(act.get(c, 0.0)) for c in COMPONENTES}
    cambio = {c: _r(final[c] - prior[c]) for c in COMPONENTES}

    # celdas[fila_codigo][componente] = valor
    celdas: dict[str, dict[str, float]] = {f[0]: {c: 0.0 for c in COMPONENTES} for f in FILAS}

    for c in COMPONENTES:
        celdas["99"][c] = final[c]
        celdas["9901"][c] = prior[c]
        celdas["990101"][c] = prior[c]
        celdas["9902"][c] = cambio[c]

    # Distribución de los cambios del año a las filas de movimiento.
    manejadas: set[str] = set()
    # 30701/30702: resultado del ejercicio + transferencia (residuo).
    for res in ("30701", "30702"):
        if cambio[res] or final[res]:
            celdas["990210"][res] = final[res]
            celdas["990205"][res] = _r(cambio[res] - final[res])
            manejadas.add(res)
    # 30601: ORI + dividendos (residuo).
    celdas["990209"]["30601"] = ori
    celdas["990204"]["30601"] = _r(cambio["30601"] - ori)
    manejadas.add("30601")
    # Capital (301/302/303): aumento/disminución.
    for cap in _CAPITAL:
        if cambio[cap]:
            celdas["990201"][cap] = cambio[cap]
        manejadas.add(cap)
    # Cualquier otro componente con cambio → Otros cambios (para que la columna cuadre).
    for c in COMPONENTES:
        if c not in manejadas and cambio[c]:
            celdas["990209"][c] = _r(celdas["990209"][c] + cambio[c])

    # Armado de filas + columna TOTAL (suma por fila).
    filas_out = []
    for cod, nombre in FILAS:
        fila = {c: _r(celdas[cod][c]) for c in COMPONENTES}
        fila["total"] = _r(sum(fila.values()))
        filas_out.append({"codigo": cod, "nombre": nombre, "celdas": fila})

    columnas = [{"codigo": c, "nombre": labels.get(c, c)} for c in COMPONENTES]
    return {"columnas": columnas, "grupos": GRUPOS, "filas": filas_out}
