import axios from "axios";

export const api = axios.create({ baseURL: `${process.env.REACT_APP_BACKEND_URL}/api` });

// Each window/tab keeps its own business token; localStorage only seeds new windows
export const getToken = () => sessionStorage.getItem("eb_token") || localStorage.getItem("eb_token");
export const setToken = (t) => { sessionStorage.setItem("eb_token", t); localStorage.setItem("eb_token", t); };
export const clearToken = () => { sessionStorage.removeItem("eb_token"); localStorage.removeItem("eb_token"); };
if (!sessionStorage.getItem("eb_token") && localStorage.getItem("eb_token")) sessionStorage.setItem("eb_token", localStorage.getItem("eb_token"));

api.interceptors.request.use((c) => {
  const t = getToken();
  if (t && !c.headers.Authorization) c.headers.Authorization = `Bearer ${t}`;
  return c;
});

api.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e.response?.status === 401 && !e.config?.url?.includes("/auth/login") && !e.config?.url?.includes("/public/")) {
      clearToken();
      if (process.env.REACT_APP_OFFLINE === "1") window.location.reload();
      else if (window.location.pathname !== "/login") window.location.href = "/login";
    }
    return Promise.reject(e);
  }
);

export function errMsg(e) {
  const d = e?.response?.data?.detail;
  if (d == null) return e?.message || "Something went wrong. Please try again.";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => (typeof x?.msg === "string" ? x.msg : JSON.stringify(x))).join(" ");
  if (typeof d?.msg === "string") return d.msg;
  return String(d);
}
