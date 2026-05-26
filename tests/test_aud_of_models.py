"""Verifica que ToolJob queda registrado en init_db()."""

from sqlalchemy import inspect

from backend.app.db.session import engine, init_db


def test_tool_jobs_table_exists():
    init_db()
    insp = inspect(engine)
    assert "tool_jobs" in insp.get_table_names()


def test_tool_jobs_required_columns():
    init_db()
    cols = {c["name"] for c in inspect(engine).get_columns("tool_jobs")}
    assert {
        "id",
        "user_id",
        "project_id",
        "tool_code",
        "status",
        "cliente_name",
        "period_label",
        "created_at",
        "expires_at",
        "summary_json",
        "error_message",
    } <= cols


def test_tool_jobs_indexes():
    init_db()
    insp = inspect(engine)
    indexes = insp.get_indexes("tool_jobs")
    indexed_cols = {col for idx in indexes for col in idx["column_names"]}
    assert "project_id" in indexed_cols
