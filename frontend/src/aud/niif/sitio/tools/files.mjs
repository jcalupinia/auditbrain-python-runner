import {unzipSync,strFromU8} from 'fflate';
import {XMLParser} from 'fast-xml-parser';
import {MAX_ROWS} from './domain.mjs';
const arr=x=>x===undefined?[]:Array.isArray(x)?x:[x];
// Texto de un nodo <t>. Con atributos (xml:space="preserve") el parser lo entrega
// como objeto, y sin texto ese objeto no trae '#text': antes se colaba como
// "[object Object]". Es justo como este mismo sitio escribe las celdas vacías
// de sus Excel, así que al volver a subir un libro exportado aquí sus filas
// vacías dejaban de serlo y la validación fallaba.
const texto=t=>t!==null&&typeof t==='object'?(t['#text']??''):(t??'');
const parser=new XMLParser({ignoreAttributes:false,attributeNamePrefix:'@',parseTagValue:false,processEntities:true});
function xml(bytes){const s=strFromU8(bytes);if(/<!DOCTYPE|<!ENTITY/i.test(s))throw Error('XML con entidades no permitido.');return parser.parse(s);}
export function parseCsv(text,delimiter){
 if(text.includes('\0'))throw Error('Archivo de texto inválido.');
 delimiter=delimiter||((text.split(/\r?\n/)[0].match(/;/g)||[]).length>(text.split(/\r?\n/)[0].match(/,/g)||[]).length?';':',');
 if(![',',';','\t'].includes(delimiter))throw Error('Separador inválido.');
 let rows=[],row=[],value='',quoted=false;for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){value+='"';i++;}else if(quoted||value==='')quoted=!quoted;else value+=c;}else if(c===delimiter&&!quoted){row.push(value);value='';}else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(value);rows.push(row);row=[];value='';}else value+=c;if(rows.length>MAX_ROWS+100||row.length>150||value.length>10000)throw Error('Archivo supera los límites de filas, columnas o longitud.');}
 if(quoted)throw Error('CSV ilegible: comillas sin cerrar.');if(value||row.length)rows.push([...row,value]);return rows;
}
export function readSpreadsheet(bytes,name){
 if(bytes.length>15*1024*1024)throw Error('El límite por archivo es 15 MB.');
 if(/\.csv$/i.test(name))return {sheets:[{name:'CSV',rows:parseCsv(new TextDecoder('utf-8',{fatal:true}).decode(bytes).replace(/^\uFEFF/,''))}]};
 if(!/\.xlsx$/i.test(name))throw Error('Para datos tabulares use XLSX o CSV.');
 let expanded=0;const z=unzipSync(bytes,{filter:e=>{expanded+=e.originalSize;if(expanded>60*1024*1024||e.originalSize>30*1024*1024)throw Error('Libro demasiado grande al descomprimir.');return /^(xl\/(workbook.xml|_rels\/workbook.xml.rels|sharedStrings.xml|worksheets\/sheet\d+.xml))$/.test(e.name);}});
 if(!z['xl/workbook.xml']||!z['xl/_rels/workbook.xml.rels'])throw Error('El contenido no es un libro XLSX válido.');
 const book=xml(z['xl/workbook.xml']),rels=arr(xml(z['xl/_rels/workbook.xml.rels']).Relationships?.Relationship),shared=z['xl/sharedStrings.xml']?arr(xml(z['xl/sharedStrings.xml']).sst?.si).map(s=>s.t!==undefined?texto(s.t):arr(s.r).map(r=>texto(r.t)).join('')):[];
 const sheets=arr(book.workbook?.sheets?.sheet).map(s=>{const rel=rels.find(r=>r['@Id']===s['@r:id']);let path=rel?.['@Target'];if(!path||rel['@TargetMode']==='External')throw Error('Referencia de hoja inválida.');path=path.startsWith('/')?path.slice(1):'xl/'+path.replace(/^\.\//,'');if(!z[path])throw Error('No se pudo leer la hoja '+s['@name']);
 const rows=[];for(const row of arr(xml(z[path]).worksheet?.sheetData?.row)){const n=Number(row['@r']);if(!Number.isInteger(n)||n>MAX_ROWS+100||n<1)throw Error(`La hoja excede ${MAX_ROWS} registros.`);const cells=[];for(const cell of arr(row.c)){const address=cell['@r']||'';const letters=address.match(/^[A-Z]+/)?.[0];if(!letters)throw Error('Celda sin referencia.');let col=0;for(const l of letters)col=col*26+l.charCodeAt(0)-64;if(col>150)throw Error('El límite es 150 columnas.');let v=cell.v??'';if(cell['@t']==='s')v=shared[Number(v)]??'';if(cell['@t']==='inlineStr')v=cell.is?.t!==undefined?texto(cell.is.t):arr(cell.is?.r).map(r=>texto(r.t)).join('');if(cell.f!==undefined&&cell.v===undefined)v='FORMULA_SIN_VALOR_GUARDADO';if(cell['@t']==='e')v='ERROR_EXCEL: '+v;cells[col-1]=String(v);}rows[n-1]=cells;}
 return {name:s['@name'],date1904:['1','true'].includes(String(book.workbook?.workbookPr?.['@date1904'])),rows:Array.from({length:rows.length},(_,i)=>rows[i]||[])};});
 if(!sheets.length)throw Error('Libro sin hojas.');return {sheets};
}
export function mappedRows(sheet,header,mapping,definition,file){
 if(!Number.isInteger(header)||header<1||header>100||!sheet.rows[header-1])throw Error('Fila de encabezado inválida.');const headers=sheet.rows[header-1];
 for(const f of definition.fields){const col=mapping[f.key];if(!Number.isInteger(col)||col<0||col>=headers.length)throw Error('Falta mapear '+f.label);}
 const rows=[];let blanks=0;for(let i=header;i<sheet.rows.length;i++){const cells=sheet.rows[i];if(!cells.some(x=>String(x??'').trim())){blanks++;continue;}const row={_file:file.name,_fileId:file.id,_sheet:sheet.name,_row:i+1};for(const f of definition.fields){let value=String(cells[mapping[f.key]]??'').trim();if(f.type==='date'&&/^\d{5}(\.0+)?$/.test(value))value=new Date((sheet.date1904?Date.UTC(1904,0,1):Date.UTC(1899,11,30))+Number(value)*86400000).toISOString().slice(0,10);row[f.key]=value;}rows.push(row);}
 return {rows,blankRows:blanks,headers};
}
