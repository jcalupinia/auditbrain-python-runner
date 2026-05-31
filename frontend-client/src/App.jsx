import Landing from "./landing/Landing.jsx";
import Login from "./auth/Login.jsx";
import ChangePassword from "./auth/ChangePassword.jsx";
import DeviceBlocked from "./auth/DeviceBlocked.jsx";
import ClientCatalog from "./catalog/ClientCatalog.jsx";
import ToolShell from "./tools/ToolShell.jsx";
import { useAuth } from "./auth/AuthProvider.jsx";
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
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/change-password" element={<ChangePassword />} />
      <Route path="/device-blocked" element={<DeviceBlocked />} />
      <Route path="/catalog" element={<Protected><ClientCatalog /></Protected>} />
      <Route path="/tools/:toolCode" element={<Protected><ToolShell /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
