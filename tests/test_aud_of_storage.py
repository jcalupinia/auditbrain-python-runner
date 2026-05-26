"""Tests de file_storage.py — helpers para /tmp efímero."""

import os
import time

import pytest

from backend.app.aud.obligaciones_fiscales import file_storage


@pytest.fixture()
def tmp_root(tmp_path, monkeypatch):
    monkeypatch.setenv("AUD_OF_TMP_DIR", str(tmp_path))
    from importlib import reload

    from backend.app.core import config

    reload(config)
    reload(file_storage)
    yield tmp_path


def test_create_job_dir_makes_inputs_subfolder(tmp_root):
    job_dir = file_storage.create_job_dir(job_id=42)
    assert job_dir.exists()
    assert (job_dir / "inputs").exists()
    assert "42" in str(job_dir)


def test_save_input_writes_file(tmp_root):
    job_dir = file_storage.create_job_dir(job_id=1)
    saved = file_storage.save_input(
        job_dir, slot="f103", filename="enero.pdf", data=b"%PDF-1.4 fake"
    )
    assert saved.exists()
    assert saved.read_bytes() == b"%PDF-1.4 fake"
    assert "f103" in str(saved)


def test_save_input_strips_unsafe_chars(tmp_root):
    job_dir = file_storage.create_job_dir(job_id=2)
    saved = file_storage.save_input(
        job_dir, slot="f104", filename="../../etc/passwd", data=b"x"
    )
    assert ".." not in saved.name
    assert "passwd" in saved.name or "etc" in saved.name


def test_output_path_returns_consistent_location(tmp_root):
    job_dir = file_storage.create_job_dir(job_id=3)
    out = file_storage.output_path(job_dir)
    assert out.name == "output.xlsx"
    assert out.parent == job_dir


def test_delete_job_dir_removes_recursively(tmp_root):
    job_dir = file_storage.create_job_dir(job_id=4)
    file_storage.save_input(job_dir, "f103", "a.pdf", b"x")
    assert job_dir.exists()
    file_storage.delete_job_dir(job_id=4)
    assert not job_dir.exists()


def test_list_inputs_by_slot(tmp_root):
    job_dir = file_storage.create_job_dir(job_id=7)
    file_storage.save_input(job_dir, "f103", "a.pdf", b"a")
    file_storage.save_input(job_dir, "f103", "b.pdf", b"b")
    file_storage.save_input(job_dir, "f104", "c.pdf", b"c")

    f103s = file_storage.list_inputs(job_dir, "f103")
    assert len(f103s) == 2

    f104s = file_storage.list_inputs(job_dir, "f104")
    assert len(f104s) == 1

    all_inputs = file_storage.list_inputs(job_dir)
    assert len(all_inputs) == 3


def test_list_orphan_job_dirs_returns_old_ones(tmp_root):
    j1 = file_storage.create_job_dir(job_id=10)
    j2 = file_storage.create_job_dir(job_id=11)
    very_old = time.time() - 7200  # 2h atrás
    os.utime(j1, (very_old, very_old))
    orphans = file_storage.list_orphan_job_dirs(max_age_seconds=3600)
    orphan_ids = [int(p.name) for p in orphans]
    assert 10 in orphan_ids
    assert 11 not in orphan_ids
