import csv
import io
import pytest
from sqlalchemy import create_engine
from backend.app.client_portal.costos.ingestion import CostIngestor, Tenant, ImportProblem

@pytest.fixture
def store(tmp_path):
    eng = create_engine(f'sqlite:///{tmp_path / "costos.db"}')
    return CostIngestor(eng, tmp_path / 'files', batch_size=17)

def csvbytes(n=70):
    s=io.StringIO()
    w=csv.writer(s); w.writerow(['codigo','cantidad','valor'])
    for i in range(n): w.writerow([f'MP{i}', '2', '3.50'])
    return s.getvalue().encode()

def test_streamed_csv_persists_all_rows_and_stats(store):
    t=Tenant(1,10,100)
    result=store.ingest_csv(t,'inventario_inicial',io.BytesIO(csvbytes(75)), 'opening.csv')
    assert result.row_count==75
    assert store.count(t,result.id)==75
    assert store.read_rows(t,result.id,limit=2)==[{'codigo':'MP0','cantidad':'2','valor':'3.50'},{'codigo':'MP1','cantidad':'2','valor':'3.50'}]

def test_tenant_isolation_even_for_known_import_id(store):
    a=Tenant(1,10,100); b=Tenant(1,11,101)
    rid=store.ingest_csv(a,'inventario_inicial',io.BytesIO(csvbytes(2)),'x.csv').id
    with pytest.raises(PermissionError): store.count(b,rid)
    with pytest.raises(PermissionError): store.read_rows(b,rid)

def test_repeat_is_idempotent_without_duplicate_rows(store):
    t=Tenant(1,10,100); p=csvbytes(2)
    x=store.ingest_csv(t,'inventario_inicial',io.BytesIO(p),'a.csv')
    y=store.ingest_csv(t,'inventario_inicial',io.BytesIO(p),'renamed.csv')
    assert x.id==y.id and store.count(t,x.id)==2

def test_same_file_different_tenants_are_isolated(store):
    p=csvbytes(2)
    a=store.ingest_csv(Tenant(1,10,100),'inventario_inicial',io.BytesIO(p),'a.csv')
    b=store.ingest_csv(Tenant(1,11,101),'inventario_inicial',io.BytesIO(p),'b.csv')
    assert a.id != b.id

def test_reject_invalid_headers_and_do_not_persist(store):
    t=Tenant(1,10,100)
    with pytest.raises(ImportProblem): store.ingest_csv(t,'inventario_inicial',io.BytesIO(b'codigo,codigo\na,b\n'),'a.csv')
    assert store.list_imports(t)==[]

def test_reject_oversize_without_loading_entire_stream(store):
    t=Tenant(1,10,100)
    with pytest.raises(ImportProblem): store.ingest_csv(t,'inventario_inicial',io.BytesIO(csvbytes(20)),'a.csv',max_bytes=25)
    assert store.list_imports(t)==[]

def test_bad_tenant_is_rejected(store):
    with pytest.raises(ImportProblem): store.ingest_csv(Tenant(1,0,100),'inventario_inicial',io.BytesIO(csvbytes(1)),'a.csv')

def test_invalid_csv_encoding_fails_closed(store):
    with pytest.raises(ImportProblem): store.ingest_csv(Tenant(1,10,100),'inventario_inicial',io.BytesIO(b'\xff\xfe'), 'bad.csv')
