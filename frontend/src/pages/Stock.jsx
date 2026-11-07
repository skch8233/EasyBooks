import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Search, Pencil, Trash2, AlertTriangle, History } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { amt, dmy, VT } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { StockDialog } from "@/components/StockDialog";

const Movements = ({ id, onClose }) => {
  const [d, setD] = useState(null);
  useEffect(() => { setD(null); if (id) api.get(`/stock-items/${id}/movements`).then((r) => setD(r.data)); }, [id]);
  return (
    <Dialog open={!!id} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="stock-movements-dialog">
        <DialogHeader><DialogTitle className="font-heading text-xl">{d?.item.name || "Stock movements"}</DialogTitle></DialogHeader>
        {d && (
          <table className="w-full eb-table">
            <thead><tr><th>Date</th><th>Voucher</th><th>Party</th><th className="!text-right">In</th><th className="!text-right">Out</th><th className="!text-right">Balance</th></tr></thead>
            <tbody>
              <tr className="font-semibold"><td colSpan={5}>Opening stock</td><td className="text-right num">{d.opening} {d.item.unit}</td></tr>
              {d.rows.map((r, i) => (
                <tr key={i}><td className="font-mono text-xs">{dmy(r.date)}</td><td><div className="font-mono text-xs">{r.voucher_no}</div><div className="text-[11px] text-slate-500">{VT[r.voucher_type]?.label}</div></td>
                  <td>{r.party}</td><td className="text-right num text-emerald-700">{r.in_qty}</td><td className="text-right num text-red-600">{r.out_qty}</td><td className="text-right num">{r.balance}</td></tr>
              ))}
            </tbody>
            <tfoot><tr><td colSpan={5}>Closing stock</td><td className="text-right num" data-testid="stock-movements-closing">{d.closing} {d.item.unit}</td></tr></tfoot>
          </table>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default function Stock() {
  const { canWrite } = useApp();
  const [data, setData] = useState({ items: [], total_value: 0, low_count: 0 });
  const [q, setQ] = useState("");
  const [lowOnly, setLowOnly] = useState(false);
  const [dlg, setDlg] = useState({ open: false, item: null });
  const [mv, setMv] = useState(null);
  const load = useCallback(() => api.get("/stock-items").then((r) => setData(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const remove = async (s) => {
    if (!window.confirm(`Remove "${s.name}"?`)) return;
    try { await api.delete(`/stock-items/${s.id}`); toast.success("Item removed"); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  const rows = data.items.filter((s) => s.name.toLowerCase().includes(q.toLowerCase()) && (!lowOnly || s.low || s.negative));

  return (
    <div className="space-y-6" data-testid="stock-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="font-heading text-3xl font-extrabold tracking-tight">Stock</h1><p className="text-slate-500 mt-1">Quantity on hand updates automatically with every sale, purchase and return.</p></div>
        {canWrite && <Button className="h-11 px-5" onClick={() => setDlg({ open: true, item: null })} data-testid="create-stock-button"><Plus className="h-4 w-4 mr-1" /> New Item</Button>}
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border bg-white p-5"><div className="text-xs font-semibold uppercase text-slate-500">Items</div><div className="num text-2xl font-semibold" data-testid="stock-count">{data.items.length}</div></div>
        <div className="rounded-xl border bg-white p-5"><div className="text-xs font-semibold uppercase text-slate-500">Stock value (avg cost)</div><div className="num text-2xl font-semibold" data-testid="stock-total-value">₹{amt(data.total_value)}</div></div>
        <button onClick={() => setLowOnly(!lowOnly)} className={`rounded-xl border p-5 text-left ${lowOnly ? "ring-2 ring-amber-400" : ""} ${data.low_count ? "bg-amber-50 border-amber-200" : "bg-white"}`} data-testid="stock-low-filter">
          <div className="text-xs font-semibold uppercase text-amber-700 flex items-center gap-1"><AlertTriangle className="h-3 w-3" /> Low / negative stock</div><div className="num text-2xl font-semibold" data-testid="stock-low-count">{data.low_count}</div></button>
      </div>
      <div className="relative w-full sm:w-80"><Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" /><Input className="h-11 pl-9" placeholder="Search items" value={q} onChange={(e) => setQ(e.target.value)} data-testid="stock-search-input" /></div>
      <div className="rounded-xl border bg-white overflow-x-auto">
        <table className="w-full eb-table min-w-[860px]" data-testid="stock-table">
          <thead><tr><th>Item</th><th>HSN</th><th className="!text-right">GST</th><th className="!text-right">Sale rate</th><th className="!text-right">Purchased</th><th className="!text-right">Sold</th><th className="!text-right">Value (₹)</th><th className="!text-right">Actions</th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={9} className="text-center py-10 text-slate-500" data-testid="stock-empty">No stock items yet. Add items to track quantity on hand.</td></tr>}
            {rows.map((s) => (
              <tr key={s.id} data-testid={`stock-row-${s.name.toLowerCase().replace(/\s+/g, "-")}`}>
                <td className="font-medium">{s.name}</td><td className="font-mono text-xs">{s.hsn || "-"}</td><td className="text-right num">{s.gst_rate}%</td>
                <td className="text-right num">{amt(s.sale_rate)}</td><td className="text-right num text-slate-500">{s.purchased_qty}</td><td className="text-right num text-slate-500">{s.sold_qty}</td>
                <td className={`text-right num font-semibold ${s.negative ? "text-red-600" : s.low ? "text-amber-600" : ""}`} data-testid="stock-on-hand">{s.on_hand} {s.unit}
                  {(s.low || s.negative) && <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">{s.negative ? "NEGATIVE" : "LOW"}</span>}</td>
                <td className="text-right num">{amt(s.value)}</td>
                <td className="text-right whitespace-nowrap">
                  <button className="p-2 rounded hover:bg-slate-100" onClick={() => setMv(s.id)} title="Movements" data-testid="stock-movements-button"><History className="h-4 w-4" /></button>
                  {canWrite && <button className="p-2 rounded hover:bg-slate-100" onClick={() => setDlg({ open: true, item: s })} data-testid="stock-edit-button"><Pencil className="h-4 w-4" /></button>}
                  {canWrite && <button className="p-2 rounded hover:bg-red-50 text-red-600" onClick={() => remove(s)} data-testid="stock-delete-button"><Trash2 className="h-4 w-4" /></button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <StockDialog open={dlg.open} item={dlg.item} onClose={() => setDlg({ open: false, item: null })} onSaved={() => { setDlg({ open: false, item: null }); load(); }} />
      <Movements id={mv} onClose={() => setMv(null)} />
    </div>
  );
}
