import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { FileSpreadsheet, Printer } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { amt, dmy } from "@/lib/format";
import { exportExcel } from "@/lib/export";
import { printNode } from "@/lib/erp";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const v = (n) => (n ? amt(n) : "-");
const Stmt = ({ title, rows, d, testid }) => (
  <div className="mb-8" data-testid={testid}>
    <div className="text-center font-bold uppercase">{d.company}</div>
    {d.cin && ["company", "llp"].includes(d.business_type) && <div className="text-center text-xs">{d.business_type === "llp" ? "LLPIN" : "CIN"}: {d.cin}</div>}
    <div className="text-center font-bold mt-1">{title}</div>
    <div className="text-center text-xs italic mb-2">{d.kind === "company" ? "(As per Schedule III to the Companies Act, 2013)" : d.purpose_text}{d.project ? ` · Project ${d.project.code} - ${d.project.name}` : ""}</div>
    <div className="text-right text-xs mb-1">(Amount in ₹)</div>
    <table className="w-full border-collapse text-[12.5px]">
      <thead><tr className="border-y-2 border-slate-800"><th className="text-left py-1.5">Particulars</th><th className="w-16 text-center">Note No.</th>
        <th className="w-36 text-right">As at / for year ended {dmy(d.to_date)}</th><th className="w-36 text-right">{d.prev_to_date ? `Previous year ${dmy(d.prev_to_date)}` : "Previous year"}</th></tr></thead>
      <tbody>{rows.map((r, i) => r.type === "title" ? <tr key={i}><td colSpan={4} className="pt-3 font-bold">{r.label}</td></tr>
        : r.type === "head" ? <tr key={i}><td colSpan={4} className="pt-2 pl-3 font-semibold">{r.label}</td></tr>
        : r.type === "total" ? <tr key={i} className="font-bold border-y border-slate-700"><td className="py-1 pl-3">{r.label}</td><td></td><td className="text-right font-mono">{v(r.cy)}</td><td className="text-right font-mono">{v(r.py)}</td></tr>
        : <tr key={i}><td className="py-0.5 pl-6">{r.label}</td><td className="text-center">{r.note || ""}</td><td className="text-right font-mono">{v(r.cy)}</td><td className="text-right font-mono">{v(r.py)}</td></tr>)}</tbody>
    </table>
  </div>
);

const Sign = ({ d, a }) => {
  const who = { company: "For and on behalf of the Board of Directors", llp: "For and on behalf of the Designated Partners", partnership: "For the Partners", proprietorship: "For the Proprietary concern" }[d.business_type];
  const role = { company: "Director (DIN: ________)", llp: "Designated Partner (DPIN: ________)", partnership: "Partner", proprietorship: "Proprietor" }[d.business_type];
  return (
    <div className="grid grid-cols-2 gap-8 text-[12px] mt-6 break-inside-avoid" data-testid="fa-signatures">
      {d.purpose !== "other" ? <div>As per our report of even date attached<br />For <b>{a.firm || "____________________"}</b><br />Chartered Accountants<br />FRN: {a.frn || "________"}
        <div className="h-12" />{a.partner || "____________________"}<br />(Partner) M. No. {a.mno || "________"}{a.udin && <><br />UDIN: {a.udin}</>}</div> : <div />}
      <div className="text-right">{who}<br /><b>{d.company}</b><div className="h-12" />{a.sign1 || role}{d.business_type === "company" && <><div className="h-10" />{a.sign2 || role}</>}</div>
      <div>Place: {a.place || "________"}<br />Date: {a.date ? dmy(a.date) : "________"}</div>
    </div>
  );
};

export default function FinalAccounts() {
  const { fy, settings } = useApp();
  const [p, setP] = useState({ from_date: fy?.start_date, to_date: fy?.end_date, business_type: settings?.business_type || "proprietorship", purpose: settings?.business_type === "company" ? "company_audit" : "tax_audit", project_id: "" });
  const [a, setA] = useState({ firm: "", frn: "", partner: "", mno: "", udin: "", place: "", date: "", sign1: "", sign2: "" });
  const [projects, setProjects] = useState([]);
  const [d, setD] = useState(null);
  const ref = useRef();
  useEffect(() => { api.get("/erp/projects").then((r) => setProjects(r.data)).catch(() => {}); }, []);
  useEffect(() => { setP((x) => ({ ...x, purpose: x.business_type === "company" ? x.purpose : x.purpose === "company_audit" ? "tax_audit" : x.purpose })); }, [p.business_type]);
  useEffect(() => {
    if (!p.to_date || (p.purpose === "company_audit" && p.business_type !== "company")) return;
    api.get("/reports/final-accounts", { params: Object.fromEntries(Object.entries(p).filter(([, x]) => x)) }).then((r) => setD(r.data)).catch((e) => toast.error(errMsg(e)));
  }, [p]);
  const set = (k) => (e) => setP({ ...p, [k]: e.target.value });
  const xl = () => {
    const cols = [{ key: "label", label: "Particulars" }, { key: "note", label: "Note" }, { key: "cy", label: "Current year", num: true }, { key: "py", label: "Previous year", num: true }];
    const flat = (rows) => rows.map((r) => ({ label: r.label, note: r.note || "", cy: r.cy ?? "", py: r.py ?? "", _bold: r.type !== "item" }));
    exportExcel("Final Accounts", `${d.company} · ${d.purpose_text}`, [
      { title: "Balance Sheet", columns: cols, rows: flat(d.balance_sheet) }, { title: "Statement of Profit and Loss", columns: cols, rows: flat(d.profit_loss) },
      ...d.notes.map((n) => ({ title: `Note ${n.no}: ${n.title}`, columns: [{ key: "particulars", label: "Particulars" }, { key: "cy", label: "Current year", num: true }, { key: "py", label: "Previous year", num: true }], rows: n.rows, footer: { particulars: "Total", cy: n.cy, py: n.py } })),
    ]);
  };
  const plTitle = d?.kind === "company" ? `Statement of Profit and Loss for the year ended ${dmy(d?.to_date)}` : `Profit and Loss Account for the year ended ${dmy(d?.to_date)}`;
  return (
    <div className="space-y-6" data-testid="final-accounts-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="font-heading text-3xl font-extrabold tracking-tight">Final Accounts</h1><p className="text-slate-500 mt-1">Balance Sheet and Profit &amp; Loss in vertical format with notes to accounts.</p></div>
        <div className="flex gap-2"><Button variant="outline" disabled={!d} onClick={xl} data-testid="fa-excel"><FileSpreadsheet className="h-4 w-4 mr-1" /> Excel</Button>
          <Button variant="outline" disabled={!d} onClick={() => printNode(ref.current, "Final Accounts")} data-testid="fa-print"><Printer className="h-4 w-4 mr-1" /> Print / PDF</Button></div>
      </div>
      <div className="rounded-xl border bg-white p-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6" data-testid="fa-filters">
        <div className="space-y-1"><Label className="text-xs">From</Label><Input type="date" className="h-10" value={p.from_date || ""} onChange={set("from_date")} data-testid="fa-from" /></div>
        <div className="space-y-1"><Label className="text-xs">To (balance sheet date)</Label><Input type="date" className="h-10" value={p.to_date || ""} onChange={set("to_date")} data-testid="fa-to" /></div>
        <div className="space-y-1"><Label className="text-xs">Business type</Label><select className="h-10 w-full rounded-md border px-2 bg-white text-sm" value={p.business_type} onChange={set("business_type")} data-testid="fa-business-type">
          <option value="proprietorship">Proprietorship</option><option value="partnership">Partnership firm</option><option value="llp">LLP</option><option value="company">Company</option></select></div>
        <div className="space-y-1"><Label className="text-xs">Purpose</Label><select className="h-10 w-full rounded-md border px-2 bg-white text-sm" value={p.purpose} onChange={set("purpose")} data-testid="fa-purpose">
          {p.business_type === "company" && <option value="company_audit">Company audit (Companies Act)</option>}<option value="tax_audit">Income tax audit (44AB)</option><option value="other">Other (bank / management)</option></select></div>
        <div className="space-y-1 lg:col-span-2"><Label className="text-xs">Project</Label><select className="h-10 w-full rounded-md border px-2 bg-white text-sm" value={p.project_id} onChange={set("project_id")} data-testid="fa-project">
          <option value="">Combined - whole business</option><option value="none">Not tagged to a project only</option>{projects.map((x) => <option key={x.id} value={x.id}>{x.code} · {x.name}</option>)}</select></div>
        {[["firm", "Auditor firm"], ["frn", "FRN"], ["partner", "Partner name"], ["mno", "Membership no."], ["udin", "UDIN"], ["place", "Place"], ["sign1", "Signatory 1 name"], ["sign2", "Signatory 2 name"]].map(([k, l]) =>
          <div key={k} className="space-y-1"><Label className="text-xs">{l}</Label><Input className="h-10" value={a[k]} onChange={(e) => setA({ ...a, [k]: e.target.value })} data-testid={`fa-${k}`} /></div>)}
        <div className="space-y-1"><Label className="text-xs">Signing date</Label><Input type="date" className="h-10" value={a.date} onChange={(e) => setA({ ...a, date: e.target.value })} data-testid="fa-sign-date" /></div>
      </div>
      {d && <div className={`rounded-lg border px-4 py-2 text-sm ${d.balanced ? "bg-emerald-50 border-emerald-200 text-emerald-800" : "bg-red-50 border-red-200 text-red-800"}`} data-testid="fa-balanced">
        {d.balanced ? "Balance Sheet totals match" : "Balance Sheet totals do not match"} · {d.schedule}</div>}
      {d && <div className="rounded-xl border bg-slate-100 p-4 overflow-x-auto"><div ref={ref} className="bg-white mx-auto max-w-[860px] p-10 text-slate-900 font-serif" data-testid="fa-document">
        <Stmt title={`Balance Sheet as at ${dmy(d.to_date)}`} rows={d.balance_sheet} d={d} testid="fa-balance-sheet" />
        <div className="text-[11px] italic mb-2">The accompanying notes 1 to {d.notes.length + 1} form an integral part of the financial statements.</div>
        <Sign d={d} a={a} />
        <div style={{ pageBreakBefore: "always" }} className="pt-8"><Stmt title={plTitle} rows={d.profit_loss} d={d} testid="fa-profit-loss" /><Sign d={d} a={a} /></div>
        <div style={{ pageBreakBefore: "always" }} className="pt-8" data-testid="fa-notes">
          <div className="text-center font-bold uppercase">{d.company}</div><div className="text-center font-bold mb-3">Notes forming part of the financial statements for the year ended {dmy(d.to_date)}</div>
          <div className="mb-4 break-inside-avoid"><div className="font-bold">Note 1: Significant accounting policies and other notes</div>
            <ol className="list-[lower-alpha] pl-6 text-[12px] space-y-1">{d.policies.map((x, i) => <li key={i}>{x}</li>)}</ol></div>
          {d.notes.map((n) => <div key={n.no} className="mb-4 break-inside-avoid" data-testid={`fa-note-${n.no}`}><div className="font-bold">Note {n.no}: {n.title}</div>
            {n.schedule?.length > 0 && <table className="w-full text-[11.5px] border-collapse mb-2" data-testid="fa-asset-schedule"><thead><tr className="border-y border-slate-700">
              {["Asset", "Method / rate", "Opening WDV", "Additions", "Deletions", "Depreciation", "Closing WDV"].map((h, i) => <th key={h} className={i > 1 ? "text-right" : "text-left"}>{h}</th>)}</tr></thead>
              <tbody>{n.schedule.map((r) => <tr key={r.ledger_id}><td className="pl-2">{r.asset}</td><td>{r.method === "none" ? "-" : `${r.method.toUpperCase()} ${r.rate}%`}</td>
                {["opening", "additions", "deletions", "depreciation", "closing"].map((k) => <td key={k} className="text-right font-mono">{v(r[k])}</td>)}</tr>)}
                <tr className="font-bold border-y border-slate-700"><td className="pl-2" colSpan={2}>Total</td>{["opening", "additions", "deletions", "depreciation", "closing"].map((k) => <td key={k} className="text-right font-mono">{v(n.schedule.reduce((s, r) => s + r[k], 0))}</td>)}</tr></tbody>
              {!n.schedule_posted && <caption className="caption-bottom text-left text-[10.5px] italic pt-1">Depreciation shown is worked out but not yet posted - post it from Year-end: Depreciation &amp; Tax.</caption>}</table>}
            <table className="w-full text-[12px] border-collapse"><thead><tr className="border-b border-slate-700"><th className="text-left">Particulars</th><th className="w-36 text-right">Current year</th><th className="w-36 text-right">Previous year</th></tr></thead>
              <tbody>{n.rows.map((r, i) => <tr key={i}><td className="pl-3">{r.particulars}</td><td className="text-right font-mono">{v(r.cy)}</td><td className="text-right font-mono">{v(r.py)}</td></tr>)}
                <tr className="font-bold border-y border-slate-700"><td className="pl-3">Total</td><td className="text-right font-mono">{v(n.cy)}</td><td className="text-right font-mono">{v(n.py)}</td></tr></tbody></table></div>)}
          <Sign d={d} a={a} />
        </div>
      </div></div>}
    </div>
  );
}
