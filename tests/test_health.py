def test_platform_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "AuditBrain Platform v1"
    assert "auth_enabled" in body


def test_legacy_root_still_works(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "AuditBrain Python Runner"


# --- /api/v1/host-capacity: lectura de capacidad del host para la admisión de previews (F2) -----------------

def test_host_capacity_apagado_sin_token_configurado(client, monkeypatch):
    monkeypatch.delenv("PREVIEW_CAPACITY_TOKEN", raising=False)
    assert client.get("/api/v1/host-capacity", headers={"X-Capacity-Token": "x" * 32}).status_code == 404


def test_host_capacity_token_corto_cuenta_como_apagado(client, monkeypatch):
    monkeypatch.setenv("PREVIEW_CAPACITY_TOKEN", "corto")
    assert client.get("/api/v1/host-capacity", headers={"X-Capacity-Token": "corto"}).status_code == 404


def test_host_capacity_rechaza_token_incorrecto_o_ausente(client, monkeypatch):
    monkeypatch.setenv("PREVIEW_CAPACITY_TOKEN", "t" * 40)
    assert client.get("/api/v1/host-capacity").status_code == 401
    assert client.get("/api/v1/host-capacity", headers={"X-Capacity-Token": "u" * 40}).status_code == 401


def test_host_capacity_devuelve_solo_metricas_agregadas(client, monkeypatch):
    monkeypatch.setenv("PREVIEW_CAPACITY_TOKEN", "t" * 40)
    r = client.get("/api/v1/host-capacity", headers={"X-Capacity-Token": "t" * 40})
    assert r.status_code == 200
    body = r.json()
    claves = {"observed_at", "source", "mem_total_mib", "mem_available_mib", "swap_total_mib", "swap_used_mib",
              "swap_used_pct", "psi_mem_some_avg60", "load1", "cpus", "disk_path", "disk_free_gib", "oom_recent"}
    assert set(body) == claves, "ningún campo adicional (nada sensible del host)"
    assert body["observed_at"].endswith("Z") and body["oom_recent"] is None
    assert isinstance(body["mem_available_mib"], int) and isinstance(body["mem_total_mib"], int)
    volcado = str(body)
    assert "PREVIEW_CAPACITY_TOKEN" not in volcado and "t" * 40 not in volcado


def test_host_capacity_snapshot_lee_proc_simulado(tmp_path):
    from backend.app.core.host_capacity import host_capacity_snapshot
    (tmp_path / "meminfo").write_text("MemTotal:        3800000 kB\nMemAvailable:    2300000 kB\nSwapTotal:       4194304 kB\nSwapFree:        3145728 kB\n", encoding="utf-8")
    (tmp_path / "psi").write_text("some avg10=0.00 avg60=12.50 avg300=0.00 total=0\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0\n", encoding="utf-8")
    (tmp_path / "loadavg").write_text("0.75 0.40 0.30 1/200 1234\n", encoding="utf-8")
    s = host_capacity_snapshot(meminfo=str(tmp_path / "meminfo"), psi=str(tmp_path / "psi"), loadavg=str(tmp_path / "loadavg"), disk_path=str(tmp_path))
    assert s["mem_total_mib"] == 3710 and s["mem_available_mib"] == 2246
    assert s["swap_total_mib"] == 4096 and s["swap_used_mib"] == 1024 and s["swap_used_pct"] == 25.0
    assert s["psi_mem_some_avg60"] == 12.5 and s["load1"] == 0.75 and s["disk_free_gib"] is not None
    # Sin PSI (núcleo sin soporte) el campo es None, no un error
    s2 = host_capacity_snapshot(meminfo=str(tmp_path / "meminfo"), psi=str(tmp_path / "no-existe"), loadavg=str(tmp_path / "loadavg"), disk_path=str(tmp_path))
    assert s2["psi_mem_some_avg60"] is None
