from backend.app.client_portal.rate_limit import check_and_record, reset_for_key


def test_rate_limit_blocks_after_max_hits():
    reset_for_key("test:abc")
    for _ in range(5):
        assert check_and_record("test:abc", max_hits=5, window_seconds=10) is True
    assert check_and_record("test:abc", max_hits=5, window_seconds=10) is False


def test_rate_limit_separate_keys():
    reset_for_key("test:k1")
    reset_for_key("test:k2")
    for _ in range(5):
        check_and_record("test:k1", max_hits=5, window_seconds=10)
    assert check_and_record("test:k2", max_hits=5, window_seconds=10) is True
