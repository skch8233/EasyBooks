import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { amt, dmy } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const Posted = ({ p, testid }) => p ? <span className="text-sm text-emerald-700" data-testid={testid}>Posted as <b>{p.voucher_no}</b> · ₹{amt(p.amount)} (posting again replaces it)</span> : <span className="text-sm text-amber-700" data-testid={testid}>Not posted yet</span>;

const State = ({ err, retry, testid }) => <div className="rounded-xl border bg-white p-6 text-sm" data-testid={testid}>
  {err ? <span className="text-red-700">Could not load: {err} <button className="underline ml-1" onClick={retry}>Try again</button></span> : <span className="text-slate-500">Loading...</span>}</div>;

const Depreciation = ({ period, canWrite, onPosted }) => {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => { setErr(""); return api.get("/depreciation", { params: period }).then((r) => setD(r.data)).catch((e) => { setD(null); setErr(errMsg(e)); }); }, [period]);
  useEffect(() => { load(); }, [load]);
  const post = async () => {
    setBusy(true);
    try { const { data } = await api.post("/depreciation/post", period); toast.success(`Depreciation ₹${amt(data.amount)} posted as ${data.voucher_no}`); load(); onPosted(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  if (!d) return <State err={err} retry={load} testid="dep-state" />;
  const C = ["opening", "additions", "deletions", "depreciation", "closing"];
  return (
    <section className="rounded-xl border bg-white" data-testid="dep-section">
      <div className="flex flex-wrap items-center gap-3 px-5 py-4 border-b"><h2 className="font-heading text-lg font-bold">1. Fixed asset depreciation</h2><Posted p={d.posted} testid="dep-posted" />
        {canWrite && <Button className="ml-auto" disabled={busy || d.total <= 0} onClick={post} data-testid="dep-post-button">Post depreciation ₹{amt(d.total)}</Button>}</div>
      <div className="overflow-x-auto"><table className="w-full eb-table text-sm" data-testid="dep-table">
        <thead><tr><th>Asset</th><th>Method</th><th className="text-right">Rate %</th><th className="text-right">Opening WDV</th><th className="text-right">Additions</th><th className="text-right">Deletions</th><th className="text-right">Depreciation</th><th className="text-right">Closing WDV</th></tr></thead>
        <tbody>{d.rows.length === 0 && <tr><td colSpan={8} className="text-center py-6 text-slate-500">No fixed asset ledgers yet. Create one under the Fixed Assets group in <Link className="text-primary underline" to="/ledgers">Ledgers</Link>.</td></tr>}
          {d.rows.map((r) => <tr key={r.ledger_id} data-testid={`dep-row-${r.asset}`}><td>{r.asset}</td>
            <td>{r.method === "none" ? <Link className="text-primary underline text-xs" to="/ledgers">Set method &amp; rate</Link> : r.method.toUpperCase()}</td><td className="text-right">{r.rate || "-"}</td>
            {C.map((k) => <td key={k} className={`text-right font-mono ${k === "depreciation" ? "font-semibold" : ""}`}>{amt(r[k])}</td>)}</tr>)}</tbody>
        <tfoot><tr className="font-semibold">{["Total", "", ""].map((x, i) => <td key={i}>{x}</td>)}{C.map((k) => <td key={k} className="text-right font-mono" data-testid={`dep-total-${k}`}>{amt(d.rows.reduce((s, r) => s + r[k], 0))}</td>)}</tr></tfoot>
      </table></div>
      <p className="px-5 py-3 text-xs text-slate-500">WDV: rate on opening value less sales, plus rate on additions (half rate if used under 180 days in the year). SLM: rate on original cost, pro-rata for additions, keeping 5% residual value. Posting creates a journal: Depreciation Dr / asset ledgers Cr, dated the last day of the period.</p>
    </section>
  );
};

const Tax = ({ period, canWrite, refresh }) => {
  const [f, setF] = useState({ rate: "", add_back: 0, deductions: 0 });
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const bad = ["rate", "add_back", "deductions"].some((k) => Number(f[k]) < 0) || Number(f.rate) > 60;
  const load = useCallback(() => {
    if (bad) return Promise.resolve();
    setErr("");
    return api.get("/tax-provision", { params: { ...period, rate: Number(f.rate) || 0, add_back: Number(f.add_back) || 0, deductions: Number(f.deductions) || 0 } })
      .then((r) => { setD(r.data); if (f.rate === "" && r.data.presets[0]?.rate) setF((x) => ({ ...x, rate: r.data.presets[0].rate })); }).catch((e) => setErr(errMsg(e)));
  }, [period, f, refresh, bad]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { const t = setTimeout(load, 400); return () => clearTimeout(t); }, [load]);
  const post = async () => {
    setBusy(true);
    try { const { data } = await api.post("/tax-provision/post", { ...period, rate: Number(f.rate), add_back: Number(f.add_back) || 0, deductions: Number(f.deductions) || 0 }); toast.success(`Tax provision ₹${amt(data.amount)} posted as ${data.voucher_no}`); load(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  if (!d) return <State err={err} retry={load} testid="tax-state" />;
  const row = (l, v, id, bold) => <div className={`flex justify-between py-1.5 border-b ${bold ? "font-bold" : ""}`}><span>{l}</span><span className="font-mono" data-testid={id}>₹{amt(v)}</span></div>;
  return (
    <section className="rounded-xl border bg-white" data-testid="tax-section">
      <div className="flex flex-wrap items-center gap-3 px-5 py-4 border-b"><h2 className="font-heading text-lg font-bold">2. Income-tax provision</h2><Posted p={d.posted} testid="tax-posted" />
        {canWrite && <Button className="ml-auto" disabled={busy || bad || d.tax <= 0} onClick={post} data-testid="tax-post-button">Post tax provision ₹{amt(d.tax)}</Button>}</div>
      <div className="grid gap-6 p-5 lg:grid-cols-2">
        <div className="space-y-3">
          {!d.depreciation_posted && <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800" data-testid="tax-dep-warning">Post depreciation first so the profit before tax is correct.</div>}
          <div className="space-y-1"><Label className="text-xs">Tax rate preset ({d.business_type})</Label>
            <select className="h-10 w-full rounded-md border px-2 bg-white text-sm" value={d.presets.find((p) => p.rate === Number(f.rate))?.rate ?? ""} onChange={(e) => setF({ ...f, rate: e.target.value })} data-testid="tax-preset">
              <option value="">Custom rate</option>{d.presets.map((p) => <option key={p.label} value={p.rate}>{p.label} - {p.rate}%</option>)}</select></div>
          <div className="grid grid-cols-3 gap-3">
            {[["rate", "Effective rate %"], ["add_back", "Add: disallowances (₹)"], ["deductions", "Less: deductions / exempt (₹)"]].map(([k, l]) =>
              <div key={k} className="space-y-1"><Label className="text-xs">{l}</Label><Input type="number" min="0" max={k === "rate" ? 60 : undefined} step="any" className="h-10 font-mono" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`tax-${k}`} /></div>)}
          </div>
          {bad && <div className="text-sm text-red-700" data-testid="tax-input-error">Rate must be 0-60% and amounts cannot be negative.</div>}
          {err && <div className="text-sm text-red-700" data-testid="tax-error">{err}</div>}
          <p className="text-xs text-slate-500">Rates include surcharge and 4% health &amp; education cess. Disallowances are items not allowed for tax (e.g. excess depreciation over tax rates, penalties, unpaid statutory dues u/s 43B).</p>
        </div>
        <div className="text-sm" data-testid="tax-computation">
          {row("Profit before tax (books, incl. stock change)", d.pbt, "tax-pbt")}
          {row("Add: disallowances", d.add_back, "tax-addback")}{row("Less: deductions", d.deductions, "tax-deductions")}
          {row("Estimated taxable income", d.taxable, "tax-taxable", true)}
          {row(`Tax @ ${Number(d.rate) || 0}% (rounded)`, d.tax, "tax-amount", true)}
          <p className="text-xs text-slate-500 mt-2">Posting creates a journal: Income Tax Expense Dr / Provision for Income Tax Cr. Advance tax and TDS paid are adjusted against the provision when you pay or file.</p>
        </div>
      </div>
    </section>
  );
};

export default function YearEnd() {
  const { fy, canWrite } = useApp();
  const [period, setPeriod] = useState({ from_date: fy?.start_date, to_date: fy?.end_date });
  const [n, setN] = useState(0);
  useEffect(() => { if (fy) setPeriod({ from_date: fy.start_date, to_date: fy.end_date }); }, [fy]);
  if (!period.from_date) return <State testid="ye-state" />;
  const badPeriod = period.from_date > period.to_date;
  return (
    <div className="space-y-6" data-testid="year-end-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="font-heading text-3xl font-extrabold tracking-tight">Depreciation &amp; Tax</h1>
          <p className="text-slate-500 mt-1">Year-end entries for {dmy(period.from_date)} to {dmy(period.to_date)}. Both flow into <Link className="text-primary underline" to="/final-accounts">Final Accounts</Link>.</p></div>
        <div className="flex gap-2">{["from_date", "to_date"].map((k) => <Input key={k} type="date" className="h-10 w-44" value={period[k]} onChange={(e) => setPeriod({ ...period, [k]: e.target.value })} data-testid={`ye-${k}`} />)}</div>
      </div>
      {badPeriod ? <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" data-testid="ye-period-error">The start date must be on or before the end date.</div> : <>
        <Depreciation period={period} canWrite={canWrite} onPosted={() => setN(n + 1)} />
        <Tax period={period} canWrite={canWrite} refresh={n} /></>}
    </div>
  );
}
