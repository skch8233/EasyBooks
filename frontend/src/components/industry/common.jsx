import React, { useCallback, useEffect, useState } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";

export const useList = (url) => {
  const [rows, setRows] = useState(null);
  const load = useCallback(() => api.get(url).then((r) => setRows(r.data)).catch(() => setRows([])), [url]);
  useEffect(() => { load(); }, [load]);
  return [rows, load];
};

export const useMoneyLedgers = () => {
  const [ledgers] = useList("/ledgers");
  return (ledgers || []).filter((l) => l.group === "cash" || l.group === "bank").sort((a, b) => (a.group === "cash" ? -1 : 0) - (b.group === "cash" ? -1 : 0));
};

export const todayIso = () => new Date().toISOString().slice(0, 10);
export const sel = "h-10 w-full rounded-md border px-3 bg-white text-sm";
export const PageHead = ({ title, sub, children }) => (
  <div className="flex flex-wrap items-end justify-between gap-3">
    <div><h1 className="font-heading text-3xl font-extrabold tracking-tight">{title}</h1>{sub && <p className="text-slate-500 mt-1">{sub}</p>}</div>
    <div className="flex gap-2">{children}</div>
  </div>
);
export const Card = ({ children, className = "", ...p }) => <div className={`rounded-xl border bg-white p-5 ${className}`} {...p}>{children}</div>;
export const Th = ({ children, r }) => <th className={`pb-2 pr-3 text-xs uppercase text-slate-500 ${r ? "text-right" : ""}`}>{children}</th>;
export const Td = ({ children, r, className = "" }) => <td className={`py-2.5 pr-3 ${r ? "text-right num" : ""} ${className}`}>{children}</td>;

const optList = (children) => React.Children.toArray(children).flatMap((c) => (c?.type === React.Fragment ? React.Children.toArray(c.props.children) : [c]))
  .filter((c) => c?.props).map((c) => ({ value: String(c.props.value ?? c.props.children), label: c.props.children }));

// Styled dropdown that accepts <option> children like a native select
export const Pick = ({ value, onChange, children, className = "", ...rest }) => {
  const opts = optList(children);
  const NONE = "__none";
  return (
    <Select value={value === "" || value == null ? NONE : String(value)} onValueChange={(v) => onChange(v === NONE ? "" : v)}>
      <SelectTrigger className={`h-10 bg-white text-slate-900 ${className}`} data-testid={rest["data-testid"]}><SelectValue /></SelectTrigger>
      <SelectContent className="max-h-72">{opts.map((o) => <SelectItem key={o.value} value={o.value === "" ? NONE : o.value}>{o.label}</SelectItem>)}</SelectContent>
    </Select>
  );
};

export const monthOptions = (n = 18) => Array.from({ length: n }, (_, i) => { const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - i + 1); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; });
