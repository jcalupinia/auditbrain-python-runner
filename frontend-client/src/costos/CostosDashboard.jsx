import PortalShell from "../shell/PortalShell.jsx";

const modules = [
  "Parametros y maestros",
  "Materia prima y suministros",
  "Acumulacion de costos de produccion",
  "Produccion en proceso y producto terminado",
  "Kardex, ventas y costo de ventas",
  "Conciliacion integral de inventarios",
  "Estado de costos de produccion y ventas",
  "Conciliacion contable integral",
];

export default function CostosDashboard() {
  return (
    <PortalShell title="SOFTWARE DE COSTOS" subtitle="AuditSmart Costo Global 2026" activeCategory="SOCIETARIAS" activeNodeCode="SOFTWARE_COSTOS">
      <section className="pc-panel">
        <header className="pc-panel-h"><span className="pc-panel-t">Software de Costos</span></header>
        <div className="pc-panel-b">
          <h2>AuditSmart Costo Global 2026</h2>
          <p>Modulo incorporado al Portal de Clientes. La carga de datos y el motor de procesamiento se habilitaran tras su integracion y validacion.</p>
          <div className="pc-tiles">
            {modules.map((name, index) => (
              <div key={name} className="pc-tile" style={{ cursor: "default" }}>
                <span className="pc-tile-n">{index + 1}</span>
                <div className="pc-tile-txt"><span className="pc-tile-t">{name}</span><span className="pc-tile-d">Pendiente de habilitacion</span></div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </PortalShell>
  );
}
