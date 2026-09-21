import { useCallback, useEffect, useMemo, useState } from "react";
import * as api from "../../api.js";
import { CATEGORIES } from "../catalog.js";
import {
  ESTADO_EN_DISENO,
  ESTADO_ENVIADA,
  ESTADO_PROBADA,
  FORMATOS_ENTRADA,
  FORMATOS_SALIDA,
  esEditable,
  etiquetaEstado,
  fechaCorta,
  fichaParaEditar,
  fichaVacia,
  gruposAlternativos,
  idCatalogo,
  itemVacio,
  nombreArchivoEncargo,
  prepararParaGuardar,
  puedeGenerarCodigo,
  salidaVacia,
  textoEncargo,
  upsertFicha,
  validarFicha,
} from "./fichaLogic.js";
import "./fichaNiif.css";

/* ============================================================
   Generación de herramientas NIIF · ficha de diseño
   Circuito completo: se DISEÑA la prueba, se prueba, alguien la
   marca «probada» (queda registrado quién y cuándo) y recién
   entonces aparece «Generar código para Claude», que produce el
   encargo para que un asistente implemente la herramienta.
   Las fichas viven en el backend (/api/v1/aud/niif/fichas), no en
   el navegador: el revisor tiene que ver lo que diseñó otro.
   El motor de cálculo NO es parte de esta entrega.
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
  const [fichas, setFichas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [intentoGuardar, setIntentoGuardar] = useState(false);
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  // Encargo generado: { fichaId, nombreArchivo, texto }
  const [encargo, setEncargo] = useState(null);
  const [copiado, setCopiado] = useState("");

  const errores = useMemo(() => validarFicha(ficha), [ficha]);
  const grupos = useMemo(() => gruposAlternativos(ficha.items), [ficha.items]);

  const recargar = useCallback(async () => {
    setCargando(true);
    try {
      setFichas(await api.niifListarFichas());
      setError("");
    } catch (e) {
      setError(e.message || "No se pudieron cargar las fichas.");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    recargar();
  }, [recargar]);

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

  async function guardar(e) {
    e.preventDefault();
    setIntentoGuardar(true);
    setError("");
    if (errores.length) {
      setAviso("");
      return;
    }
    const payload = prepararParaGuardar(ficha);
    setOcupado(true);
    try {
      const guardada = ficha.id
        ? await api.niifActualizarFicha(ficha.id, payload)
        : await api.niifCrearFicha(payload);
      setFichas((lista) => upsertFicha(lista, guardada));
      setFicha(fichaVacia());
      setIntentoGuardar(false);
      setAviso(
        `Ficha «${guardada.nombre}» guardada en estado «${etiquetaEstado(guardada.estado)}».`
      );
    } catch (err) {
      setAviso("");
      setError(err.message || "No se pudo guardar la ficha.");
    } finally {
      setOcupado(false);
    }
  }

  async function devolverADiseno(g) {
    setError("");
    setOcupado(true);
    try {
      const actualizada = await api.niifCambiarEstado(g.id, ESTADO_EN_DISENO);
      setFichas((lista) => upsertFicha(lista, actualizada));
      setAviso(
        `«${actualizada.nombre}» volvió a diseño. Se borró la marca de probada: ` +
          `hay que volver a probarla antes de generar el código.`
      );
    } catch (err) {
      setAviso("");
      setError(err.message || "No se pudo devolver la ficha a diseño.");
    } finally {
      setOcupado(false);
    }
  }

  async function borrarFicha(g) {
    setError("");
    const escrito = window.prompt(
      `Esto elimina la ficha definitivamente. Escriba su nombre para confirmar:

${g.nombre}`
    );
    if (escrito === null) return;
    if (escrito !== g.nombre) {
      setError("El nombre no coincide: la ficha no se eliminó.");
      return;
    }
    setOcupado(true);
    try {
      await api.niifBorrarFicha(g.id, g.nombre);
      setFichas((lista) => lista.filter((x) => x.id !== g.id));
      setFicha((f) => (f.id === g.id ? fichaVacia() : f));
      setAviso(`«${g.nombre}» se eliminó definitivamente.`);
    } catch (err) {
      setAviso("");
      setError(err.message || "No se pudo eliminar la ficha.");
    } finally {
      setOcupado(false);
    }
  }

  async function marcarProbada(g) {
    setError("");
    setOcupado(true);
    try {
      const actualizada = await api.niifCambiarEstado(g.id, ESTADO_PROBADA);
      setFichas((lista) => upsertFicha(lista, actualizada));
      // Si estaba abierta en el formulario, ya no se edita.
      setFicha((f) => (f.id === g.id ? fichaVacia() : f));
      setAviso(
        `«${actualizada.nombre}» quedó marcada como probada por ` +
          `${actualizada.probada_por_email}.`
      );
    } catch (err) {
      setAviso("");
      setError(err.message || "No se pudo marcar la ficha como probada.");
    } finally {
      setOcupado(false);
    }
  }

  async function generarCodigo(g) {
    setError("");
    setOcupado(true);
    try {
      // El paso de estado lo valida el backend: de «probada» a «enviada».
      const actualizada = await api.niifCambiarEstado(g.id, ESTADO_ENVIADA);
      setFichas((lista) => upsertFicha(lista, actualizada));
      setEncargo({
        fichaId: actualizada.id,
        nombreArchivo: nombreArchivoEncargo(actualizada),
        texto: textoEncargo(actualizada, RUBROS),
      });
      setCopiado("");
      setAviso("");
    } catch (err) {
      setError(err.message || "No se pudo generar el encargo.");
    } finally {
      setOcupado(false);
    }
  }

  async function copiarEncargo() {
    try {
      await navigator.clipboard.writeText(encargo.texto);
      setCopiado("Encargo copiado al portapapeles.");
    } catch {
      setCopiado(
        "El navegador bloqueó el portapapeles: selecciona el texto de abajo y cópialo a mano."
      );
    }
  }

  function descargarEncargo() {
    const blob = new Blob([encargo.texto], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = encargo.nombreArchivo;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function editar(g) {
    setFicha(fichaParaEditar(g));
    setIntentoGuardar(false);
    setAviso("");
    setError("");
  }

  function nueva() {
    setFicha(fichaVacia());
    setIntentoGuardar(false);
    setAviso("");
    setError("");
  }

  return (
    <div className="of-tool">
      <header className="of-head">
        <h2>Generación de herramientas NIIF</h2>
        <p className="muted">
          Ficha de diseño de una prueba de auditoría: qué es, qué se le pide al
          cliente y qué cédulas produce. El circuito es{" "}
          <span className="nf-badge">en diseño</span> →{" "}
          <span className="nf-badge probada">probada</span> →{" "}
          <span className="nf-badge enviada">enviada</span>. Las fichas son de la
          firma: las ve todo el equipo, y quien marca una como probada queda
          registrado.
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
          {ficha.nombre && ficha.rubro && (
            <p className="muted nf-idcat">
              Identificador en el catálogo AUD: <code>{idCatalogo(ficha)}</code>
            </p>
          )}
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
        {error && <div className="notice warn nf-errores">{error}</div>}

        <div className="of-stage-actions">
          <button type="submit" className="btn primary lg" disabled={ocupado}>
            {ficha.id ? "Guardar cambios" : "Guardar ficha (en diseño)"}
          </button>
          <button type="button" className="btn" onClick={nueva} disabled={ocupado}>
            {ficha.id ? "Cancelar edición" : "Limpiar"}
          </button>
        </div>
      </form>

      {/* ---------- Encargo generado ---------- */}
      {encargo && (
        <div className="nf-encargo">
          <div className="nf-encargo-h">
            <h3>Encargo para el asistente</h3>
            <span className="nf-ficha-meta">{encargo.nombreArchivo}</span>
            <span className="nf-recent-acts">
              <button type="button" className="btn sm" onClick={copiarEncargo}>
                Copiar al portapapeles
              </button>
              <button type="button" className="btn sm" onClick={descargarEncargo}>
                Descargar .md
              </button>
              <button type="button" className="link" onClick={() => setEncargo(null)}>
                Cerrar
              </button>
            </span>
          </div>
          {copiado && <div className="notice nf-errores">{copiado}</div>}
          <textarea className="nf-encargo-texto" readOnly value={encargo.texto} rows={22} />
        </div>
      )}

      {/* ---------- Fichas de la firma ---------- */}
      <div className="of-recent">
        <h3>Fichas de la firma</h3>
        {cargando && <p className="muted">Cargando fichas…</p>}
        {!cargando && fichas.length === 0 && (
          <p className="muted">Todavía no hay ninguna ficha guardada.</p>
        )}
        <ul className="of-recent-list">
          {fichas.map((g) => (
            <li key={g.id}>
              <div className="nf-recent-row">
                <span className="nf-recent-name">{g.nombre}</span>
                <span className={`nf-badge ${g.estado === ESTADO_EN_DISENO ? "" : g.estado}`}>
                  {etiquetaEstado(g.estado)}
                </span>
                <span className="nf-ficha-meta">
                  {g.norma} {g.parrafo} · {(g.items || []).length} ítem(s) ·{" "}
                  {(g.salidas || []).length} cédula(s) · diseñada por {g.autor_email || "—"}
                  {g.probada_por_email
                    ? ` · probada por ${g.probada_por_email} el ${fechaCorta(g.probada_en)}`
                    : ""}
                  {g.estado === ESTADO_ENVIADA
                    ? ` · enviada el ${fechaCorta(g.enviada_en)}`
                    : ""}
                </span>
                <span className="nf-recent-acts">
                  {esEditable(g) && (
                    <>
                      <button type="button" className="link" onClick={() => editar(g)}>
                        Abrir
                      </button>
                      <button
                        type="button"
                        className="btn sm"
                        disabled={ocupado}
                        onClick={() => marcarProbada(g)}
                      >
                        Marcar probada
                      </button>
                    </>
                  )}
                  {puedeGenerarCodigo(g) && (
                    <>
                      <button
                        type="button"
                        className="link"
                        disabled={ocupado}
                        onClick={() => devolverADiseno(g)}
                      >
                        Devolver a diseño
                      </button>
                      <button
                        type="button"
                        className="btn sm primary"
                        disabled={ocupado}
                        onClick={() => generarCodigo(g)}
                      >
                        Generar código para Claude
                      </button>
                    </>
                  )}
                  <button
                    type="button"
                    className="link peligro"
                    disabled={ocupado}
                    onClick={() => borrarFicha(g)}
                  >
                    Eliminar
                  </button>
                </span>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
