"""Hash-chain de la bitácora del encargo (P2-G, ENG-020) — módulo puro."""
import types

import pytest

from backend.app.aud.niif.ciclo.gobernanza import (
    GENESIS,
    CadenaCorrupta,
    compute_hash_evento,
    entrada_de_evento,
    entrada_firmada,
    rol_de_usuario,
    verificar_cadena,
)


def _e(**k):
    base = dict(seq=1, ts="2026-09-24T00:00:00", actor="a@x.ec", rol="SOCIO",
                accion="approve", prueba_id=7, revision=1, estado_anterior="EN_REVISION",
                estado_nuevo="APROBADO", content_hash="", comentario="ok")
    base.update(k)
    return entrada_firmada(**base)


def test_hash_estable_y_depende_del_prev():
    e = _e()
    h1 = compute_hash_evento(e, GENESIS)
    assert len(h1) == 64 and h1 == compute_hash_evento(e, GENESIS)
    assert compute_hash_evento(e, h1) != h1  # encadena con el prev


def test_vector_fijo_blinda_el_contrato_de_campos():
    # Si se reordena/cambia _CAMPOS_EVENTO, este vector cambia y avisa.
    e = entrada_firmada(seq=1, ts="2026-01-01T00:00:00+00:00", actor="x", rol="ADMIN",
                        accion="create", prueba_id=1, revision=1, estado_anterior=None,
                        estado_nuevo="PRUEBA_SELECCIONADA", content_hash="", comentario="")
    assert compute_hash_evento(e, GENESIS) == \
        "4e6727a95bbfc53402659f3b06cc06013cfadfad5d18cddf1b7a55928028a808"


def test_none_se_normaliza_igual_al_firmar_y_verificar():
    firmado = entrada_firmada(estado_anterior=None)
    assert firmado["estado_anterior"] == ""  # None → "" (consistente con la fila)


def _fila(**k):
    return types.SimpleNamespace(
        seq=k["seq"], creado_en=None, actor=k.get("actor", "a"), rol=k.get("rol", ""),
        accion=k.get("accion", "x"), prueba_id=k.get("prueba_id", 1),
        revision=k.get("revision", 1), estado_anterior=k.get("estado_anterior"),
        estado_nuevo=k.get("estado_nuevo", "S"), content_hash="",
        comentario=k.get("comentario"), prev_hash=k["prev_hash"], hash=k["hash"],
    )


def _cadena(n=3):
    filas, prev = [], GENESIS
    for i in range(1, n + 1):
        f = _fila(seq=i, estado_anterior=(None if i == 1 else "S"), prev_hash=prev, hash="")
        f.hash = compute_hash_evento(entrada_de_evento(f), prev)
        prev = f.hash
        filas.append(f)
    return filas


def test_verificar_cadena_integra():
    filas = _cadena(3)
    ok = verificar_cadena(filas)
    assert [f.seq for f in ok] == [1, 2, 3] and ok[0].prev_hash == GENESIS


def test_manipular_un_evento_rompe_la_verificacion():
    filas = _cadena(3)
    filas[1].estado_nuevo = "ALTERADO"  # cambia el contenido sin recomputar el hash
    with pytest.raises(CadenaCorrupta) as exc:
        verificar_cadena(filas)
    assert exc.value.seq == 2


def test_borrar_un_evento_rompe_la_verificacion():
    filas = _cadena(3)
    del filas[1]  # borrar el intermedio: seq 1,3 → no contiguo / prev no encadena
    with pytest.raises(CadenaCorrupta):
        verificar_cadena(filas)


def test_rol_de_usuario():
    assert rol_de_usuario(types.SimpleNamespace(role="socio")) == "SOCIO"
    assert rol_de_usuario(types.SimpleNamespace(role="user")) == "PREPARADOR"
    assert rol_de_usuario(types.SimpleNamespace(role="admin")) == "ADMIN"
    assert rol_de_usuario(types.SimpleNamespace(role=None)) == "ADMIN"
