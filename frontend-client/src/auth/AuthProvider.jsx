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

  const login = async (email, password) => {
    const r = await api.login(email, password);
    await refresh();
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
