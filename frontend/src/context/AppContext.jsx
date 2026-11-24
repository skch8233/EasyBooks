import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getToken, setToken, clearToken } from "@/lib/api";
import { OFFLINE } from "@/lib/offline";

const AppCtx = createContext(null);
export const useApp = () => useContext(AppCtx);

export function AppProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = logged out
  const [fys, setFys] = useState([]);
  const [fy, setFyState] = useState(null);
  const [settings, setSettings] = useState(null);
  const [biz, setBiz] = useState(null);
  const [industry, setIndustry] = useState(null);
  const loadIndustry = useCallback(() => (OFFLINE ? Promise.resolve() : api.get("/industry").then((r) => setIndustry(r.data)).catch(() => {})), []);
  const loadBiz = useCallback(() => api.get("/billing/status").then((r) => setBiz(r.data)), []);

  const loadMeta = useCallback(async (me) => {
    const [f, s] = await Promise.all([api.get("/financial-years"), api.get("/settings"), loadBiz(), loadIndustry()]);
    setFys(f.data);
    setSettings(s.data);
    const want = me?.working_fy_id || localStorage.getItem("eb_fy");
    setFyState(f.data.find((x) => x.id === want) || f.data.find((x) => x.is_active) || f.data[0] || null);
  }, [loadBiz, loadIndustry]);

  useEffect(() => {
    if (OFFLINE) {
      const start = (n) => api.post("/offline/session").then(async (r) => {
        let u = r.data.user, tok = r.data.token;
        const want = sessionStorage.getItem("eb_biz") || localStorage.getItem("eb_biz");
        if (want && want !== u.business_id) {
          try { const s = (await api.post("/ca/switch", { business_id: want }, { headers: { Authorization: `Bearer ${tok}` } })).data; tok = s.token; u = s.user; } catch { sessionStorage.removeItem("eb_biz"); }
        }
        sessionStorage.setItem("eb_token", tok);
        await loadMeta(u);
        setUser(u);
      })
        .catch(() => (n < 10 ? setTimeout(() => start(n + 1), 1500) : setUser(false)));
      start(0);
      return;
    }
    if (!getToken()) return setUser(false);
    api.get("/auth/me").then((r) => { setUser(r.data); return loadMeta(r.data); }).catch(() => { clearToken(); setUser(false); });
  }, [loadMeta]);

  useEffect(() => {
    const h = (e) => { if (e.key === "eb_token" && !e.newValue && !OFFLINE) { sessionStorage.removeItem("eb_token"); setUser(false); } };
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);

  const startSession = async (data) => {
    setToken(data.token);
    localStorage.removeItem("eb_fy");
    setUser(data.user);
    await loadMeta(data.user);
  };
  const signup = async (body) => startSession((await api.post("/auth/signup", body)).data);
  const startDemo = (data) => startSession(data);
  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.removeItem("eb_fy");
    setToken(data.token);
    try { await loadMeta(data.user); } catch (e) { clearToken(); throw e; }
    setUser(data.user);
  };
  const logout = () => {
    clearToken();
    localStorage.removeItem("eb_biz");
    sessionStorage.removeItem("eb_biz");
    setUser(false);
  };
  const enterSupport = async (data) => {
    sessionStorage.setItem("eb_token_home", getToken());
    sessionStorage.setItem("eb_token", data.token);
    await loadMeta(null);
    setUser(data.user);
  };
  const exitSupport = async () => {
    sessionStorage.setItem("eb_token", sessionStorage.getItem("eb_token_home") || localStorage.getItem("eb_token"));
    sessionStorage.removeItem("eb_token_home");
    const me = (await api.get("/auth/me")).data;
    await loadMeta(me);
    setUser(me);
  };
  const switchBusiness = async (business_id) => {
    const { data } = await api.post("/ca/switch", { business_id });
    setToken(data.token);
    sessionStorage.setItem("eb_biz", business_id);
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
    <AppCtx.Provider value={{ user, login, signup, logout, switchBusiness, enterSupport, exitSupport, startDemo, industry, setIndustry, biz, loadBiz, expired, fys, fy, setFy, setCompanyFy, settings, setSettings, loadMeta, canWrite, isAdmin }}>
      {children}
    </AppCtx.Provider>
  );
}
