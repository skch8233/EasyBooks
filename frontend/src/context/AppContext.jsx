import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { OFFLINE } from "@/lib/offline";

const AppCtx = createContext(null);
export const useApp = () => useContext(AppCtx);

export function AppProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = logged out
  const [fys, setFys] = useState([]);
  const [fy, setFyState] = useState(null);
  const [settings, setSettings] = useState(null);
  const [biz, setBiz] = useState(null);
  const loadBiz = useCallback(() => api.get("/billing/status").then((r) => setBiz(r.data)), []);

  const loadMeta = useCallback(async (me) => {
    const [f, s] = await Promise.all([api.get("/financial-years"), api.get("/settings"), loadBiz()]);
    setFys(f.data);
    setSettings(s.data);
    const want = me?.working_fy_id || localStorage.getItem("eb_fy");
    setFyState(f.data.find((x) => x.id === want) || f.data.find((x) => x.is_active) || f.data[0] || null);
  }, [loadBiz]);

  useEffect(() => {
    if (OFFLINE) {
      const start = (n) => api.post("/offline/session").then(async (r) => {
        localStorage.setItem("eb_token", r.data.token);
        let u = r.data.user;
        const want = localStorage.getItem("eb_biz");
        if (want && want !== u.business_id) {
          try { const s = (await api.post("/ca/switch", { business_id: want })).data; localStorage.setItem("eb_token", s.token); u = s.user; } catch { localStorage.removeItem("eb_biz"); }
        }
        await loadMeta(u);
        setUser(u);
      })
        .catch(() => (n < 10 ? setTimeout(() => start(n + 1), 1500) : setUser(false)));
      start(0);
      return;
    }
    if (!localStorage.getItem("eb_token")) return setUser(false);
    api.get("/auth/me").then((r) => { setUser(r.data); return loadMeta(r.data); }).catch(() => { localStorage.removeItem("eb_token"); setUser(false); });
  }, [loadMeta]);

  const startSession = async (data) => {
    localStorage.setItem("eb_token", data.token);
    localStorage.removeItem("eb_fy");
    setUser(data.user);
    await loadMeta(data.user);
  };
  const signup = async (body) => startSession((await api.post("/auth/signup", body)).data);
  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.removeItem("eb_fy");
    localStorage.setItem("eb_token", data.token);
    try { await loadMeta(data.user); } catch (e) { localStorage.removeItem("eb_token"); throw e; }
    setUser(data.user);
  };
  const logout = () => {
    localStorage.removeItem("eb_token");
    localStorage.removeItem("eb_biz");
    setUser(false);
  };
  const switchBusiness = async (business_id) => {
    const { data } = await api.post("/ca/switch", { business_id });
    localStorage.setItem("eb_token", data.token);
    localStorage.setItem("eb_biz", business_id);
    localStorage.removeItem("eb_fy");
    await loadMeta(null);
    setUser(data.user);
    return data.user;
  };
  const setFy = (f) => {
    localStorage.setItem("eb_fy", f.id);
    setFyState(f);
    api.put(`/financial-years/${f.id}/working`).catch(() => {});
  };
  const setCompanyFy = async (f) => {
    await api.put(`/financial-years/${f.id}/company-default`);
    setFys((list) => list.map((x) => ({ ...x, is_active: x.id === f.id })));
    setFyState({ ...f, is_active: true });
  };

  const expired = biz?.status === "expired";
  const canWrite = user && ["admin", "accountant"].includes(user.role) && !expired;
  const isAdmin = user && user.role === "admin";

  return (
    <AppCtx.Provider value={{ user, login, signup, logout, switchBusiness, biz, loadBiz, expired, fys, fy, setFy, setCompanyFy, settings, setSettings, loadMeta, canWrite, isAdmin }}>
      {children}
    </AppCtx.Provider>
  );
}
