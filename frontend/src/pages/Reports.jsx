import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { FileSpreadsheet, FileText, Printer, CheckCircle2, AlertTriangle } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { dmy } from "@/lib/format";
import { REPORTS } from "@/lib/reports";
import { exportExcel, exportPdf } from "@/lib/export";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DateInput } from "@/components/DateInput";
import { LedgerSelect } from "@/components/LedgerSelect";
import { ReportTable } from "@/components/ReportTable";
import { VoucherDialog } from "@/components/VoucherDialog";

export default function Reports() {
  const { report = "trial-balance" } = useParams();
  const [sp, setSp] = useSearchParams();
  const nav = useNavigate();
  const { fy, settings } = useApp();
  const cfg = REPORTS.find((r) => r.id === report) || REPORTS[0];
  const [p, setP] = useState({ from: fy?.start_date, to: fy?.end_date });
  const [ledgers, setLedgers] = useState([]);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState(null);
  const ledger = sp.get("ledger") || "";

  useEffect(() => { api.get("/ledgers").then((r) => setLedgers(r.data)); }, []);
  useEffect(() => { if (fy) setP({ from: fy.start_date, to: fy.end_date }); }, [fy]);
  useEffect(() => {
    if (cfg.groups && ledgers.length && !ledgers.some((l) => l.id === ledger && cfg.groups.includes(l.group))) {
      const first = ledgers.find((l) => cfg.groups.includes(l.group));
      if (first) setSp({ ledger: first.id }, { replace: true });
    }
  }, [cfg, ledgers, ledger, setSp]);
  useEffect(() => {
    if (!p.from) return;
    let alive = true;
    setErr("");
    setRes(null);
    cfg.load({ ...p, ledger }).then((r) => alive && setRes(r)).catch((e) => alive && setErr(errMsg(e)));
    return () => { alive = false; };
  }, [cfg, p, ledger]);

  const sub = cfg.filter === "asof" ? `As on ${dmy(p.to)}` : `${dmy(p.from)} to ${dmy(p.to)}`;
  const title = `${cfg.label}${res?.note ? ` - ${res.note}` : ""}`;

  return (
    <div className="space-y-6" data-testid="reports-page">
      <div className="no-print flex gap-2 overflow-x-auto pb-1" data-testid="report-tabs">
        {REPORTS.map((r) => (
          <button key={r.id} onClick={() => nav(`/reports/${r.id}`)} data-testid={`report-tab-${r.id}`}
            className={`shrink-0 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${r.id === cfg.id ? "bg-primary text-white border-primary" : "bg-white hover:bg-slate-50"}`}>{r.label}</button>
        ))}
      </div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight" data-testid="report-title">{cfg.label}</h1>
          <p className="text-slate-500 mt-1">{settings?.company_name} · {sub}{res?.note ? ` · ${res.note}` : ""}</p>
        </div>
        <div className="no-print flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => exportExcel(title, sub, res?.sections || [])} data-testid="export-excel-button"><FileSpreadsheet className="h-4 w-4 mr-1" /> Excel</Button>
          <Button variant="outline" onClick={() => exportPdf(title, sub, res?.sections || [], settings?.company_name)} data-testid="export-pdf-button"><FileText className="h-4 w-4 mr-1" /> PDF</Button>
          <Button variant="outline" onClick={() => window.print()} data-testid="print-report-button"><Printer className="h-4 w-4 mr-1" /> Print</Button>
        </div>
      </div>
      <div className="no-print grid gap-3 rounded-xl border bg-white p-4 sm:grid-cols-2 lg:grid-cols-[170px_170px_1fr]">
        {cfg.filter !== "asof" && <div><div className="text-xs font-semibold text-slate-500 mb-1">From</div><DateInput value={p.from} onChange={(from) => setP({ ...p, from })} testid="report-filter-date-from" /></div>}
        <div><div className="text-xs font-semibold text-slate-500 mb-1">{cfg.filter === "asof" ? "As on" : "To"}</div><DateInput value={p.to} onChange={(to) => setP({ ...p, to })} testid="report-filter-date-to" /></div>
        {cfg.filter === "ledger" && <div><div className="text-xs font-semibold text-slate-500 mb-1">Ledger</div>
          <LedgerSelect ledgers={ledgers} groups={cfg.groups} value={ledger} onChange={(id) => setSp({ ledger: id })} testid="report-ledger-select" /></div>}
      </div>
      {res?.balanced !== undefined && (
        <div className={`flex items-center gap-2 rounded-lg border px-4 py-3 text-sm font-medium ${res.balanced ? "bg-emerald-50 border-emerald-200 text-emerald-800" : "bg-red-50 border-red-200 text-red-800"}`} data-testid="report-balanced-status">
          {res.balanced ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />} {res.balanced ? "Totals match. Books are balanced." : "Totals do not match."}
        </div>
      )}
      {err && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>}
      {res && res.sections.length === 0 && <div className="rounded-xl border bg-white p-10 text-center text-slate-500">{res.note}</div>}
      <div className={res?.side ? "grid gap-6 lg:grid-cols-2" : "space-y-6"}>
        {res?.sections.map((s, i) => <ReportTable key={i} section={s} onRowClick={setOpen} testid={`report-table-${i}`} />)}
      </div>
      <VoucherDialog id={open} onClose={() => setOpen(null)} onChanged={() => setP({ ...p })} />
    </div>
  );
}
