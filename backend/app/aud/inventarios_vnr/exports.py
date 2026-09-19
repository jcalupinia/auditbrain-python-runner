"""Doce cédulas compartidas por Excel/HTML; fórmulas con valores cacheados."""
from io import BytesIO
from decimal import Decimal
from html import escape
from pathlib import Path
from base64 import b64encode
from PIL import Image
import xlsxwriter
from .engine import money
from .metadata import SHEETS,TITLES,NOTES,REFERENCES


def f(formula,value):return {'formula':formula,'value':value}
def n(value):return float(Decimal(str(value or '0')))
def cell_value(value):return value.get('value','') if isinstance(value,dict) else value


def schedules(r):
    ctx,p,tax=r['context'],r['policy'],r['tax']; rows=r['rows']; totals=r['totals']
    tables=[]
    def add(headers,values):tables.append({'name':SHEETS[len(tables)],'title':TITLES[len(tables)],'headers':headers,'rows':values,'note':NOTES[len(tables)]})
    add(['Dato','Valor'],[[k,str(v)] for k,v in ctx.items()]+[['Estado',r['status']],['Versión',r['version']],['SHA256 solicitud',r['input_sha256']]])
    add(['Parámetro','Valor'],[
        ['Marco', 'NIIF completas' if ctx['framework']=='full' else 'NIIF para las PYMES'],['Edición',ctx['edition']],['Adopción local',ctx['adoption']],['Política',p['basis']],['Revisión normativa',p['normative_reference']],['Método venta',p['selling_method']],['Gastos necesarios',n(p.get('eligible_expenses',0))],['Ventas población',n(p.get('sales_base',0))],['Porcentaje calculado',f('=IF(B11="ratio",IF(B13>0,B12/B13,0),0)',n(r['selling_ratio']))],['Sustento asignación',p.get('allocation_basis','Por unidad')],['Sustento reversión',p.get('reversal_basis','No corresponde')]]+[[x['title'],x['url']] for x in REFERENCES if x['framework'] in ('all',ctx['framework'],ctx['country'])])
    evidence=[[e.get('slot',''),e.get('name',''),e.get('sha256',''),e.get('note','')] for e in r.get('evidence',[])]
    add(['Fuente','Archivo','SHA256','Observación'],evidence or [['Manual','Datos transcritos y revisados','','Consulte referencias por ítem']])
    add(['Código','Descripción','Cantidad','Costo unitario','Costo total','Deterioro registrado','Referencia'],[[x['code'],x['description'],n(x['quantity']),n(x['unit_cost']),f(f'=ROUND(C{i}*D{i},2)',n(x['cost'])),n(x['recorded_impairment']),x['source']] for i,x in enumerate(rows,6)])
    add(['Código','Precio unitario','Referencia'],[[x['code'],n(x['selling_price']),x['source']] for x in rows])
    add(['Código','Terminación unitaria','Venta unitaria aportada','Venta unitaria aplicada'],[[x['code'],n(x['completion_cost']),n(x['selling_cost']),f(f'=IF(\'01 Criterio\'!B11="ratio",ROUND(\'04 Precios\'!B{i}*\'01 Criterio\'!B14,2),C{i})',n(x['selling_cost']))] for i,x in enumerate(rows,6)])
    vnr=[]
    for i,x in enumerate(rows,6):
        vnr.append([x['code'],f(f"='03 Inventario'!C{i}",n(x['quantity'])),f(f"='03 Inventario'!E{i}",n(x['cost'])),f(f"='04 Precios'!B{i}",n(x['selling_price'])),f(f"='05 Gastos'!B{i}+'05 Gastos'!D{i}",n(Decimal(x['completion_cost'])+Decimal(x['selling_cost']))),f(f'=MAX(0,D{i}-E{i})',n(Decimal(x['raw_nrv_unit']) if Decimal(x['raw_nrv_unit'])>0 else 0)),f(f'=ROUND(B{i}*F{i},2)',n(x['nrv'])),f(f'=MAX(0,C{i}-G{i})',n(x['impairment'])),f(f"='03 Inventario'!F{i}",n(x['recorded_impairment'])),f(f'=H{i}-I{i}',n(x['adjustment'])),f(f'=C{i}-H{i}',n(x['carrying']))])
    last=5+len(rows)
    totalrow=last+1
    vnr.append(['TOTAL','']+[f(f'=SUM({c}6:{c}{last})',n(totals[k])) if k else '' for c,k in [('C','cost'),('D',None),('E',None),('F',None),('G','nrv'),('H','impairment'),('I','recorded_impairment'),('J','adjustment'),('K','carrying')]])
    add(['Código','Cantidad','Costo total','Precio unitario','Costos unitarios','VNR unitario','VNR total','Deterioro requerido','Registrado','Ajuste','Valor contable final'],vnr)
    add(['Concepto','Población','Mayor','Diferencia','Tolerancia','Estado'],[
        ['Costo bruto',f(f"='06 VNR'!C{totalrow}",n(totals['cost'])),n(r['ledger_cost']),f('=ROUND(B6-C6,2)',n(r['controls']['cost_difference'])),n(r['tolerance']),f('=IF(ABS(D6)<=E6,"Conciliado","Diferencia")','Conciliado' if abs(Decimal(r['controls']['cost_difference']))<=Decimal(r['tolerance']) else 'Diferencia')],
        ['Deterioro registrado',f(f"='06 VNR'!I{totalrow}",n(totals['recorded_impairment'])),n(r['ledger_impairment']),f('=ROUND(B7-C7,2)',n(r['controls']['impairment_difference'])),n(r['tolerance']),f('=IF(ABS(D7)<=E7,"Conciliado","Diferencia")','Conciliado' if abs(Decimal(r['controls']['impairment_difference']))<=Decimal(r['tolerance']) else 'Diferencia')]])
    adjustments=[]
    for i,x in enumerate(rows,6):
        adjustments.append([x['code'],f(f"='06 VNR'!J{i}",n(x['adjustment'])),f(f'=MAX(0,B{i})',n(x['expense'])),f(f'=MAX(0,-B{i})',n(x['reversal'])),f(f'=IF(B{i}<0,"Reversión: débito deterioro / crédito resultado",IF(B{i}>0,"Débito gasto / crédito deterioro","Sin ajuste"))','Reversión: débito deterioro / crédito resultado' if n(x['adjustment'])<0 else 'Débito gasto / crédito deterioro' if n(x['adjustment'])>0 else 'Sin ajuste')])
    add(['Código','Ajuste neto','Gasto adicional','Reversión','Asiento propuesto, sujeto a revisión'],adjustments)
    deferred=[]
    if tax.get('enabled'):
        for i,x in enumerate(rows,6):
            base=Decimal(x['tax_base']);carrying=Decimal(x['carrying'])
            deferred.append([x['code'],f(f"='06 VNR'!K{i}",n(carrying)),n(base),f(f'=MAX(0,C{i}-B{i})',n(max(0,base-carrying))),f(f'=MAX(0,B{i}-C{i})',n(max(0,carrying-base))),f(f'=IF($Q$7=1,ROUND(D{i}*$Q$6,2),0)',n(x['dta'])),f(f'=ROUND(E{i}*$Q$6,2)',n(x['dtl']))])
        deferred.extend([['TOTAL','','','','',f(f'=SUM(F6:F{last})',n(totals['dta'])),f(f'=SUM(G6:G{last})',n(totals['dtl']))],['SALDO REGISTRADO','','','','',f('=$Q$8',n(tax['recorded_dta'])),f('=$Q$9',n(tax['recorded_dtl']))],['AJUSTE PROPUESTO','','','','',f(f'=F{totalrow}-F{totalrow+1}',n(totals['dta_adjustment'])),f(f'=G{totalrow}-G{totalrow+1}',n(totals['dtl_adjustment']))]])
    else:deferred=[['No calculado: evaluación tributaria no habilitada','','','','','','']]
    add(['Código','Valor contable','Base fiscal','Diferencia deducible','Diferencia imponible','Activo diferido','Pasivo diferido'],deferred)
    add(['Aspecto','Resultado'],[['Conclusión','Pendiente de revisión profesional'],['Población',len(rows)],['Ajuste neto propuesto',f(f"='06 VNR'!J{totalrow}",n(totals['adjustment']))],['Conciliación','Conciliada' if r['controls']['reconciled'] else 'Diferencias pendientes'],['Procedimientos','Inspección de precios, costos necesarios, políticas, saldos y hechos posteriores; evaluar evidencia y riesgos según NIA.'],['Excepciones','Ítems con ajuste/reversión se detallan en 08 Ajustes; las diferencias se detallan en 07 Conciliacion.']])
    add(['Control','Estado'],[['Preparado por',ctx['preparer']],['Revisado por',ctx['reviewer']],['Normativa y política','Declarada revisada por el usuario'],['Evidencia','Declarada revisada por el usuario'],['Aprobación profesional','PENDIENTE — nombres declarados no son firmas'],['Conclusión del revisor','Completar en papeles de trabajo'],['Trazabilidad',r['input_sha256']]])
    return tables


def logo_path(r):
    name='logo_partner_auditing.png' if r['context']['firm']=='partner_auditing' else 'logo_audit_consulting.png'
    return Path(__file__).parent/'assets'/name


def build_xlsx(r):
    buf=BytesIO();wb=xlsxwriter.Workbook(buf,{'in_memory':True,'strings_to_formulas':False,'strings_to_urls':False})
    wb.set_properties({'title':'VNR · '+r['context']['client'],'author':r['context']['firm'],'comments':'AuditBrain VNR '+r['version']})
    title=wb.add_format({'bold':True,'font_size':18,'font_color':'#FFFFFF','bg_color':'#102D4D','valign':'vcenter'})
    header=wb.add_format({'bold':True,'font_color':'#FFFFFF','bg_color':'#217A55','border':1,'text_wrap':True})
    text=wb.add_format({'font_name':'Calibri','font_size':10,'border':1,'border_color':'#D9E3E9','valign':'top','text_wrap':True})
    numeric=wb.add_format({'font_name':'Calibri','font_size':10,'border':1,'border_color':'#D9E3E9','num_format':'#,##0.00;[Red](#,##0.00)','valign':'top'})
    formula=wb.add_format({'font_name':'Calibri','font_size':10,'border':1,'border_color':'#D9E3E9','bg_color':'#EAF6EF','num_format':'#,##0.00;[Red](#,##0.00)','text_wrap':True})
    note=wb.add_format({'font_size':10,'font_color':'#435766','text_wrap':True,'valign':'top'})
    for table in schedules(r):
        ws=wb.add_worksheet(table['name']); width=max(2,len(table['headers']))
        ws.hide_gridlines(2);ws.set_tab_color('#217A55');ws.set_landscape();ws.set_paper(9);ws.fit_to_pages(1,0);ws.repeat_rows(0,4);ws.freeze_panes(5,1)
        ws.set_column(0,width-1,19);ws.set_column(0,0,26)
        if width==2:ws.set_column(1,1,92)
        ws.merge_range(0,0,0,width-1,table['title'],title);ws.set_row(0,30)
        firm='Partner Auditing Cía. Ltda.' if r['context']['firm']=='partner_auditing' else 'AuditConsulting Auditores Cía. Ltda.'
        ws.merge_range(1,0,1,width-1,firm+' · '+r['context']['client'],note)
        ws.merge_range(2,0,2,width-1,f"{r['context']['cutoff']} · {r['context']['currency']} · {r['status']}",note)
        if table['name']=='00 Portada':
            logo=logo_path(r)
            with Image.open(logo) as im: scale=min(180/im.width,55/im.height)
            ws.set_row(3,48)
            ws.insert_image(3,0,str(logo),{'x_scale':scale,'y_scale':scale,'object_position':1,'description':firm})
        ws.write_row(4,0,table['headers'],header);ws.set_row(4,32)
        for row_idx,row in enumerate(table['rows'],5):
            ws.set_row(row_idx,30)
            for col,v in enumerate(row):
                if isinstance(v,dict):ws.write_formula(row_idx,col,v['formula'],formula,v['value'])
                elif isinstance(v,(int,float)):ws.write_number(row_idx,col,v,numeric)
                else:ws.write_string(row_idx,col,str(v),text)
        end=5+len(table['rows']);ws.autofilter(4,0,max(5,end-1),width-1)
        ws.merge_range(end+2,0,end+4,width-1,'CÓMO SE CALCULA / PROCEDIMIENTO: '+table['note'],note)
        ws.set_footer('&L'+firm+'&R&P / &N')
        if table['name']=='09 Diferido' and r['tax'].get('enabled'):
            for idx,(label,value) in enumerate([('Tasa',n(r['tax']['rate'])),('Reconocer activo',int(r['tax'].get('recognize_dta') is True)),('Activo registrado',n(r['tax']['recorded_dta'])),('Pasivo registrado',n(r['tax']['recorded_dtl']))],5):
                ws.write_string(idx,15,label,text);ws.write_number(idx,16,value,numeric)
            ws.write_string(10,15,'Base normativa',text);ws.write_string(10,16,r['tax']['reference'],text)
            ws.write_string(11,15,'Recuperabilidad',text);ws.write_string(11,16,r['tax'].get('recoverability','No reconocida'),text)
            ws.set_column(15,15,25);ws.set_column(16,16,40);ws.print_area(0,0,end+5,16)
        else:ws.print_area(0,0,end+5,width-1)
    wb.close();return buf.getvalue()


def build_html(r):
    esc=lambda v:escape(str(v),quote=True)
    sections=[];nav=[]
    logo=b64encode(logo_path(r).read_bytes()).decode('ascii')
    for i,table in enumerate(schedules(r)):
        nav.append(f'<a href="#s{i}">{i+1:02d} {esc(table["title"])}</a>')
        body=''.join('<tr>'+''.join('<td>'+esc(cell_value(v))+(f'<details><summary>Fórmula auditable</summary><code>{esc(v["formula"])}</code></details>' if isinstance(v,dict) else '')+'</td>' for v in row)+'</tr>' for row in table['rows'])
        sections.append(f'<section id="s{i}"><h2>{esc(table["title"])}</h2><div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in table['headers'])+'</tr></thead><tbody>'+body+'</tbody></table></div><p><b>Cómo se calcula / procedimiento:</b> '+esc(table['note'])+'</p></section>')
    if r['tax'].get('enabled'):sections[9]+=f'<section><h3>Parámetros de diferidos</h3><pre>{esc(str(r["tax"]))}</pre></section>'
    return '<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>AuditBrain · VNR</title><style>body{margin:0;background:#0d2037;color:#eef5fb;font:15px/1.6 Arial}header,main{max-width:1250px;margin:auto;padding:24px}header{border-bottom:1px solid #2c4765}h1,h2{color:#75e49c}nav{display:flex;gap:10px;flex-wrap:wrap}a{color:#75e49c}section{margin:22px 0;padding:22px;background:#142d4b;border:1px solid #2c4765;border-radius:12px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%}th,td{border:1px solid #38516c;padding:10px;text-align:left;vertical-align:top}th{background:#17563f}td,pre{white-space:pre-wrap;overflow-wrap:anywhere}code{font-size:12px}details{margin-top:8px}@media print{body,section{background:white;color:black}h1,h2,a{color:#17563f}nav{display:none}section{break-before:page}.scroll{overflow:visible}}</style><header><img alt="Firma auditora" style="max-width:180px;max-height:75px" src="data:image/png;base64,'+logo+'"><h1>Valor neto de realización</h1><p>'+esc(r['context']['client'])+' · '+esc(r['context']['cutoff'])+' · '+esc(r['context']['currency'])+'</p><p>Borrador para revisión · Documento de consulta; recalcule en Excel o en Command Center.</p><nav>'+''.join(nav)+'</nav></header><main>'+''.join(sections)+'</main></html>'
