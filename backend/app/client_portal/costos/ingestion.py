"""Tenant-scoped, bounded-memory CSV staging. This is not an HTTP endpoint.
Caller MUST check authenticated tenant context and tool entitlement first.
Production schemas require reviewed migrations; create_all is for isolated tests.
"""
from __future__ import annotations
import csv
import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from sqlalchemy import MetaData, Table, Column, Integer, String, Text, ForeignKey, UniqueConstraint, select, func
from sqlalchemy.engine import Engine

class ImportProblem(ValueError):
    pass

@dataclass(frozen=True)
class Tenant:
    organization_id: int
    client_id: int
    project_id: int

@dataclass(frozen=True)
class ImportResult:
    id: int
    row_count: int
    checksum: str

metadata = MetaData()
imports = Table('costos_imports', metadata,
    Column('id', Integer, primary_key=True),
    Column('organization_id', Integer, nullable=False),
    Column('client_id', Integer, nullable=False),
    Column('project_id', Integer, nullable=False),
    Column('slot', String(80), nullable=False),
    Column('checksum', String(64), nullable=False),
    Column('original_filename', String(255), nullable=False),
    Column('row_count', Integer, nullable=False),
    UniqueConstraint('organization_id','client_id','project_id','slot','checksum',name='uq_costos_import_identity'))
rows = Table('costos_import_rows', metadata,
    Column('id',Integer,primary_key=True),
    Column('import_id',Integer,ForeignKey('costos_imports.id',ondelete='CASCADE'),nullable=False),
    Column('line_number',Integer,nullable=False),
    Column('payload',Text,nullable=False),
    UniqueConstraint('import_id','line_number',name='uq_costos_import_line'))

class CostIngestor:
    def __init__(self, engine: Engine, root: Path, batch_size: int = 1000):
        if batch_size < 1:
            raise ValueError('batch_size must be positive')
        self.engine, self.root, self.batch_size = engine, Path(root), batch_size
        metadata.create_all(engine, tables=[imports, rows])

    @staticmethod
    def _validate_tenant(t: Tenant):
        if any(type(x) is not int or x <= 0 for x in (t.organization_id,t.client_id,t.project_id)):
            raise ImportProblem('complete positive tenant required')

    @staticmethod
    def _scope(t: Tenant):
        return (imports.c.organization_id==t.organization_id)&(imports.c.client_id==t.client_id)&(imports.c.project_id==t.project_id)

    def _guard(self, db, t, import_id):
        self._validate_tenant(t)
        if db.execute(select(imports.c.id).where(self._scope(t),imports.c.id==import_id)).scalar_one_or_none() is None:
            raise PermissionError('import not accessible')

    def ingest_csv(self, tenant: Tenant, slot: str, stream: BinaryIO, filename: str, max_bytes: int = 50*1024*1024) -> ImportResult:
        self._validate_tenant(tenant)
        if not slot or len(slot)>80 or not slot.replace('_','').isalnum():
            raise ImportProblem('invalid slot')
        if not filename or Path(filename).name != filename or len(filename)>255 or not filename.lower().endswith('.csv'):
            raise ImportProblem('invalid filename')
        if max_bytes<=0:
            raise ImportProblem('invalid limit')
        self.root.mkdir(parents=True,exist_ok=True)
        tmp=None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root,delete=False) as out:
                tmp=Path(out.name)
                checksum=hashlib.sha256()
                count_bytes=0
                while True:
                    part=stream.read(min(1024*1024,max_bytes-count_bytes+1))
                    if not part: break
                    count_bytes+=len(part)
                    if count_bytes>max_bytes: raise ImportProblem('file exceeds limit')
                    checksum.update(part)
                    out.write(part)
            sha=checksum.hexdigest()
            with self.engine.connect() as db:
                old=db.execute(select(imports.c.id,imports.c.row_count).where(self._scope(tenant),imports.c.slot==slot,imports.c.checksum==sha)).first()
                if old: return ImportResult(old.id,old.row_count,sha)
            try:
                with tmp.open('r',encoding='utf-8-sig',errors='strict',newline='') as inp:
                    reader=csv.DictReader(inp,strict=True)
                    if not reader.fieldnames or any(not x or not x.strip() for x in reader.fieldnames) or len(reader.fieldnames)!=len(set(reader.fieldnames)):
                        raise ImportProblem('invalid or duplicate CSV headers')
                    with self.engine.begin() as db:
                        rid=db.execute(imports.insert().values(organization_id=tenant.organization_id,client_id=tenant.client_id,
                            project_id=tenant.project_id,slot=slot,checksum=sha,original_filename=filename,row_count=0)).inserted_primary_key[0]
                        total=0
                        batch=[]
                        for entry in reader:
                            if None in entry or any(v is None for v in entry.values()):
                                raise ImportProblem('malformed CSV row')
                            total+=1
                            batch.append(dict(import_id=rid,line_number=reader.line_num,payload=json.dumps(entry,ensure_ascii=False)))
                            if len(batch)>=self.batch_size:
                                db.execute(rows.insert(),batch)
                                batch=[]
                        if batch: db.execute(rows.insert(),batch)
                        db.execute(imports.update().where(imports.c.id==rid).values(row_count=total))
                        return ImportResult(rid,total,sha)
            except (UnicodeError,csv.Error) as exc:
                raise ImportProblem('invalid CSV data') from exc
        finally:
            if tmp: tmp.unlink(missing_ok=True)

    def count(self,tenant: Tenant,import_id: int) -> int:
        with self.engine.connect() as db:
            self._guard(db,tenant,import_id)
            return db.execute(select(func.count()).select_from(rows).where(rows.c.import_id==import_id)).scalar_one()

    def read_rows(self,tenant: Tenant,import_id: int,limit: int=100,offset: int=0) -> list[dict]:
        if not 1<=limit<=1000 or offset<0: raise ImportProblem('invalid pagination')
        with self.engine.connect() as db:
            self._guard(db,tenant,import_id)
            return [json.loads(x) for x in db.execute(select(rows.c.payload).where(rows.c.import_id==import_id).order_by(rows.c.id).limit(limit).offset(offset)).scalars()]

    def list_imports(self,tenant: Tenant) -> list[ImportResult]:
        self._validate_tenant(tenant)
        with self.engine.connect() as db:
            return [ImportResult(x.id,x.row_count,x.checksum) for x in db.execute(select(imports.c.id,imports.c.row_count,imports.c.checksum).where(self._scope(tenant)).order_by(imports.c.id))]
