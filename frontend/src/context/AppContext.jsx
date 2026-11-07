import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AppCtx = createContext(null);
export const useApp = () => useContext(AppCtx);

export function AppProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = logged out
  const [fys, setFys] = useState([]);
  const [fy, setFyState] = useState(null);
  const [settings, setSettings] = useState(null);

  const loadMeta = useCallback(async () => {
    const [f, s] = await Promise.all([api.get("/financial-years"), api.get("/settings")]);
    setFys(f.data);
    setSettings(s.data);
    const saved = localStorage.getItem("eb_fy");
    setFyState(f.data.find((x) => x.id === saved) || f.data.find((x) => x.is_active) || f.data[0] || null);
  }, []);

  useEffect(() => {
    if (!localStorage.getItem("eb_token")) return setUser(false);
    api.get("/auth/me").then((r) => { setUser(r.data); return loadMeta(); }).catch(() => setUser(false));
  }, [loadMeta]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("eb_token", data.token);
    setUser(data.user);
    await loadMeta();
  };
  const logout = () => {
    localStorage.removeItem("eb_token");
    setUser(false);
  };
  const setFy = (f) => { localStorage.setItem("eb_fy", f.id); setFyState(f); };

  const canWrite = user && ["admin", "accountant"].includes(user.role);
  const isAdmin = user && user.role === "admin";

  return (
    <AppCtx.Provider value={{ user, login, logout, fys, fy, setFy, settings, setSettings, loadMeta, canWrite, isAdmin }}>
      {children}
    </AppCtx.Provider>
  );
}
