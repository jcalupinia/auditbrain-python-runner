"""Paneles analíticos (riesgo/evidencia) en el papel de trabajo del ciclo.

El enriquecimiento que ``ciclo.insights`` deja en el registro (``riskScoring`` /
``evidenceMatrix``) se renderiza como cédulas "15_Riesgo" / "16_Evidencia" en el
libro (``procesadores/libro.py``), solo cuando hay datos."""
import io

from openpyxl import load_workbook

from backend.app.aud.niif.procesadores import libro

_DEF = {"name": "Prueba X", "area": "CXC", "program": []}


def _wb(reg):
    return load_workbook(io.BytesIO(libro.xlsx(_DEF, reg, [], 1, "APROBADO")))


def test_panel_riesgo_y_evidencia_aparecen_con_datos():
    reg = {
        "engagement": {"client": "C", "cutoff": "2025-12-31"},
        "run": {"engine": "x", "hojas": []},
        "riskScoring": {"campos": ["saldo"], "resumen": {"total": 6, "alto": 1, "medio": 0, "bajo": 5},
                        "anomalias": [{"indice": 5, "score": 91.0, "nivel": "alto",
                                       "factores": [{"variable": "saldo", "z": 6.2, "contribucion": 91.0}]}]},
        "evidenceMatrix": {"resumen": {"requerimientos": 2, "con_evidencia": 1, "sin_evidencia": 1, "corroborados": 0},
                           "entradas": [{"requerimiento": "RQ-001", "documento": "Cartera", "fuentes": 2,
                                         "corroborado": True, "estado": "pendiente"},
                                        {"requerimiento": "RQ-002", "documento": "Mayor", "fuentes": 0,
                                         "corroborado": False, "estado": "pendiente"}]},
    }
    wb = _wb(reg)
    assert "15_Riesgo" in wb.sheetnames and "16_Evidencia" in wb.sheetnames
    # el panel de riesgo lista la fila atípica con su score y factores
    r = wb["15_Riesgo"]
    fila = [r.cell(row=5, column=c).value for c in range(1, 5)]
    assert fila[0] == 5 and fila[2] == "alto" and "saldo" in str(fila[3])
    # el panel de evidencia muestra la corroboración
    e = wb["16_Evidencia"]
    assert [e.cell(row=5, column=c).value for c in range(1, 6)] == ["RQ-001", "Cartera", 2, "Sí", "pendiente"]


def test_solo_evidencia_cuando_no_hay_scoring():
    reg = {"engagement": {}, "run": {"engine": "x", "hojas": []},
           "riskScoring": {},  # procesador sin campos numéricos declarativos
           "evidenceMatrix": {"entradas": [{"requerimiento": "RQ-1", "documento": "D", "fuentes": 1,
                                            "corroborado": False, "estado": "pendiente"}]}}
    wb = _wb(reg)
    assert "16_Evidencia" in wb.sheetnames and "15_Riesgo" not in wb.sheetnames


def test_sin_enriquecimiento_no_agrega_paneles():
    wb = _wb({"engagement": {}, "run": {"engine": "x", "hojas": []}})
    assert "15_Riesgo" not in wb.sheetnames and "16_Evidencia" not in wb.sheetnames
    # el papel base sigue cerrando en Control de revisión
    assert "14_Control_Revision" in wb.sheetnames
