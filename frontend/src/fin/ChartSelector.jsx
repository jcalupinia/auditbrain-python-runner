// Skill 051 · Dashboard Chart Selector — AuditBrain
// Asistente in-app: 5 preguntas -> recomienda el gráfico óptimo entre 20,
// con vista previa (Chart.js), especificación y snippets Power BI / Chart.js.
// Chart.js se importa del paquete (no de window) para correr en Vite.
import { useState, useEffect, useRef } from "react";
import Chart from "chart.js/auto";

const QUESTIONS = [
  { id:"Q1", label:"Pregunta 1 de 5", text:"¿Cuál es el objetivo principal del dashboard?",
    options:[{val:"tendencias",label:"Mostrar tendencias en el tiempo"},{val:"comparacion",label:"Comparar categorías o entidades"},{val:"composicion",label:"Mostrar composición (partes de un todo)"},{val:"variacion",label:"Analizar variaciones o desviaciones"},{val:"correlacion",label:"Correlacionar variables"},{val:"kpi_meta",label:"Monitorear KPI vs. meta"},{val:"riesgo",label:"Gestión de riesgo y control"}]},
  { id:"Q2", label:"Pregunta 2 de 5", text:"¿Cuántas métricas principales se visualizarán?",
    options:[{val:"1",label:"1 métrica"},{val:"2",label:"2 métricas"},{val:"3+",label:"3 o más métricas"}]},
  { id:"Q3", label:"Pregunta 3 de 5", text:"¿Cuál es el perfil de la audiencia?",
    options:[{val:"directorio",label:"Directorio / Junta (alta gerencia)"},{val:"cfo",label:"CFO / Gerente Financiero"},{val:"auditor",label:"Auditor / Analista financiero"},{val:"operativo",label:"Operativo / Área específica"}]},
  { id:"Q4", label:"Pregunta 4 de 5", text:"¿Existe dimensión temporal en los datos?",
    options:[{val:"si",label:"Sí — datos históricos o proyectados"},{val:"no",label:"No — datos de un punto en el tiempo"}]},
  { id:"Q5", label:"Pregunta 5 de 5", text:"¿Cuántas categorías o ítems tiene el dato?",
    options:[{val:"1-3",label:"1 a 3 ítems"},{val:"4-6",label:"4 a 6 ítems"},{val:"7+",label:"7 o más ítems"}]},
];

const CHARTS = {
  C01:{id:"C01",name:"Gráfico de líneas",cat:"Rendimiento y tendencias",catBg:"#E6F1FB",catTxt:"#0C447C",complexity:"Baja",impact:5,impactLabel:"Muy alto",tools:["Power BI Line Chart","Chart.js line","Tableau Line"],use:"Series de tiempo: ingresos, flujo de caja, KPIs mensuales.",axes:"X = período · Y = valor",code:"line"},
  C02:{id:"C02",name:"Barras verticales",cat:"Rendimiento y tendencias",catBg:"#EAF3DE",catTxt:"#27500A",complexity:"Baja",impact:4,impactLabel:"Alto",tools:["Power BI Clustered Bar","Chart.js bar","Tableau Bar"],use:"Comparación de ventas, gastos o ingresos por período o categoría.",axes:"X = categoría · Y = valor",code:"vbar"},
  C03:{id:"C03",name:"Barras horizontales",cat:"Rendimiento y tendencias",catBg:"#EAF3DE",catTxt:"#27500A",complexity:"Baja",impact:4,impactLabel:"Alto",tools:["Power BI Bar Chart","Chart.js horizontal","Tableau Bar"],use:"Rankings de productos, clientes o proveedores con muchos ítems.",axes:"Y = categoría · X = valor",code:"hbar"},
  C04:{id:"C04",name:"Gráfico de área",cat:"Rendimiento y tendencias",catBg:"#FAEEDA",catTxt:"#633806",complexity:"Baja",impact:3,impactLabel:"Medio",tools:["Power BI Area Chart","Chart.js area","Tableau Area"],use:"Volumen acumulado: cartera, deuda, crecimiento de base.",axes:"X = período · Y = valor acumulado",code:"area"},
  C05:{id:"C05",name:"Velas (Candlestick)",cat:"Rendimiento y tendencias",catBg:"#E1F5EE",catTxt:"#085041",complexity:"Media",impact:4,impactLabel:"Alto (bursátil)",tools:["Power BI Custom Visual","ApexCharts","TradingView"],use:"Precios de acciones: apertura, máximo, mínimo, cierre.",axes:"X = fecha · Y = precio OHLC",code:"candle"},
  C06:{id:"C06",name:"Torta (Pie)",cat:"Composición y distribución",catBg:"#FCEBEB",catTxt:"#791F1F",complexity:"Baja",impact:3,impactLabel:"Medio",tools:["Power BI Pie Chart","Chart.js pie","Tableau Pie"],use:"Participación porcentual — máximo 6 segmentos.",axes:"N/A — proporciones sobre 100%",code:"pie"},
  C07:{id:"C07",name:"Dona (Donut)",cat:"Composición y distribución",catBg:"#FBEAF0",catTxt:"#72243E",complexity:"Baja",impact:5,impactLabel:"Muy alto",tools:["Power BI Donut","Chart.js doughnut","Tableau Donut"],use:"Composición con KPI central destacado en el centro.",axes:"N/A — proporciones con métrica central",code:"donut"},
  C08:{id:"C08",name:"Barras apiladas",cat:"Composición y distribución",catBg:"#EAF3DE",catTxt:"#27500A",complexity:"Baja",impact:4,impactLabel:"Alto",tools:["Power BI Stacked Bar","Chart.js stacked","Tableau Stacked"],use:"Composición de costos/ingresos a lo largo del tiempo.",axes:"X = período · Y = subcategorías apiladas",code:"stacked"},
  C09:{id:"C09",name:"Treemap",cat:"Composición y distribución",catBg:"#FAEEDA",catTxt:"#633806",complexity:"Media",impact:4,impactLabel:"Alto visual",tools:["Power BI Treemap","D3.js treemap","Tableau Treemap"],use:"Distribución jerárquica de presupuesto o costos por área.",axes:"N/A — área de rectángulo proporcional al valor",code:"treemap"},
  C10:{id:"C10",name:"Sankey",cat:"Composición y distribución",catBg:"#EEEDFE",catTxt:"#3C3489",complexity:"Alta",impact:5,impactLabel:"Muy alto",tools:["Power BI Sankey Custom","D3.js Sankey","Plotly Sankey"],use:"Flujo de ingresos a utilidades, cadena de valor financiera.",axes:"N/A — flujo entre nodos con magnitudes",code:"sankey"},
  C11:{id:"C11",name:"Cascada (Waterfall)",cat:"Análisis financiero especializado",catBg:"#E6F1FB",catTxt:"#0C447C",complexity:"Media",impact:5,impactLabel:"Muy alto",tools:["Power BI Waterfall","Chart.js custom stacked","Plotly Waterfall","ApexCharts"],use:"Bridge financiero: de ingresos brutos a utilidad neta, variaciones YoY.",axes:"X = concepto · Y = monto positivo/negativo acumulado",code:"waterfall"},
  C12:{id:"C12",name:"Embudo (Funnel)",cat:"Análisis financiero especializado",catBg:"#E1F5EE",catTxt:"#085041",complexity:"Baja",impact:4,impactLabel:"Alto",tools:["Power BI Funnel","Funnel-graph-js","Chart.js custom"],use:"Cobranza, pipeline de ventas, proceso de aprobaciones.",axes:"Etapas secuenciales con reducción de volumen",code:"funnel"},
  C13:{id:"C13",name:"Dispersión (Scatter)",cat:"Análisis financiero especializado",catBg:"#FAECE7",catTxt:"#712B13",complexity:"Media",impact:3,impactLabel:"Medio",tools:["Power BI Scatter","Chart.js scatter","Tableau Scatter"],use:"Correlación: rentabilidad vs. riesgo, costo vs. volumen.",axes:"X = variable 1 · Y = variable 2",code:"scatter"},
  C14:{id:"C14",name:"Burbuja",cat:"Análisis financiero especializado",catBg:"#FAEEDA",catTxt:"#633806",complexity:"Media",impact:4,impactLabel:"Alto",tools:["Power BI Bubble","Chart.js bubble","Tableau Bubble"],use:"Portafolio: rentabilidad + riesgo + tamaño de posición.",axes:"X, Y = métricas · Tamaño = tercera variable",code:"bubble"},
  C15:{id:"C15",name:"Velocímetro (Gauge)",cat:"Análisis financiero especializado",catBg:"#FCEBEB",catTxt:"#791F1F",complexity:"Baja",impact:5,impactLabel:"Muy alto",tools:["Power BI Gauge","ApexCharts Radial","Chart.js custom arc"],use:"Cumplimiento de meta: presupuesto, cobranza, KPI único.",axes:"N/A — valor actual vs. rango meta definido",code:"gauge"},
  C16:{id:"C16",name:"Radar / Araña",cat:"Control, riesgo y gestión",catBg:"#EEEDFE",catTxt:"#3C3489",complexity:"Media",impact:4,impactLabel:"Alto en auditoría",tools:["Power BI Radar","Chart.js radar","Tableau Radar Custom"],use:"Ratios financieros multidimensionales, benchmarking de riesgo.",axes:"N/A — 5 a 8 ejes radiales normalizados 0–100",code:"radar"},
  C17:{id:"C17",name:"Mapa de calor (Heatmap)",cat:"Control, riesgo y gestión",catBg:"#EAF3DE",catTxt:"#27500A",complexity:"Media",impact:5,impactLabel:"Muy alto en auditoría",tools:["Power BI Matrix + CF","D3.js Heatmap","Plotly Heatmap"],use:"Concentración de transacciones, riesgo por período y categoría.",axes:"Filas = categoría · Columnas = período · Color = intensidad",code:"heatmap"},
  C18:{id:"C18",name:"Box plot",cat:"Control, riesgo y gestión",catBg:"#F1EFE8",catTxt:"#444441",complexity:"Media-Alta",impact:3,impactLabel:"Medio",tools:["Power BI Box Custom","Plotly Box","D3.js Box"],use:"Distribución de márgenes, variabilidad de costos, detección de outliers.",axes:"X = grupo · Y = distribución estadística (Q1–Q3, mediana, outliers)",code:"boxplot"},
  C19:{id:"C19",name:"Histograma",cat:"Control, riesgo y gestión",catBg:"#E6F1FB",catTxt:"#0C447C",complexity:"Media",impact:3,impactLabel:"Medio",tools:["Power BI Histogram Custom","Chart.js bar (bins)","Plotly Histogram"],use:"Frecuencia de montos de transacciones, rangos de cobro.",axes:"X = intervalos (bins) · Y = frecuencia de ocurrencia",code:"histogram"},
  C20:{id:"C20",name:"Combinado (Combo)",cat:"Rendimiento y tendencias",catBg:"#FAECE7",catTxt:"#712B13",complexity:"Baja-Media",impact:5,impactLabel:"Muy alto",tools:["Power BI Line+Column","Chart.js mixed","Tableau Dual Axis"],use:"Ingresos + margen, presupuesto vs. real + % desviación en un panel.",axes:"X = período · Y1 = barras · Y2 = línea (doble eje)",code:"combo"},
};

const DECISION = [
  {match:a=>a.Q1==="tendencias"&&a.Q2==="1"&&a.Q4==="si",primary:"C01",alts:["C04","C20"],rationale:"La línea es el estándar para series de tiempo de una sola métrica. Comunica dirección y velocidad de cambio de forma inmediata para cualquier audiencia."},
  {match:a=>a.Q1==="tendencias"&&a.Q2==="2"&&a.Q4==="si",primary:"C20",alts:["C01","C08"],rationale:"El Combo permite mostrar dos escalas distintas en un solo panel — ideal para ingresos + margen o volumen + precio en reportes de CFO."},
  {match:a=>a.Q1==="tendencias"&&a.Q2==="3+",primary:"C08",alts:["C04","C20"],rationale:"Las barras apiladas permiten mostrar múltiples métricas que componen un total, manteniendo legibilidad para directivos."},
  {match:a=>a.Q1==="comparacion"&&a.Q5==="1-3",primary:"C02",alts:["C20","C07"],rationale:"Las barras verticales son la forma más intuitiva para comparar pocas categorías. Alta legibilidad para cualquier perfil de audiencia."},
  {match:a=>a.Q1==="comparacion"&&a.Q5==="4-6",primary:"C02",alts:["C08","C03"],rationale:"Barras verticales agrupadas permiten comparación directa. Con 4–6 categorías mantienen legibilidad sin saturar el panel ejecutivo."},
  {match:a=>a.Q1==="comparacion"&&a.Q5==="7+",primary:"C03",alts:["C09","C17"],rationale:"Las barras horizontales acomodan mejor etiquetas largas y muchos ítems. Más legibles en rankings extensos de productos o clientes."},
  {match:a=>a.Q1==="composicion"&&a.Q5==="1-3"&&a.Q3==="directorio",primary:"C07",alts:["C06","C15"],rationale:"La dona es la elección ideal para directorio: composición visual con KPI central prominente. Máximo impacto ejecutivo en un solo vistazo."},
  {match:a=>a.Q1==="composicion"&&a.Q4==="si",primary:"C08",alts:["C04","C10"],rationale:"Las barras apiladas combinan evolución temporal con composición por subcategoría — herramienta estándar en reportes mensuales de CFO."},
  {match:a=>a.Q1==="composicion"&&a.Q5==="7+",primary:"C09",alts:["C10","C03"],rationale:"El treemap es ideal para estructuras jerárquicas con muchos ítems. Revela la proporción de cada componente del presupuesto de forma visual."},
  {match:a=>a.Q1==="variacion"&&(a.Q3==="cfo"||a.Q3==="directorio"),primary:"C11",alts:["C20","C02"],rationale:"El Waterfall es el estándar de facto para bridge financiero. El favorito de CFO y directorio para analizar desviaciones paso a paso con trazabilidad."},
  {match:a=>a.Q1==="variacion"&&a.Q3==="auditor",primary:"C11",alts:["C17","C16"],rationale:"El Waterfall permite descomponer cada variación con trazabilidad auditora. Complementar con heatmap para análisis de concentración de diferencias."},
  {match:a=>a.Q1==="kpi_meta"&&a.Q2==="1",primary:"C15",alts:["C07","C02"],rationale:"El Gauge comunica cumplimiento de meta de forma visual inmediata. El más efectivo para una sola métrica vs. objetivo en dashboards de monitoreo."},
  {match:a=>a.Q1==="kpi_meta"&&a.Q2!=="1",primary:"C20",alts:["C08","C02"],rationale:"Con múltiples métricas vs. meta, el Combo es más informativo: barras de real + línea de presupuesto en el mismo panel y escala."},
  {match:a=>a.Q1==="correlacion"&&a.Q2==="2",primary:"C13",alts:["C20","C14"],rationale:"El scatter es la herramienta correcta para analizar correlación entre dos variables financieras continuas con precisión estadística."},
  {match:a=>a.Q1==="correlacion"&&a.Q2==="3+",primary:"C14",alts:["C13","C09"],rationale:"El gráfico de burbuja añade una tercera dimensión al scatter — ideal para portafolios: rentabilidad + riesgo + tamaño de posición."},
  {match:a=>a.Q1==="riesgo"&&a.Q3==="auditor",primary:"C17",alts:["C16","C19"],rationale:"El heatmap revela concentraciones y patrones de riesgo en matrices período/categoría. Herramienta clave en auditoría de datos y control interno."},
  {match:a=>a.Q1==="riesgo",primary:"C16",alts:["C15","C17"],rationale:"El radar permite evaluar múltiples dimensiones de riesgo simultáneamente — ideal para benchmarking y scorecards de gestión ejecutiva."},
];
const DEFAULT = {primary:"C11",alts:["C20","C07"],rationale:"El Waterfall es la recomendación más versátil para dashboards financieros ejecutivos con múltiples componentes de desglose."};

function MiniChart({ chartId }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);
  useEffect(() => {
    if (!canvasRef.current) return;
    if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null; }
    const ctx = canvasRef.current.getContext("2d");
    const configs = {
      C01: { type:"line", data:{ labels:["Ene","Feb","Mar","Abr","May","Jun"], datasets:[{ data:[320,410,380,510,490,620], borderColor:"#185FA5", backgroundColor:"rgba(55,138,221,0.08)", tension:0.4, fill:true, pointRadius:3 }] }, options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{ x:{grid:{display:false},ticks:{font:{size:9},color:"#888"}}, y:{grid:{color:"rgba(128,128,128,0.1)"},ticks:{font:{size:9},color:"#888",callback:v=>"$"+v+"k"}} } } },
      C02: { type:"bar", data:{ labels:["Ventas","Costo","Margen","Gastos","EBITDA"], datasets:[{ data:[850,420,430,180,250], backgroundColor:["#1D9E75","#E24B4A","#1D9E75","#E24B4A","#185FA5"], borderRadius:3 }] }, options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{ x:{grid:{display:false},ticks:{font:{size:9},color:"#888"}}, y:{grid:{color:"rgba(128,128,128,0.1)"},ticks:{font:{size:9},color:"#888",callback:v=>"$"+v+"k"}} } } },
      C07: { type:"doughnut", data:{ labels:["A","B","C","Otros"], datasets:[{ data:[42,28,18,12], backgroundColor:["#1D9E75","#185FA5","#534AB7","#B4B2A9"], borderWidth:0 }] }, options:{ responsive:true, maintainAspectRatio:false, cutout:"65%", plugins:{legend:{display:false}} } },
      C08: { type:"bar", data:{ labels:["Q1","Q2","Q3","Q4"], datasets:[{ label:"A", data:[210,230,250,280], backgroundColor:"#1D9E75" },{ label:"B", data:[150,160,170,190], backgroundColor:"#185FA5" },{ label:"C", data:[90,100,110,120], backgroundColor:"#534AB7" }] }, options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{ x:{stacked:true,grid:{display:false},ticks:{font:{size:9},color:"#888"}}, y:{stacked:true,grid:{color:"rgba(128,128,128,0.1)"},ticks:{font:{size:9},color:"#888",callback:v=>"$"+v+"k"}} } } },
      C11: ()=>{
        const raw=[4200,-380,-1540,-820,-210,-185,-212];
        const labels=["Ing.","Desc.","C.V.","G.O.","D&A","G.F.","Imp."];
        let run=0; const bases=[],floats=[],cols=[];
        raw.forEach(v=>{ if(v>=0){bases.push(0);floats.push(v);run+=v;cols.push("#1D9E75");}else{bases.push(run+v);floats.push(-v);run+=v;cols.push("#E24B4A");}});
        return { type:"bar", data:{ labels, datasets:[{ data:bases, backgroundColor:"transparent", stack:"w" },{ data:floats, backgroundColor:cols, borderRadius:2, stack:"w" }] }, options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{ x:{stacked:true,grid:{display:false},ticks:{font:{size:9},color:"#888"}}, y:{stacked:true,grid:{color:"rgba(128,128,128,0.1)"},ticks:{font:{size:9},color:"#888",callback:v=>v>=1000?"$"+(v/1000).toFixed(1)+"M":"$"+v+"k"}} } } };
      },
      C15: { type:"doughnut", data:{ labels:["Logrado","Pendiente"], datasets:[{ data:[78,22], backgroundColor:["#1D9E75","rgba(128,128,128,0.15)"], borderWidth:0, circumference:180, rotation:270 }] }, options:{ responsive:true, maintainAspectRatio:false, cutout:"70%", plugins:{legend:{display:false}} } },
      C16: { type:"radar", data:{ labels:["Liquidez","Solvencia","Rentab.","Eficiencia","Riesgo"], datasets:[{ data:[72,85,63,78,55], borderColor:"#185FA5", backgroundColor:"rgba(55,138,221,0.1)", pointRadius:3 },{ data:[65,70,70,65,60], borderColor:"#888", backgroundColor:"rgba(136,135,128,0.05)", borderDash:[4,4], pointRadius:2 }] }, options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{ r:{min:0,max:100,ticks:{font:{size:8},stepSize:25},pointLabels:{font:{size:9}}} } } },
      C20: { type:"bar", data:{ labels:["Ene","Feb","Mar","Abr","May","Jun"], datasets:[{ type:"bar", data:[420,480,390,550,510,630], backgroundColor:"rgba(29,158,117,0.7)", borderRadius:3, yAxisID:"y" },{ type:"line", data:[28,31,25,34,30,36], borderColor:"#185FA5", pointRadius:3, tension:0.4, yAxisID:"y2" }] }, options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{ x:{grid:{display:false},ticks:{font:{size:9},color:"#888"}}, y:{grid:{color:"rgba(128,128,128,0.1)"},ticks:{font:{size:9},color:"#888",callback:v=>"$"+v+"k"}}, y2:{position:"right",grid:{display:false},ticks:{font:{size:9},color:"#888",callback:v=>v+"%"}} } } },
    };
    let cfg = configs[chartId];
    if (typeof cfg === "function") cfg = cfg();
    if (!cfg) {
      ctx.fillStyle = "#eee"; ctx.fillRect(0,0,canvasRef.current.width,canvasRef.current.height);
      ctx.fillStyle="#888"; ctx.font="12px sans-serif"; ctx.textAlign="center";
      ctx.fillText(CHARTS[chartId]?.name || chartId, canvasRef.current.width/2, canvasRef.current.height/2);
      return;
    }
    chartRef.current = new Chart(ctx, cfg);
    return () => { if(chartRef.current) chartRef.current.destroy(); };
  }, [chartId]);
  return <canvas ref={canvasRef} role="img" aria-label={"Vista previa "+chartId} style={{width:"100%",height:"100%"}} />;
}

export default function ChartSelector({ onSelect }) {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [previewId, setPreviewId] = useState(null);
  const TOTAL = QUESTIONS.length;

  const select = (qid, val) => setAnswers(prev => ({ ...prev, [qid]: val }));
  function next() {
    if (step < TOTAL - 1) setStep(s => s + 1);
    else {
      let res = DEFAULT;
      for (const rule of DECISION) { if (rule.match(answers)) { res = rule; break; } }
      setResult(res); setPreviewId(res.primary); setStep(TOTAL);
    }
  }
  function reset() { setStep(0); setAnswers({}); setResult(null); setPreviewId(null); }

  const q = step < TOTAL ? QUESTIONS[step] : null;
  const pc = result ? CHARTS[result.primary] : null;
  const alts = result ? result.alts.map(id => CHARTS[id]).filter(Boolean) : [];
  const stepLabels = ["Objetivo","Métricas","Audiencia","Temporal","Ítems","Resultado"];

  return (
    <div style={{fontFamily:"sans-serif",fontSize:14,color:"#1a1a1a"}}>
      <div style={{display:"flex",gap:6,flexWrap:"wrap",marginBottom:16}}>
        {stepLabels.map((l,i) => (
          <span key={i} style={{fontSize:11,padding:"3px 10px",borderRadius:99,
            background:i<step?"#E1F5EE":i===step?"#EEEDFE":"transparent",
            color:i<step?"#085041":i===step?"#3C3489":"#888",
            border:i>=step?"0.5px solid #ccc":"none",fontWeight:i===step?500:400}}>
            {i<step?"✓ ":""}{l}
          </span>
        ))}
      </div>

      {q && (
        <div style={{border:"0.5px solid #e0e0e0",borderRadius:12,padding:"1rem 1.25rem",marginBottom:12}}>
          <div style={{fontSize:11,color:"#888",marginBottom:6}}>{q.label}</div>
          <div style={{fontSize:15,fontWeight:500,marginBottom:14}}>{q.text}</div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(190px,1fr))",gap:8}}>
            {q.options.map(o => (
              <button key={o.val} onClick={() => select(q.id, o.val)} style={{
                background:answers[q.id]===o.val?"#EEEDFE":"#f5f5f5",
                border:answers[q.id]===o.val?"1.5px solid #AFA9EC":"0.5px solid #e0e0e0",
                borderRadius:8,padding:"8px 12px",textAlign:"left",fontSize:12,
                color:answers[q.id]===o.val?"#3C3489":"#1a1a1a",cursor:"pointer",
                fontWeight:answers[q.id]===o.val?500:400,lineHeight:1.4}}>{o.label}</button>
            ))}
          </div>
          <div style={{display:"flex",justifyContent:"space-between",marginTop:14}}>
            {step>0 ? <button onClick={()=>setStep(s=>s-1)} style={{fontSize:12,padding:"5px 14px",borderRadius:8,border:"0.5px solid #ccc",background:"transparent",cursor:"pointer"}}>← Anterior</button> : <span/>}
            <button onClick={next} disabled={!answers[q.id]} style={{fontSize:12,padding:"5px 16px",borderRadius:8,
              background:answers[q.id]?"#534AB7":"#f5f5f5",color:answers[q.id]?"#fff":"#888",border:"none",
              cursor:answers[q.id]?"pointer":"default",fontWeight:500}}>
              {step===TOTAL-1?"Ver recomendación →":"Siguiente →"}
            </button>
          </div>
        </div>
      )}

      {result && pc && (
        <div style={{border:"0.5px solid #e0e0e0",borderRadius:12,padding:"1.25rem"}}>
          <div style={{display:"flex",alignItems:"flex-start",gap:12,marginBottom:14}}>
            <div style={{width:48,height:48,borderRadius:10,background:pc.catBg,display:"flex",alignItems:"center",justifyContent:"center",fontSize:22,flexShrink:0}}>📊</div>
            <div style={{flex:1}}>
              <div style={{fontSize:11,color:"#888",marginBottom:3}}>Gráfico recomendado — Skill 051</div>
              <div style={{fontSize:18,fontWeight:500,marginBottom:5}}>{pc.name}</div>
              <span style={{background:pc.catBg,color:pc.catTxt,fontSize:11,fontWeight:500,padding:"2px 9px",borderRadius:99}}>{pc.cat}</span>
            </div>
            <div style={{textAlign:"right",flexShrink:0}}>
              <div style={{fontSize:11,color:"#888",marginBottom:2}}>Impacto ejecutivo</div>
              <div style={{color:"#854F0B",fontSize:14}}>{"★".repeat(pc.impact)+"☆".repeat(5-pc.impact)}</div>
              <div style={{fontSize:11,color:"#888"}}>{pc.impactLabel}</div>
            </div>
          </div>
          <div style={{background:"#f8f8f8",borderRadius:8,padding:"10px 12px",fontSize:13,color:"#666",lineHeight:1.6,marginBottom:14}}>{result.rationale}</div>
          <div style={{background:"#f8f8f8",borderRadius:8,padding:10,marginBottom:14}}>
            <div style={{fontSize:11,color:"#888",marginBottom:6}}>Vista previa — {CHARTS[previewId]?.name}</div>
            <div style={{height:160,position:"relative"}}><MiniChart chartId={previewId} /></div>
          </div>
          <div style={{borderTop:"0.5px solid #e0e0e0",paddingTop:12,marginBottom:14}}>
            <div style={{fontSize:11,color:"#888",marginBottom:8}}>Alternativas — clic para previsualizar</div>
            <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(150px,1fr))",gap:8}}>
              {alts.map(a => (
                <div key={a.id} onClick={()=>setPreviewId(a.id)} style={{
                  border:previewId===a.id?"1.5px solid #AFA9EC":"0.5px solid #e0e0e0",borderRadius:8,
                  padding:"8px 10px",cursor:"pointer",background:previewId===a.id?"#EEEDFE":"transparent"}}>
                  <div style={{fontSize:12,fontWeight:500,marginBottom:3,color:previewId===a.id?"#3C3489":"#1a1a1a"}}>{a.name}</div>
                  <div style={{fontSize:11,color:"#888",lineHeight:1.4}}>{a.use.substring(0,55)}...</div>
                </div>
              ))}
            </div>
          </div>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",gap:8}}>
            <button onClick={reset} style={{fontSize:12,padding:"6px 14px",borderRadius:8,border:"0.5px solid #ccc",background:"transparent",cursor:"pointer"}}>↺ Nueva consulta</button>
            {onSelect && (
              <button onClick={()=>onSelect(CHARTS[previewId] || pc)} style={{fontSize:12,padding:"6px 16px",borderRadius:8,background:"#534AB7",color:"#fff",border:"none",cursor:"pointer",fontWeight:500}}>
                ✓ Aplicar “{CHARTS[previewId]?.name}” al dashboard
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
