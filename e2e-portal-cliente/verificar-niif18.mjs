#!/usr/bin/env node
/**
 * Verificación de extremo a extremo del NIIF 18 Studio dentro del portal.
 *
 * Monta el mismo reparto que producción: el portal sirve la página en un
 * origen y el backend responde en otro (con CORS), y la página lee el token
 * de sesión del portal desde `localStorage`. Comprueba en un navegador real:
 *
 *   Tarea A — Cuadra vive en la Etapa 1, paso 4; toma las partidas de la
 *             homologación sin recarga manual; conserva C3, C5, C7 y NIC 7;
 *             la conciliación cuadra (mismo resultado en NIC 1 y NIIF 18).
 *   Tarea B — Base normativa enlaza la biblioteca; un `client` ve solo la
 *             normativa y un operador ve además los modelos de las firmas.
 *   Tarea C — Sin login propio: la sesión es la del portal (Bearer HS256).
 *
 *   node e2e-portal-cliente/verificar-niif18.mjs
 *
 * Variables: PY (intérprete con las dependencias), CHROMIUM_PATH (navegador).
 */
import { spawn, spawnSync } from "node:child_process";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PY = process.env.PY || "python3";
const PUERTO_API = 8788;
const PUERTO_PORTAL = 8789;
const ORIGEN_PORTAL = `http://127.0.0.1:${PUERTO_PORTAL}`;
const ORIGEN_API = `http://127.0.0.1:${PUERTO_API}`;
const STUDIO = path.join(RAIZ, "frontend-client", "public", "niif18", "studio.html");

const BIBLIOTECA =
  process.env.NIIF18_BIBLIOTECA_DIR ||
  path.join(RAIZ, "..", "herramienta-niif-18", "base-normativa", "libro");

let fallos = 0, pruebas = 0;
const ok = (cond, texto, detalle = "") => {
  pruebas++;
  console.log(`  ${cond ? "✓" : "✕"} ${texto}${!cond && detalle ? " — " + detalle : ""}`);
  if (!cond) fallos++;
};

if (!fs.existsSync(STUDIO)) {
  console.error(`No existe ${STUDIO}. Genere la V4 y cópiela (ver public/niif18/LEEME.md).`);
  process.exit(1);
}
if (!fs.existsSync(BIBLIOTECA)) {
  console.error(`No existe la biblioteca en ${BIBLIOTECA}. Defina NIIF18_BIBLIOTECA_DIR.`);
  process.exit(1);
}

const bd = path.join(RAIZ, "verificacion_niif18.db");
for (const f of [bd, bd + "-wal", bd + "-shm"]) if (fs.existsSync(f)) fs.unlinkSync(f);

const ENV = {
  ...process.env,
  // El backend se importa como paquete `backend.*` desde la raíz del repo.
  PYTHONPATH: RAIZ + (process.env.PYTHONPATH ? ":" + process.env.PYTHONPATH : ""),
  DATABASE_URL: `sqlite:///${bd}`,
  AUDITBRAIN_JWT_SECRET: "verificacion-local-no-productiva-0123456789abcdef",
  NIIF18_BIBLIOTECA_DIR: BIBLIOTECA,
  CORS_ALLOW_ORIGINS: ORIGEN_PORTAL,
  // Las capas de dispositivo y sesión única son del login real del portal; aquí
  // se inyecta el token directamente, así que se usan los toggles de QA.
  CLIENT_PORTAL_DEVICE_CHECK_ENABLED: "false",
  CLIENT_PORTAL_SESSION_CHECK_ENABLED: "false",
};

// ---- 1. Semilla -----------------------------------------------------------
const semilla = spawnSync(PY, ["scripts/_seed_niif18_demo.py"], {
  cwd: RAIZ, env: ENV, encoding: "utf8",
});
if (semilla.status !== 0) {
  console.error("Falló la semilla:\n", semilla.stderr || semilla.stdout);
  process.exit(1);
}
const CUENTAS = JSON.parse(semilla.stdout.trim().split("\n").pop());

// ---- 2. Backend -----------------------------------------------------------
const api = spawn(PY, ["-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", String(PUERTO_API)],
  { cwd: RAIZ, env: ENV, stdio: ["ignore", "pipe", "pipe"] });
api.stderr.on("data", (d) => { if (process.env.VERBOSE) process.stderr.write(d); });

// ---- 3. Portal (estático, mismo origen que el Studio) ---------------------
const portal = http.createServer((req, res) => {
  const ruta = req.url.split("?")[0];
  if (ruta === "/niif18/studio.html" || ruta === "/") {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(fs.readFileSync(STUDIO));
    return;
  }
  res.writeHead(404).end("no");
});
await new Promise((r) => portal.listen(PUERTO_PORTAL, "127.0.0.1", r));

const esperarApi = async () => {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`${ORIGEN_API}/healthz`);
      if (r.ok) return true;
    } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
};
if (!(await esperarApi())) {
  console.error("El backend no respondió en /healthz");
  api.kill(); portal.close(); process.exit(1);
}

const navegador = await chromium.launch(
  process.env.CHROMIUM_PATH
    ? { executablePath: process.env.CHROMIUM_PATH, args: ["--no-sandbox"] }
    : {}
);

async function abrir(token) {
  const ctx = await navegador.newContext({ baseURL: ORIGEN_PORTAL });
  const page = await ctx.newPage();
  const errores = [];
  page.on("console", (m) => { if (m.type() === "error") errores.push(m.text()); });
  page.on("pageerror", (e) => errores.push("pageerror: " + e.message));
  // El portal deja el token aquí; el marco es del mismo origen y lo lee.
  await ctx.addInitScript((t) => {
    try { localStorage.setItem("ab_client_token", t); } catch {}
  }, token);
  await page.goto(`/niif18/studio.html?api=${encodeURIComponent(ORIGEN_API)}`);
  await page.waitForSelector(".side .nav");
  return { ctx, page, errores };
}

try {
  // ======================= CLIENTE =======================
  console.log("\n1) Sesión de CLIENTE (rol client, con la herramienta concedida)");
  const { ctx: c1, page, errores } = await abrir(CUENTAS.cliente.token);

  await page.waitForFunction(() => document.querySelector(".sesion-chip") !== null, { timeout: 15000 })
    .catch(() => {});
  const chip = await page.textContent(".sesion-chip").catch(() => "");
  ok(/client/.test(chip || ""), "la barra muestra la sesión del portal", chip || "(sin chip)");
  ok(!(await page.$("#usuario")) && !(await page.$("form#f")), "no hay login propio en el Studio");

  const navs = await page.$$eval(".side .nav", (n) => n.map((x) => x.textContent.trim()));
  ok(navs.length >= 15, `el Studio conserva sus módulos (${navs.length})`);
  ok(!navs.some((n) => n.includes("Cuadra")), "Cuadra ya NO es un módulo suelto del menú");

  // ---- Tarea A: Cuadra en la Etapa 1, paso 4 ----
  console.log("\n2) Tarea A · Cuadra en el paso 4 (Conversión preliminar)");
  await page.click('.nav:has-text("Conversión preliminar")');
  await page.waitForSelector("#cuaRecon");
  const texto = await page.textContent(".main");

  ok(texto.includes("Conversión preliminar NIC 1 → NIIF 18"), "es el paso 4 de la Etapa 1");
  for (const ctrl of ["C3", "C5", "C7", "NIC 7"]) {
    ok(texto.includes(ctrl), `control ${ctrl} conservado`);
  }
  ok(texto.includes("Exportar puente CSV"), "la exportación del puente se conserva");
  ok(texto.includes("Resultado fuente"), "los KPI del puente se conservan");

  const recon = await page.textContent("#cuaRecon");
  ok(recon.includes("Concilia"), "la conciliación NIC 1 ↔ NIIF 18 se muestra", recon.slice(0, 70));

  // Toma las partidas de la homologación (semilla del Studio: 6 partidas)
  const filas = await page.$$eval("table.cua tbody tr", (r) => r.length);
  ok(filas === 6, `toma las 6 partidas de la homologación sin recarga manual (${filas})`);
  ok(texto.includes("homologación"), "declara que las partidas vienen de la homologación");
  ok(/Pendiente|sin clasificar/i.test(texto), "señala la partida pendiente de juicio");

  // La conciliación debe cuadrar: mismo resultado del periodo en ambas columnas
  const [ias1, ifrs18] = await Promise.all([
    page.textContent("#cuaIas1"),
    page.textContent("#cuaIfrs18"),
  ]);
  const ultimo = (t) => (t.match(/-?[\d.]+,\d{2}/g) || []).pop();
  ok(ultimo(ias1) === ultimo(ifrs18),
     `mismo resultado del periodo en NIC 1 y NIIF 18 (${ultimo(ias1)} vs ${ultimo(ifrs18)})`);

  for (const [tab, marca] of [
    ["MPM", "Conciliación de medidas"],
    ["Notas", "Notas a los estados"],
    ["Consolidación", "Consolidación del grupo"],
    ["Pista de auditoría", "Registro append-only"],
  ]) {
    await page.click(`.cua-tab:has-text("${tab}")`);
    await page.waitForTimeout(140);
    ok((await page.textContent(".main")).includes(marca), `pestaña ${tab} funciona`);
  }

  // ---- Tarea B: Base normativa para el cliente ----
  console.log("\n3) Tarea B · Base normativa (rol client)");
  await page.click('.nav:has-text("Base normativa")');
  await page.waitForSelector("#normaLista", { timeout: 15000 });
  const normas = await page.$$("[data-norma]");
  ok(normas.length >= 60, `lista la normativa desde el backend (${normas.length} normas)`);
  const tb = await page.textContent(".main");
  ok(tb.includes("restringido a operadores"), "los modelos de las firmas salen bloqueados");
  ok(!tb.includes("Abrir PDF"), "no se ofrece ningún PDF de las firmas al cliente");
  for (const firma of ["EY", "KPMG", "Deloitte", "Grant Thornton"]) {
    ok(!new RegExp(`${firma}[^<]{0,40}\\.pdf`, "i").test(tb), `no se filtra el archivo de ${firma}`);
  }
  // Una norma abre de verdad, con la sesión del portal
  const href = await page.getAttribute("[data-norma] a", "href");
  const r1 = await page.request.get(href, {
    headers: { Authorization: `Bearer ${CUENTAS.cliente.token}` },
  });
  ok(r1.status() === 200, `la norma enlazada abre (${href.split("/").pop()})`, String(r1.status()));

  ok(errores.length === 0, "sin errores de consola (cliente)", errores.slice(0, 2).join(" | "));
  await c1.close();

  // ======================= OPERADOR =======================
  console.log("\n4) Tarea B · Base normativa (rol admin = operador)");
  const { ctx: c2, page: p2, errores: e2 } = await abrir(CUENTAS.operador.token);
  await p2.click('.nav:has-text("Base normativa")');
  await p2.waitForSelector("#normaLista", { timeout: 15000 });
  const to = await p2.textContent(".main");
  ok(to.includes("Abrir PDF"), "el operador sí ve los modelos de las firmas");
  for (const firma of ["EY", "KPMG", "Deloitte", "Grant Thornton", "PwC"]) {
    ok(to.includes(firma), `modelo de ${firma} listado`);
  }
  const pdf = await p2.getAttribute('a[href*="/modelos/"]', "href");
  const r2 = await p2.request.get(pdf, {
    headers: { Authorization: `Bearer ${CUENTAS.operador.token}` },
  });
  ok(r2.status() === 200, "el PDF del modelo se descarga para el operador", String(r2.status()));
  ok((r2.headers()["content-type"] || "").includes("pdf"), "se sirve como PDF");

  // El mismo PDF, con el token del cliente, debe ser rechazado por el SERVIDOR
  const r3 = await p2.request.get(pdf, {
    headers: { Authorization: `Bearer ${CUENTAS.cliente.token}` },
  });
  ok(r3.status() === 403, "el servidor rechaza ese PDF al rol client (403)", String(r3.status()));

  ok(e2.length === 0, "sin errores de consola (operador)", e2.slice(0, 2).join(" | "));
  await c2.close();
} finally {
  await navegador.close();
  api.kill("SIGTERM");
  portal.close();
  for (const f of [bd, bd + "-wal", bd + "-shm"]) {
    try { if (fs.existsSync(f)) fs.unlinkSync(f); } catch {}
  }
}

console.log("\n──────────────────────────────────────────");
console.log(fallos === 0
  ? `RESULTADO: ${pruebas} comprobaciones, 0 fallos.`
  : `RESULTADO: ${fallos} FALLOS de ${pruebas}.`);
process.exit(fallos === 0 ? 0 : 1);
