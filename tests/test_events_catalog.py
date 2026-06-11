from backend.app.events.catalog import EVENTS, get_event


def test_charla_event_exists():
    ev = get_event("charla-anexos-2026-06")
    assert ev is not None
    assert ev.titulo == "Elaboración de Anexos Tributarios con Herramienta de Automatización"
    assert ev.fecha_texto == "Jueves 18 de junio"
    assert ev.modalidad == "Zoom"
    assert len(ev.beneficios) == 5
    assert ev.activo is True


def test_get_event_unknown_returns_none():
    assert get_event("no-existe") is None


def test_events_dict_keyed_by_slug():
    for slug, ev in EVENTS.items():
        assert ev.slug == slug
