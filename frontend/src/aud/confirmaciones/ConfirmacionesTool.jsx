import {useEffect, useState} from 'react';
import '../of/ofWorkspace.css';
import './confirmaciones.css';
import {loadContext, extractFile, processConfirmaciones, downloadConfirmaciones} from './api.js';
import {TYPE_KEYS, TYPE_LABEL, METHODS, LANGUAGES, mapSample, emptyItem, ITEM_FIELDS, FIELD_HELP} from './logic.js';

const today = new Date().toISOString().slice(0, 10);
const initialCtx = {client: '', client_ruc: '', country: 'Ecuador', currency: 'USD', year: '', cutoff: '',
  visit: '', preparer: '', reviewer: '', firm: '', signatory: '', signatory_role: '',
  auditor_email: '', auditor_address: '', auditor_phone: '', response_deadline: '', request_round: 'primera',
  language: 'es', place: '', letter_date: today, period_start: ''};

export default function ConfirmacionesTool({projectId, sharedContext, onShareContext}) {
  const [ctx, setCtx] = useState({...initialCtx, ...sharedContext});
  const [types, setTypes] = useState(TYPE_KEYS.map(k => ({key: k, label: TYPE_LABEL[k]})));
  const [defaultMethod, setDefaultMethod] = useState('');
  const [responseSlip, setResponseSlip] = useState(false);
  const [langs, setLangs] = useState(LANGUAGES);
  const [source, setSource] = useState(null);      // {tables, mapping, tableIndex, name}
  const [items, setItems] = useState([]);
  const [ledger, setLedger] = useState({});         // {type: saldo}
  const [tolerance, setTolerance] = useState('0.01');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');

  useEffect(() => {
    let cancelled = false;
    if (projectId) loadContext(projectId).then(c => {
      if (cancelled) return;
      if (Array.isArray(c.types) && c.types.length) setTypes(c.types.map(t => ({key: t.key, label: t.label})));
      if (c.languages) setLangs(Object.entries(c.languages));
      if (!sharedContext) setCtx(p => ({...p, client: c.client, client_ruc: c.client_ruc || '', year: c.year, cutoff: c.cutoff, preparer: c.preparer}));
    }).catch(e => !cancelled && setError(e.message));
    return () => {cancelled = true;};
  }, [projectId]);

  const invalidate = () => {setResult(null); setNotice('');};
  const setC = (k, v) => {invalidate(); setCtx(p => ({...p, [k]: v}));};
  const action = async fn => {setError(''); setBusy(true); try {await fn();} catch (e) {setError(e.message);} finally {setBusy(false);}};

  function guessMapping(table) {
    const norm = h => String(h || '').trim().toLowerCase();
    const find = (...keys) => table.headers.findIndex(h => keys.some(k => norm(h).includes(k)));
    return {id: find('id', 'código', 'codigo'), type: find('tipo', 'rubro'), entity: find('entidad', 'nombre', 'razón', 'razon'),
      contact_name: find('contacto', 'atención', 'atencion'), contact_email: find('correo', 'email', 'e-mail'),
      contact_address: find('direcc'), account_ref: find('cuenta', 'póliza', 'poliza', 'referencia'),
      amount: find('saldo', 'importe', 'monto', 'valor'), method: find('método', 'metodo'),
      reference: find('mayor', 'origen'), notes: find('nota', 'observ')};
  }

  async function upload(file) {
    if (!file) return;
    invalidate();
    await action(async () => {
      const extracted = await extractFile(projectId, file);
      if (!extracted.tables || !extracted.tables.length) throw Error('El archivo no contiene una tabla. Cargue XLSX o CSV con encabezados.');
      setSource({...extracted, tableIndex: 0, mapping: guessMapping(extracted.tables[0])});
    });
  }

  function importSample() {
    try {
      const next = mapSample(source.tables[source.tableIndex], source.mapping);
      invalidate(); setItems(next); setNotice(`${next.length} registros importados. Revise la muestra antes de procesar.`); setError('');
    } catch (e) {setError(e.message);}
  }

  const editItem = (i, k, v) => {invalidate(); setItems(items.map((it, j) => j === i ? {...it, [k]: v} : it));};
  const addItem = () => {invalidate(); setItems([...items, emptyItem()]);};
  const removeItem = i => {invalidate(); setItems(items.filter((_, j) => j !== i));};

  const payload = () => ({
    context: {...ctx, year: Number(ctx.year) || ctx.year},
    defaults: {...(defaultMethod ? {method: defaultMethod} : {}), include_response_slip: responseSlip},
    items: items.map(it => ({...it, method: it.method || undefined, amount: it.amount || undefined})),
    coverage: Object.entries(ledger).filter(([, v]) => v !== '').map(([type, ledger_balance]) => ({type, ledger_balance})),
    tolerance,
  });

  const process = () => action(async () => {
    if (!items.length) throw Error('Cargue o agregue al menos un elemento en la muestra.');
    const r = await processConfirmaciones(projectId, payload());
    setResult(r); onShareContext && onShareContext(ctx);
    setNotice(`${r.totals.count} cartas preparadas · ${r.totals.with_email} con correo, ${r.totals.without_email} sin correo.`);
  });
  const download = fmt => action(() => downloadConfirmaciones(projectId, payload(), fmt));

  const ctxField = (k, label, type = 'text') => (
    <label key={k}>{label}
      <input type={type} value={ctx[k] ?? ''} onChange={e => setC(k, e.target.value)} />
      {FIELD_HELP[k] && <small className="cf-help">{FIELD_HELP[k]}</small>}
    </label>);

  if (!projectId) return <p>Seleccione un proyecto antes de abrir Confirmaciones.</p>;

  return (
    <div className="cf-tool of-ws">
      <header className="pc-panel-h"><div><span className="pc-code">CIRC</span>
        <h2>Confirmaciones de saldos</h2></div>
        <span className="pc-panel-m">{result ? 'PREPARADO · BORRADOR' : 'PREPARACIÓN'}</span></header>
      <p className="cf-note">Auditoría externa → Análisis → Confirmaciones de saldos (junto al motor de balances).
        Las cartas y resultados permanecen en esta pestaña: descargue antes de salir. El servidor procesa sin
        conservarlos y no envía correo por sí mismo.</p>
      {error && <p className="cf-error" role="alert">{error}</p>}
      {notice && <p className="cf-ok">{notice}</p>}

      <section className="cf-card"><h3>1 · Ficha del encargo</h3>
        <div className="cf-grid">
          {ctxField('client', 'Cliente')}{ctxField('client_ruc', 'RUC / ID fiscal')}
          {ctxField('country', 'País')}{ctxField('currency', 'Moneda (3 letras)')}
          {ctxField('year', 'Ejercicio', 'number')}{ctxField('cutoff', 'Corte', 'date')}
          <label>Visita<select value={ctx.visit} onChange={e => setC('visit', e.target.value)}>
            <option value="">—</option><option>Preliminar</option><option>Final</option></select></label>
          <label>Firma auditora<select value={ctx.firm} onChange={e => setC('firm', e.target.value)}>
            <option value="">—</option><option value="audit_consulting">AuditConsulting</option>
            <option value="partner_auditing">Partner Auditing</option></select></label>
          {ctxField('preparer', 'Preparado por')}{ctxField('reviewer', 'Revisado por')}
          {ctxField('signatory', 'Firmante del cliente')}{ctxField('signatory_role', 'Cargo del firmante')}
          {ctxField('auditor_email', 'Correo del auditor (respuestas)')}
          {ctxField('auditor_address', 'Dirección del auditor')}{ctxField('auditor_phone', 'Teléfono del auditor')}
          {ctxField('response_deadline', 'Fecha límite de respuesta', 'date')}
          <label>Vuelta<select value={ctx.request_round} onChange={e => setC('request_round', e.target.value)}>
            <option value="primera">Primera</option><option value="segunda">Segunda</option></select></label>
          <label>Idioma de las cartas<select value={ctx.language} onChange={e => setC('language', e.target.value)}>
            {langs.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          {ctxField('place', 'Ciudad de emisión')}{ctxField('letter_date', 'Fecha de la carta', 'date')}
          {ctxField('period_start', 'Inicio del período', 'date')}
          <label>Método por defecto<select value={defaultMethod} onChange={e => {invalidate(); setDefaultMethod(e.target.value);}}>
            {METHODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
            <small className="cf-help">{FIELD_HELP.method}</small></label>
          <label className="cf-check"><input type="checkbox" checked={responseSlip}
            onChange={e => {invalidate(); setResponseSlip(e.target.checked);}} /> Incluir recuadro de respuesta
            <small className="cf-help">El formato de la firma no lo usa; actívelo si desea un desprendible.</small></label>
        </div>
      </section>

      <section className="cf-card"><h3>2 · Muestra a circularizar</h3>
        <p>Suba el listado (XLSX/CSV) con: identificador, tipo, entidad, correo y saldo. Luego revise y procese.</p>
        <input type="file" accept=".xlsx,.csv,.xml,.txt" onChange={e => upload(e.target.files[0])} disabled={busy} />
        {source && <div className="cf-map">
          <p><b>{source.name}</b> — asigne columnas:</p>
          <div className="cf-grid">{ITEM_FIELDS.map(k =>
            <label key={k}>{k}<select value={source.mapping[k] ?? -1}
              onChange={e => setSource({...source, mapping: {...source.mapping, [k]: Number(e.target.value)}})}>
              <option value={-1}>—</option>
              {source.tables[source.tableIndex].headers.map((h, i) => <option key={i} value={i}>{h || `col ${i}`}</option>)}
            </select></label>)}</div>
          <button className="btn" onClick={importSample} disabled={busy}>Importar muestra</button>
        </div>}
        <div className="cf-actions"><button className="btn" onClick={addItem}>+ Agregar elemento</button></div>
        {items.length > 0 && <div className="cf-scroll"><table className="cf-table"><thead><tr>
          <th>ID</th><th>Tipo</th><th>Entidad</th><th>Correo</th><th>Ref.</th><th>Saldo</th><th>Método</th><th></th></tr></thead>
          <tbody>{items.map((it, i) => <tr key={i}>
            <td><input value={it.id} onChange={e => editItem(i, 'id', e.target.value)} /></td>
            <td><select value={it.type} onChange={e => editItem(i, 'type', e.target.value)}>
              {types.map(t => <option key={t.key} value={t.key}>{t.label}</option>)}</select></td>
            <td><input value={it.entity} onChange={e => editItem(i, 'entity', e.target.value)} /></td>
            <td><input value={it.contact_email} onChange={e => editItem(i, 'contact_email', e.target.value)} /></td>
            <td><input value={it.account_ref} onChange={e => editItem(i, 'account_ref', e.target.value)} /></td>
            <td><input value={it.amount} onChange={e => editItem(i, 'amount', e.target.value)} /></td>
            <td><select value={it.method} onChange={e => editItem(i, 'method', e.target.value)}>
              {METHODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></td>
            <td><button className="cf-x" onClick={() => removeItem(i)} title="Quitar">✕</button></td>
          </tr>)}</tbody></table></div>}
      </section>

      <section className="cf-card"><h3>3 · Cobertura (opcional)</h3>
        <p>Saldo del mayor por rubro para medir cobertura de la muestra.</p>
        <div className="cf-grid">{types.map(t =>
          <label key={t.key}>{t.label}
            <input value={ledger[t.key] ?? ''} placeholder="saldo mayor"
              onChange={e => {invalidate(); setLedger({...ledger, [t.key]: e.target.value});}} /></label>)}
          <label>Tolerancia<input value={tolerance} onChange={e => {invalidate(); setTolerance(e.target.value);}} /></label>
        </div>
      </section>

      <section className="cf-card"><h3>4 · Procesar y descargar</h3>
        <div className="cf-actions">
          <button className="btn btn-primary" onClick={process} disabled={busy}>Procesar</button>
          <button className="btn" onClick={() => download('docx')} disabled={busy || !result}>Cartas (Word)</button>
          <button className="btn" onClick={() => download('xlsx')} disabled={busy || !result}>Registro (Excel)</button>
          <button className="btn" onClick={() => download('html')} disabled={busy || !result}>Vista + envío (HTML)</button>
        </div>
        {result && <div className="cf-summary">
          <p><b>{result.totals.count}</b> cartas · circularizado {result.context.currency} {result.totals.total_sampled} ·
            {' '}con correo {result.totals.with_email} / sin correo {result.totals.without_email}</p>
          <ul>{result.letters.slice(0, 30).map(l => <li key={l.id}>
            <b>{l.id}</b> · {l.type_label} — {l.entity} <span className="cf-tag">{l.method}</span></li>)}</ul>
          <p className="cf-note">Descargue el HTML para enviar cada carta desde el correo del auditor, o el Word para
            adjuntarlas. El auditor conserva el control del envío y de la respuesta (NIA 505).</p>
        </div>}
      </section>
    </div>);
}
