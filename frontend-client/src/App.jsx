import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./auth/AuthProvider.jsx";
import Landing from "./landing/Landing.jsx";

// Placeholders — implementadas en tareas posteriores
function Login() { return <div style={{padding:40}}>Login (pendiente)</div>; }
function Catalog() { return <div style={{padding:40}}>Catálogo (pendiente)</div>; }

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
      <Route path="/catalog" element={<Protected><Catalog /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
