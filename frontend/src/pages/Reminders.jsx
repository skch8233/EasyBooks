import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { BellRing, ChevronDown, ChevronRight, MessageCircle, AlertTriangle } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { amt, dmy, dmyTime } from "@/lib/format";
import { sendReminder } from "@/lib/whatsapp";
import { Button } from "@/components/ui/button";

const Row = ({ c, canWrite, onSent }) => {
  const { settings } = useApp();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    try { await sendReminder(c.ledger_id, settings); toast.success(`Reminder opened in WhatsApp for ${c.name}`); onSent(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const slug = c.name.toLowerCase().replace(/\s+/g, "-");
  return (
    <>
      <tr data-testid={`reminder-row-${slug}`}>
        <td><button className="flex items-center gap-2 font-medium" onClick={() => setOpen(!open)} data-testid={`reminder-expand-${slug}`}>{open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}{c.name}</button>
          <div className="text-xs text-slate-500 ml-6">{c.phone || <span className="text-amber-700">No phone, choose contact in WhatsApp</span>} · {c.credit_days} days credit</div></td>
        <td className="text-right num">{amt(c.outstanding)}</td>
        <td className="text-right num font-semibold text-red-600" data-testid="reminder-overdue-amount">{amt(c.overdue_amount)}</td>
        <td className="text-right num">{c.max_days_overdue ? `${c.max_days_overdue} days` : "-"}</td>
        <td className="text-xs text-slate-500">{c.last_reminded_at ? <>{dmyTime(c.last_reminded_at)}<div>{c.reminder_count} sent</div></> : "Never"}</td>
        <td className="text-right">{canWrite && c.overdue_amount > 0 && (
          <Button size="sm" onClick={send} disabled={busy} className="bg-[#25D366] hover:bg-[#1ebe5b] text-white" data-testid={`send-reminder-${slug}`}><MessageCircle className="h-4 w-4 mr-1" /> Remind</Button>)}</td>
      </tr>
      {open && c.bills.map((b, i) => (
        <tr key={i} className="bg-slate-50/80 text-sm">
        <td className="pl-10 font-mono text-xs">{b.voucher_no}{b.date && <span className="text-slate-500"> · {dmy(b.date)}</span>}<div className="font-sans text-xs text-slate-500">{b.due_date ? `Due ${dmy(b.due_date)}` : "Opening balance"}</div></td>
          <td className="text-right num">{amt(b.pending)}</td>
          <td className="text-right num">{b.overdue ? amt(b.pending) : "-"}</td>
          <td className="text-right">{b.overdue ? <span className="text-xs font-semibold text-red-600">{b.days_overdue ? `${b.days_overdue} days late` : "Overdue"}</span> : <span className="text-xs text-emerald-700">Not due</span>}</td>
          <td colSpan={2} />
        </tr>
      ))}
    </>
  );
};

export default function Reminders() {
  const { canWrite, settings } = useApp();
  const [d, setD] = useState(null);
  const [showAll, setShowAll] = useState(false);
  const load = useCallback(() => api.get("/reminders/overdue").then((r) => setD(r.data)), []);
  useEffect(() => { load(); }, [load]);
  const rows = d ? d.customers.filter((c) => showAll || c.overdue_amount > 0) : [];

  return (
    <div className="space-y-6" data-testid="reminders-page">
      <div><h1 className="font-heading text-3xl font-extrabold tracking-tight flex items-center gap-3"><BellRing className="h-7 w-7 text-primary" /> Payment Reminders</h1>
        <p className="text-slate-500 mt-1">Overdue bills by customer. Bills are due after each customer's credit days. Payments are applied to the oldest bills first.</p></div>
      {settings && !settings.upi_id && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900" data-testid="reminder-upi-warning">
          <AlertTriangle className="h-4 w-4" /> Add your UPI ID so reminders include a one-tap UPI payment link. <Link to="/settings" className="font-semibold underline">Open Settings → Invoice Branding</Link></div>)}
      {d && (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border bg-red-50 border-red-200 p-5"><div className="text-xs font-semibold uppercase text-red-700">Total overdue</div><div className="num text-2xl font-semibold text-red-700" data-testid="reminders-total-overdue">₹{amt(d.total_overdue)}</div></div>
          <div className="rounded-xl border bg-white p-5"><div className="text-xs font-semibold uppercase text-slate-500">Customers overdue</div><div className="num text-2xl font-semibold" data-testid="reminders-overdue-count">{d.overdue_customers}</div></div>
          <div className="rounded-xl border bg-white p-5"><div className="text-xs font-semibold uppercase text-slate-500">Total receivable</div><div className="num text-2xl font-semibold">₹{amt(d.total_outstanding)}</div></div>
        </div>
      )}
      <label className="flex items-center gap-2 text-sm w-fit"><input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} data-testid="reminders-show-all" /> Also show customers with dues not yet overdue</label>
      <div className="rounded-xl border bg-white overflow-x-auto">
        <table className="w-full eb-table min-w-[820px]" data-testid="reminders-table">
          <thead><tr><th>Customer</th><th className="!text-right">Outstanding (₹)</th><th className="!text-right">Overdue (₹)</th><th className="!text-right">Oldest overdue</th><th>Last reminder</th><th /></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={6} className="text-center py-10 text-slate-500" data-testid="reminders-empty">No overdue bills. All customers are up to date.</td></tr>}
            {rows.map((c) => <Row key={c.ledger_id} c={c} canWrite={canWrite} onSent={load} />)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
