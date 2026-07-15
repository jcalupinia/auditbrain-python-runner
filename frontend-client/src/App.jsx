import CharlaLanding from "./charla/CharlaLanding.jsx";
import Login from "./auth/Login.jsx";
import ChangePassword from "./auth/ChangePassword.jsx";
import DeviceBlocked from "./auth/DeviceBlocked.jsx";
import ClientCatalog from "./catalog/ClientCatalog.jsx";
import ToolShell from "./tools/ToolShell.jsx";
import ICTDashboard from "./ict/ICTDashboard.jsx";
import FlujoDashboard from "./flujo/FlujoDashboard.jsx";
import ForgeDashboard from "./forge/ForgeDashboard.jsx";
import { useAuth } from "./auth/AuthProvider.jsx";
import ThemeSwitcher from "./theme/ThemeSwitcher.jsx";
import { Routes, Route, Navigate } from "react-router-dom";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div style={{padding:40}}>Cargando...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.password_reset_required) return <Navigate to="/change-password" replace />;
  return children;
}

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/charla" element={<CharlaLanding />} />
        <Route path="/login" element={<Login />} />
        <Route path="/change-password" element={<ChangePassword />} />
        <Route path="/device-blocked" element={<DeviceBlocked />} />
        <Route path="/catalog" element={<Protected><ClientCatalog /></Protected>} />
        <Route path="/tools/ICT_2025" element={<Protected><ICTDashboard /></Protected>} />
        <Route path="/tools/FLUJO_EFECTIVO" element={<Protected><FlujoDashboard /></Protected>} />
        <Route path="/tools/FORGE_CONSOLE" element={<Protected><ForgeDashboard /></Protected>} />
        <Route path="/tools/:toolCode" element={<Protected><ToolShell /></Protected>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      {/* Selector de color de fondo — global, visible en todas las pantallas */}
      <ThemeSwitcher />
    </>
  );
}
