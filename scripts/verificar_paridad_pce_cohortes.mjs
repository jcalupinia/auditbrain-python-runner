/* Verificador de paridad del motor de PCE por cohortes (AUD-ECL-01).
 *
 * Replica FIEL el motor de cálculo del artefacto de referencia
 * `AuditBrain_NIIF9_Matriz_PCE` (las funciones num/toDate/parseYear/run,
 * sin el acoplamiento al DOM) y emite en JSON las cifras del recálculo.
 * El verificador Python (`verificar_paridad_pce_cohortes.py`) corre el
 * procesador del repo sobre el MISMO dataset y compara dígito a dígito.
 *
 * Uso:  node scripts/verificar_paridad_pce_cohortes.mjs <fixture.json>
 * El fixture: {corte, params:{...}, cartera_t2:[{doc,cliente,tipo,vence,saldo}],
 *              cartera_t1:[...], cartera_t:[...], castigos:[{doc,importe}]}
 */
import fs from 'node:fs';

// --- helpers verbatim del artefacto ---
const num = v => { if (v == null || v === '') return 0; const n = parseFloat(String(v).replace(/[^0-9.\-]/g, '')); return isNaN(n) ? 0 : n; };
function toDate(v) {
  if (v instanceof Date && !isNaN(v)) return v;
  if (v == null || v === '') return null;
  if (typeof v === 'number') { const d = new Date(Date.UTC(1899, 11, 30) + v * 864e5); return isNaN(d) ? null : d; }
  const s = String(v).trim();
  let m = s.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})$/);
  if (m) { let y = +m[3]; if (y < 100) y += 2000; return new Date(y, +m[2] - 1, +m[1]); }
  m = s.match(/^(\d{4})[\/\-.](\d{1,2})[\/\-.](\d{1,2})/);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
  const d = new Date(s); return isNaN(d) ? null : d;
}
function bandOf(dias, bands) { for (const b of bands) if (dias >= b.d && dias <= b.h) return b.n; return bands[bands.length - 1].n; }
const esDesdoblar = v => ['sí', 'si', '1', 'true', 's'].includes(String(v == null ? 'Sí' : v).trim().toLowerCase());

function parseYear(rows, corte, relKey) {
  const out = []; let dup = 0, bad = 0; const seen = new Set();
  for (const r of rows || []) {
    const doc = String(r.doc == null ? '' : r.doc).trim();
    const saldo = num(r.saldo);
    const fven = toDate(r.vence);
    if (!doc || !fven || Math.abs(saldo) < 0.005) { if (doc || saldo) bad++; continue; }
    if (seen.has(doc)) { dup++; continue; }
    seen.add(doc);
    const tipoRaw = String(r.tipo == null ? '' : r.tipo).toUpperCase();
    const rel = tipoRaw.includes(relKey) && !tipoRaw.includes('NO-' + relKey) && !tipoRaw.includes('NO ' + relKey);
    const dias = Math.round((corte - fven) / 864e5);
    out.push({ doc, saldo, fven, dias, seg: rel ? 'RELACIONADOS' : 'NO-RELACIONADOS' });
  }
  return { rows: out, dup, bad };
}

function run(fx) {
  const P = fx.params, relKey = String(P.relKey || 'RELACIONAD').toUpperCase();
  const c3 = new Date(fx.corte + 'T00:00:00');
  const cort = {
    a3: c3, a2: new Date(c3.getFullYear() - 1, c3.getMonth(), c3.getDate()),
    a1: new Date(c3.getFullYear() - 2, c3.getMonth(), c3.getDate()),
  };
  const defD = +P.umbral || 730;
  let bands = [
    { n: 'Por vencer', d: -999999, h: 0 }, { n: '0 a 30 días', d: 1, h: 30 }, { n: '31 a 60 días', d: 31, h: 60 },
    { n: '61 a 90 días', d: 61, h: 90 }, { n: '91 a 180 días', d: 91, h: 180 }, { n: '181 a 360 días', d: 181, h: 360 },
    { n: 'Más de 360 días', d: 361, h: 999999 },
  ];
  if (esDesdoblar(P.desdoblar)) {
    const last = bands[bands.length - 1];
    if (last.h > defD && last.d < defD) {
      bands.pop();
      bands.push({ n: `${last.d} d — ${Math.round(defD / 365)} años`, d: last.d, h: defD });
      bands.push({ n: `Más de ${Math.round(defD / 365)} años`, d: defD + 1, h: 999999 });
    }
  }
  const BN = bands.map(b => b.n), SEG = ['NO-RELACIONADOS', 'RELACIONADOS'];
  const D = {};
  D.a1 = parseYear(fx.cartera_t2, cort.a1, relKey);
  D.a2 = parseYear(fx.cartera_t1, cort.a2, relKey);
  D.a3 = parseYear(fx.cartera_t, cort.a3, relKey);
  for (const k of ['a1', 'a2', 'a3']) D[k].rows.forEach(r => r.b = bandOf(r.dias, bands));

  const set3 = new Set(D.a3.rows.map(r => r.doc));
  const hits = D.a1.rows.filter(r => set3.has(r.doc)).length;
  const traz = D.a1.rows.length ? hits / D.a1.rows.length : 0;

  const expFile = {}; SEG.forEach(s => { expFile[s] = {}; BN.forEach(b => expFile[s][b] = 0); });
  D.a3.rows.forEach(r => expFile[r.seg][r.b] += r.saldo);
  const expFileSeg = {}; SEG.forEach(s => expFileSeg[s] = BN.reduce((a, b) => a + expFile[s][b], 0));

  const eNR = num(P.eNR_t), eR = num(P.eR_t), eTot = eNR + eR, anchor = eTot > 0;
  const EXP = {}; SEG.forEach(s => {
    const f = anchor && expFileSeg[s] > 0 ? ((s === 'RELACIONADOS' ? eR : eNR) / expFileSeg[s]) : 1;
    EXP[s] = {}; BN.forEach(b => EXP[s][b] = expFile[s][b] * f);
  });
  const totExp = SEG.reduce((a, s) => a + BN.reduce((x, b) => x + EXP[s][b], 0), 0);

  const map3 = new Map(D.a3.rows.map(r => [r.doc, r.saldo]));
  const CO = {}; SEG.forEach(s => { CO[s] = {}; BN.forEach(b => CO[s][b] = { e: 0, r: 0, n: 0 }); });
  D.a1.rows.forEach(r => { const c = CO[r.seg][r.b]; c.e += r.saldo; c.n++; c.r += (map3.get(r.doc) || 0); });
  const TASA = {}; SEG.forEach(s => { TASA[s] = {}; BN.forEach(b => { const c = CO[s][b]; TASA[s][b] = c.e > 0 ? c.r / c.e : null; }); });

  const F = { 'NO-RELACIONADOS': +P.fT || 1, 'RELACIONADOS': +P.fR || 1 };
  const cells = []; let PCE = 0;
  SEG.forEach(s => BN.forEach(b => {
    const t = (TASA[s][b] == null ? 0 : TASA[s][b]) * F[s];
    const e = EXP[s][b], p = e * t; PCE += p;
    cells.push({ s, b, e, tasaObs: TASA[s][b], tasaApl: t, pce: p });
  }));

  const may = ['t2', 't1', 't'].map(suf => ({
    ini: num(P['provIni_' + suf]), con: num(P['provCon_' + suf]), rev: num(P['provRev_' + suf]),
    cas: num(P['provCas_' + suf]), bal: num(P['provBal_' + suf]),
  }));
  may.forEach(m => m.fin = m.ini + m.con - m.rev - m.cas);
  const provReg = may[2].bal || may[2].fin;
  const castAcum = may.reduce((a, m) => a + m.cas, 0);
  const cohorteBase = BN.reduce((a, b) => a + SEG.reduce((x, s) => x + CO[s][b].e, 0), 0);
  const tasaCastigo = cohorteBase > 0 ? castAcum / cohorteBase : 0;

  return { PCE, totExp, provReg, tasaCastigo, traza: traz, cells };
}

const fx = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
process.stdout.write(JSON.stringify(run(fx)));
