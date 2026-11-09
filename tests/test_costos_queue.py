"""Worker queue state machine contract (no HTTP side effects)."""
import pytest
from sqlalchemy import create_engine
from backend.app.client_portal.costos.queue import CostQueue

@pytest.fixture
def q(tmp_path):
    return CostQueue(create_engine(f"sqlite:///{tmp_path/'queue.sqlite'}"))

def test_enqueue_claim_complete(q):
    job=q.enqueue(1,10,100,"inventario_inicial","/private/input.csv")
    assert q.status(1,10,100,job)=="pending"
    claimed=q.claim("worker-A")
    assert claimed.id==job and claimed.status=="processing"
    assert q.claim("worker-B") is None
    q.complete(job,"worker-A",result_ref="import:123")
    assert q.status(1,10,100,job)=="done"

def test_cross_tenant_cannot_read(q):
    job=q.enqueue(1,10,100,"inventario_inicial","x.csv")
    with pytest.raises(PermissionError): q.status(1,11,101,job)

def test_failed_job_retries_then_fails(q):
    job=q.enqueue(1,10,100,"inventario_inicial","x.csv",max_attempts=2)
    a=q.claim("w1")
    q.fail(job,"w1","invalid header")
    assert q.status(1,10,100,job)=="pending"
    b=q.claim("w2")
    assert b.id==job and b.attempts==2
    q.fail(job,"w2","invalid header")
    assert q.status(1,10,100,job)=="failed"

def test_other_worker_cannot_complete(q):
    job=q.enqueue(1,10,100,"inventario_inicial","x.csv")
    q.claim("w1")
    with pytest.raises(PermissionError): q.complete(job,"w2","ref")

def test_stale_worker_is_recovered(q):
    job=q.enqueue(1,10,100,"inventario_inicial","x.csv",max_attempts=2)
    q.claim("w1",lease_seconds=0)
    assert q.recover_expired()==1
    assert q.status(1,10,100,job)=="pending"
    assert q.claim("w2").id==job

def test_invalid_tenant_and_attempts_fail(q):
    with pytest.raises(ValueError): q.enqueue(0,10,100,"inventory","x.csv")
    with pytest.raises(ValueError): q.enqueue(1,10,100,"inventory","x.csv",max_attempts=0)
