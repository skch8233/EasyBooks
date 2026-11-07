import { useCallback, useEffect, useState } from "react";
import { Search, FileSpreadsheet, FileText, X } from "lucide-react";
import { api } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { amt, dmy, VT, VTYPES } from "@/lib/format";
import { exportExcel, exportPdf } from "@/lib/export";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DateInput } from "@/components/DateInput";
import { LedgerSelect } from "@/components/LedgerSelect";
import { VoucherDialog } from "@/components/VoucherDialog";
import { WhatsAppButton } from "@/components/WhatsAppButton";

const COLS = [
  { key: "date", label: "Date" }, { key: "voucher_no", label: "Voucher No" }, { key: "type", label: "Type" },
  { key: "party_name", label: "Party / Particulars" }, { key: "narration", label: "Narration" }, { key: "amount", label: "Amount", num: true }, { key: "status", label: "Status" },
];

export default function Vouchers() {
  const { fy, settings } = useApp();
  const [flt, setFlt] = useState({ from: fy?.start_date, to: fy?.end_date, type: "all", ledger: "", q: "" });
  const [rows, setRows] = useState([]);
  const [ledgers, setLedgers] = useState([]);
  const [open, setOpen] = useState(null);

  useEffect(() => { api.get("/ledgers").then((r) => setLedgers(r.data)); }, []);
  useEffect(() => { if (fy) setFlt((f) => ({ ...f, from: fy.start_date, to: fy.end_date })); }, [fy]);
  const load = useCallback(() => {
    const p = { from_date: flt.from, to_date: flt.to };
    if (flt.type !== "all") p.voucher_type = flt.type;
    if (flt.ledger) p.ledger_id = flt.ledger;
    if (flt.q) p.q = flt.q;
    api.get("/vouchers", { params: p }).then((r) => setRows(r.data));
  }, [flt]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  const active = rows.filter((r) => r.status === "active");
  const total = active.reduce((s, r) => s + r.amount, 0);
  const exportRows = rows.map((r) => ({ ...r, date: dmy(r.date), type: VT[r.voucher_type]?.label }));
  const sub = `${dmy(flt.from)} to ${dmy(flt.to)}`;
  const sec = [{ columns: COLS, rows: exportRows, footer: { party_name: "Total (active)", amount: total } }];

  return (
    <div className="space-y-6" data-testid="vouchers-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="font-heading text-3xl font-extrabold tracking-tight">Vouchers</h1><p className="text-slate-500 mt-1">Search by date, party, type or voucher number.</p></div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => exportExcel("Voucher List", sub, sec)} data-testid="export-excel-button"><FileSpreadsheet className="h-4 w-4 mr-1" /> Excel</Button>
          <Button variant="outline" onClick={() => exportPdf("Voucher List", sub, sec, settings?.company_name)} data-testid="export-pdf-button"><FileText className="h-4 w-4 mr-1" /> PDF</Button>
        </div>
      </div>
      <div className="grid gap-3 rounded-xl border bg-white p-4 sm:grid-cols-2 lg:grid-cols-[160px_160px_180px_1fr_1fr]">
        <DateInput value={flt.from} onChange={(from) => setFlt({ ...flt, from })} testid="filter-date-from" />
        <DateInput value={flt.to} onChange={(to) => setFlt({ ...flt, to })} testid="filter-date-to" />
        <Select value={flt.type} onValueChange={(type) => setFlt({ ...flt, type })}>
          <SelectTrigger className="h-11" data-testid="filter-voucher-type"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="all">All types</SelectItem>{VTYPES.map((v) => <SelectItem key={v.key} value={v.key}>{v.label}</SelectItem>)}</SelectContent>
        </Select>
        <div className="flex gap-1">
          <LedgerSelect ledgers={ledgers} value={flt.ledger} onChange={(ledger) => setFlt({ ...flt, ledger })} placeholder="Any party / ledger" testid="filter-party" />
          {flt.ledger && <Button variant="ghost" size="icon" className="h-11 w-11" onClick={() => setFlt({ ...flt, ledger: "" })} data-testid="filter-party-clear"><X className="h-4 w-4" /></Button>}
        </div>
        <div className="relative"><Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" /><Input className="h-11 pl-9" placeholder="Voucher no, narration, party..." value={flt.q} onChange={(e) => setFlt({ ...flt, q: e.target.value })} data-testid="filter-search-input" /></div>
      </div>
      <div className="rounded-xl border bg-white overflow-x-auto">
        <table className="w-full eb-table min-w-[800px]" data-testid="vouchers-table">
          <thead><tr><th>Date</th><th>Voucher No</th><th>Type</th><th>Party / Particulars</th><th>Narration</th><th className="!text-right">Amount (₹)</th><th>Status</th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={7} className="text-center text-slate-500 py-10" data-testid="vouchers-empty">No vouchers found for these filters.</td></tr>}
            {rows.map((r) => (
              <tr key={r.id} onClick={() => setOpen(r.id)} className={`cursor-pointer ${r.status === "cancelled" ? "opacity-60" : ""}`} data-testid={`voucher-row-${r.voucher_no}`}>
                <td className="font-mono text-xs">{dmy(r.date)}</td>
                <td className="font-mono text-xs">{r.voucher_no}</td>
                <td><span className={`rounded border px-2 py-0.5 text-xs font-semibold ${VT[r.voucher_type]?.color}`}>{VT[r.voucher_type]?.label}</span></td>
                <td className="font-medium">{r.party_name}</td>
                <td className="text-slate-500 truncate max-w-[240px]">{r.narration}</td>
                <td className={`text-right num ${r.status === "cancelled" ? "line-through" : ""}`}>{amt(r.amount)}</td>
                <td className="whitespace-nowrap">{r.status === "cancelled" ? <span className="text-xs font-semibold text-red-600">Cancelled</span> : <span className="text-xs font-semibold text-emerald-700">Active</span>}
                  <WhatsAppButton voucher={r} compact testid={`row-whatsapp-${r.voucher_no}`} /></td>
              </tr>
            ))}
          </tbody>
          <tfoot><tr><td colSpan={5}>{active.length} active vouchers</td><td className="text-right num" data-testid="vouchers-total">{amt(total)}</td><td /></tr></tfoot>
        </table>
      </div>
      <VoucherDialog id={open} onClose={() => setOpen(null)} onChanged={load} />
    </div>
  );
}
