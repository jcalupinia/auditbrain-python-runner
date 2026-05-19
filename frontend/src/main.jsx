import React, { Suspense, lazy, useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

/* Command Center: ruta aislada por hash. El bundle y los estilos del
   nuevo OS solo se cargan al entrar a #/command-center | #/auditbrain-os.
   El frontend legacy (App + styles.css) queda intacto y por defecto. */
const CommandCenter = lazy(() => import("./command-center/index.jsx"));

const OS_HASHES = new Set(["#/command-center", "#/auditbrain-os"]);
const isOsRoute = () => OS_HASHES.has(window.location.hash);

function Root() {
  const [os, setOs] = useState(isOsRoute());
  useEffect(() => {
    const onHash = () => setOs(isOsRoute());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  if (os) {
    return (
      <Suspense
        fallback={
          <div
            style={{
              minHeight: "100vh",
              display: "grid",
              placeItems: "center",
              background: "#0A0B0D",
              color: "#9AA1AD",
              fontFamily: "ui-monospace, monospace",
              fontSize: 13,
            }}
          >
            Cargando AuditBrain Executive OS…
          </div>
        }
      >
        <CommandCenter />
      </Suspense>
    );
  }
  return <App />;
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
