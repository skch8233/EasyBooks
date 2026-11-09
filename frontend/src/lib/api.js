import axios from "axios";

export const api = axios.create({ baseURL: `${process.env.REACT_APP_BACKEND_URL}/api` });

api.interceptors.request.use((c) => {
  const t = localStorage.getItem("eb_token");
  if (t) c.headers.Authorization = `Bearer ${t}`;
  return c;
});

api.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e.response?.status === 401 && !e.config?.url?.includes("/auth/login") && !e.config?.url?.includes("/public/")) {
      localStorage.removeItem("eb_token");
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
