import { useCallback, useEffect, useState } from "react";

import * as api from "../../api";
import { nombreEstado } from "./cicloLogic";
import { Prueba } from "./PruebasEncargo";

// Bandejas (diseño §8): las pruebas en revisión y las aprobadas de todos los
// proyectos AUD que el usuario ve, para quien revisa.
export default function Bandejas() {
  const [filas, setFilas] = useState(null);
  const [error, setError] = useState("");
  const [abierta, setAbierta] = useState(null);

  const recargar = useCallback(async () => {
    try {
      setFilas(await api.cicloBandejas());
      setError("");
    } catch (e) {
      setError(e.message || String(e));
    }
  }, []);
  useEffect(() => { recargar(); }, [recargar]);

  if (error) return <p role="alert" className="nf-error">{error}</p>;
  if (!filas) return <p className="muted">Cargando…</p>;
  const grupos = [["EN_REVISION", "En revisión"], ["APROBADO", "Aprobados"]];
  return (
    <div className="nf-ciclo">
      {grupos.map(([estado, titulo]) => {
        const suyas = filas.filter((f) => f.estado === estado);
        return (
          <section key={estado} className="nf-rec-panel">
            <p className="nf-eyebrow">{titulo.toUpperCase()} · {suyas.length}</p>
            {suyas.length === 0 ? (
              <p className="muted">Nada por ahora.</p>
            ) : (
              <ul className="nf-consola-lista">
                {suyas.map((f) => (
                  <li key={f.id}>
                    <button type="button" className={abierta === f.id ? "selected" : ""} onClick={() => setAbierta(abierta === f.id ? null : f.id)}>
                      <strong>{f.cliente} · {f.nombre} · v{f.version}</strong>
                      <small>
                        {f.proyecto} · {nombreEstado(f.estado)}
                        {estado === "EN_REVISION" ? ` · ${f.notas_abiertas} puntos sin resolver` : ` · aprobada por ${f.aprobada_por}`}
                      </small>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}
      {abierta && <Prueba key={abierta} id={abierta} onCambio={recargar} onAbrir={setAbierta} />}
    </div>
  );
}
