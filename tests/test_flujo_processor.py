"""Tests del processor de la Herramienta Flujo de Efectivo.

Cubre el pipeline interno (leer inputs por slot -> parsear -> generar Excel)
de forma pragmática, sin montar toda la DB. El test de humo verifica que:
  - el processor existe y es invocable,
  - la lógica de leer los DOS slots (balanza_anterior/balanza_actual) desde
    file_storage, parsear y generar produce un .xlsx válido de 9 hojas,
  - el summary refleja las cuadraturas.
"""
import io

from openpyxl import Workbook, load_workbook

from backend.app.client_portal.flujo import processor


def _balanza_xlsx_bytes(rows):
    wb = Workbook()
    ws = wb.active
    ws.append(["Cuenta", "CODIGO SUPER CIAS", "Codigos SRI", "Saldos 31 DIC"])
    for r in rows:
        ws.append(list(r))
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def test_processor_existe_y_es_invocable():
    assert callable(processor.flujo_efectivo_processor)


def test_pipeline_interno_genera_excel_de_9_hojas(tmp_path):
    # Slots separados en subcarpetas, como los organiza file_storage.
    from backend.app.aud.obligaciones_fiscales import file_storage

    job_dir = tmp_path / "inputs_job"
    (job_dir / file_storage.INPUTS_DIR).mkdir(parents=True)

    ant = _balanza_xlsx_bytes([
        ("Caja", "1010101", "311", 400.0),
        ("Proveedores", "2010301", "413", -400.0),
    ])
    act = _balanza_xlsx_bytes([
        ("Caja", "1010101", "311", 500.0),
        ("Proveedores", "2010301", "413", -500.0),
    ])
    file_storage.save_input(job_dir, "balanza_anterior", "ant.xlsx", ant)
    file_storage.save_input(job_dir, "balanza_actual", "act.xlsx", act)

    # El processor expone un helper interno testeable que hace parse+generar
    # sobre un job_dir concreto y devuelve (out_path, summary).
    out_path, summary = processor._procesar_job_dir(job_dir)

    assert out_path.exists()
    wb = load_workbook(out_path)
    assert len(wb.sheetnames) == 9
    assert summary["filas_anterior"] == 2
    assert summary["filas_actual"] == 2
    assert "cuadre_esf" in summary
    assert "cuadre_af" in summary
