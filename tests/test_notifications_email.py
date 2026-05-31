"""Tests for notifications.email (Resend wrapper)."""
from unittest.mock import patch
from backend.app.notifications import email as email_mod


def test_render_job_ready_template():
    html = email_mod.render_job_ready(
        client_name="Empresa XYZ",
        tool_label="Anexo ICT 2025",
        download_url="https://example.com/download",
    )
    assert "Empresa XYZ" in html
    assert "Anexo ICT 2025" in html
    assert "https://example.com/download" in html
    assert "24h" in html or "24 horas" in html


@patch("backend.app.notifications.email.time.sleep", lambda _: None)  # speed up retry
@patch("backend.app.notifications.email._post_to_resend")
def test_send_email_retries_on_failure(mock_post):
    mock_post.side_effect = [
        Exception("temporary"),
        Exception("temporary"),
        {"id": "msg_123"},
    ]
    result = email_mod.send_email(
        to="x@example.com", subject="Test", html="<p>x</p>"
    )
    assert result == {"id": "msg_123"}
    assert mock_post.call_count == 3


@patch("backend.app.notifications.email.time.sleep", lambda _: None)
@patch("backend.app.notifications.email._post_to_resend")
def test_send_email_returns_none_after_max_retries(mock_post):
    mock_post.side_effect = Exception("permanent")
    result = email_mod.send_email(
        to="x@example.com", subject="Test", html="<p>x</p>", max_retries=2
    )
    assert result is None
    assert mock_post.call_count == 2
