"""Lectura de imágenes PRIVADAS en GHCR por el controlador de previews.

1. Unidad (sin red): el flujo real de autenticación del registro —canje del PAT por un token de registro con
   autenticación Basic y HEAD del manifiesto con Bearer— reproducido con un `urlopen` falso que valida cabeceras.
2. Integración (red real, solo lecturas): se ejecuta cuando hay un token con `read:packages` en el entorno
   (GHCR_READ_TOKEN o GHCR_PUBLISH_TOKEN; en CI lo aporta el secreto del repositorio) y comprueba contra GHCR que
   las tres imágenes `sha-b8cff2da…` existen, que un SHA inexistente devuelve lista vacía y que sin credencial un
   paquete privado no se lee. Sin token se omite (no se inventa el resultado).
"""
from __future__ import annotations

import base64
import importlib.util
import io
import json
import os
import sys
import urllib.error
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parents[1] / "scripts" / "preview_lifecycle.py"
spec = importlib.util.spec_from_file_location("preview_lifecycle_ghcr", RUTA)
pl = importlib.util.module_from_spec(spec)
sys.modules["preview_lifecycle_ghcr"] = pl
spec.loader.exec_module(pl)

SHA_PUBLICADO = "b8cff2daeea166704427f6ef63738ad24db812ec"   # P1C del 2026-10-20: tres imágenes privadas verificadas
TOKEN = os.environ.get("GHCR_READ_TOKEN") or os.environ.get("GHCR_PUBLISH_TOKEN") or ""


class _Resp(io.BytesIO):
    def __init__(self, status, body=b""):
        super().__init__(body)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _opener_falso(existentes: set[str], pat_valido: str = "PAT-OK"):
    """Imita GHCR: /token exige Basic owner:PAT válido; el manifiesto exige Bearer del token canjeado."""
    registro = []

    def opener(req, timeout=0):
        url, auth = req.full_url, req.get_header("Authorization", "")
        registro.append((req.get_method(), url, auth[:6]))
        if url.startswith("https://ghcr.io/token?"):
            assert "service=ghcr.io" in url and ":pull" in url
            esperado = "Basic " + base64.b64encode(f"{pl.GHCR_OWNER}:{pat_valido}".encode()).decode()
            if auth != esperado:
                raise urllib.error.HTTPError(url, 401, "denied", {}, None)
            pkg = url.split("repository:")[1].split(":pull")[0].split("/")[-1]
            return _Resp(200, json.dumps({"token": f"REG-{pkg}"}).encode())
        if "/manifests/" in url:
            pkg = url.split("/v2/")[1].split("/manifests/")[0].split("/")[-1]
            assert req.get_method() == "HEAD" and req.get_header("Accept") == pl.ACCEPT_MANIFIESTO
            if auth != f"Bearer REG-{pkg}":
                raise urllib.error.HTTPError(url, 401, "unauthorized", {}, None)
            if url.split("/manifests/", 1)[1] in existentes:
                return _Resp(200)
            raise urllib.error.HTTPError(url, 404, "not found", {}, None)
        raise AssertionError(f"URL inesperada {url}")

    opener.registro = registro
    return opener


def test_unidad_canje_basic_y_head_con_bearer():
    op = _opener_falso({f"sha-{SHA_PUBLICADO}"})
    assert pl.imagenes_publicadas(SHA_PUBLICADO, "PAT-OK", op) == ["backend", "consola", "clientes"]
    assert pl.imagenes_publicadas("0" * 40, "PAT-OK", op) == []
    # El PAT nunca viaja como Bearer directo al manifiesto: solo el token canjeado
    assert all(not (m == "HEAD" and a.startswith("Basic")) for m, u, a in op.registro)
    assert any(u.startswith("https://ghcr.io/token?") and a == "Basic " for m, u, a in op.registro)


def test_unidad_sin_pat_o_pat_sin_permiso_no_lee_privados():
    op = _opener_falso({f"sha-{SHA_PUBLICADO}"})
    assert pl.imagenes_publicadas(SHA_PUBLICADO, "PAT-MALO", op) == []
    assert pl.imagenes_publicadas(SHA_PUBLICADO, "", op) == []


@pytest.mark.skipif(not TOKEN, reason="sin GHCR_READ_TOKEN/GHCR_PUBLISH_TOKEN en el entorno: la lectura real contra GHCR no se puede comprobar")
def test_integracion_ghcr_real_lee_las_tres_imagenes_privadas():
    assert pl.imagenes_publicadas(SHA_PUBLICADO, TOKEN) == ["backend", "consola", "clientes"]
    assert pl.imagenes_publicadas("f" * 40, TOKEN) == []


@pytest.mark.skipif(not TOKEN, reason="sin token: se omite la comprobación de que el acceso anónimo falla")
def test_integracion_ghcr_real_anonimo_no_lee_privados():
    assert pl.imagenes_publicadas(SHA_PUBLICADO, "") == []
