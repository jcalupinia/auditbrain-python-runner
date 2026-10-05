/**
 * Regresión de la navegación por secciones del HTML de la herramienta
 * "ANÁLISIS DE AUDITORÍA" (planificación NIA), que se sirve desde
 * backend/app/aud/niif/assets/artefacto_planificacion.tmpl.html
 * (servicio.papel_procesador -> artefacto_html.render para processor
 * "planificacion_nia").
 *
 * Contrato bajo prueba: al activar una pestaña/chip (Materialidad, Índices,
 * etc.; anclas tipo #materia) DEBE quedar visible SOLO esa sección y las
 * demás ocultas. El bug reportado por el cliente es "al hacer clic se
 * despliega todo el HTML" (todas las secciones visibles).
 *
 * La prueba NO reimplementa la lógica: extrae el listener de clic REAL del
 * template y lo ejecuta contra un DOM mínimo. Si alguien cambia la línea que
 * oculta los paneles (o la regla CSS que las esconde) y reintroduce el bug,
 * estas aserciones fallan.
 *
 * Corre en el entorno node del repo (sin jsdom, que no está instalado).
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const TMPL = fileURLToPath(
  new URL(
    "../../../../backend/app/aud/niif/assets/artefacto_planificacion.tmpl.html",
    import.meta.url
  )
);
const HTML = readFileSync(TMPL, "utf8");

const TABS = [
  "dashboard", "perfil", "situacion", "resultados", "analitico",
  "ratios", "materia", "riesgos", "notas", "control", "programa",
];

/** DOM mínimo con los 11 paneles (solo dashboard visible) y los 11 botones. */
function buildDom() {
  const panels = {};
  const buttons = [];
  TABS.forEach((t, i) => {
    panels["panel-" + t] = { id: "panel-" + t, hidden: i !== 0, style: {} };
    const cls = new Set(i === 0 ? ["tab-btn", "on"] : ["tab-btn"]);
    const b = { dataset: { tab: t } };
    b.classList = {
      toggle: (c, on) => (on ? cls.add(c) : cls.delete(c)),
      contains: (c) => cls.has(c),
    };
    buttons.push(b);
  });
  panels["depthRow"] = { id: "depthRow", style: {} };
  const $ = (id) => panels[id];
  const tabBar = {
    _fn: null,
    addEventListener: (type, fn) => {
      if (type === "click") tabBar._fn = fn;
    },
    querySelectorAll: (sel) => (sel === ".tab-btn" ? buttons : []),
  };
  return { panels, buttons, $, els: { tabBar } };
}

/** Dispara el listener real como lo haría un clic en el botón de esa pestaña. */
function click(dom, tab) {
  const b = dom.buttons.find((x) => x.dataset.tab === tab);
  dom.els.tabBar._fn({ target: { closest: (sel) => (sel === ".tab-btn" ? b : null) } });
}

function visibles(dom) {
  return TABS.filter((t) => !dom.panels["panel-" + t].hidden);
}

/** Extrae el cuerpo del listener de clic de la barra de pestañas del template. */
function extraerListenerClic() {
  const marca = "els.tabBar.addEventListener('click',function(e){";
  const start = HTML.indexOf(marca);
  if (start < 0) throw new Error("no se encontró el listener de la barra de pestañas en el template");
  const end = HTML.indexOf("\n});", start) + 4;
  return HTML.slice(start, end);
}

/** Adjunta el listener real al DOM, con stubs no-op para lo que no es navegación. */
function adjuntarListenerReal(dom) {
  const noop = () => {};
  const attach = new Function(
    "els", "$", "state", "setTimeout",
    "drawAnaliticoCharts", "drawRatioChart", "drawDashboardChart",
    "renderPrograma", "wirePrograma", "renderControl", "renderRiesgos",
    extraerListenerClic()
  );
  attach(
    dom.els, dom.$, { result: null }, (f) => (typeof f === "function" ? f() : 0),
    noop, noop, noop, () => "", noop, () => "", () => ""
  );
}

describe("artefacto de planificación: estructura de las secciones", () => {
  it("tiene 11 botones de pestaña y 11 paneles (solo 'dashboard' visible al inicio)", () => {
    const panels = [...HTML.matchAll(/<div class="tab-panel" id="panel-([a-z]+)"( hidden)?><\/div>/g)];
    const btns = [...HTML.matchAll(/<button class="tab-btn( on)?" data-tab="([a-z]+)"/g)];
    expect(panels.map((m) => m[1])).toEqual(TABS);
    expect(btns.map((m) => m[2])).toEqual(TABS);
    // Solo el panel y el botón 'dashboard' arrancan activos; el resto oculto.
    expect(panels.filter((m) => !m[2]).map((m) => m[1])).toEqual(["dashboard"]);
    expect(btns.filter((m) => m[1]).map((m) => m[2])).toEqual(["dashboard"]);
  });

  it("incluye la regla CSS que oculta los paneles marcados con [hidden]", () => {
    // Sin esta regla, poner .hidden=true no esconde visualmente la sección
    // y se verían todas (el síntoma reportado).
    expect(HTML).toMatch(/\.tab-panel\[hidden\]\{display:none;?\}/);
  });
});

describe("artefacto de planificación: al activar una sección solo esa queda visible", () => {
  it.each(TABS)("activar '%s' deja visible solo esa sección", (tab) => {
    const dom = buildDom();
    adjuntarListenerReal(dom);
    click(dom, tab);
    expect(visibles(dom)).toEqual([tab]);
  });

  it("navegar por el hash #materia (que hace clic en su pestaña) muestra solo Materialidad", () => {
    const dom = buildDom();
    adjuntarListenerReal(dom);
    // El script del template resuelve el hash con
    //   document.querySelector('.tab-btn[data-tab="'+h+'"]').click()
    // que equivale a este clic en la pestaña 'materia'.
    click(dom, "materia");
    expect(visibles(dom)).toEqual(["materia"]);
  });

  it("el verificador detecta el bug reportado (handler que deja TODAS las secciones visibles)", () => {
    // Prueba de que las aserciones de arriba tienen filo: con la variante
    // ROTA (hidden=false para todos) el verificador ve todas las secciones
    // y la igualdad a ["materia"] fallaría.
    const dom = buildDom();
    const bug = new Function(
      "els", "$",
      "els.tabBar.addEventListener('click',function(e){var b=e.target.closest('.tab-btn');if(!b)return;" +
        "['dashboard','perfil','situacion','resultados','analitico','ratios','materia','riesgos','notas','control','programa']" +
        ".forEach(function(t){$('panel-'+t).hidden=false;});});"
    );
    bug(dom.els, dom.$);
    click(dom, "materia");
    expect(visibles(dom)).toEqual(TABS); // todas visibles == bug
    expect(visibles(dom)).not.toEqual(["materia"]);
  });
});
