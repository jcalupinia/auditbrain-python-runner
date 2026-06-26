import { createContext, useContext, useState, useEffect, useCallback } from "react";
import * as api from "../api.js";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionInvalidated, setSessionInvalidated] = useState(false);
  const [deviceBlocked, setDeviceBlocked] = useState(false);

  const refresh = useCallback(async () => {
    if (!api.getToken()) {
      setUser(null); setLoading(false); return;
    }
    try {
      const me = await api.me();
      setUser(me);
    } catch (e) {
      if (e.code === "session_invalidated") setSessionInvalidated(true);
      if (e.code === "device_unauthorized") setDeviceBlocked(true);
      setUser(null);
      api.setToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Heartbeat de sesión única: mientras la pestaña esté abierta y haya un
  // usuario logueado, hacemos un ping cada 3 min (/me → touch_session en el
  // backend) para mantener viva la sesión. El backend libera la cuenta tras
  // ~10 min de inactividad; así, mientras la persona tiene el portal abierto
  // nadie más puede entrar, pero si cierra el navegador la sesión se libera
  // sola y otro podrá ingresar (regla "el primero gana").
  useEffect(() => {
    if (!user || user.password_reset_required) return;
    const id = setInterval(() => {
      if (!api.getToken()) return;
      api.me().catch((e) => {
        if (e.code === "session_invalidated") {
          setSessionInvalidated(true);
          setUser(null);
          api.setToken(null);
        }
      });
    }, 3 * 60 * 1000);
    return () => clearInterval(id);
  }, [user]);

  const login = async (email, password) => {
    const r = await api.login(email, password);
    // Si el usuario debe cambiar contraseña, NO llamamos a me() todavía:
    // el endpoint requiere device validation y la cookie device_id recién
    // seteada puede no haberse propagado, lo cual borraría el token (vía
    // refresh() catch). Marcamos un usuario "parcial" sólo para que las
    // pantallas protegidas detecten password_reset_required y redirijan
    // a /change-password sin perder el token Bearer.
    if (r.password_reset_required) {
      setUser({ email, password_reset_required: true });
      setLoading(false);
    } else {
      await refresh();
    }
    return r;
  };

  const logout = async () => {
    await api.logout();
    setUser(null);
  };

  return (
    <AuthCtx.Provider value={{
      user, loading, login, logout, refresh,
      sessionInvalidated, clearSessionFlag: () => setSessionInvalidated(false),
      deviceBlocked, clearDeviceBlockedFlag: () => setDeviceBlocked(false),
    }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
