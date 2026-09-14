from backend.app.client_portal.rate_limit import check_and_record, reset_for_key


def test_rate_limit_blocks_after_max_hits():
    reset_for_key("test:abc")
    for _ in range(5):
        assert check_and_record("test:abc", max_hits=5, window_seconds=10) is True
    assert check_and_record("test:abc", max_hits=5, window_seconds=10) is False


def test_barrido_elimina_claves_viejas(monkeypatch):
    from collections import defaultdict, deque

    from backend.app.client_portal import rate_limit as rl

    monkeypatch.setattr(rl, "_WINDOWS", defaultdict(deque))
    monkeypatch.setattr(rl, "_MAX_KEYS", 2)
    ahora = [1000.0]
    monkeypatch.setattr(rl.time, "monotonic", lambda: ahora[0])
    rl.check_and_record("viejo:a", max_hits=5, window_seconds=10)
    rl.check_and_record("viejo:b", max_hits=5, window_seconds=10)
    ahora[0] += 3601
    rl.check_and_record("nuevo:c", max_hits=5, window_seconds=10)
    rl.check_and_record("nuevo:d", max_hits=5, window_seconds=10)  # 3 > 2 → barre
    assert set(rl._WINDOWS) == {"nuevo:c", "nuevo:d"}


def test_rate_limit_separate_keys():
    reset_for_key("test:k1")
    reset_for_key("test:k2")
    for _ in range(5):
        check_and_record("test:k1", max_hits=5, window_seconds=10)
    assert check_and_record("test:k2", max_hits=5, window_seconds=10) is True
