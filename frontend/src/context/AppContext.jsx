import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AppCtx = createContext(null);
export const useApp = () => useContext(AppCtx);

export function AppProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = logged out
  const [fys, setFys] = useState([]);
  const [fy, setFyState] = useState(null);
  const [settings, setSettings] = useState(null);
  const [biz, setBiz] = useState(null);
  const loadBiz = useCallback(() => api.get("/billing/status").then((r) => setBiz(r.data)), []);

  const loadMeta = useCallback(async () => {
    const [f, s] = await Promise.all([api.get("/financial-years"), api.get("/settings"), loadBiz()]);
    setFys(f.data);
    setSettings(s.data);
    const saved = localStorage.getItem("eb_fy");
    setFyState(f.data.find((x) => x.id === saved) || f.data.find((x) => x.is_active) || f.data[0] || null);
  }, [loadBiz]);

  useEffect(() => {
    if (!localStorage.getItem("eb_token")) return setUser(false);
    api.get("/auth/me").then((r) => { setUser(r.data); return loadMeta(); }).catch(() => setUser(false));
  }, [loadMeta]);

  const startSession = async (data) => {
    localStorage.setItem("eb_token", data.token);
    localStorage.removeItem("eb_fy");
    setUser(data.user);
    await loadMeta();
  };
  const signup = async (body) => startSession((await api.post("/auth/signup", body)).data);
  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.removeItem("eb_fy");
    localStorage.setItem("eb_token", data.token);
    setUser(data.user);
    await loadMeta();
  };
  const logout = () => {
    localStorage.removeItem("eb_token");
    setUser(false);
  };
  const setFy = (f) => { localStorage.setItem("eb_fy", f.id); setFyState(f); };

  const expired = biz?.status === "expired";
  const canWrite = user && ["admin", "accountant"].includes(user.role) && !expired;
  const isAdmin = user && user.role === "admin";

  return (
    <AppCtx.Provider value={{ user, login, signup, logout, biz, loadBiz, expired, fys, fy, setFy, settings, setSettings, loadMeta, canWrite, isAdmin }}>
      {children}
    </AppCtx.Provider>
  );
}
