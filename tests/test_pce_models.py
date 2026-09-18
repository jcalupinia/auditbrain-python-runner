"""Persistencia de las corridas del papel de trabajo de pérdidas esperadas."""
from datetime import date

from backend.app.aud.pce_cxc.models import CorridaPCE, guardar_corrida
from backend.app.db.session import SessionLocal, init_db


def test_la_corrida_guarda_parametros_y_resultado():
    init_db()
    db = SessionLocal()
    try:
        c = guardar_corrida(db, project_id=None, user_id=None, entidad="PRUEBA S.A.",
                            fecha_corte=date(2025, 12, 31),
                            parametros={"umbral_individual": 100000},
                            resultado={"ecl_total": 1234.56})
        assert c.id is not None
        leida = db.get(CorridaPCE, c.id)
        assert leida.resultado["ecl_total"] == 1234.56
        assert leida.parametros["umbral_individual"] == 100000
        assert leida.created_at is not None
    finally:
        db.close()
