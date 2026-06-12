"""El catálogo debe leer el link del grupo de WhatsApp desde la env var.

Usa ``_build_events()`` directamente (lee ``os.getenv`` en cada llamada), sin
recargar el módulo ni tocar el ``EVENTS`` global, para no contaminar otros tests.
"""

import backend.app.events.catalog as catalog


def test_build_events_reads_whatsapp_group_url_from_env(monkeypatch):
    monkeypatch.setenv(
        "CHARLA_WHATSAPP_GROUP_URL", "https://chat.whatsapp.com/ENVTEST"
    )
    events = catalog._build_events()
    ev = events["charla-anexos-2026-06"]
    assert ev.whatsapp_group_url == "https://chat.whatsapp.com/ENVTEST"


def test_build_events_default_group_url_empty(monkeypatch):
    monkeypatch.delenv("CHARLA_WHATSAPP_GROUP_URL", raising=False)
    events = catalog._build_events()
    assert events["charla-anexos-2026-06"].whatsapp_group_url == ""
