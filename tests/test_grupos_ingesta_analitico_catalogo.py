"""Regresion de inventario: ambos grupos existentes deben permanecer accesibles.

Prueba estatica sin navegador; no certifica endpoints ni despliegue.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGO = ROOT / "frontend/src/aud/catalog.js"
VISTA = ROOT / "frontend/src/aud/ToolCatalog.jsx"


def test_grupos_registrados_una_sola_vez():
    texto = CATALOGO.read_text(encoding="utf-8")
    assert texto.count('id: "INGESTA",') == 1
    assert texto.count('id: "MOTOR_ANALITICO",') == 1


def test_cuatro_herramientas_ingesta_ruteadas():
    catalogo = CATALOGO.read_text(encoding="utf-8")
    vista = VISTA.read_text(encoding="utf-8")
    for clave in ("MOTOR", "NARRATIVO", "RESOLVER", "MAPEO"):
        identificador = f"AUD.INGESTA.{clave}"
        assert catalogo.count(f'id: "{identificador}"') == 1
        assert f'"{identificador}":' in vista
    assert "<IngestaUnificadaTool" in vista


def test_analitico_ruteado():
    catalogo = CATALOGO.read_text(encoding="utf-8")
    vista = VISTA.read_text(encoding="utf-8")
    assert catalogo.count('id: "AUD.MOTOR_ANALITICO"') == 1
    assert 'activeTool === "AUD.MOTOR_ANALITICO"' in vista
    assert "<MotorAnaliticoTool projectId={projectId} />" in vista
