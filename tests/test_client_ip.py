"""IP del cliente para los límites de intentos (Render detrás de Cloudflare).

X-Forwarded-For lo controla el cliente en Render (el proxy agrega, no reemplaza),
así que no sirve para limitar; Cloudflare fija True-Client-IP / CF-Connecting-IP.
"""

from starlette.requests import Request

from backend.app.events.router import _client_ip


def _req(headers: dict[str, str], client=("10.0.0.9", 443)) -> Request:
    return Request(
        {
            "type": "http",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": client,
        }
    )


def test_prefiere_true_client_ip():
    r = _req({"True-Client-IP": "1.1.1.1", "CF-Connecting-IP": "2.2.2.2", "X-Forwarded-For": "6.6.6.6"})
    assert _client_ip(r) == "1.1.1.1"


def test_usa_cf_connecting_ip_si_no_hay_true_client_ip():
    r = _req({"CF-Connecting-IP": "2.2.2.2", "X-Forwarded-For": "6.6.6.6"})
    assert _client_ip(r) == "2.2.2.2"


def test_ignora_x_forwarded_for_falsificable():
    r = _req({"X-Forwarded-For": "6.6.6.6, 7.7.7.7"})
    assert _client_ip(r) == "10.0.0.9"


def test_sin_conexion_devuelve_unknown():
    assert _client_ip(_req({}, client=None)) == "unknown"
