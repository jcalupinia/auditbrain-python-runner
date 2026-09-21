import {unzipSync,strFromU8} from 'fflate';
import {XMLParser,XMLValidator} from 'fast-xml-parser';
import {parseCsv} from '../tools/files.mjs';
export const MAX_FILE=25*1024*1024;
const TEXT_LIMIT=5000000,CELL_LIMIT=50000;
const arr=x=>x===undefined?[]:Array.isArray(x)?x:[x];
const parser=new XMLParser({ignoreAttributes:false,attributeNamePrefix:'@',parseTagValue:false,processEntities:true});
const ordered=new XMLParser({preserveOrder:true,ignoreAttributes:true,parseTagValue:false,processEntities:true});
function xml(bytes,order=false){const s=strFromU8(bytes);if(/<!DOCTYPE|<!ENTITY/i.test(s))throw Error('XML con entidades no permitido.');return (order?ordered:parser).parse(s);}
const scalar=v=>String(v && typeof v==='object' ? (v['#text']??'') : (v??''));
export function unpack(bytes){
 let expanded=0,count=0;const names=new Set();
 return unzipSync(bytes,{filter:e=>{if(++count>300||e.originalSize>20*1024*1024||(expanded+=e.originalSize)>40*1024*1024)throw Error('El ZIP supera el límite de 300 entradas o 40 MB descomprimidos.');
 if(e.name.length>300||e.name.includes('\\')||e.name.startsWith('/')||e.name.split('/').includes('..')||/^[a-z]:/i.test(e.name)||/[\x00-\x1f]/.test(e.name))throw Error('ZIP con ruta no permitida.');
 if(names.has(e.name))throw Error('ZIP con nombres duplicados.');names.add(e.name);return !e.name.endsWith('/');}});
}
function workbook(z){
 if(!z['xl/workbook.xml']||!z['xl/_rels/workbook.xml.rels'])throw Error('Contenido XLSX inválido.');
 const book=xml(z['xl/workbook.xml']),rels=arr(xml(z['xl/_rels/workbook.xml.rels']).Relationships?.Relationship);
 const shared=z['xl/sharedStrings.xml']?arr(xml(z['xl/sharedStrings.xml']).sst?.si).map(s=>s.t!==undefined?scalar(s.t):arr(s.r).map(r=>scalar(r.t)).join('')):[];
 let count=0,formulaCount=0,missing=0;const warnings=['Las fórmulas se conservan para inspección; no se recalculan. Los valores guardados pueden estar desactualizados.'];
 const sheets=arr(book.workbook?.sheets?.sheet).map(s=>{const rel=rels.find(r=>r['@Id']===s['@r:id']);const target=rel?.['@Target'];if(!target||rel['@TargetMode']==='External'||target.includes('..'))throw Error('Referencia de hoja no permitida.');const key=target.startsWith('/')?target.slice(1):'xl/'+target.replace(/^\.\//,'');if(!z[key])throw Error('No se encontró la hoja '+s['@name']);
 const cells=[],formulas=[],rows=[];for(const r of arr(xml(z[key]).worksheet?.sheetData?.row)){for(const c of arr(r.c)){if(++count>CELL_LIMIT)throw Error('El libro supera 50.000 celdas con contenido. Divídalo en archivos menores.');const address=c['@r'];if(!/^[A-Z]{1,3}[1-9]\d{0,6}$/.test(address||''))throw Error('Celda sin referencia válida.');let value=c['@t']==='s'?(shared[Number(c.v)]??''):c['@t']==='inlineStr'?(c.is?.t!==undefined?scalar(c.is.t):arr(c.is?.r).map(v=>scalar(v.t)).join('')):scalar(c.v);if(value.length>10000)throw Error('Celda demasiado extensa.');cells.push({cell:address,value});
 if(c.f!==undefined){formulaCount++;if(c.v===undefined)missing++;formulas.push({cell:address,formula:scalar(c.f),cached:c.v===undefined?null:scalar(c.v),type:c.f?.['@t']||'normal',sharedIndex:c.f?.['@si']??null,range:c.f?.['@ref']??null});}}
 if(rows.length<20)rows.push(arr(r.c).slice(0,12).map(c=>({cell:c['@r'],value:cells.findLast(v=>v.cell===c['@r'])?.value??''})));}
 return {name:s['@name'],visibility:s['@state']||'visible',cellCount:cells.length,cells,formulas,preview:rows};});
 if(!sheets.length||sheets.length>50)throw Error('Se admiten entre 1 y 50 hojas por libro.');
 if(missing)warnings.push(`${missing} fórmulas sin valor guardado.`);
 if(sheets.some(s=>s.formulas.some(f=>f.type!=='normal')))warnings.push('Hay fórmulas compartidas o matriciales: se muestra el XML original, sin expandir fórmulas dependientes.');
 if(Object.keys(z).some(k=>/externalLinks|vbaProject|connections\.xml/i.test(k)))warnings.push('Contiene vínculos, conexiones o macros: no se ejecutan ni se consultan.');
 return {kind:'xlsx',status:'extracted',sheets,formulaCount,cellCount:count,warnings};
}
function word(z){if(!z['word/document.xml'])throw Error('Contenido DOCX inválido.');let text='';function walk(nodes){for(const n of arr(nodes)){for(const [key,v]of Object.entries(n)){if(key==='#text')text+=String(v);else if(key==='w:tab')text+='\t';else if(key==='w:br')text+='\n';else if(Array.isArray(v)){walk(v);if(['w:p','w:tr'].includes(key))text+='\n';if(key==='w:tc')text+='\t';}if(text.length>TEXT_LIMIT)throw Error('El Word supera el límite de texto; divídalo en documentos menores.');}}}walk(xml(z['word/document.xml'],true));return {kind:'docx',status:'extracted',text:text.trim(),warnings:['Texto del cuerpo y tablas; no incluye imágenes, comentarios, encabezados ni contenido incrustado.']};}
export async function extractFile(bytes,name,depth=0){
 if(!bytes.length||bytes.length>MAX_FILE)throw Error('Cada archivo debe tener contenido y pesar como máximo 25 MB.');
 const ext=name.toLowerCase().split('.').pop();
 if(['xls','doc','xlsm','heic'].includes(ext))throw Error('Convierta el archivo a XLSX, DOCX, PDF, JPG o PNG. No se ejecutan macros.');
 if(['xlsx','docx','zip'].includes(ext)){
 if(bytes[0]!==80||bytes[1]!==75)throw Error('Contenido ZIP/Office inválido.');const z=unpack(bytes);
 if(ext==='xlsx')return workbook(z);if(ext==='docx')return word(z);
 if(depth)throw Error('Los ZIP anidados no se procesan.');const entries=Object.entries(z).filter(([n])=>!n.startsWith('__MACOSX/')&&!n.split('/').pop().startsWith('.'));if(entries.length>25)throw Error('El ZIP admite hasta 25 archivos.');
 const children=[];let textBudget=0;for(const [child,data]of entries){let result;if(/\.(xlsx|docx|csv|txt|md|xml|pdf|png|jpe?g|webp)$/i.test(child)){try{result=await extractFile(data,child,depth+1);textBudget+=JSON.stringify(result).length;if(textBudget>3000000)throw Error('El contenido extraído del ZIP supera el límite.');}catch(e){result={status:'error',warnings:[e.message]};}}else result={status:'unsupported',warnings:['Formato no procesado; se conserva dentro del ZIP original.']};children.push({name:child,size:data.length,...result});}
 return {kind:'zip',status:children.some(c=>c.status==='error'||c.status==='unsupported')?'partial':'extracted',children,warnings:['Los ZIP anidados y formatos no admitidos no se procesan. Los PDF e imágenes dentro del ZIP deben adjuntarse por separado para enviarlos a visión IA.']};
 }
 if(ext==='csv'||ext==='txt'||ext==='md'){const text=new TextDecoder('utf-8',{fatal:true}).decode(bytes).replace(/^\uFEFF/,'');if(text.includes('\0'))throw Error('Texto inválido: use UTF-8.');
 // El CSV no se limita por caracteres sino por filas (MAX_ROWS, dentro de
 // parseCsv): una población de 100.000 filas son millones de caracteres y es
 // perfectamente válida. El tope de texto aplica a los formatos que SÍ
 // devuelven su texto completo: txt, md, xml y docx.
 if(ext!=='csv'&&text.length>TEXT_LIMIT)throw Error('Texto superior a 5.000.000 de caracteres. Divida el archivo o entréguelo por componentes.');if(ext==='txt'||ext==='md')return {kind:ext,status:'extracted',text,warnings:[]};const rows=parseCsv(text);return {kind:'csv',status:'extracted',sheets:[{name:'CSV',rows,rowCount:rows.length}],warnings:['Los campos se leen como texto; no se ejecutan fórmulas contenidas en el CSV.']};}
 if(ext==='xml'){const text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);if(text.length>TEXT_LIMIT||text.includes('\0'))throw Error('XML demasiado extenso o ilegible.');if(/<!DOCTYPE|<!ENTITY/i.test(text))throw Error('XML con entidades no permitido.');if(XMLValidator.validate(text)!==true)throw Error('XML inválido.');return {kind:'xml',status:'extracted',text,warnings:['XML leído como evidencia. Requiere interpretación y conciliación; no se convierte automáticamente en cálculos.']};}
 if(ext==='pdf'){
 if(strFromU8(bytes.slice(0,5))!=='%PDF-')throw Error('Contenido PDF inválido.');
 const {getDocumentProxy}=await import('unpdf');let pdf;
 try{pdf=await getDocumentProxy(bytes.slice(),{isEvalSupported:false,maxImageSize:16777216,useSystemFonts:false});if(pdf.numPages>50)throw Error('El PDF supera 50 páginas; divídalo antes de cargarlo.');let text='',empty=0;for(let i=1;i<=pdf.numPages;i++){const page=await pdf.getPage(i),content=await page.getTextContent();const line=content.items.map(x=>'str' in x?x.str:'').join(' ');if(!line.trim())empty++;text+=`\n[Página ${i}]\n${line}`;page.cleanup();if(text.length>TEXT_LIMIT)throw Error('El PDF supera el límite de texto; divídalo.');}return {kind:'pdf',status:empty?'partial':'extracted',pages:pdf.numPages,text,warnings:empty?[`${empty} páginas sin texto extraíble. Para escaneos o tablas visuales use análisis IA con el PDF original.`]:['Se extrae texto; el orden de columnas y tablas debe revisarse con el original.']};}finally{await pdf?.loadingTask?.destroy();}
 }
 const mime=ext==='png'&&bytes.slice(0,8).join(',')==='137,80,78,71,13,10,26,10'?'image/png':['jpg','jpeg'].includes(ext)&&bytes[0]===255&&bytes[1]===216&&bytes[2]===255?'image/jpeg':ext==='webp'&&strFromU8(bytes.slice(0,4))==='RIFF'&&strFromU8(bytes.slice(8,12))==='WEBP'?'image/webp':null;
 if(mime)return {kind:'image',mime,status:'vision_pending',warnings:['Imagen recibida. La lectura visual y transcripción requieren IA configurada; aún no se ha extraído su contenido.']};
 throw Error('Formato no admitido o contenido inválido. Use DOCX, XLSX, CSV, TXT, PDF, ZIP, JPG, PNG o WebP.');
}
export function brief(result){return {kind:result.kind,status:result.status,formulaCount:result.formulaCount,cellCount:result.cellCount,pages:result.pages,sheets:result.sheets?.map(s=>({name:s.name,cellCount:s.cellCount,rowCount:s.rowCount,formulaCount:s.formulas?.length})),entries:result.children?.map(c=>({name:c.name,kind:c.kind,status:c.status})),warnings:result.warnings};}
