"""Fase B/C/D condensada — Auditoría dirigida del A1 (588 celdas rojas).

Compara las fórmulas en celdas ROJAS del ICT_14 (golden master) contra
las reglas codificadas en `backend/app/ict/fillers/a1_mapeo.py`.

Estrategia (finance:reconciliation):
  - Lado A (golden): fórmulas que el cliente escribió/aprobó
  - Lado B (regla): qué fórmula generaría el código actual para ese cas
  - Reconciling items: diferencias

Mapeo Excel → casillero:
  Cada fila del A1 tiene un casillero en col A. Las celdas rojas en
  cols C, D, E, F, G corresponden a:
    C = valor declarado (F-101)
    D = código contable
    E = nombre cuenta
    F = saldo final (balance)
    G = diferencia (F - C)

Output:
  audit_artifacts/a1_redcells_analysis.csv
  audit_artifacts/a1_redcells_dashboard.md
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

OUT_DIR = Path("audit_artifacts")


def normalize_formula(f: str) -> str:
    """Patrón normalizado (shape) — referencias → REF, números → NUM."""
    s = re.sub(r"\$?[A-Z]+\$?\d+", "REF", f)
    s = re.sub(r"\b\d+\.?\d*\b", "NUM", s)
    return s


def coord_to_col_row(coord: str) -> tuple[str, int]:
    m = re.match(r"^([A-Z]+)(\d+)$", coord)
    return (m.group(1), int(m.group(2))) if m else ("", 0)


def main():
    golden_path = OUT_DIR / "golden_ict14.json"
    if not golden_path.exists():
        sys.exit("Run scripts/extract_golden_formulas.py first")

    data = json.loads(golden_path.read_text(encoding="utf-8"))
    a1_data = data.get("MAPEO DE LA DECLARACIÓN A1")
    if not a1_data:
        sys.exit("FATAL: no se encontró hoja 'MAPEO DE LA DECLARACIÓN A1'")

    # Cargar lookup cas ← fila del A1
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from backend.app.ict.cell_maps.a1 import A1_CASILLEROS_ORDERED, A1_FIRST_DATA_ROW

    # Sin la regla de inserciones dinámicas del filler, no podemos saber
    # con precisión qué fila tiene qué cas. Pero podemos detectar el cas
    # mirando la propia hoja: col A tiene el cas en string.
    formulas = a1_data["formulas"]
    values = a1_data["values"]
    red_cells = a1_data["red_cells"]

    # Construir lookup row → casillero (desde valores en col A)
    row_to_cas: dict[int, str] = {}
    for coord, v in values.items():
        col, row = coord_to_col_row(coord)
        if col == "A":
            cas = str(v).strip()
            if cas.isdigit():
                row_to_cas[row] = cas

    print(f"[INFO] {len(row_to_cas)} casilleros encontrados en col A del A1")
    print(f"[INFO] {len(formulas)} fórmulas totales en hoja A1")
    print(f"[INFO] {len(red_cells)} celdas rojas")

    # Analizar celdas rojas
    analysis = []
    by_col = Counter()
    by_shape = Counter()
    by_cas_count = Counter()
    formulas_in_red = 0
    no_formula_in_red = 0
    sample_per_col: dict[str, list[dict]] = defaultdict(list)

    for rc in red_cells:
        coord = rc["coord"]
        col, row = coord_to_col_row(coord)
        cas = row_to_cas.get(row, "—")
        is_f = rc.get("is_formula", False)
        formula = rc["value"] if is_f else None
        literal = rc["value"] if not is_f else None

        by_col[col] += 1
        if is_f:
            formulas_in_red += 1
            shape = normalize_formula(formula)
            by_shape[shape] += 1
        else:
            no_formula_in_red += 1

        if cas != "—":
            by_cas_count[cas] += 1

        item = {
            "sheet": "MAPEO DE LA DECLARACIÓN A1",
            "coord": coord,
            "col": col,
            "row": row,
            "casillero": cas,
            "is_formula": is_f,
            "formula": formula or "",
            "literal_value": str(literal) if literal is not None else "",
            "shape": normalize_formula(formula) if formula else "",
            "fill_rgb": rc.get("fill", ""),
            "font_rgb": rc.get("font", ""),
        }
        analysis.append(item)
        if len(sample_per_col[col]) < 5:
            sample_per_col[col].append(item)

    # Escribir CSV
    csv_path = OUT_DIR / "a1_redcells_analysis.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(analysis[0].keys()))
        writer.writeheader()
        for r in analysis:
            writer.writerow(r)

    # Dashboard MD
    lines = [
        "# Análisis de Celdas Rojas — Anexo A1 (MAPEO DECLARACIÓN)\n",
        f"**Total celdas rojas**: {len(red_cells)}",
        f"**Con fórmula**: {formulas_in_red}",
        f"**Con valor literal (no fórmula)**: {no_formula_in_red}",
        "",
        "## Distribución por columna del A1\n",
        "| Columna | Celdas Rojas | % | Significado |",
        "|---------|-------------:|---:|-------------|",
    ]
    col_meaning = {
        "A": "Casillero", "B": "Nombre Casillero",
        "C": "Valor declarado F-101", "D": "Código contable",
        "E": "Nombre Cuenta", "F": "Saldo final balance",
        "G": "Diferencia (F-C)", "H": "Observaciones",
    }
    total = sum(by_col.values())
    for col in sorted(by_col):
        pct = 100 * by_col[col] / total
        lines.append(
            f"| **{col}** | {by_col[col]} | {pct:.1f}% | {col_meaning.get(col, '?')} |"
        )

    lines += [
        "",
        "## Top 15 patrones de fórmula (en celdas rojas)\n",
        "| # | Shape (normalizada) | Conteo |",
        "|---|---------------------|-------:|",
    ]
    for i, (shape, n) in enumerate(by_shape.most_common(15), 1):
        # Truncar para legibilidad
        s = shape[:80] + ("..." if len(shape) > 80 else "")
        lines.append(f"| {i} | `{s}` | {n} |")

    lines += [
        "",
        "## Top 20 casilleros con más celdas rojas\n",
        "| # | Cas | Conteo |",
        "|---|-----|-------:|",
    ]
    for i, (cas, n) in enumerate(by_cas_count.most_common(20), 1):
        lines.append(f"| {i} | {cas} | {n} |")

    lines += [
        "",
        "## Muestras por columna (5 ejemplos por col)\n",
    ]
    for col in sorted(sample_per_col):
        lines.append(f"### Col {col} — {col_meaning.get(col, '?')}\n")
        lines.append("| Coord | Cas | Fórmula / Valor |")
        lines.append("|-------|-----|------------------|")
        for s in sample_per_col[col]:
            v = s["formula"] if s["is_formula"] else s["literal_value"]
            v_disp = (v[:80] + "...") if len(v) > 80 else v
            lines.append(f"| {s['coord']} | {s['casillero']} | `{v_disp}` |")
        lines.append("")

    md_path = OUT_DIR / "a1_redcells_dashboard.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n[OK] CSV → {csv_path}")
    print(f"[OK] MD  → {md_path}")
    print(f"\n=== TOP DISTRIBUCIÓN ===")
    print(f"Columnas: {dict(by_col.most_common())}")
    print(f"Patrones únicos: {len(by_shape)}")
    print(f"Cas con rojas: {len(by_cas_count)} casilleros distintos")
    print(f"Top 5 cas: {by_cas_count.most_common(5)}")


if __name__ == "__main__":
    main()
