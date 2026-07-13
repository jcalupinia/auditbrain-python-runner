"""Propagación por grupo: las cuentas HOJA huérfanas heredan el Super/SRI de sus
hermanas del mismo grupo (mismo código padre) ya homologadas, como sugerencia
pintada y confirmable. No sugiere si el grupo es ambiguo."""
from backend.app.client_portal.flujo import motor_balances as mb


def _f(cuenta, super_cias="", sri="", es_hoja=True):
    return {"cuenta": cuenta, "nombre": cuenta, "super_cias": super_cias,
            "sri": sri, "es_hoja": es_hoja, "saldos": {}}


def test_grupo_prefijo_padre():
    assert mb._grupo("1.01.01.01.006") == "1.01.01.01."
    assert mb._grupo("1.01.01.02.001") == "1.01.01.02."
    assert mb._grupo("2.01.03.05.010") == "2.01.03.05."


def test_hereda_super_sri_de_hermana_homologada():
    filas = [
        _f("1.01.01.01.", es_hoja=False),               # subtotal CAJA
        _f("1.01.01.01.006", "1010101", "311"),          # hermana homologada
        _f("1.01.01.01.002"),                            # huérfana → hereda
        _f("1.01.01.01.008"),                            # huérfana → hereda
    ]
    out = mb.sugerir_por_grupo(filas)
    d = {f["cuenta"]: f for f in out}
    assert d["1.01.01.01.002"]["super_cias"] == "1010101"
    assert d["1.01.01.01.002"]["sri"] == "311"
    assert d["1.01.01.01.002"]["sugerido"] is True
    assert d["1.01.01.01.008"]["super_cias"] == "1010101"
    assert d["1.01.01.01.008"]["sugerido"] is True
    # La hermana ya homologada NO se marca como sugerida.
    assert d["1.01.01.01.006"].get("sugerido") is not True


def test_no_sugiere_si_grupo_ambiguo():
    filas = [
        _f("1.01.01.02.001", "1010103", "311"),          # banco A
        _f("1.01.01.02.014", "1010301", "312"),          # inversión (otro super)
        _f("1.01.01.02.099"),                            # huérfana, grupo ambiguo
    ]
    out = mb.sugerir_por_grupo(filas)
    d = {f["cuenta"]: f for f in out}
    assert d["1.01.01.02.099"]["super_cias"] == ""       # no adivina
    assert d["1.01.01.02.099"].get("sugerido") is not True


def test_no_sugiere_a_subtotales():
    filas = [
        _f("1.01.01.01.006", "1010101", "311"),
        _f("1.01.01.01.", es_hoja=False),                # subtotal huérfano
    ]
    out = mb.sugerir_por_grupo(filas)
    d = {f["cuenta"]: f for f in out}
    assert d["1.01.01.01."].get("sugerido") is not True
    assert d["1.01.01.01."]["super_cias"] == ""


def test_no_hay_hermana_homologada_queda_huerfana():
    filas = [_f("1.01.02.01.001"), _f("1.01.02.01.002")]
    out = mb.sugerir_por_grupo(filas)
    assert all(not f.get("sugerido") for f in out)
    assert all(f["super_cias"] == "" for f in out)


def test_homologar_archivos_incluye_sugerencias(monkeypatch):
    """La orquestación aplica sugerencias por grupo tras propagar el mapeo."""
    from backend.app.client_portal.flujo import parser

    def fake_parse_balanza(_b):
        # el "mapeo" solo trae la hermana .006
        return [{"cuenta": "1.01.01.01.006", "nombre": "Caja Chica Ing Quito",
                 "super_cias": "1010101", "sri": "311"}]

    def fake_parse_multi(_b):
        return {"estado": "esf", "periodos": ["2025"], "filas": [
            {"cuenta": "1.01.01.01.", "nombre": "CAJA", "saldos": [100.0]},
            {"cuenta": "1.01.01.01.006", "nombre": "Caja Chica Ing Quito", "saldos": [50.0]},
            {"cuenta": "1.01.01.01.002", "nombre": "Caja Chica Quito", "saldos": [50.0]},
        ]}

    monkeypatch.setattr(parser, "parse_balanza", lambda b: fake_parse_balanza(b) if b == b"MAP" else [])
    monkeypatch.setattr(parser, "parse_balanza_multiperiodo", fake_parse_multi)
    res = mb.homologar_archivos([("map.xlsx", b"MAP"), ("bal.xlsx", b"BAL")])
    d = {f["cuenta"]: f for f in res["esf"]["filas"]}
    assert d["1.01.01.01.002"]["super_cias"] == "1010101"
    assert d["1.01.01.01.002"]["sugerido"] is True
    # una cuenta sugerida deja de ser huérfana
    assert "1.01.01.01.002" not in res["esf"]["huerfanas"]
