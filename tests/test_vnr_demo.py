"""Shared browser demo fixture must agree with the production Decimal engine."""
import json
import unittest
from pathlib import Path
from tests.test_vnr import payload
from backend.app.aud.inventarios_vnr.engine import calculate

class DemoTests(unittest.TestCase):
    def test_guided_case_matches_expected_values_for_both_frameworks(self):
        d=json.loads((Path(__file__).resolve().parents[1]/'frontend/src/aud/vnr/demoCase.json').read_text())
        rows=[]
        for i,values in enumerate(d['inventory']['rows']):
            row=dict(zip(d['inventory']['headers'],values))
            for slot in ['prices','expenses']:row.update(dict(zip(d[slot]['headers'],d[slot]['rows'][i])))
            row['source']='DEMO / fuentes sintéticas';rows.append(row)
        for framework in ['full','sme']:
            p=payload();p['rows']=rows;p.update(d['ledger']);p['context'].update(framework=framework,edition='2015' if framework=='sme' else '2026');p['policy']['reversal_basis']='Supuesto didáctico: recuperación sustentada de DEMO-B'
            r=calculate(p)
            for key,value in d['expected'].items():self.assertEqual(r['totals'][key],value)
            self.assertTrue(r['controls']['reconciled'])
