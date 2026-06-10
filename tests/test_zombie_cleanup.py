"""Test: jobs en 'processing' por más de 30 min → marcados 'error' automáticamente."""
import datetime
import uuid
from backend.app.aud.obligaciones_fiscales.cleanup import cleanup_once
from backend.app.aud.obligaciones_fiscales.models import ToolJob
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.auth.models import Role
from backend.app.context.models import Organization, Client, Project
from backend.app.db.session import SessionLocal


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_zombie_processing_job_marked_error():
    db = SessionLocal()
    try:
        suffix = _unique("z")
        org = Organization(name=f"ZO-{suffix}", slug=f"z-o-{suffix}", is_active=True)
        db.add(org); db.commit(); db.refresh(org)
        cli = Client(organization_id=org.id, name=f"ZC-{suffix}", is_active=True)
        db.add(cli); db.commit(); db.refresh(cli)
        proj = Project(organization_id=org.id, client_id=cli.id, name=f"ZP-{suffix}")
        db.add(proj); db.commit(); db.refresh(proj)
        email = f"zombie-{suffix}@x.com"
        u = get_user_by_email(db, email) or create_user(db, email, "x", Role.client)

        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        job = ToolJob(
            user_id=u.id, project_id=proj.id, tool_code="STUB_ECHO",
            status="processing", cliente_name="x", period_label="x",
            created_at=now - datetime.timedelta(hours=2),
            expires_at=now + datetime.timedelta(hours=22),
            initiated_from="client",
        )
        db.add(job); db.commit(); db.refresh(job)
        zombie_id = job.id

        summary = cleanup_once()
        db.close()  # cleanup_once uses its own session; reopen to read fresh
        db = SessionLocal()
        job = db.get(ToolJob, zombie_id)
        assert job.status == "error"
        assert "zombie" in (job.error_message or "").lower() or "tiempo" in (job.error_message or "").lower()
        assert summary.get("zombie_jobs", 0) >= 1
    finally:
        db.close()
