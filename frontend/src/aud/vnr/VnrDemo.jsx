import {useState} from 'react';
import {SLOTS} from './logic.js';
import {DEMO,demoPolicy,exampleFile} from './demo.js';
import {saveBlob} from './api.js';
export default function VnrDemo({onLoad,busy}){
 const [framework,setFramework]=useState('full'),[error,setError]=useState(''),[downloading,setDownloading]=useState(false);
 async function download(slot,blank){setError('');setDownloading(true);try{const f=await exampleFile(slot,blank);saveBlob(f,f.name)}catch(e){setError(e.message)}finally{setDownloading(false)}}
 const p=demoPolicy(framework);
 return <section className="pc-panel"><div className="pc-panel-h"><h3>Ejemplo / Demo · aprende a llenar VNR</h3></div><div className="pc-panel-b">
 <p><b>Comercial Ejemplo · datos ficticios · USD · 31/12/2026.</b> Tres productos muestran deterioro, recuperación y ajuste adicional. Este ejercicio no incluye impuesto diferido.</p>
 <label>Marco del ejemplo<select value={framework} onChange={e=>setFramework(e.target.value)}><option value="full">NIIF completas</option><option value="sme">NIIF para las PYMES · supuesto edición 2015</option></select></label>
 <p>El marco elegido orienta el texto del ejemplo; deberá comprobar la edición y adopción que corresponda al encargo real.</p>
 <button className="btn primary" disabled={busy||downloading} onClick={()=>onLoad(framework)}>Cargar ejemplo completo en la herramienta</button>
 <p>Este botón carga los cuatro archivos por el mismo proceso de extracción del sistema. Después deberá revisar y marcar las dos confirmaciones, y pulsar <b>Procesar</b>.</p>
 <h4>1. Descarga los archivos y practica la carga manual</h4><div className="vnr-grid">{SLOTS.map(([slot,label],i)=><article className="vnr-source" key={slot}><h4>{i+1}. {label}</h4><button className="btn" disabled={downloading} onClick={()=>download(slot,false)}>Descargar {slot==='policy'?'soporte TXT':'ejemplo Excel'}</button>{slot!=='policy'&&<button className="link" disabled={downloading} onClick={()=>download(slot,true)}>Descargar plantilla vacía Excel</button>}</article>)}</div>
 {error&&<p role="alert">{error}</p>}
 <ol><li>En Mi prueba, confirma la ficha. Para practicar manualmente utiliza una ficha identificada como DEMO.</li><li>Sube primero el inventario y selecciona la hoja <b>Datos</b>. Asigna cada columna con el mismo nombre y pulsa <b>Importar datos de esta fuente</b>.</li><li>Repite con precios y gastos, en ese orden. Los códigos DEMO-A, DEMO-B y DEMO-C vinculan los archivos.</li><li>Sube el soporte TXT en Políticas. Copia y adapta los textos ilustrativos de abajo; el TXT no rellena automáticamente los campos.</li><li>Selecciona <b>Costo por unidad</b>; mayor bruto <b>940</b>, deterioro registrado <b>65</b> y tolerancia <b>0.01</b>. Deja desmarcado impuesto diferido.</li><li>Revisa los datos y las dos confirmaciones. Pulsa Procesar, compara resultados, descarga Excel/HTML y finalmente Encerar.</li></ol>
 <h4>2. Qué escribir en los campos</h4><dl><dt>Política contable y alcance</dt><dd>{p.basis}</dd><dt>Norma, párrafos y vigencia</dt><dd>{p.normative_reference} Las confirmaciones permanecen desmarcadas hasta tu revisión.</dd><dt>Sustento de reversión</dt><dd>{p.reversal_basis}</dd><dt>Preparado por / Revisado por</dt><dd>Nombres de quienes realizan y revisan el trabajo. En el ejercicio: Preparador DEMO y Revisor DEMO.</dd></dl>
 <h4>3. Resultados que debes obtener</h4><div className="vnr-scroll"><table><thead><tr><th>Producto</th><th>Costo</th><th>VNR total</th><th>Deterioro requerido</th><th>Registrado</th><th>Ajuste</th></tr></thead><tbody><tr><td>DEMO-A</td><td>200</td><td>150</td><td>50</td><td>5</td><td>45</td></tr><tr><td>DEMO-B</td><td>500</td><td>575</td><td>0</td><td>40</td><td>−40</td></tr><tr><td>DEMO-C</td><td>240</td><td>180</td><td>60</td><td>20</td><td>40</td></tr></tbody></table></div>
 <p>DEMO-A: 10 × (18 − 1 − 2) = 150 de VNR. Deterioro: 200 − 150 = 50. Ajuste adicional: 50 − 5 = 45.</p>
 <p><b>Totales:</b> costo {DEMO.expected.cost}; deterioro {DEMO.expected.impairment}; gasto adicional {DEMO.expected.expense}; reversión {DEMO.expected.reversal}; ajuste neto {DEMO.expected.adjustment}; valor contable {DEMO.expected.carrying}. Diferencias con el mayor: cero.</p>
 </div></section>
}
