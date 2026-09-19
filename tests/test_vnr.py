import copy
import unittest
from backend.app.aud.inventarios_vnr.engine import calculate


def payload():
    return {
        'context': {'client':'Empresa de prueba', 'country':'Ecuador','currency':'USD','year':2026,'cutoff':'2026-09-30','visit':'Preliminar','preparer':'Preparador','reviewer':'Revisor','firm':'audit_consulting','framework':'full','edition':'2026','adoption':'Aplicación local revisada','reuse_scope':'one'},
        'policy': {'basis':'Inventario ordinario, ítems individualmente','reviewed':True,'selling_method':'unit','normative_reference':'NIC 2.9, 28-34','evidence_reviewed':True},
        'rows': [{'code':'A','description':'Artículo A','quantity':'10','unit_cost':'20','selling_price':'18','completion_cost':'1','selling_cost':'2','recorded_impairment':'5','source':'Inventario fila 2 / precios fila 2'}],
        'ledger_cost':'200', 'ledger_impairment':'5', 'tolerance':'0.01',
        'tax': {'enabled':False}
    }


class VnrTests(unittest.TestCase):
    def test_manual_calculation(self):
        r=calculate(payload())
        self.assertEqual(r['rows'][0]['nrv_unit'],'15.00')
        self.assertEqual(r['totals']['impairment'],'50.00')
        self.assertEqual(r['totals']['adjustment'],'45.00')
    def test_reversal_requires_basis_and_is_limited(self):
        p=payload();p['rows'][0]['selling_price']='40'
        with self.assertRaises(ValueError): calculate(p)
        p['policy']['reversal_basis']='Mejora de precios sustentada en ventas posteriores'
        r=calculate(p);self.assertEqual(r['totals']['reversal'],'5.00')
    def test_negative_nrv_cannot_make_inventory_negative(self):
        p=payload();p['rows'][0]['selling_cost']='30'
        self.assertEqual(calculate(p)['totals']['impairment'],'200.00')
    def test_duplicate_missing_nonfinite_rejected(self):
        for field,value in [('selling_price',None),('quantity','NaN'),('unit_cost','-2')]:
            p=payload();p['rows'][0][field]=value
            with self.assertRaises(ValueError):calculate(p)
        p=payload();p['rows']*=2
        with self.assertRaises(ValueError):calculate(p)
    def test_framework_and_evidence_not_implicit(self):
        p=payload();p['context']['framework']=''
        with self.assertRaises(ValueError):calculate(p)
        p=payload();p['policy']['evidence_reviewed']=False
        with self.assertRaises(ValueError):calculate(p)
    def test_ratio_sales_allocation(self):
        p=payload();p['policy'].update(selling_method='ratio',eligible_expenses='100',sales_base='1000',allocation_basis='Gastos necesarios de la misma población')
        r=calculate(p);self.assertEqual(r['rows'][0]['selling_cost'],'1.80');self.assertEqual(r['totals']['impairment'],'48.00')
    def test_tax_explicit_recognition(self):
        p=payload();p['rows'][0]['tax_base']='200';p['tax']={'enabled':True,'rate':'0.25','reference':'Norma fiscal verificada para el caso','recoverability':'Proyección de utilidades fiscales revisada','recognize_dta':True,'recorded_dta':'3','recorded_dtl':'0'}
        r=calculate(p);self.assertEqual(r['totals']['dta'],'12.50');self.assertEqual(r['totals']['dta_adjustment'],'9.50')
        p['tax']['reference']=''
        with self.assertRaises(ValueError):calculate(p)
    def test_decimal_and_regional_number(self):
        p=payload();p['rows'][0].update(quantity='3',unit_cost='0,10',selling_price='0,09',completion_cost='0',selling_cost='0',recorded_impairment='0');p['ledger_cost']='0.30';p['ledger_impairment']='0'
        self.assertEqual(calculate(p)['totals']['impairment'],'0.03')
    def test_ledger_difference_disclosed(self):
        p=payload();p['ledger_cost']='201'
        self.assertEqual(calculate(p)['controls']['cost_difference'],'-1.00')
        self.assertFalse(calculate(p)['controls']['reconciled'])

if __name__=='__main__':unittest.main()

class RegionalRegressionTests(unittest.TestCase):
    def test_ambiguous_and_bad_grouping_are_rejected(self):
        for value in ['1,234','1,2.34','1.2,34']:
            from backend.app.aud.inventarios_vnr.engine import number
            with self.assertRaises(ValueError):number(value,'importe')
    def test_regional_policy_values_are_canonical_for_exports(self):
        p=payload();p['policy'].update(selling_method='ratio',eligible_expenses='100,50',sales_base='1.000,00',allocation_basis='Misma población')
        r=calculate(p)
        self.assertEqual(r['policy']['eligible_expenses'],'100.50')
