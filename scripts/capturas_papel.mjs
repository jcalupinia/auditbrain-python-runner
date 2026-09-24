// Prueba visual del HTML ejecutivo del papel de trabajo NIIF (Playwright).
//
//   node scripts/capturas_papel.mjs <papel.html> <carpeta_capturas> [prefijo]
//
// - A 1440 px y 390 px: sin desborde horizontal de la página, ninguna cifra o
//   rótulo KPI desbordado y ninguna tabla «Cómo se calcula» más ancha que su panel.
// - Captura cada pestaña (sección) a 1440 px, el panel a 390 px, el panel en tema
//   Claro y en cada tipo de gráfico (barras, líneas, área, puntos).
// Sale con código 1 si algo se desborda. Usa @playwright/test (e2e/package.json)
// o, si no está instalado, el módulo indicado en PLAYWRIGHT_MODULE.
import fs from "node:fs";
import path from "node:path";

const [, , archivo, salida, prefijo = path.basename(archivo || "papel", ".html")] = process.argv;
if (!archivo || !salida) {
  console.error("uso: node scripts/capturas_papel.mjs <papel.html> <carpeta> [prefijo]");
  process.exit(2);
}
let pw;
try { pw = await import("@playwright/test"); }
catch { pw = await import(process.env.PLAYWRIGHT_MODULE || "playwright"); }
const { chromium } = pw;
fs.mkdirSync(salida, { recursive: true });
const url = "file://" + path.resolve(archivo);
const b = await chromium.launch();
const fallas = [];

async function revisar(p, ancho, donde) {
  const r = await p.evaluate(() => {
    document.querySelectorAll("details.calc").forEach((d) => (d.open = true));
    const desb = (sel) => [...document.querySelectorAll(sel)]
      .filter((e) => e.offsetParent !== null && e.scrollWidth > e.clientWidth + 1)
      .map((e) => (e.textContent || "").trim().slice(0, 40));
    const calc = [...document.querySelectorAll("table.calc")]
      .filter((t) => t.offsetParent !== null && t.getBoundingClientRect().width > t.closest(".panel").getBoundingClientRect().width + 1)
      .length;
    return { pagina: document.documentElement.scrollWidth, kpi: desb(".kpi-val,.kpi-etq,.kpi-exacto,.kpi-var"), calc };
  });
  if (r.pagina > ancho) fallas.push(`${donde}: la página mide ${r.pagina}px (> ${ancho})`);
  if (r.kpi.length) fallas.push(`${donde}: KPI desbordado ${JSON.stringify(r.kpi)}`);
  if (r.calc) fallas.push(`${donde}: ${r.calc} tabla(s) «Cómo se calcula» más anchas que su panel`);
  return r;
}

for (const ancho of [1440, 390]) {
  const p = await b.newPage({ viewport: { width: ancho, height: 900 } });
  await p.goto(url);
  const tabs = await p.$$eval(".tab", (ts) => ts.map((t) => [t.dataset.s, t.textContent.trim()]));
  for (const [i, [sid, nombre]] of tabs.entries()) {
    await p.click(`.tab[data-s="${sid}"]`);
    await revisar(p, ancho, `${ancho}px · ${nombre}`);
    if (ancho === 1440 || i === 0) {
      const f = `${prefijo}_${ancho}_${String(i).padStart(2, "0")}_${nombre.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^\w]+/g, "_")}.png`;
      await p.screenshot({ path: path.join(salida, f), fullPage: true });
    }
  }
  await p.close();
}
// Temas y tipos de gráfico (panel)
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto(url);
for (const [sel, val] of [["t", "claro"], ["g", "barras"], ["g", "lineas"], ["g", "area"], ["g", "puntos"], ["t", "esmeralda"], ["v", "presentacion"]]) {
  await p.selectOption(`#sel-${sel}`, val);
  await revisar(p, 1440, `panel ${sel}=${val}`);
  await p.screenshot({ path: path.join(salida, `${prefijo}_panel_${sel}-${val}.png`) });
}
await p.close();
await b.close();
console.log(fallas.length ? "FALLAS:\n" + fallas.join("\n") : "OK: sin desbordes a 1440 y 390 px");
process.exit(fallas.length ? 1 : 0);
