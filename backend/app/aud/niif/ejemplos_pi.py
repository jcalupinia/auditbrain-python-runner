"""Datos de ejemplo (ficticios) de la herramienta «Deterioro de cuentas por
cobrar · pérdidas incurridas (PYMES)» — procesador ``perdidas_incurridas_s11``.

Única fuente de verdad de esos datos: la usan
  - ``scripts/ejemplos_perdidas_incurridas.py`` (escribe los .xlsx/.docx del
    manifiesto de requerimientos), y
  - el endpoint de solo lectura del «Ejercicio modelo» (corre el procesador
    sobre estos datos para armar el recorrido).

Determinista: la aleatoriedad sale de ``random.Random(SEMILLA)`` y la semilla de
``zlib.crc32`` (NUNCA ``hash()``, que varía entre procesos). Sin I/O de archivos.

Calibrado para que la pérdida recalculada quede en el rango realista de un
encargo (≈5–15 % de la cartera), sin «provisión sin cruzar» y con el movimiento
de la provisión conciliado (saldo final de un año = inicial del siguiente y la
inicial 2025 = total del anexo de provisión inicial).
"""
from __future__ import annotations

import random
import zlib
from datetime import date, timedelta

from backend.app.aud.niif.procesadores import perdidas_incurridas_s11 as pi

SEMILLA = zlib.crc32(b"perdidas_incurridas_s11/ejemplo/v1") & 0xFFFFFFFF
CORTE = "2025-12-31"
ANIOS = (2023, 2024, 2025)
PLAZOS = (30, 45, 60, 90)
CORTES = {2023: date(2023, 12, 31), 2024: date(2024, 12, 31), 2025: date(2025, 12, 31)}

# RUC ecuatoriano de 13 dígitos (sociedades). El arquetipo decide cómo cobra:
# «bueno» paga dentro del plazo, «medio» se atrasa y paga parcial, «moroso»
# arrastra saldo entre ejercicios (esas facturas generan la pérdida incurrida).
CLIENTES = [
    ("Constructora Andina S.A.", "1790011223001", "bueno"),
    ("Agroexport del Litoral Cía. Ltda.", "0990022334001", "bueno"),
    ("Minera Austral S.A.", "1790033445001", "medio"),
    ("Vialidad Norte S.A.", "1090044556001", "moroso"),
    ("Hidrosur Cía. Ltda.", "0190055667001", "medio"),
    ("Obras Civiles Pacífico S.A.", "1390066778001", "moroso"),
]

# Saldo vivo al cierre de cada ejercicio como fracción del importe original,
# contado desde el año de emisión (índice 0 = cierre del año de emisión).
FRESCA = [1.00, 0.00, 0.00]
TEMPRANA = {
    "bueno": [0.00, 0.00, 0.00],
    "medio": [0.30, 0.06, 0.00],
    "moroso": [0.45, 0.22, 0.10],
}


def _r2(x: float) -> float:
    return round(x + 1e-9, 2)


def _saldos(arq: str, anio_emision: int, importe: float, q4: bool) -> dict:
    tabla = FRESCA if q4 else TEMPRANA[arq]
    saldos = {}
    for k, cierre in enumerate(a for a in ANIOS if a >= anio_emision):
        frac = tabla[k] if k < len(tabla) else 0.0
        s = _r2(importe * frac)
        if s > 0:
            saldos[cierre] = s
    return saldos


def generar_facturas() -> list[dict]:
    """42 facturas (14 por ejercicio) de los 6 clientes, con su saldo por cobrar
    a cada cierre. Números correlativos 001-001-000001001…"""
    rng = random.Random(SEMILLA)
    facturas = []
    correlativo = 1001
    for anio in ANIOS:
        for i in range(14):
            nombre, ruc, arq = CLIENTES[(i + anio) % len(CLIENTES)]
            mes = rng.randint(10, 12) if i < 6 else rng.randint(1, 9)
            dia = rng.randint(1, 28)
            emision = date(anio, mes, dia)
            vence = emision + timedelta(days=PLAZOS[rng.randrange(len(PLAZOS))])
            importe = _r2(rng.uniform(2000, 45000))
            numero = f"001-001-{correlativo:09d}"
            correlativo += 1
            facturas.append({"numero": numero, "cliente": nombre, "ruc": ruc, "arq": arq, "emision": emision,
                             "vence": vence, "importe": importe, "saldos": _saldos(arq, anio, importe, mes >= 10)})
    return facturas


def cartera_de(facturas, anio: int) -> list[dict]:
    filas = [{"N° de factura": f["numero"], "Cliente": f["cliente"], "RUC / identificación": f["ruc"],
              "Fecha de emisión": f["emision"], "Fecha de vencimiento": f["vence"],
              "Importe original": f["importe"], "Saldo por cobrar": f["saldos"][anio]}
             for f in facturas if f["saldos"].get(anio)]
    filas.sort(key=lambda x: x["N° de factura"])
    return filas


def provision_inicial(facturas) -> list[dict]:
    """Provisión y diferido por factura al inicio de 2025. SOLO facturas que
    también están en la cartera 2024 y 2025 (cruzan): no genera «provisión sin
    cruzar». La provisión ≈ 40 % del saldo con mora grave del cierre anterior."""
    en_2024 = {f["numero"] for f in facturas if 2024 in f["saldos"]}
    filas = []
    for f in facturas:
        if 2025 in f["saldos"] and f["numero"] in en_2024 and (CORTES[2024] - f["vence"]).days >= 361:
            prov = _r2(f["saldos"][2024] * 0.40)
            if prov > 0:
                filas.append({"N° de factura": f["numero"], "Cliente": f["cliente"],
                              "Provisión / deterioro": prov, "Impuesto diferido": _r2(prov * 0.25)})
    filas.sort(key=lambda x: x["N° de factura"])
    return filas


def movimiento(prov_filas) -> list[dict]:
    """Movimiento de 3 ejercicios: final de un año = inicial del siguiente y la
    inicial 2025 = total del RQ-004."""
    ini_2025 = _r2(sum(f["Provisión / deterioro"] for f in prov_filas))
    ini_2024 = _r2(ini_2025 * 0.70)
    ini_2023 = _r2(ini_2024 * 0.60)
    ini = {2023: ini_2023, 2024: ini_2024, 2025: ini_2025}
    fin = {2023: ini_2024, 2024: ini_2025}
    filas = []
    for anio in ANIOS:
        gasto = _r2(fin.get(anio, ini[anio]) - ini[anio])
        filas.append({"Año": str(anio), "Provisión inicial": ini[anio], "Gasto del año": gasto,
                      "Castigos": 0.0, "Recuperaciones": 0.0})
    return filas


def cobros_posteriores(facturas) -> list[dict]:
    rng = random.Random(SEMILLA ^ 0x00C0B305)
    candidatas = sorted((f for f in facturas if 2025 in f["saldos"]), key=lambda x: x["numero"])[:8]
    filas = []
    for f in candidatas:
        fecha = date(2026, 1, 1) + timedelta(days=rng.randint(1, 85))
        filas.append({"Fecha de cobro": fecha, "N° de factura": f["numero"], "Cliente": f["cliente"],
                      "Valor cobrado": _r2(f["saldos"][2025] * rng.uniform(0.25, 0.9)),
                      "Referencia bancaria": f"TRF-2026-{4200 + len(filas)}"})
    return filas


def ventas_por_factura(facturas) -> list[dict]:
    return [{"N° de factura": f["numero"], "Cliente": f["cliente"], "Fecha de emisión": f["emision"],
             "Importe facturado": f["importe"]} for f in sorted(facturas, key=lambda x: x["numero"])]


def _internas(tipo: str, filas: list[dict]) -> list[dict]:
    """Traduce las filas rotuladas (rótulos de CAMPOS) a las claves internas que
    espera ``perdidas_incurridas_s11.ejecutar`` — el mismo mapeo que hace el
    ciclo por los alias de cada campo."""
    rot = {c["label"]: c["key"] for c in pi.CAMPOS[tipo]}
    return [{rot[k]: v for k, v in fila.items() if k in rot} for fila in filas]


def datasets() -> dict:
    """Los cinco anexos de cálculo en la forma interna que consume ``ejecutar``."""
    f = generar_facturas()
    return {
        "a1": _internas("cartera", cartera_de(f, 2023)),
        "a2": _internas("cartera", cartera_de(f, 2024)),
        "a3": _internas("cartera", cartera_de(f, 2025)),
        "provision": _internas("provision", provision_inicial(f)),
        "movimiento": _internas("movimiento", movimiento(provision_inicial(f))),
    }


PARAMETROS = {"tasaDesc": "0"}


def ejercicio_modelo() -> dict:
    """Forma ``{corte, datasets, parametros}`` que consumen ``ejecutar`` y el
    recorrido del ejercicio modelo (misma firma que ``EJEMPLO``/``ESCENARIOS``)."""
    return {"corte": CORTE, "datasets": datasets(), "parametros": dict(PARAMETROS)}
