"""Guardar, leer y corregir la clasificación de un job."""

import pytest

from backend.app.aud.obligaciones_fiscales.mayor.clasificacion_service import (
    aplicar_correcciones,
    clasificacion_de_job,
    guardar_clasificacion,
)
from backend.app.aud.obligaciones_fiscales.mayor.tipos import (
    PerfilCuenta,
    ResultadoClasificacion,
    Senal,
)
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _resultado(codigo="2.1.7.3.2", categoria="RET_IVA", confianza="alta"):
    return ResultadoClasificacion(
        codigo=codigo, nombre="Ret. 70% Servicios", categoria=categoria,
        confianza=confianza, origen="reglas", tarifa=70.0,
        puntajes={"RET_IVA": 65},
        senales=[Senal("RET_IVA", 40, "nombre con tarifa 70.0%")],
    )


def _perfil(codigo="2.1.7.3.2"):
    return PerfilCuenta(codigo=codigo, nombre="Ret. 70% Servicios",
                        n_movimientos=149, debe=7490.42, haber=7490.42,
                        por_mes={"01": 0.0})


def test_guarda_una_fila_por_cuenta_con_su_justificacion():
    db = SessionLocal()
    try:
        guardar_clasificacion(db, job_id=9001,
                              resultados=[_resultado()],
                              perfiles={"2.1.7.3.2": _perfil()})
        filas = clasificacion_de_job(db, job_id=9001)
        assert len(filas) == 1
        assert filas[0].categoria_sugerida == "RET_IVA"
        assert filas[0].categoria_final == "RET_IVA"
        assert filas[0].n_movimientos == 149
        assert filas[0].senales_json[0]["motivo"].startswith("nombre")
    finally:
        db.close()


def test_guardar_de_nuevo_reemplaza_la_clasificacion_anterior_del_job():
    db = SessionLocal()
    try:
        guardar_clasificacion(db, job_id=9002, resultados=[_resultado()],
                              perfiles={"2.1.7.3.2": _perfil()})
        guardar_clasificacion(db, job_id=9002, resultados=[_resultado()],
                              perfiles={"2.1.7.3.2": _perfil()})
        assert len(clasificacion_de_job(db, job_id=9002)) == 1
    finally:
        db.close()


def test_una_correccion_del_auditor_cambia_la_categoria_final_y_queda_marcada():
    db = SessionLocal()
    try:
        guardar_clasificacion(db, job_id=9003, resultados=[_resultado()],
                              perfiles={"2.1.7.3.2": _perfil()})
        n = aplicar_correcciones(
            db, job_id=9003,
            correcciones=[{"codigo_cuenta": "2.1.7.3.2", "categoria": "RET_RENTA"}],
            user_id=7,
        )
        assert n == 1
        fila = clasificacion_de_job(db, job_id=9003)[0]
        assert fila.categoria_sugerida == "RET_IVA"   # se conserva lo que dijo el motor
        assert fila.categoria_final == "RET_RENTA"    # y lo que decidió el humano
        assert fila.corregida is True
        assert fila.origen == "manual"
    finally:
        db.close()


def test_confirmar_sin_cambiar_no_marca_la_fila_como_corregida():
    db = SessionLocal()
    try:
        guardar_clasificacion(db, job_id=9004, resultados=[_resultado()],
                              perfiles={"2.1.7.3.2": _perfil()})
        aplicar_correcciones(
            db, job_id=9004,
            correcciones=[{"codigo_cuenta": "2.1.7.3.2", "categoria": "RET_IVA"}],
            user_id=7,
        )
        fila = clasificacion_de_job(db, job_id=9004)[0]
        assert fila.corregida is False
        assert fila.origen == "reglas"
    finally:
        db.close()


def test_una_correccion_para_una_cuenta_inexistente_se_ignora():
    db = SessionLocal()
    try:
        guardar_clasificacion(db, job_id=9005, resultados=[_resultado()],
                              perfiles={"2.1.7.3.2": _perfil()})
        n = aplicar_correcciones(
            db, job_id=9005,
            correcciones=[{"codigo_cuenta": "0.0.0", "categoria": "VENTAS"}],
            user_id=7,
        )
        assert n == 0
    finally:
        db.close()


def test_reclasificar_entre_naturalezas_corrige_el_lado_en_el_libro():
    """Extremo a extremo del bug de signos: se guarda una cuenta con débito y
    crédito, el motor la sugiere como activo (lee el débito); el auditor la
    reclasifica a un pasivo y, al armar el libro, "según libros" pasa a leer el
    CRÉDITO (el devengo), no el débito."""
    from openpyxl import Workbook

    from backend.app.aud.obligaciones_fiscales.libro.hoja_mayores import (
        SHEET_MAYORES, build_hoja_mayores,
    )

    db = SessionLocal()
    try:
        perfil = PerfilCuenta(codigo="2.3.2.13", nombre="Retención IVA 100%",
                              n_movimientos=2, debe=5.0, haber=1000.0,
                              por_mes_debe={"01": 5.0}, por_mes_haber={"01": 1000.0})
        res = ResultadoClasificacion(
            codigo="2.3.2.13", nombre="Retención IVA 100%",
            categoria="IVA_COMPRAS",  # el motor la cree activo (lado débito)
            confianza="media", origen="reglas", tarifa=None,
            puntajes={}, senales=[],
        )
        guardar_clasificacion(db, job_id=9006, resultados=[res],
                              perfiles={"2.3.2.13": perfil})
        # Se persisten los DOS lados.
        fila = clasificacion_de_job(db, job_id=9006)[0]
        assert fila.por_mes_json == {"debe": {"01": 5.0}, "haber": {"01": 1000.0}}

        # El auditor la reclasifica a RET_IVA (pasivo).
        aplicar_correcciones(
            db, job_id=9006,
            correcciones=[{"codigo_cuenta": "2.3.2.13", "categoria": "RET_IVA"}],
            user_id=7,
        )
        filas = clasificacion_de_job(db, job_id=9006)

        wb = Workbook()
        lookup = build_hoja_mayores(wb, filas)
        ws = wb[SHEET_MAYORES]
        addr = lookup[("cuenta:2.3.2.13", "01")]
        celda = ws[addr.split("!", 1)[1]]
        assert celda.value == 1000.0  # el crédito (devengo), no el débito 5.0
    finally:
        db.close()
