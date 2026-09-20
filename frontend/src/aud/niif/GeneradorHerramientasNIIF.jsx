import { useMemo, useState } from "react";
import { CATEGORIES } from "../catalog.js";
import {
  FORMATOS_ENTRADA,
  FORMATOS_SALIDA,
  borrarFicha,
  fichaParaEditar,
  fichaVacia,
  guardarFicha,
  gruposAlternativos,
  itemVacio,
  listarFichas,
  prepararParaGuardar,
  salidaVacia,
  validarFicha,
} from "./fichaLogic.js";
import "./fichaNiif.css";

/* ============================================================
   Generación de herramientas NIIF · ficha de diseño
   Primera entrega: se DISEÑA la prueba (identificación, qué se le
   pide al cliente y qué cédulas produce) y queda "en diseño".
   El motor de cálculo, la carga de archivos del cliente y la
   generación del Excel NO son parte de esta entrega.
   Fuente: docs/pruebas/ESTRUCTURA_HERRAMIENTA.md (bloques 2 y 4).
   ============================================================ */

// El rubro sale del mismo catálogo AUD donde la herramienta terminada va a
// vivir (Bloque 6 del documento), para no inventar una lista paralela.
const RUBROS = CATEGORIES.filter((c) => c.type !== "herramienta");

function Formatos({ opciones, seleccion, onToggle }) {
  return (
    <div className="nf-formatos">
      {opciones.map((f) => {
        const on = (seleccion || []).includes(f.id);
        return (
          <label key={f.id} className={`nf-fmt ${on ? "on" : ""}`}>
            <input type="checkbox" checked={on} onChange={() => onToggle(f.id)} />
            {f.label}
          </label>
        );
      })}
    </div>
  );
}

export default function GeneradorHerramientasNIIF() {
  const [ficha, setFicha] = useState(fichaVacia);
  const [fichas, setFichas] = useState(listarFichas);
  const [intentoGuardar, setIntentoGuardar] = useState(false);
  const [aviso, setAviso] = useState("");

  const errores = useMemo(() => validarFicha(ficha), [ficha]);
  const grupos = useMemo(() => gruposAlternativos(ficha.items), [ficha.items]);

  const set = (campo, valor) => setFicha((f) => ({ ...f, [campo]: valor }));

  function setFila(lista, key, cambios) {
    setFicha((f) => ({
      ...f,
      [lista]: f[lista].map((x) => (x.key === key ? { ...x, ...cambios } : x)),
    }));
  }
  function quitarFila(lista, key) {
    setFicha((f) => ({ ...f, [lista]: f[lista].filter((x) => x.key !== key) }));
  }
  function toggleFormato(lista, fila, id) {
    const actuales = fila.formatos || [];
    setFila(lista, fila.key, {
      formatos: actuales.includes(id) ? actuales.filter((x) => x !== id) : [...actuales, id],
    });
  }

  function guardar(e) {
    e.preventDefault();
    setIntentoGuardar(true);
    if (errores.length) {
      setAviso("");
      return;
    }
    const guardada = prepararParaGuardar(ficha);
    setFichas(guardarFicha(guardada));
    setFicha(fichaVacia());
    setIntentoGuardar(false);
    setAviso(`Ficha «${guardada.nombre}» guardada en estado «en diseño».`);
  }

  function editar(g) {
    setFicha(fichaParaEditar(g));
    setIntentoGuardar(false);
    setAviso("");
  }

  function nueva() {
    setFicha(fichaVacia());
    setIntentoGuardar(false);
    setAviso("");
  }

  return (
    <div className="of-tool">
      <header className="of-head">
        <h2>Generación de herramientas NIIF</h2>
        <p className="muted">
          Ficha de diseño de una prueba de auditoría: qué es, qué se le pide al
          cliente y qué cédulas produce. Al guardar queda en estado{" "}
          <span className="nf-badge">en diseño</span> — el motor de cálculo se
          construye después.
        </p>
      </header>

      <form className="of-form" onSubmit={guardar}>
        {/* ---------- 1 · Identificación ---------- */}
        <section className="nf-sec">
          <div className="nf-sec-h">
            <h3>1 · Identificación</h3>
            <span className="nf-ref">ficha del encargo</span>
          </div>
          <div className="of-form-row">
            <label>
              Nombre de la prueba*
              <input
                value={ficha.nombre}
                placeholder="Valor neto de realización de inventarios"
                onChange={(e) => set("nombre", e.target.value)}
              />
            </label>
            <label>
              Rubro o ciclo*
              <select value={ficha.rubro} onChange={(e) => set("rubro", e.target.value)}>
                <option value="">Selecciona el rubro…</option>
                {RUBROS.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="of-form-row">
            <label>
              Norma NIIF / NIC*
              <input
                value={ficha.norma}
                placeholder="NIC 2 · Inventarios"
                onChange={(e) => set("norma", e.target.value)}
              />
            </label>
            <label>
              Párrafo*
              <input
                value={ficha.parrafo}
                placeholder="§ 9, 28-33"
                onChange={(e) => set("parrafo", e.target.value)}
              />
            </label>
          </div>
        </section>

        {/* ---------- 2 · Requerimiento al cliente ---------- */}
        <section className="nf-sec">
          <div className="nf-sec-h">
            <h3>2 · Requerimiento al cliente</h3>
            <span className="nf-ref">bloque 2</span>
            <p className="muted">
              Un ítem por documento pedido, definido por contenido y no por
              extensión.
            </p>
          </div>

          <div className="of-slots">
            {ficha.items.map((it, i) => (
              <div key={it.key} className={`of-slot ${it.obligatorio ? "req" : ""}`}>
                <div className="nf-card-h">
                  <span className="nf-card-n">Ítem {i + 1}</span>
                  <button
                    type="button"
                    className="nf-del"
                    title="Quitar ítem"
                    disabled={ficha.items.length === 1}
                    onClick={() => quitarFila("items", it.key)}
                  >
                    ✕
                  </button>
                </div>

                <label className="nf-lbl" htmlFor={`${it.key}-q`}>
                  Qué se le pide al cliente
                </label>
                <input
                  id={`${it.key}-q`}
                  className="nf-in"
                  value={it.que_se_pide}
                  placeholder="Kárdex valorado a la fecha de corte"
                  onChange={(e) => setFila("items", it.key, { que_se_pide: e.target.value })}
                />

                <span className="nf-lbl">Formatos aceptados</span>
                <Formatos
                  opciones={FORMATOS_ENTRADA}
                  seleccion={it.formatos}
                  onToggle={(id) => toggleFormato("items", it, id)}
                />

                <label className="nf-flag">
                  <input
                    type="checkbox"
                    checked={it.obligatorio}
                    onChange={(e) => setFila("items", it.key, { obligatorio: e.target.checked })}
                  />
                  Obligatorio
                </label>

                <div className="nf-grid2">
                  <div>
                    <label className="nf-lbl" htmlFor={`${it.key}-c`}>
                      ¿En cuántos componentes viene?
                    </label>
                    <input
                      id={`${it.key}-c`}
                      className="nf-in"
                      type="number"
                      min="1"
                      value={it.componentes}
                      onChange={(e) =>
                        setFila("items", it.key, { componentes: Number(e.target.value) })
                      }
                    />
                  </div>
                  <div>
                    <label className="nf-lbl" htmlFor={`${it.key}-g`}>
                      Grupo de fuentes alternativas
                    </label>
                    <input
                      id={`${it.key}-g`}
                      className="nf-in"
                      value={it.grupo_alternativas}
                      placeholder="(opcional) Saldo de inventario"
                      onChange={(e) =>
                        setFila("items", it.key, { grupo_alternativas: e.target.value })
                      }
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="of-form-row" style={{ marginTop: 10 }}>
            <button
              type="button"
              className="btn sm"
              onClick={() => setFicha((f) => ({ ...f, items: [...f.items, itemVacio()] }))}
            >
              + Añadir ítem
            </button>
          </div>

          {Object.keys(grupos).length > 0 && (
            <div className="nf-grupos">
              Grupos de fuentes alternativas — basta con recibir una de las
              fuentes de cada grupo:
              {Object.entries(grupos).map(([nombre, miembros]) => (
                <div key={nombre}>
                  <b>{nombre}</b>: {miembros.map((m) => m.que_se_pide || "(sin nombre)").join(" · ")}{" "}
                  ({miembros.length})
                </div>
              ))}
            </div>
          )}
        </section>

        {/* ---------- 3 · Salidas ---------- */}
        <section className="nf-sec">
          <div className="nf-sec-h">
            <h3>3 · Salidas</h3>
            <span className="nf-ref">bloque 4</span>
            <p className="muted">
              Toda hoja entregada en el Excel tiene su cédula. El número de
              cédulas es libre.
            </p>
          </div>

          <div className="of-slots">
            {ficha.salidas.map((s, i) => (
              <div key={s.key} className="of-slot">
                <div className="nf-card-h">
                  <span className="nf-card-n">Cédula {i + 1}</span>
                  <button
                    type="button"
                    className="nf-del"
                    title="Quitar cédula"
                    disabled={ficha.salidas.length === 1}
                    onClick={() => quitarFila("salidas", s.key)}
                  >
                    ✕
                  </button>
                </div>

                <label className="nf-lbl" htmlFor={`${s.key}-n`}>
                  Cédula que produce
                </label>
                <input
                  id={`${s.key}-n`}
                  className="nf-in"
                  value={s.nombre}
                  placeholder="Cédula de VNR por ítem"
                  onChange={(e) => setFila("salidas", s.key, { nombre: e.target.value })}
                />

                <span className="nf-lbl">Formatos de entrega</span>
                <Formatos
                  opciones={FORMATOS_SALIDA}
                  seleccion={s.formatos}
                  onToggle={(id) => toggleFormato("salidas", s, id)}
                />
              </div>
            ))}
          </div>

          <div className="of-form-row" style={{ marginTop: 10 }}>
            <button
              type="button"
              className="btn sm"
              onClick={() => setFicha((f) => ({ ...f, salidas: [...f.salidas, salidaVacia()] }))}
            >
              + Añadir cédula
            </button>
          </div>
        </section>

        {intentoGuardar && errores.length > 0 && (
          <div className="notice warn nf-errores">
            Faltan datos para guardar la ficha:
            <ul>
              {errores.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </div>
        )}
        {aviso && <div className="notice nf-errores">{aviso}</div>}

        <div className="of-stage-actions">
          <button type="submit" className="btn primary lg">
            Guardar ficha (en diseño)
          </button>
          <button type="button" className="btn" onClick={nueva}>
            Limpiar
          </button>
        </div>
      </form>

      {fichas.length > 0 && (
        <div className="of-recent">
          <h3>Herramientas en diseño</h3>
          <ul className="of-recent-list">
            {fichas.map((g) => (
              <li key={g.id}>
                <div className="nf-recent-row">
                  <span className="nf-recent-name">{g.nombre}</span>
                  <span className="nf-badge">en diseño</span>
                  <span className="nf-ficha-meta">
                    {g.norma} {g.parrafo} · {g.items.length} ítem(s) · {g.salidas.length} cédula(s)
                  </span>
                  <span className="nf-recent-acts">
                    <button type="button" className="link" onClick={() => editar(g)}>
                      Abrir
                    </button>
                    <button
                      type="button"
                      className="link"
                      onClick={() => setFichas(borrarFicha(g.id))}
                    >
                      Borrar
                    </button>
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
