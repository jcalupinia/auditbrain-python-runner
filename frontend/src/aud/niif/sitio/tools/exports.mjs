import {PORTABLE_ENGINE_SOURCE} from './portable-engine.mjs';
import {calculationNotes} from './explanations.mjs';
import {zipSync,strToU8} from 'fflate';
import {sheetXml,styles,labels} from './workbook-presentation.mjs';
import {renderHtml} from './html-presentation.mjs';
import {auditLogoBase64} from './brand.mjs';
import {catalog,SHEETS,ENGINE_VERSION,MAX_ROWS,decimal,rounded,formatted,validDate,validateDefinition,validateRows,checkBuckets,calculate,seriesKeys} from './domain.mjs';
const esc=s=>String(s??'').replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g,'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const col=i=>{let s='';for(i++;i>0;i=Math.floor((i-1)/26))s=String.fromCharCode(65+(i-1)%26)+s;return s;};
const formula=(f,v='',type='auto')=>({f,v,type});
const numeric=v=>({n:String(v)});
const serial=d=>Math.round((Date.parse(d)-Date.UTC(1899,11,30))/86400000);
export {SHEETS};
// Cedulas que otras hojas referencian por formula: la portada lee 05 y 07, los
// calculos leen 03, 05 y 06. Omitir cualquiera de ellas rompe el libro, asi que
// el plan siempre las conserva. Las otras siete no tienen referencias entrantes.
const CORE=[0,2,4,5,6];
const CUADRO=SHEETS.indexOf('13_Cuadro');
/**
 * Indices de las cedulas que lleva esta herramienta. Sin `sheets`, todas.
 * El cuadro de periodos es la excepcion, en los dos caminos: esta si y solo si
 * la herramienta tiene serie. Sin serie no hay cuadro que ensenar; con serie el
 * motor lo calcula igual, y omitirlo seria volver a esconderlo, asi que se
 * conserva como el nucleo aunque la definicion no lo declare.
 */
export function sheetPlan(d){
 const serie=!!d?.series,pick=d?.sheets;
 if(!Array.isArray(pick)||!pick.length)return SHEETS.map((_,i)=>i).filter(i=>i!==CUADRO||serie);
 const keep=new Set(serie?[...CORE,CUADRO]:CORE);
 for(const x of pick){const i=SHEETS.indexOf(String(x));if(i<0)throw Error(`Cedula desconocida: ${x}. Use los nombres de SHEETS.`);if(i!==CUADRO||serie)keep.add(i);}
 return [...keep].sort((a,b)=>a-b);
}
export const sheetNames=d=>sheetPlan(d).map(i=>SHEETS[i]);
export const sheetLabels=d=>sheetPlan(d).map(i=>labels[i]);
export function workbookSheets(t,template=false){
 if(template)t={...t,run:null,rows:[],validation:null,reconciliation:{ledger:'0',tolerance:t.reconciliation?.tolerance||'0',difference:'0',within:true,acceptance:''}};
 const d=t.definition,run=t.run||{rows:[],totals:{},exceptions:[]},data=template?Array.from({length:20},()=>({})):t.rows||[],e=t.engagement||{},s=[];
 const plan=sheetPlan(d);
 const intro=(title,headers)=>[[title],[`${e.client||'Cliente pendiente'} · Corte ${e.cutoff||'Pendiente'} · ${e.firm||'Audit Consulting Group'} · Ref. ${d.id.toUpperCase()} · v${t.version} · Preparó: ${e.preparer||'Pendiente'} · Revisó: ${e.reviewer||'Pendiente'}`],[t.demo?'DEMOSTRACIÓN — DATOS FICTICIOS — NO ES UN PAPEL APROBADO':template?'PLANTILLA REUTILIZABLE — sin resultados aprobados':t.draft?'BORRADOR — PENDIENTE DE REVISIÓN — FUENTES NO VERIFICADAS':'COPIA DEL PAPEL APROBADO — los cambios locales requieren una nueva revisión'],headers];
 const primaryCol=col((d.id==='pce'?3:1)+d.rules.findIndex(r=>r.key===d.primary));
 s[0]=[
 ['AuditBrain · AUDITORÍA EXTERNA'],[e.firm||'Audit Consulting Group'],[`${e.client||'Cliente pendiente'} · ${d.area} · ${e.year||''}`],[d.name],
 ['REGISTROS','','RESULTADO PRINCIPAL','','VERSIÓN'],
 [formula(`COUNTIF('05_Data_Original'!A5:A${data.length+4},"<>")`,template?'0':String(data.length)),'',formula(`SUM('07_Calculos'!${primaryCol}5:${primaryCol}${data.length+4})`,template?'0':run.totals[d.primary]||'0'),'',numeric(t.version)],[],
 ['DATOS DEL ENCARGO'],
 ['Cliente','',e.client||'Pendiente'],['Período / corte','',`${e.year||''} · ${e.cutoff||'Pendiente'}`],['Preparado por','',e.preparer||'Pendiente'],['Revisado por','',e.reviewer||'Pendiente'],['Marco / país','',`${e.framework||'Pendiente'} · ${t.country||'Pendiente'}`],['Estado del archivo','',template?'PLANTILLA · pendiente de datos y revisión':`${t.state||'BORRADOR'} · ${t.approvedBy||'Pendiente de aprobación'}`],[],
 ['ÍNDICE DE CÉDULAS · pulse un nombre para abrir'],
 ...plan.slice(1).map((sheet,i)=>[labels[sheet],'','','','',String(i+2).padStart(2,'0')]),[],
 ['Entradas en verde claro · Fórmulas visibles · Diferencias resaltadas en ámbar'],
 [t.demo?'DEMOSTRACIÓN — DATOS FICTICIOS. Sin aprobación ni conclusión de auditoría.':template?'Plantilla reutilizable: complete datos, recalcule y obtenga revisión profesional.':t.draft?'Borrador generado desde ChatGPT. Fuentes y conclusión pendientes de revisión profesional.':'Copia aprobada. Todo cambio local exige recálculo y nueva revisión; conserve el original.']
 ];
 s[1]=intro('Programa de auditoría',['Código','Objetivo','Riesgo','Afirmación','Procedimiento','Evidencia','Criterio','Norma / fuente','Estado']);for(const p of t.program||[])s[1].push([p.code,p.objective,p.risk,p.assertion,p.procedure,p.evidence,p.criterion,p.source?.document,p.state]);
 s[2]=intro('Parámetros y reglas',['Parámetro','Valor','Sustento / unidad']);s[2].push(['Fecha de corte',{n:serial(e.cutoff||'2000-01-01'),date:true},'Fecha del encargo'],['Tolerancia',numeric(t.reconciliation?.tolerance||'0'),'Aceptada por auditor'],['Saldo contable',numeric(t.reconciliation?.ledger||'0'),'Saldo de control'],['Motor',ENGINE_VERSION,'Decimal, redondeo por partida']);
 const constants={};for(const r of d.rules)for(const a of [r.a,r.b])if(a.startsWith('#')&&!constants[a]){constants[a]=s[2].length+1;s[2].push([`Constante ${a}`,numeric(a.slice(1)),'Constante de metodología']);}
 const bucketStart=s[2].length+2;s[2].push(['Mora desde','Mora hasta','Tasa (0 a 1)']);for(const b of t.parameters?.buckets||[])s[2].push([numeric(b.min),b.max===null?'Sin límite':numeric(b.max),numeric(b.rate)]);
 s[2].push([],['Código','Operación','Operando A','Operando B','Decimales']);for(const r of d.rules)s[2].push([r.key,r.op,r.a,r.b,numeric(r.precision)]);
 s[3]=intro('Fuentes y normativa',['Categoría','Organismo','Documento','Artículo / párrafo','Fecha / vigencia','URL','Procedimientos','Verificada']);for(const x of t.sources||[])s[3].push([x.category,x.organization,x.document,x.section,x.date,x.url,(x.procedures||[]).join(', '),x.verified?'Sí':'Pendiente']);
 s[4]=intro('Datos originales mapeados',['Identificador',...d.fields.slice(1).map(f=>f.label),'Archivo','Hoja','Fila origen']);
 s[5]=intro('Datos procesados',d.fields.map(f=>f.label));
 s[6]=intro('Cálculos auditables',['Identificador',...(d.id==='pce'?['Días de mora','Tasa']:[]),...d.rules.map(r=>r.label)]);
 const ruleOffset=d.id==='pce'?3:1;
 data.forEach((row,i)=>{const n=i+5;const isEmpty=Object.keys(row).length===0;const processed=[];
 s[4].push([...d.fields.map(f=>{const v=row[f.key];return v===undefined?'':f.type==='number'?numeric(v):f.type==='date'?{n:serial(v),date:true}:v;}),row._file||'',row._sheet||'',row._row?numeric(row._row):'']);
 d.fields.forEach((f,j)=>processed.push(formula(`IF('05_Data_Original'!${col(j)}${n}="","",'05_Data_Original'!${col(j)}${n})`,isEmpty?'':f.type==='date'?serial(row[f.key]):row[f.key],f.type==='text'?'text':f.type==='date'?'date':'auto')));s[5].push(processed);
 const line=[formula(`IF('06_Data_Procesada'!A${n}="","",'06_Data_Procesada'!A${n})`,row.id||'','text')];
 if(d.id==='pce'){const due=col(d.fields.findIndex(f=>f.key==='due_date'));line.push(formula(`IF(A${n}="","",MAX(0,'03_Parametros'!$B$5-'06_Data_Procesada'!${due}${n}))`,run.rows[i]?.days||''));let rate='NA()';for(let k=(t.parameters?.buckets||[]).length-1;k>=0;k--){const br=bucketStart+k;rate=`IF(AND(B${n}>='03_Parametros'!$A$${br},${t.parameters.buckets[k].max===null?'TRUE':`B${n}<='03_Parametros'!$B$${br}`}),'03_Parametros'!$C$${br},${rate})`;}line.push(formula(`IF(A${n}="","",${rate})`,run.rows[i]?.rate||''));}
 const ref=a=>a.startsWith('#')?`'03_Parametros'!$B$${constants[a]}`:a==='rate'&&d.id==='pce'?`C${n}`:d.fields.some(f=>f.key===a)?`'06_Data_Procesada'!${col(d.fields.findIndex(f=>f.key===a))}${n}`:`${col(ruleOffset+d.rules.findIndex(r=>r.key===a))}${n}`;
 d.rules.forEach(r=>{const a=ref(r.a),b=ref(r.b);const exp={add:`${a}+${b}`,subtract:`${a}-${b}`,multiply:`${a}*${b}`,divide:`${a}/${b}`,min:`MIN(${a},${b})`,max:`MAX(${a},${b})`}[r.op];line.push(formula(`IF(COUNTA('05_Data_Original'!A${n}:${col(d.fields.length-1)}${n})=0,"",IF(COUNTA('05_Data_Original'!A${n}:${col(d.fields.length-1)}${n})<${d.fields.length},NA(),ROUND(ROUND(${exp},6),${r.precision})))`,template?'':run.rows[i]?.[r.key]??''));});s[6].push(line);
 });
 s[7]=intro('Controles y conciliaciones',['Control','Resultado','Criterio / evidencia']);s[7].push(['Registros',numeric(template?0:data.length),'Población conservada'],['Saldo contable',formula("'03_Parametros'!B7",t.reconciliation?.ledger||'0'),'Saldo del mayor']);
 const controlField=d.fields.findIndex(f=>f.key===d.control),controlColumn=controlField>=0?col(controlField):col(ruleOffset+d.rules.findIndex(r=>r.key===d.control));const controlSheet=controlField>=0?'06_Data_Procesada':'07_Calculos';
 s[7].push(['Población',formula(`ROUND(SUM('${controlSheet}'!${controlColumn}5:${controlColumn}${data.length+4}),2)`,run.totals[d.control]||'0'),'Suma del campo de conciliación'],['Diferencia',formula('B7-B6',t.reconciliation?.difference||'0'),'Población menos saldo contable'],['Resultado',formula('IF(ABS(B8)<=\'03_Parametros\'!B6,"CONFORME","REVISAR")',t.reconciliation?.within?'CONFORME':'REVISAR'),'Revisar diferencias fuera de tolerancia'],['Aceptación documentada',t.reconciliation?.acceptance||'No aplica','No sustituye corrección de errores'],['Validación',t.validation?.ok?'Conforme':'Pendiente',`${t.validation?.errors?.length||0} errores; ${t.validation?.warnings?.length||0} advertencias`]);
 s[8]=intro('Excepciones',['Fila','Identificador','Código','Observación','Importe']);for(const x of template?[]:run.exceptions||[])s[8].push([numeric(x.row),x.id,x.code,x.message,numeric(x.amount)]);
 s[9]=intro('Sumaria',['Resultado','Importe']);for(const r of d.rules.filter(r=>r.precision===2)){const c=col(ruleOffset+d.rules.findIndex(x=>x.key===r.key));s[9].push([r.label,formula(`SUM('07_Calculos'!${c}5:${c}${data.length+4})`,template?'0':run.totals[r.key]||'0')]);}
 s[10]=intro('Conclusión',['Sección','Contenido']);s[10].push(['Análisis',template?'Pendiente de ejecución':t.analysis||'PENDIENTE'],['Evaluación de excepciones',template?'PENDIENTE':t.exceptionReview||'No aplica'],['Conclusión del auditor',template?'PENDIENTE':t.conclusion||'PENDIENTE'],['Revisada',template?'No':t.conclusionReviewed?'Sí':'No']);
 s[11]=intro('Control de revisión',['Tipo','Usuario','Fecha','Estado anterior','Estado nuevo','Comentario / respuesta','Versión']);for(const x of t.events||[])s[11].push([x.action,x.actor,x.at,x.previous,x.next,x.comment||'',numeric(x.version||t.version)]);for(const x of t.notes||[])s[11].push(['Punto '+x.id,x.createdBy,x.createdAt,x.section,x.status,x.comment+' / '+x.response,numeric(t.version)]);
 // 13 · El cuadro que el motor ya calculaba y nadie leia. Ancho: una fila por
 // periodo y una columna por concepto, en el orden en que la serie los calcula
 // —asi se lee un cuadro de amortizacion, no en formato largo—. Los contratos
 // llegan concatenados en `schedule`: el identificador se repite en cada fila
 // (para filtrar uno solo) y una fila en blanco separa un contrato del siguiente.
 if(d.series){
  const claves=seriesKeys(d),etiquetas=[...(d.series.backward||[]),...(d.series.forward||[])];
  s[12]=intro('Cuadro de períodos',['Identificador','Período','Períodos',...claves.map(k=>etiquetas.find(x=>x.key===k)?.label||k)]);
  let anterior=null;
  for(const f of run.schedule||[]){
   if(anterior!==null&&f.id!==anterior)s[12].push([]);
   anterior=f.id;
   s[12].push([f.id,numeric(f.periodo),numeric(f.periodos),...claves.map(k=>numeric(f[k]))]);
  }
 }
 for(const rows of [s[1],s[3],s[10],s[11]]){for(let i=4;i<rows.length;i++){const r=rows[i];if(r.some(v=>typeof v==='string'&&v.length>500)){const count=Math.max(...r.map(v=>typeof v==='string'?Math.ceil(v.length/500):1));rows.splice(i,1,...Array.from({length:count},(_,k)=>r.map((v,j)=>typeof v==='string'?(v.length>500?v.slice(k*500,(k+1)*500):k===0?v:''):k===0?v:'')));i+=count-1;}}}
 s[2].push([],['CONTEXTO METODOLÓGICO','Valor']);for(const [key,label]of Object.entries({framework:'Marco contable',edition:'Edición',adoption:'Adopción local',visit:'Visita',currency:'Moneda',reuseScope:'Alcance de reutilización'}))s[2].push([label,e[key]||'Por confirmar']);s[2].push(['Versión de memoria',t.methodologyVersion||'No registrada'],['Revisión de evidencia',t.evidenceReview?.text||'Pendiente']);
 const notes=calculationNotes(t);s.forEach((rows,i)=>rows.push([],['CÓMO SE PREPARA Y CALCULA'],[notes[i]]));
 return plan.map(i=>s[i]);
}
export function buildWorkbook(t,template=false){
 const sheets=workbookSheets(t,template),plan=sheetPlan(t.definition),names=plan.map(i=>SHEETS[i]),lab=plan.map(i=>labels[i]),z={};const hasLogo=!t.engagement?.firm||/audit.*consult/i.test(t.engagement.firm);const put=(n,s)=>z[n]=strToU8(s);
 put('[Content_Types].xml',`<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>${hasLogo?'<Default Extension="png" ContentType="image/png"/><Override PartName="/xl/drawings/drawing1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>':''}<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>${sheets.map((_,i)=>`<Override PartName="/xl/worksheets/sheet${i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('')}</Types>`);
 put('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>');
 put('xl/workbook.xml',`<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${names.map((n,i)=>`<sheet name="${n}" sheetId="${i+1}" r:id="rId${i+1}"/>`).join('')}</sheets><definedNames>${names.map((n,i)=>`<definedName name="_xlnm.Print_Area" localSheetId="${i}">&apos;${n}&apos;!$A$1:$${col(i===0?5:Math.max(2,...sheets[i].map(r=>r.length))-1)}$${sheets[i].length}</definedName>${i===0?'':`<definedName name="_xlnm.Print_Titles" localSheetId="${i}">&apos;${n}&apos;!$1:$4</definedName>`}`).join('')}</definedNames><calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>`);
 put('xl/_rels/workbook.xml.rels',`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${sheets.map((_,i)=>`<Relationship Id="rId${i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i+1}.xml"/>`).join('')}<Relationship Id="rStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`);
 if(hasLogo){z['xl/media/logo.png']=Uint8Array.from(atob(auditLogoBase64),c=>c.charCodeAt(0));put('xl/worksheets/_rels/sheet1.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rLogo" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing1.xml"/></Relationships>');put('xl/drawings/_rels/drawing1.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rImage" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/logo.png"/></Relationships>');put('xl/drawings/drawing1.xml','<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><xdr:oneCellAnchor><xdr:from><xdr:col>4</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>0</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from><xdr:ext cx="1714500" cy="578038"/><xdr:pic><xdr:nvPicPr><xdr:cNvPr id="1" name="Audit Consulting Group"/><xdr:cNvPicPr/></xdr:nvPicPr><xdr:blipFill><a:blip xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:embed="rImage"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill><xdr:spPr><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic><xdr:clientData/></xdr:oneCellAnchor></xdr:wsDr>');}
 put('xl/styles.xml',styles);sheets.forEach((s,i)=>put(`xl/worksheets/sheet${i+1}.xml`,sheetXml(s,plan[i],{...t,hasLogo},names,lab)));return zipSync(z,{level:6,mtime:new Date('2026-01-01T00:00:00Z')});
}
export function buildHtml(t,template=false){
 const engine=PORTABLE_ENGINE_SOURCE;
 return renderHtml(t,template,engine,workbookSheets(t,template),sheetPlan(t.definition));
}

// Comprobación ejecutable: node lib/tools/exports.mjs
// Prueba que las cédulas salgan de la definición y que ninguna fórmula quede
// apuntando a una hoja que se omitió.
if (typeof process !== 'undefined' && process.argv?.[1]?.endsWith('exports.mjs')) {
 const assert = (ok, msg) => { if (!ok) throw new Error('FALLA: ' + msg); };
 const tool = d => ({definition:d, version:1, country:'Ecuador', engagement:{client:'Prueba', cutoff:'2025-12-31', year:'2025'},
  parameters:{}, reconciliation:{ledger:'0', tolerance:'0', difference:'0', within:true, acceptance:''},
  program:[], sources:[], events:[], notes:[], rows:[]});

 const huerfanas = (hojas, incluidas) => {
  const rotas = [];
  for (const rows of hojas) for (const row of rows) for (const cell of row)
   if (cell && typeof cell === 'object' && 'f' in cell)
    for (const n of SHEETS) if (!incluidas.includes(n) && cell.f.includes("'" + n + "'")) rotas.push(n);
  return [...new Set(rotas)];
 };

 const completa = tool(catalog.vnr);
 const todas = workbookSheets(completa, true);
 assert(todas.length === SHEETS.length - 1, 'sin declarar cédulas y sin serie salen todas menos el cuadro, no ' + todas.length);
 assert(!sheetNames(catalog.vnr).includes('13_Cuadro'), 'sin serie no hay cuadro de períodos');
 assert(huerfanas(todas, SHEETS).length === 0, 'el libro completo no debe tener referencias rotas');

 // El cuadro de períodos entra si y solo si hay serie, declárese o no.
 const conSerie = {...catalog.vnr, series:{count:'quantity',
  forward:[{key:'unidad',label:'Unidad',op:'add',a:'periodo',b:'#0',precision:2}]}};
 validateDefinition(conSerie);
 assert(sheetNames(conSerie).join() === SHEETS.join(), 'con serie salen las trece: ' + sheetNames(conSerie).join());
 assert(workbookSheets(tool(conSerie), true).length === SHEETS.length, 'trece cédulas con serie');
 assert(sheetNames({...conSerie, sheets:['11_Conclusion']}).includes('13_Cuadro'),
  'con serie el cuadro se conserva aunque la definición no lo declare');
 assert(!sheetNames({...catalog.vnr, sheets:['13_Cuadro']}).includes('13_Cuadro'),
  'sin serie el cuadro declarado no se arma: quedaría vacío');

 const recortada = tool({...catalog.vnr, sheets:['02_Programa','11_Conclusion']});
 const nombres = sheetNames(recortada.definition);
 assert(nombres.join() === '01_Caratula,02_Programa,03_Parametros,05_Data_Original,06_Data_Procesada,07_Calculos,11_Conclusion',
  'el plan conserva el núcleo y agrega lo declarado: ' + nombres.join());
 const pocas = workbookSheets(recortada, true);
 assert(pocas.length === 7, 'siete cédulas declaradas, no ' + pocas.length);
 assert(huerfanas(pocas, nombres).length === 0, 'fórmulas hacia cédulas omitidas: ' + huerfanas(pocas, nombres).join());

 const zip = buildWorkbook(recortada, true);
 assert(zip.length > 3000, 'el libro recortado se arma');
 assert(sheetLabels(recortada.definition).length === 7, 'siete etiquetas para siete cédulas');

 let fallo = '';
 try { sheetPlan({sheets:['99_Inventada']}); } catch (e) { fallo = e.message; }
 assert(fallo.includes('99_Inventada'), 'una cédula inexistente se rechaza, no se ignora');

 let mala = '';
 try { validateDefinition({...catalog.vnr, sheets:['99_Inventada']}); } catch (e) { mala = e.message; }
 assert(mala.includes('SHEETS'), 'la definición rechaza la cédula inexistente al crearse, no al descargar');
 validateDefinition({...catalog.vnr, sheets:['02_Programa']});

 console.log('tools/exports.mjs: todas las comprobaciones pasaron');
}
