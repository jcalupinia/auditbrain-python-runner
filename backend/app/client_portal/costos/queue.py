"""Durable tenant-scoped queue for a separate AuditSmart worker.
Schema must be applied by migration in production, not by request handlers.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from sqlalchemy import MetaData, Table, Column, Integer, String, DateTime, Text, select, update
from sqlalchemy.engine import Engine

metadata = MetaData()
jobs = Table("costos_queue_jobs", metadata,
    Column("id", Integer, primary_key=True),
    Column("organization_id", Integer, nullable=False),
    Column("client_id", Integer, nullable=False),
    Column("project_id", Integer, nullable=False),
    Column("slot", String(80), nullable=False),
    Column("file_ref", Text, nullable=False),
    Column("status", String(16), nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("max_attempts", Integer, nullable=False),
    Column("worker_id", String(128)),
    Column("lease_until", DateTime),
    Column("result_ref", Text),
    Column("error_message", Text))

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

@dataclass(frozen=True)
class ClaimedJob:
    id: int
    organization_id: int
    client_id: int
    project_id: int
    slot: str
    file_ref: str
    status: str
    attempts: int

class CostQueue:
    def __init__(self, engine: Engine):
        self.engine = engine
        metadata.create_all(engine, tables=[jobs])  # only local/test; migrate production explicitly

    @staticmethod
    def _tenant(org, client, project):
        if any(type(v) is not int or v <= 0 for v in (org, client, project)):
            raise ValueError("positive tenant identifiers required")

    def enqueue(self, org: int, client: int, project: int, slot: str, file_ref: str, max_attempts: int=3) -> int:
        self._tenant(org, client, project)
        if type(max_attempts) is not int or not 1 <= max_attempts <= 10 or not slot or not file_ref:
            raise ValueError("invalid queue configuration")
        with self.engine.begin() as conn:
            return conn.execute(jobs.insert().values(organization_id=org, client_id=client,
                project_id=project,slot=slot,file_ref=file_ref,status="pending",attempts=0,
                max_attempts=max_attempts)).inserted_primary_key[0]

    def status(self, org: int, client: int, project: int, job_id: int) -> str:
        self._tenant(org,client,project)
        with self.engine.connect() as conn:
            state = conn.execute(select(jobs.c.status).where(jobs.c.id==job_id,
                jobs.c.organization_id==org,jobs.c.client_id==client,jobs.c.project_id==project)).scalar_one_or_none()
            if state is None: raise PermissionError("job not accessible")
            return state

    def claim(self, worker_id: str, lease_seconds: int=300) -> ClaimedJob | None:
        if not worker_id or len(worker_id)>128 or lease_seconds<0:
            raise ValueError("invalid worker or lease")
        for _ in range(4):
            with self.engine.begin() as conn:
                candidate = conn.execute(select(jobs.c.id).where(jobs.c.status=="pending")
                    .order_by(jobs.c.id).limit(1)).scalar_one_or_none()
                if candidate is None: return None
                updated = conn.execute(update(jobs).where(jobs.c.id==candidate,jobs.c.status=="pending")
                    .values(status="processing", attempts=jobs.c.attempts+1,
                    worker_id=worker_id,lease_until=utcnow()+timedelta(seconds=lease_seconds)))
                if updated.rowcount==1:
                    job=conn.execute(select(jobs).where(jobs.c.id==candidate)).mappings().one()
                    return ClaimedJob(**{k:job[k] for k in ClaimedJob.__dataclass_fields__})
        return None

    def complete(self, job_id: int, worker_id: str, result_ref: str):
        if not result_ref: raise ValueError("result reference required")
        with self.engine.begin() as conn:
            updated=conn.execute(update(jobs).where(jobs.c.id==job_id,jobs.c.status=="processing",
                jobs.c.worker_id==worker_id).values(status="done",result_ref=result_ref,
                worker_id=None,lease_until=None))
            if updated.rowcount!=1: raise PermissionError("worker does not own active job")

    def fail(self, job_id: int, worker_id: str, message: str):
        with self.engine.begin() as conn:
            state=conn.execute(select(jobs.c.attempts,jobs.c.max_attempts).where(
                jobs.c.id==job_id,jobs.c.status=="processing",jobs.c.worker_id==worker_id)).first()
            if state is None: raise PermissionError("worker does not own active job")
            next_state="failed" if state.attempts>=state.max_attempts else "pending"
            conn.execute(update(jobs).where(jobs.c.id==job_id,jobs.c.status=="processing",
                jobs.c.worker_id==worker_id).values(status=next_state,
                error_message=(message or "")[:1000],worker_id=None,lease_until=None))

    def recover_expired(self) -> int:
        with self.engine.begin() as conn:
            due=conn.execute(select(jobs.c.id,jobs.c.attempts,jobs.c.max_attempts).where(
                jobs.c.status=="processing",jobs.c.lease_until<=utcnow())).all()
            for job in due:
                conn.execute(update(jobs).where(jobs.c.id==job.id,jobs.c.status=="processing",
                    jobs.c.lease_until<=utcnow()).values(status="failed" if job.attempts>=job.max_attempts else "pending",
                    worker_id=None,lease_until=None,error_message="worker lease expired"))
            return len(due)
