from unittest import TestCase
from unittest.mock import patch
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app.aud.inventarios_vnr.router import router, access
from backend.app.auth.deps import require_staff
from backend.app.db.session import get_db
from tests.test_vnr import payload

class RouterTests(TestCase):
    def setUp(self):
        self.app=FastAPI();self.app.include_router(router);self.client=TestClient(self.app)
    def test_auth_required(self):
        self.assertEqual(self.client.post('/aud/inventarios-vnr/1/process',json=payload()).status_code,401)
    def test_project_denied_before_process(self):
        class DB:
            def get(self,*a):return SimpleNamespace(is_active=True)
        self.app.dependency_overrides[require_staff]=lambda:SimpleNamespace(id=1)
        self.app.dependency_overrides[get_db]=lambda:DB()
        with patch('backend.app.aud.inventarios_vnr.router.user_can_access_project',return_value=False):
            for suffix in ('process','download?format=xlsx','extract?filename=x.csv'):
                self.assertEqual(self.client.post('/aud/inventarios-vnr/9/'+suffix,json=payload()).status_code,403)
    def test_process_download_same_result(self):
        self.app.dependency_overrides[access]=lambda:(None,None,None)
        r=self.client.post('/aud/inventarios-vnr/1/process',json=payload())
        self.assertEqual(r.status_code,200);self.assertEqual(r.json()['totals']['adjustment'],'45.00')
        self.assertEqual(len(r.json()['schedules']),12)
        r=self.client.post('/aud/inventarios-vnr/1/download?format=xlsx',json=payload())
        self.assertEqual(r.status_code,200);self.assertEqual(r.headers['cache-control'],'no-store')
    def test_invalid_and_large_body(self):
        self.app.dependency_overrides[access]=lambda:(None,None,None)
        self.assertEqual(self.client.post('/aud/inventarios-vnr/1/process',content='bad').status_code,400)
        self.assertEqual(self.client.post('/aud/inventarios-vnr/1/extract?filename=x.csv',content=b'x'*(8*1024*1024+1)).status_code,413)
