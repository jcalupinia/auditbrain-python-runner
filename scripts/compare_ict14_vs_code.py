"""Comparación dirigida: rojos del ICT_14 vs lo que el código debería generar.

Sin necesidad de regenerar ICT_15. Analiza por cas:
  - ¿Cuántas cuentas tiene mapeadas el balance PROPHAR para ese cas?
  - ¿Cuántas filas DETALLE pintó el cliente en rojo (col D/E/F)?
  - ¿Coinciden? → Si no coinciden, hay omisión del código.

Output:
  audit_artifacts/a1_no_trasladado.csv  (cas con cuentas no extraídas)
  audit_artifacts/a1_diferencias_dashboard.md
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUT_DIR = Path("audit_artifacts")
BALANCE_PATH = Path(r"C:\Users\jcalu\Downloads\BALANCE MAPEADO.xlsx")


def coord_to_col_row(coord: str) -> tuple[str, int]:
    m = re.match(r"^([A-Z]+)(\d+)$", coord)
    return (m.group(1), int(m.group(2))) if m else ("", 0)


def main():
    # 1. Cargar golden
    golden_path = OUT_DIR / "golden_ict14.json"
    if not golden_path.exists():
        sys.exit("Run extract_golden_formulas.py first")
    data = json.loads(golden_path.read_text(encoding="utf-8"))
    a1 = data["MAPEO DE LA DECLARACIÓN A1"]
    formulas = a1["formulas"]
    values = a1["values"]
    red_cells = a1["red_cells"]

    # 2. Construir map row → cas (col A)
    row_to_cas: dict[int, str] = {}
    for coord, v in values.items():
        col, row = coord_to_col_row(coord)
        if col == "A":
            s = str(v).strip()
            if s.isdigit():
                row_to_cas[row] = s

    # 3. Asignar cas a TODAS las filas (sub-cuentas heredan el cas de la fila TOTAL)
    rows_with_cas: dict[int, str] = {}
    current = None
    for row in range(1, max(row_to_cas.keys(), default=1) + 1):
        if row in row_to_cas:
            current = row_to_cas[row]
        if current:
            rows_with_cas[row] = current

    # 4. Por cas: ¿cuántas filas DETALLE tiene el cliente?
    # Una fila detalle = tiene contenido en col D o E (código contable o nombre).
    cas_detalle_filas: dict[str, int] = defaultdict(int)
    cas_detalle_red: dict[str, int] = defaultdict(int)
    cas_total_rows: dict[str, int] = {}

    for coord, v in values.items():
        col, row = coord_to_col_row(coord)
        if col == "D":  # código contable presente
            cas = rows_with_cas.get(row)
            if cas:
                cas_detalle_filas[cas] += 1
                # ¿La celda es roja?
                if any(rc["coord"] == coord for rc in red_cells):
                    cas_detalle_red[cas] += 1
        if col == "A":
            cas = rows_with_cas.get(row)
            if cas:
                cas_total_rows[cas] = row

    # 5. Cargar balance PROPHAR
    print("Leyendo balance PROPHAR...")
    from backend.app.ict.parsers.balance_mapeado_excel import parse_balance_mapeado
    bal_res = parse_balance_mapeado(BALANCE_PATH.read_bytes())
    cuentas = bal_res.get("cuentas", [])
    print(f"  Balance: {len(cuentas)} cuentas parseadas")

    # Cuentas por cas en el balance
    bal_por_cas: dict[str, list] = defaultdict(list)
    for c in cuentas:
        cas = str(c.get("casillero_sri", "")).strip()
        if cas.isdigit():
            bal_por_cas[cas].append(c)

    # 6. Reporte: ¿Cuáles cas tienen DESALINEACIÓN entre balance y A1 del cliente?
    out_rows = []
    for cas in sorted(cas_detalle_filas, key=int):
        balance_n = len(bal_por_cas.get(cas, []))
        a1_filas = cas_detalle_filas[cas]
        a1_rojas = cas_detalle_red[cas]
        diff = a1_filas - balance_n
        out_rows.append({
            "cas": cas,
            "row_a1": cas_total_rows.get(cas, ""),
            "balance_cuentas": balance_n,
            "a1_detalle_filas": a1_filas,
            "a1_detalle_rojas": a1_rojas,
            "diferencia": diff,
            "balance_suma": round(sum(float(c.get("saldo", 0) or 0)
                                      for c in bal_por_cas.get(cas, [])), 2),
        })

    # 7. También cas en el BALANCE que NO tienen detalle en A1 = omisión total
    cas_balance_no_en_a1 = []
    for cas, items in bal_por_cas.items():
        if cas not in cas_detalle_filas and cas not in cas_total_rows:
            cas_balance_no_en_a1.append({
                "cas": cas,
                "cuentas_balance": len(items),
                "suma_balance": round(sum(float(c.get("saldo", 0) or 0)
                                          for c in items), 2),
            })

    # Escribir CSV
    csv_path = OUT_DIR / "a1_no_trasladado.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        for r in out_rows:
            writer.writerow(r)

    # Dashboard
    lines = [
        "# Diferencias A1 cliente (ICT_14) vs Balance PROPHAR vs Código\n",
        "## Cas con discrepancia entre balance y filas A1 del cliente\n",
        "| Cas | Cuentas balance | Filas A1 detalle | Filas rojas | Diferencia | Suma balance |",
        "|-----|----------------:|-----------------:|------------:|-----------:|-------------:|",
    ]
    discrepant = [r for r in out_rows if r["diferencia"] != 0 or r["a1_detalle_rojas"] > 0]
    discrepant.sort(key=lambda x: -abs(x["diferencia"]))
    for r in discrepant[:50]:
        lines.append(
            f"| {r['cas']} | {r['balance_cuentas']} | {r['a1_detalle_filas']} | "
            f"{r['a1_detalle_rojas']} | {r['diferencia']:+d} | "
            f"${r['balance_suma']:,.2f} |"
        )

    if cas_balance_no_en_a1:
        lines += [
            "",
            "## Cas en balance que NO aparecen en A1 cliente (omisión total)\n",
            "| Cas | # Cuentas | Suma balance |",
            "|-----|----------:|-------------:|",
        ]
        cas_balance_no_en_a1.sort(key=lambda x: -x["suma_balance"])
        for r in cas_balance_no_en_a1[:30]:
            lines.append(f"| {r['cas']} | {r['cuentas_balance']} | ${r['suma_balance']:,.2f} |")

    # Resumen ejecutivo
    total_red_cas = len([r for r in out_rows if r["a1_detalle_rojas"] > 0])
    total_red_filas = sum(r["a1_detalle_rojas"] for r in out_rows)
    cas_con_balance_completo = len([r for r in out_rows if r["diferencia"] == 0])
    cas_con_mas_filas_a1 = len([r for r in out_rows if r["diferencia"] > 0])
    cas_con_mas_filas_bal = len([r for r in out_rows if r["diferencia"] < 0])

    lines = [
        "# Diferencias A1 (cliente) vs Balance PROPHAR\n",
        "## Resumen ejecutivo\n",
        f"- **Cas con detalle en A1**: {len(out_rows)}",
        f"- **Cas con celdas rojas en col D (cuenta agregada por cliente)**: {total_red_cas}",
        f"- **Filas rojas en cols D (total)**: {total_red_filas}",
        f"- **Cas A1 detalle = balance**: {cas_con_balance_completo}",
        f"- **Cas A1 con MÁS filas que balance**: {cas_con_mas_filas_a1} (cliente agregó cuentas que balance no tiene)",
        f"- **Cas A1 con MENOS filas que balance**: {cas_con_mas_filas_bal} (código NO extrajo todas las cuentas)",
        f"- **Cas en balance NO en A1**: {len(cas_balance_no_en_a1)}",
        "",
    ] + lines[1:]

    md_path = OUT_DIR / "a1_diferencias_dashboard.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nReporte: {md_path}")
    print(f"\n=== RESUMEN ===")
    print(f"Cas con discrepancia: {len(discrepant)}")
    print(f"Cas en balance NO en A1: {len(cas_balance_no_en_a1)}")
    print(f"Total filas rojas col D: {total_red_filas}")


if __name__ == "__main__":
    main()
