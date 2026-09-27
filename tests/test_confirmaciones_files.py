import unittest
from io import BytesIO

from backend.app.aud.confirmaciones_saldos.parsers import extract


class ParsersTests(unittest.TestCase):
    def test_csv_sample(self):
        csv = ('id,tipo,entidad,correo,saldo\n'
               'C-01,cuentas_por_cobrar,Distribuidora Sur,pagos@dsur.ec,48200.00\n'
               'P-01,proveedores,Importadora Global,cxp@global.com,\n')
        r = extract('muestra.csv', csv.encode('utf-8'))
        self.assertEqual(len(r['tables']), 1)
        self.assertEqual(r['tables'][0]['headers'][0], 'id')
        self.assertEqual(len(r['tables'][0]['rows']), 2)
        self.assertEqual(r['tables'][0]['rows'][0][2], 'Distribuidora Sur')

    def test_xlsx_sample(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['id', 'tipo', 'entidad', 'correo'])
        ws.append(['B-01', 'bancos', 'Banco Pichincha', 'confirma@pichincha.com'])
        buf = BytesIO(); wb.save(buf)
        r = extract('muestra.xlsx', buf.getvalue())
        self.assertTrue(r['tables'])
        self.assertEqual(r['tables'][0]['rows'][0][1], 'bancos')
        self.assertEqual(len(r['sha256']), 64)

    def test_rejects_empty_and_oversize(self):
        with self.assertRaises(ValueError):
            extract('x.csv', b'')
        with self.assertRaises(ValueError):
            extract('x.bin', b'data')   # extensión no admitida

    def test_txt_supporting_text(self):
        r = extract('nota.txt', 'Contacto adicional del banco.'.encode('utf-8'))
        self.assertIn('Contacto adicional', r['text'])


if __name__ == '__main__':
    unittest.main()
