"""Normalización de hostnames (backend/app/core/hostnames.py)."""

import pytest

from backend.app.core.hostnames import normalize_host, split_hosts


@pytest.mark.parametrize("entrada,esperado", [
    ("123.api.preview.audit-ia.ec", "123.api.preview.audit-ia.ec"),
    ("  123.API.Preview.Audit-IA.ec. ", "123.api.preview.audit-ia.ec"),
    ("123.api.preview.audit-ia.ec:10000", "123.api.preview.audit-ia.ec"),
    ("https://123.api.preview.audit-ia.ec:10000/ruta?x=1", "123.api.preview.audit-ia.ec"),
    ("http://user:pass@host.example.com/", "host.example.com"),
    ("host.example.com/ruta", "host.example.com"),
    ("", None), (None, None), ("   ", None),
    ("1.2.3.4", None),                       # IP literal
    ("algo_raro.example.com", None),         # guion bajo
    ("-mal.example.com", None),              # guion inicial
    ("a" * 254 + ".com", None),              # demasiado largo
    ("[::1]:5432", None),                    # IPv6 literal
])
def test_normalize_host(entrada, esperado):
    assert normalize_host(entrada) == esperado


def test_split_hosts_separa_por_comas_y_espacios_y_descarta_invalidos():
    assert split_hosts("123.api.preview.audit-ia.ec, https://123.consola.preview.audit-ia.ec  1.2.3.4 ,,") == [
        "123.api.preview.audit-ia.ec", "123.consola.preview.audit-ia.ec"]
    assert split_hosts(None) == [] and split_hosts("") == []
    assert split_hosts("a.b, A.B") == ["a.b"]  # sin duplicados tras normalizar
