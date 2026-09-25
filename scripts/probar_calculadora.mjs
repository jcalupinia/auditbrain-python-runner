// Prueba en el navegador de la «Calculadora reutilizable» del HTML de una prueba declarativa.
//
//   node scripts/probar_calculadora.mjs <papel.html> <total_esperado> [captura.png]
//
// Abre la pestaña «Calculadora», recalcula con los datos de la versión y comprueba que el
// resultado principal sea <total_esperado> (es-EC, p. ej. «82,00»); luego cambia un dato,
// agrega y quita una fila y restablece. Sale con código 1 si algo falla o hay errores de JS.
import path from "node:path";

const [, , archivo, esperado, captura] = process.argv;
let pw;
try { pw = await import("@playwright/test"); }
catch { pw = await import(process.env.PLAYWRIGHT_MODULE || "playwright"); }
const b = await pw.chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } });
const errores = [];
p.on("pageerror", (e) => errores.push(String(e)));
p.on("console", (m) => { if (m.type() === "error") errores.push(m.text()); });
await p.goto("file://" + path.resolve(archivo));
const falla = (m) => { console.error("FALLA:", m); process.exitCode = 1; };

await p.click('.tab[data-s="s-calc"]');
const filas = await p.locator("#calc-in tbody tr").count();
if (!filas) falla("la calculadora no muestra la población");
await p.click("#calc-run");
const valores = await p.locator("#calc-res .kpi-val").allTextContents();
console.log("totales:", valores.join(" · "));
if (!valores.includes(esperado)) falla(`no aparece el total esperado ${esperado}`);
if (!(await p.locator("#calc-estado").textContent()).includes("Simulación calculada")) falla("estado sin calcular");

// Cambiar un dato invalida el resultado; recalcular lo actualiza.
const antes = valores.join("|");
const celda = p.locator("#calc-in tbody tr").first().locator("input").nth(2);
await celda.fill(String(Number(await celda.inputValue()) * 2));
if (await p.locator("#calc-res .kpi").count()) falla("el resultado no se invalidó al cambiar un dato");
await p.click("#calc-run");
const despues = (await p.locator("#calc-res .kpi-val").allTextContents()).join("|");
if (despues === antes) falla("recalcular con otro dato no cambió el resultado");
console.log("con el dato cambiado:", despues.replaceAll("|", " · "));

// Agregar y quitar filas; restablecer vuelve a los datos de la versión.
await p.click("#calc-add");
if ((await p.locator("#calc-in tbody tr").count()) !== filas + 1) falla("no agregó la fila");
await p.locator("#calc-in tbody tr").last().getByRole("button", { name: /Quitar/ }).click();
await p.click("#calc-reset");
await p.click("#calc-run");
if ((await p.locator("#calc-res .kpi-val").allTextContents()).join("|") !== antes) falla("restablecer no volvió a los datos de la versión");

// Un dato inválido muestra el error sin romper la página.
await p.locator("#calc-in tbody tr").first().locator("input").nth(2).fill("abc");
await p.click("#calc-run");
if (!(await p.locator("#calc-error").textContent()).trim()) falla("un dato inválido no muestra error");
await p.click("#calc-reset");
await p.click("#calc-run");
if (captura) await p.screenshot({ path: captura, fullPage: true });

// Al imprimir (Guardar como PDF) la calculadora no aparece.
await p.emulateMedia({ media: "print" });
if (await p.locator("#s-calc").isVisible()) falla("la calculadora se imprime");
if (errores.length) falla("errores de JavaScript: " + errores.join(" | "));
await b.close();
if (!process.exitCode) console.log("OK: calculadora reutilizable");
