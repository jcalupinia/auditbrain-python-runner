import { useEffect, useState } from "react";
import { pceCxcAnalizar, pceCxcDescargarExcel, pceCxcLimites } from "../api.js";
import {
  FORMATOS_ACEPTADOS,
  SEGMENTOS,
  archivosDeFormatoNoLeible,
  archivosQueSuperanElLimite,
  bandasDeLaPolitica,
  carteraMedidaDe,
  coberturaDe,
  controlDeLaCohorte,
  cotasDeLaCorrida,
  evaluacionIndividualCompleta,
  factorProspectivoDeclarado,
  filasIncompletas,
  parametrosDeLaCorrida,
  sinMedirNoNeteado,
  tasaSustitutaCompleta,
  tramosVisibles,
} from "./pceCxc.js";
import "./pceCxc.css";

const CORTES = [
  { k: "a1", t: "Corte más antiguo (t-2)" },
  { k: "a2", t: "Corte intermedio (t-1)" },
  { k: "a3", t: "Corte actual" },
];

const TASA_SUSTITUTA_VACIA = { segmento: SEGMENTOS[0], banda: "", tasa: "", justificacion: "" };
const EVALUACION_VACIA = { segmento: SEGMENTOS[0], cliente: "", ecl: "", justificacion: "" };

const money = (v) =>
  v == null || isNaN(v)
    ? "—"
    : Number(v).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pct = (v) => (v == null || !isFinite(v) ? "—" : `${(v * 100).toFixed(2)} %`);

export default function PceCxcTool({ projectId }) {
  const [archivos, setArchivos] = useState({});
  const [fechas, setFechas] = useState({ a1: "", a2: "", a3: "" });
  const [datos, setDatos] = useState({
    entidad: "",
    ruc: "",
    materialidad: "",
    umbral_individual: "",
    eeff_nr: "",
    eeff_r: "",
    umbral_dias: 730,
    mayor_provision: "",
    // Política de deterioro del cliente, en % por banda. Lo que quede en
    // blanco NO se envía: el papel lo declara «sin comparar» en vez de
    // suponer un 0 % que el cliente nunca afirmó.
    politica: {},
    // Componente prospectivo (NIIF 9 5.5.17(c)). Vacío = 1,000, sin ajuste.
    factor_nr: "",
    factor_r: "",
    justificacion_prospectivo: "",
    // Tasas que sustituyen a la observada y saldos medidos uno por uno: el
    // backend los acepta desde siempre y la pantalla no tenía por dónde
    // ingresarlos.
    tasas_sustitutas: [],
    evaluaciones_individuales: [],
  });
  // Límites de carga del backend: se consultan al abrir la pantalla para
  // poder ANUNCIAR el máximo por archivo antes de que el auditor intente subir
  // uno grande, en vez de que se entere con un 413 después de la subida. La
  // cifra la fija `MAX_BYTES_POR_ARCHIVO` en el router; aquí no se reescribe.
  const [limites, setLimites] = useState(null);
  const [procesando, setProcesando] = useState(false);
  const [error, setError] = useState("");
  const [res, setRes] = useState(null);
  const [descargando, setDescargando] = useState(false);

  useEffect(() => {
    let vivo = true;
    // Si la consulta falla, la pantalla sigue funcionando sin anunciar el
    // límite: el backend lo aplica igual. Lo que no se puede es inventarlo.
    pceCxcLimites()
      .then((l) => vivo && setLimites(l))
      .catch(() => {});
    return () => {
      vivo = false;
    };
  }, []);

  const listoLosCortes = CORTES.every((c) => archivos[c.k] && fechas[c.k]);
  const archivosGrandes = archivosQueSuperanElLimite(
    CORTES.map((c) => archivos[c.k]),
    limites
  );
  // El backend solo lee libros de Excel modernos. Se dice ANTES de subir tres
  // archivos, no después: el 400 con la instrucción sigue estando, pero el
  // auditor no tiene por qué esperar la subida para enterarse.
  const archivosNoLeibles = archivosDeFormatoNoLeible(CORTES.map((c) => archivos[c.k]));

  // Filas repetibles (tasas sustitutas y evaluaciones individuales): se
  // añaden, se editan y se quitan sobre el mismo estado.
  const agregarFila = (campo, vacia) =>
    setDatos((d) => ({ ...d, [campo]: [...d[campo], { ...vacia }] }));
  const editarFila = (campo, i, clave, valor) =>
    setDatos((d) => ({
      ...d,
      [campo]: d[campo].map((f, j) => (j === i ? { ...f, [clave]: valor } : f)),
    }));
  const quitarFila = (campo, i) =>
    setDatos((d) => ({ ...d, [campo]: d[campo].filter((_, j) => j !== i) }));

  const bandas = bandasDeLaPolitica(datos.umbral_dias);
  // El factor prospectivo fuera de rango se dice aquí, junto al campo, y
  // bloquea el cálculo: es el mismo criterio que aplica el backend (400), no
  // una validación de pantalla que el servidor luego contradiga.
  let factorFueraDeRango = "";
  try {
    factorProspectivoDeclarado(datos);
  } catch (e) {
    factorFueraDeRango = e.message;
  }
  const listo =
    listoLosCortes &&
    !factorFueraDeRango &&
    archivosGrandes.length === 0 &&
    archivosNoLeibles.length === 0;
  const sustitutasIncompletas = filasIncompletas(datos.tasas_sustitutas, tasaSustitutaCompleta);
  const evaluacionesIncompletas = filasIncompletas(
    datos.evaluaciones_individuales,
    evaluacionIndividualCompleta
  );

  async function calcular() {
    setProcesando(true);
    setError("");
    setRes(null);
    try {
      const salida = await pceCxcAnalizar(
        CORTES.map((c) => archivos[c.k]),
        parametrosDeLaCorrida(
          datos,
          CORTES.map((c) => fechas[c.k]),
          projectId
        )
      );
      setRes(salida);
    } catch (e) {
      setError(`No se pudo calcular la matriz: ${e.message}`);
    } finally {
      setProcesando(false);
    }
  }

  async function descargar() {
    setDescargando(true);
    setError("");
    try {
      await pceCxcDescargarExcel(res.corrida_id);
    } catch (e) {
      setError(e.message);
    } finally {
      setDescargando(false);
    }
  }

  const exposicion = res?.exposicion;
  const matriz = res?.matriz;
  const individual = res?.individual;
  const conciliacion = res?.conciliacion;
  const sinMedirTotal = exposicion?.sin_medir ?? 0;
  const sinEstratificar = exposicion?.sin_estratificar ?? 0;
  const cartera = exposicion?.total ?? null;
  // La cartera medida y la cobertura las calcula el motor
  // (`motor.resumen_deterioro`): la pantalla las muestra, no las vuelve a deducir.
  const carteraMedida = carteraMedidaDe(res);
  const cobertura = coberturaDe(res);
  const controlCohorte = controlDeLaCohorte(res);
  // Cotas que actuaron: ninguna puede quedarse solo en el papel. Si el motor
  // recortó un importe, la pantalla lo dice con la cifra sin acotar a la vista.
  const cotas = cotasDeLaCorrida(res);
  // Lo sin medir se declara por su MAGNITUD y la cartera medida sale del NETO:
  // cuando difieren, la pantalla dice por qué antes de que el auditor concluya
  // que una de las dos cifras está mal. Lo mismo que imprime 08-Conciliacion.
  const avisoSinMedir = sinMedirNoNeteado(res);
  const filasMatriz = tramosVisibles(matriz?.tramos);
  const filasOmitidas = (matriz?.tramos?.length ?? 0) - filasMatriz.length;

  return (
    <div className="pce">
      <h2>Matriz de pérdidas crediticias esperadas · NIIF 9</h2>
      <p className="pce-sub">
        Enfoque simplificado. Las tasas se derivan del comportamiento observado de la cartera; el
        sistema no asume ninguna. Lo que falte para medir se reporta como pendiente, nunca como
        cero.
      </p>

      {limites?.mensaje_limite && (
        <div className="pce-hint">
          <b>Tamaño de los archivos:</b> {limites.mensaje_limite}
        </div>
      )}

      <div className="pce-grid">
        {CORTES.map((c) => (
          <div key={c.k} className="pce-slot">
            <div className="pce-tag">{c.t}</div>
            <input
              type="file"
              accept={FORMATOS_ACEPTADOS}
              onChange={(e) =>
                setArchivos({ ...archivos, [c.k]: e.target.files[0] || null })
              }
            />
            {archivos[c.k] && <span className="pce-filename">{archivos[c.k].name}</span>}
            <label>Fecha de corte</label>
            <input
              type="date"
              value={fechas[c.k]}
              onChange={(e) => setFechas({ ...fechas, [c.k]: e.target.value })}
            />
          </div>
        ))}
      </div>

      <div className="pce-grid">
        <label>
          Entidad auditada
          <input
            value={datos.entidad}
            onChange={(e) => setDatos({ ...datos, entidad: e.target.value })}
          />
        </label>
        <label>
          RUC de la entidad
          <input
            value={datos.ruc}
            placeholder="1791240154001"
            onChange={(e) => setDatos({ ...datos, ruc: e.target.value })}
          />
        </label>
        <label>
          Materialidad de desempeño
          <input
            type="number"
            value={datos.materialidad}
            onChange={(e) => setDatos({ ...datos, materialidad: e.target.value })}
          />
        </label>
        <label>
          Umbral de evaluación individual
          <input
            type="number"
            value={datos.umbral_individual}
            onChange={(e) => setDatos({ ...datos, umbral_individual: e.target.value })}
          />
        </label>
        <label>
          Cartera según EEFF · no relacionados
          <input
            type="number"
            value={datos.eeff_nr}
            onChange={(e) => setDatos({ ...datos, eeff_nr: e.target.value })}
          />
        </label>
        <label>
          Cartera según EEFF · relacionados
          <input
            type="number"
            value={datos.eeff_r}
            onChange={(e) => setDatos({ ...datos, eeff_r: e.target.value })}
          />
        </label>
        <label>
          Incumplimiento (días sin cobro)
          <input
            type="number"
            value={datos.umbral_dias}
            onChange={(e) => setDatos({ ...datos, umbral_dias: e.target.value })}
          />
        </label>
      </div>

      <label className="pce-declaracion">
        Mayores de la provisión de los tres ejercicios — referencia y conclusión sobre los castigos
        <textarea
          rows={2}
          placeholder="P. ej.: mayor 2.1.3.01 de 2022, 2023 y 2024 (PT B-2); castigos por USD 340, inmateriales frente a la cartera."
          value={datos.mayor_provision}
          onChange={(e) => setDatos({ ...datos, mayor_provision: e.target.value })}
        />
        <span>
          El método de permanencia supone que lo que desapareció de la cartera se cobró. Eso solo
          vale si los castigos del período fueron inmateriales, y eso se demuestra con los mayores
          de la provisión. Si se deja vacío, queda declarado como pendiente.
        </span>
      </label>

      <fieldset className="pce-politica">
        <legend>Política de deterioro del cliente (% por banda)</legend>
        <p className="pce-hint">
          Es el porcentaje que la entidad provisiona hoy en cada banda, según su política escrita.
          La banda que se deje en blanco queda <b>sin comparar</b> en el papel de trabajo y se
          declara como pendiente: el sistema no la supone en 0 %, porque eso acusaría al cliente de
          no provisionar una banda que nadie le preguntó.
        </p>
        <div className="pce-grid">
          {bandas.map((banda) => (
            <label key={banda}>
              {banda}
              <input
                type="number"
                step="0.01"
                min="0"
                max="100"
                placeholder="sin declarar"
                value={datos.politica[banda] ?? ""}
                onChange={(e) =>
                  setDatos({
                    ...datos,
                    politica: { ...datos.politica, [banda]: e.target.value },
                  })
                }
              />
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="pce-politica">
        <legend>Componente prospectivo (NIIF 9 5.5.17 c)</legend>
        <p className="pce-hint">
          Factor por el que se multiplica la tasa observada de cada segmento: <b>1,000 es sin
          ajuste</b>, 1,100 es un 10 % más de pérdida esperada. La norma exige que el ajuste esté
          sustentado (B5.5.51-52), así que <b>sin justificación escrita el factor no se aplica</b>{" "}
          y queda el hallazgo «Ausencia del componente prospectivo». Un factor que lleve la tasa
          sobre el 100 % se acota al importe en libros bruto y el papel lo declara. Un factor
          de <b>0,000 no se admite</b>: no es un ajuste, anula la pérdida esperada de todas las
          bandas cualquiera que sea su tasa observada.
        </p>
        {factorFueraDeRango && <div className="pce-msg pce-bad">{factorFueraDeRango}</div>}
        <div className="pce-grid">
          <label>
            Factor · no relacionados
            <input
              type="number"
              step="0.001"
              min="0.001"
              placeholder="1,000"
              value={datos.factor_nr}
              onChange={(e) => setDatos({ ...datos, factor_nr: e.target.value })}
            />
          </label>
          <label>
            Factor · relacionados
            <input
              type="number"
              step="0.001"
              min="0.001"
              placeholder="1,000"
              value={datos.factor_r}
              onChange={(e) => setDatos({ ...datos, factor_r: e.target.value })}
            />
          </label>
        </div>
        <label className="pce-declaracion">
          Justificación del ajuste prospectivo — variables, fuente y traslación al factor
          <textarea
            rows={2}
            placeholder="P. ej.: proyección del PIB del sector del BCE (-2,1 % para 2026) trasladada a la tasa de la banda vencida con la elasticidad observada 2019-2024 (PT C-3)."
            value={datos.justificacion_prospectivo}
            onChange={(e) => setDatos({ ...datos, justificacion_prospectivo: e.target.value })}
          />
        </label>
      </fieldset>

      <fieldset className="pce-politica">
        <legend>Tasas sustitutas por banda (opcional)</legend>
        <p className="pce-hint">
          Solo para las bandas sin historia propia en la cohorte, o cuya tasa observada no es
          representativa. La tasa sustituta <b>manda sobre la observada</b> y exige justificación
          escrita: sin ella no se envía y la banda se mide con la observada o queda sin medir.
        </p>
        {datos.tasas_sustitutas.map((fila, i) => (
          <div key={i} className="pce-fila-editable">
            <label>
              Segmento
              <select
                value={fila.segmento}
                onChange={(e) => editarFila("tasas_sustitutas", i, "segmento", e.target.value)}
              >
                {SEGMENTOS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Banda
              <select
                value={fila.banda}
                onChange={(e) => editarFila("tasas_sustitutas", i, "banda", e.target.value)}
              >
                <option value="">(elija una banda)</option>
                {bandas.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Tasa (%)
              <input
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={fila.tasa}
                onChange={(e) => editarFila("tasas_sustitutas", i, "tasa", e.target.value)}
              />
            </label>
            <label className="pce-ancha">
              Justificación
              <input
                value={fila.justificacion}
                placeholder="Analogía con el segmento comparable y referencia del papel"
                onChange={(e) =>
                  editarFila("tasas_sustitutas", i, "justificacion", e.target.value)
                }
              />
            </label>
            <button type="button" className="pce-quitar" onClick={() => quitarFila("tasas_sustitutas", i)}>
              Quitar
            </button>
          </div>
        ))}
        <button
          type="button"
          className="pce-btn pce-btn-sec"
          onClick={() => agregarFila("tasas_sustitutas", TASA_SUSTITUTA_VACIA)}
        >
          Añadir una tasa sustituta
        </button>
        {sustitutasIncompletas > 0 && (
          <div className="pce-msg pce-warn">
            {sustitutasIncompletas} tasa(s) sustituta(s) quedaron incompletas y <b>no se enviarán</b>:
            hacen falta el segmento, la banda, la tasa y la justificación escrita.
          </div>
        )}
      </fieldset>

      <fieldset className="pce-politica">
        <legend>Evaluaciones individuales medidas por el auditor (opcional)</legend>
        <p className="pce-hint">
          Pérdida esperada que el auditor midió uno por uno (litigio, concurso, acuerdo de pago).
          Sustituye a la medición provisional con la tasa de la matriz para ese cliente y cubre
          todo su saldo, así que exige justificación escrita. El importe va en dólares y no puede
          ser negativo ni superar el saldo del cliente; un <b>0,00 declarado sí viaja</b>: «medí y
          no hay pérdida» no es lo mismo que «no se midió».
        </p>
        {datos.evaluaciones_individuales.map((fila, i) => (
          <div key={i} className="pce-fila-editable">
            <label>
              Segmento
              <select
                value={fila.segmento}
                onChange={(e) =>
                  editarFila("evaluaciones_individuales", i, "segmento", e.target.value)
                }
              >
                {SEGMENTOS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Cliente (tal como aparece en el archivo)
              <input
                value={fila.cliente}
                onChange={(e) =>
                  editarFila("evaluaciones_individuales", i, "cliente", e.target.value)
                }
              />
            </label>
            <label>
              Pérdida esperada (USD)
              <input
                type="number"
                step="0.01"
                min="0"
                value={fila.ecl}
                onChange={(e) => editarFila("evaluaciones_individuales", i, "ecl", e.target.value)}
              />
            </label>
            <label className="pce-ancha">
              Justificación
              <input
                value={fila.justificacion}
                placeholder="Sustento de la estimación y referencia del papel"
                onChange={(e) =>
                  editarFila("evaluaciones_individuales", i, "justificacion", e.target.value)
                }
              />
            </label>
            <button
              type="button"
              className="pce-quitar"
              onClick={() => quitarFila("evaluaciones_individuales", i)}
            >
              Quitar
            </button>
          </div>
        ))}
        <button
          type="button"
          className="pce-btn pce-btn-sec"
          onClick={() => agregarFila("evaluaciones_individuales", EVALUACION_VACIA)}
        >
          Añadir una evaluación individual
        </button>
        {evaluacionesIncompletas > 0 && (
          <div className="pce-msg pce-warn">
            {evaluacionesIncompletas} evaluación(es) individual(es) quedaron incompletas y{" "}
            <b>no se enviarán</b>: hacen falta el segmento, el cliente, el importe y la
            justificación escrita.
          </div>
        )}
      </fieldset>

      <button className="pce-btn" disabled={!listo || procesando} onClick={calcular}>
        Calcular la matriz
      </button>
      {!listoLosCortes && !procesando && (
        <div className="pce-hint">Suba los tres cortes con su fecha para habilitar el cálculo.</div>
      )}
      {archivosGrandes.length > 0 && !procesando && (
        <div className="pce-msg pce-bad">
          {archivosGrandes.length === 1 ? "Este archivo supera" : "Estos archivos superan"} el
          límite de {limites.max_mb_por_archivo} MB por archivo:{" "}
          {archivosGrandes.map((a) => `${a.nombre} (${a.mb} MB)`).join(", ")}. {limites.mensaje_limite}
        </div>
      )}
      {archivosNoLeibles.length > 0 && !procesando && (
        <div className="pce-msg pce-bad">
          {archivosNoLeibles.length === 1
            ? "Este archivo no es un libro de Excel"
            : "Estos archivos no son libros de Excel"}{" "}
          ({FORMATOS_ACEPTADOS}): {archivosNoLeibles.map((a) => a.nombre).join(", ")}. Ábralo en
          Excel y guárdelo con «Guardar como → Libro de Excel (*.xlsx)» antes de subirlo.
        </div>
      )}
      {listoLosCortes && factorFueraDeRango && !procesando && (
        <div className="pce-msg pce-bad">{factorFueraDeRango}</div>
      )}
      {procesando && <div className="pce-msg pce-info">Procesando los tres cortes…</div>}
      {error && <div className="pce-msg pce-bad">{error}</div>}

      {res && (
        <div className="pce-res">
          <div className="pce-preliminar">
            Papel de trabajo PRELIMINAR — pendiente de revisión y aprobación del Socio responsable.
          </div>

          <div className="pce-kpis">
            <div>
              <span>Cartera total</span>
              <b>{money(cartera)}</b>
            </div>
            <div>
              {/* Misma cifra y misma etiqueta que 08-Conciliacion del Excel. */}
              <span>Cartera medida</span>
              <b>{money(carteraMedida)}</b>
            </div>
            <div className={sinMedirTotal > 0.005 ? "pce-kpi-bad" : ""}>
              <span>Sin medir</span>
              <b>{money(sinMedirTotal)}</b>
            </div>
            <div>
              <span>Pérdida esperada (ECL)</span>
              <b>{money(res.ecl_total)}</b>
            </div>
            <div>
              <span>Cobertura sobre lo medido</span>
              <b>{pct(cobertura)}</b>
            </div>
            <div>
              <span>Trazabilidad de la cohorte</span>
              <b>{pct(res.trazabilidad)}</b>
            </div>
          </div>

          {cotas.map((cota) => (
            <div key={cota.clave} className="pce-msg pce-bad">
              <b>Acotamiento aplicado:</b> {cota.texto}
            </div>
          ))}
          {sinMedirTotal > 0.005 && (
            <div className="pce-msg pce-bad">
              Quedan {money(sinMedirTotal)} sin medir por falta de tasa histórica en su banda. Una
              tasa cero por ausencia de historia no es evidencia de ausencia de pérdida.
            </div>
          )}
          {avisoSinMedir && <div className="pce-msg pce-warn">{avisoSinMedir}</div>}
          {sinEstratificar > 0.005 && (
            <div className="pce-msg pce-warn">
              {money(sinEstratificar)} de los estados financieros no se pudo ubicar en ningún
              segmento del análisis de antigüedad cargado: revise si falta cartera por cargar.
            </div>
          )}
          {controlCohorte && !controlCohorte.consistente && (
            <div className="pce-msg pce-bad">
              <b>Control del corte intermedio:</b> {controlCohorte.total} documento(s) de la cohorte
              siguen una trayectoria imposible entre los tres cortes ({controlCohorte.ejemplos}):
              desaparecen en el corte intermedio y reaparecen en el actual, o su saldo crece sin
              facturación nueva. {money(controlCohorte.importe)} del remanente que alimenta las
              tasas provienen de esos documentos.
            </div>
          )}
          {controlCohorte && controlCohorte.consistente && (
            <div className="pce-msg pce-info">
              <b>Control del corte intermedio:</b> los {controlCohorte.documentos} documentos de la
              cohorte son coherentes entre los tres cortes; {controlCohorte.vivos} seguían vivos en
              t-1 ({pct(controlCohorte.permanencia)}).
            </div>
          )}
          {conciliacion && conciliacion.cuadra != null && !conciliacion.cuadra && (
            <div className="pce-msg pce-warn">
              La cartera analizada no concilia con el saldo contable: diferencia de{" "}
              {money(conciliacion.diferencia)}.
            </div>
          )}

          <h3>Matriz por banda</h3>
          <table className="pce-tabla">
            <thead>
              <tr>
                <th>Segmento</th>
                <th>Banda</th>
                <th>Exposición</th>
                <th>Tasa</th>
                <th>Pérdida esperada</th>
              </tr>
            </thead>
            <tbody>
              {filasMatriz.map((t, i) => (
                <tr key={`${t.segmento}-${t.tramo}-${i}`} className={t.ecl == null ? "pce-sinmedir" : ""}>
                  <td>{t.segmento}</td>
                  <td>{t.tramo}</td>
                  <td>{money(t.exposicion)}</td>
                  <td>{t.tasa_perdida == null ? "sin medir" : pct(t.tasa_perdida)}</td>
                  <td>{t.ecl == null ? "sin medir" : money(t.ecl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {filasOmitidas > 0 && (
            <div className="pce-nota-tabla">
              No se listan {filasOmitidas} combinaciones de segmento × banda por estar sin
              exposición ni tasa observada: no son una pérdida cero medida, son combinaciones que
              no existen en la cartera del corte.
            </div>
          )}

          {individual && individual.casos.length > 0 && (
            <>
              <h3>Evaluación individual</h3>
              <table className="pce-tabla">
                <thead>
                  <tr>
                    <th>Cliente</th>
                    <th>Saldo</th>
                    <th>Pérdida esperada</th>
                    <th>Sustento</th>
                  </tr>
                </thead>
                <tbody>
                  {individual.casos.map((c, i) => (
                    <tr key={i} className={c.saldo_sin_tasa > 0.005 ? "pce-sinmedir" : ""}>
                      <td>{c.identificacion}</td>
                      <td>{money(c.saldo)}</td>
                      <td>{money(c.ecl)}</td>
                      <td>{c.sustento}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {res.hallazgos && res.hallazgos.length > 0 && (
            <>
              <h3>Hallazgos</h3>
              <ul className="pce-hallazgos">
                {res.hallazgos.map((h, i) => (
                  <li key={i}>
                    <b>
                      [{h.riesgo}] {h.titulo}
                    </b>
                    <span>{h.condicion}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {res.pendientes.length > 0 && (
            <div className="pce-msg pce-warn">
              <b>Pendientes que impiden concluir:</b>
              <ul>
                {res.pendientes.map((p, i) => (
                  <li key={i}>
                    {p.variable} — {p.efecto} ({p.responsable})
                  </li>
                ))}
              </ul>
            </div>
          )}

          {res.corrida_id != null && (
            <button className="pce-btn" disabled={descargando} onClick={descargar}>
              {descargando ? "Descargando…" : "Descargar el papel de trabajo"}
            </button>
          )}
          <div className="pce-nota">
            Papel de trabajo preliminar. Requiere revisión y aprobación del Socio responsable antes
            de usarse como conclusión de auditoría.
          </div>
        </div>
      )}
    </div>
  );
}
