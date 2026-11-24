import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Minus, Plus, Printer, ScanBarcode, Trash2 } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { amt, inr } from "@/lib/format";
import { printThermal } from "@/lib/receipts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, PageHead, sel, todayIso, useList, useMoneyLedgers, Pick, monthOptions } from "@/components/industry/common";

// MRP is tax-inclusive: rate stored is the taxable value per unit
const r2 = (n) => Math.round(n * 100) / 100;
// same rounding as the server: taxable per line to 2dp, GST on that
const lineTotal = (c) => { const t = r2(c.qty * c.rate); return t + r2((t * c.gst_rate) / 100); };
// For MRP items pick per-unit rates so the server's rounded total equals qty x MRP exactly
const exactRate = (qty, mrp, g) => {
  const want = r2(qty * mrp), base = r2(want / (1 + g / 100));
  for (const t of [base, r2(base - 0.01), r2(base + 0.01), r2(base - 0.02), r2(base + 0.02)]) if (r2(t + r2((t * g) / 100)) === want) return Math.round((t / qty) * 1e6) / 1e6;
  return null;
};
// returns posting lines for one cart row (split into two lines if one rate cannot hit the MRP total)
const postLines = (c) => {
  if (!c.mrp) return [c];
  const one = exactRate(c.qty, c.mrp, c.gst_rate);
  if (one !== null) return [{ ...c, rate: one }];
  const a = c.qty > 1 && exactRate(c.qty - 1, c.mrp, c.gst_rate), b = exactRate(1, c.mrp, c.gst_rate);
  if (a && b) return [{ ...c, qty: c.qty - 1, rate: a }, { ...c, qty: 1, rate: b }];
  return [c];
};
const rowTotal = (c) => postLines(c).reduce((s, l) => s + lineTotal(l), 0);
const baseRate = (it) => (it.mrp ? Math.round((it.mrp / (1 + it.gst_rate / 100)) * 10000) / 10000 : it.sale_rate || 0);

export default function Pos() {
  const { settings } = useApp();
  const [stock, reload] = useList("/stock-items");
  const items = stock?.items;
  const [ledgers] = useList("/ledgers");
  const money = useMoneyLedgers();
  const [q, setQ] = useState("");
  const [cart, setCart] = useState([]);
  const [pay, setPay] = useState("");
  const [busy, setBusy] = useState(false);
  const ref = useRef();
  const hits = useMemo(() => (q.trim() ? (items || []).filter((i) => i.barcode === q.trim() || i.name.toLowerCase().includes(q.trim().toLowerCase())).slice(0, 8) : []), [q, items]);
  const add = (it) => {
    setCart((c) => { const x = c.find((y) => y.item_id === it.id); return x ? c.map((y) => (y === x ? { ...y, qty: y.qty + 1 } : y))
      : [...c, { item_id: it.id, name: it.name, qty: 1, rate: baseRate(it), mrp: it.mrp, gst_rate: it.gst_rate, on_hand: it.on_hand, low: it.low }]; });
    setQ(""); ref.current?.focus();
  };
  const onKey = (e) => { if (e.key === "Enter" && hits.length) { e.preventDefault(); add(hits.find((h) => h.barcode === q.trim()) || hits[0]); } };
  const setQty = (id, d) => setCart((c) => c.map((y) => (y.item_id === id ? { ...y, qty: Math.max(1, y.qty + d) } : y)));
  const total = r2(cart.reduce((s, c) => s + rowTotal(c), 0));
  const payId = pay || money[0]?.id;
  const sales = (ledgers || []).find((l) => l.group === "sales");
  const save = async () => {
    if (!cart.length) return toast.error("Scan or add an item first");
    setBusy(true);
    try {
      const { data } = await api.post("/vouchers", { voucher_type: "sales", date: todayIso(), party_ledger_id: payId, account_ledger_id: sales?.id, gst_type: "intra",
        narration: "POS counter sale", items: cart.flatMap(postLines).map((c) => ({ item_id: c.item_id, description: c.name, qty: c.qty, rate: c.rate, gst_rate: c.gst_rate })) });
      const taxable = cart.flatMap(postLines).reduce((s, c) => s + r2(c.qty * c.rate), 0), gst = total - taxable;
      toast.success(`Bill ${data.voucher_no} saved`);
      printThermal(settings, { ...data, totals: { taxable, cgst: gst / 2, sgst: gst / 2, total } }, cart, money.find((m) => m.id === payId)?.name || "Cash");
      setCart([]); reload();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const lowList = (items || []).filter((i) => i.low);
  return (
    <div className="space-y-6" data-testid="pos-page">
      <PageHead title="POS Billing" sub="Scan a barcode or type an item name, then press Enter." />
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card className="space-y-4">
          <div className="relative"><ScanBarcode className="absolute left-3 top-3 h-5 w-5 text-slate-400" />
            <Input ref={ref} autoFocus value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey} placeholder="Barcode / item name" className="h-11 pl-10" data-testid="pos-search-input" />
            {hits.length > 0 && <div className="absolute z-10 mt-1 w-full rounded-lg border bg-white shadow-lg" data-testid="pos-search-results">
              {hits.map((h) => <button key={h.id} onClick={() => add(h)} className="flex w-full justify-between px-4 py-2 text-sm hover:bg-slate-50" data-testid={`pos-hit-${h.id}`}>
                <span>{h.name} <span className="text-xs text-slate-400">{h.barcode}</span></span><span className="num">MRP {amt(h.mrp || h.sale_rate)} · {h.on_hand} left</span></button>)}</div>}
          </div>
          <table className="w-full text-sm" data-testid="pos-cart"><tbody>
            {cart.map((c) => <tr key={c.item_id} className="border-t" data-testid={`pos-line-${c.item_id}`}>
              <td className="py-2">{c.name}<div className="text-xs text-slate-500">{c.mrp ? `MRP ${inr(c.mrp)} incl. ${c.gst_rate}% GST` : `${inr(c.rate)} + ${c.gst_rate}% GST`}{c.qty > c.on_hand && <span className="ml-2 text-red-600">only {c.on_hand} in stock</span>}</div></td>
              <td className="py-2"><div className="flex items-center gap-1"><Button size="icon" variant="outline" className="h-7 w-7" onClick={() => setQty(c.item_id, -1)} data-testid={`pos-minus-${c.item_id}`}><Minus className="h-3 w-3" /></Button>
                <span className="w-8 text-center num" data-testid={`pos-qty-${c.item_id}`}>{c.qty}</span><Button size="icon" variant="outline" className="h-7 w-7" onClick={() => setQty(c.item_id, 1)} data-testid={`pos-plus-${c.item_id}`}><Plus className="h-3 w-3" /></Button></div></td>
              <td className="py-2 text-right num">{amt(rowTotal(c))}</td>
              <td className="py-2 text-right"><Button size="icon" variant="ghost" onClick={() => setCart(cart.filter((y) => y !== c))} data-testid={`pos-remove-${c.item_id}`}><Trash2 className="h-4 w-4 text-red-500" /></Button></td></tr>)}
            {!cart.length && <tr><td className="py-8 text-center text-slate-400">Cart is empty</td></tr>}
          </tbody></table>
        </Card>
        <div className="space-y-4">
          <div className="rounded-xl p-5 space-y-4 bg-[#0F172A] text-white">
            <div className="text-sm text-slate-300">Bill total (incl. GST)</div><div className="num text-4xl font-bold text-emerald-400" data-testid="pos-total">{inr(total)}</div>
            <Pick value={payId || ""} onChange={(v) => setPay(v)} data-testid="pos-pay-select">{money.map((m) => <option key={m.id} value={m.id}>Paid by: {m.name}</option>)}</Pick>
            <Button onClick={save} disabled={busy || !sales || !payId} className="w-full h-12 bg-emerald-500 hover:bg-emerald-600" data-testid="pos-save-print-button"><Printer className="h-4 w-4 mr-2" />Save & print receipt</Button>
          </div>
          <Card data-testid="pos-low-stock"><div className="font-semibold mb-2">Low-stock alerts</div>
            {lowList.length ? lowList.map((i) => <div key={i.id} className="flex justify-between text-sm py-1"><span>{i.name}</span><span className="text-amber-700 num">{i.on_hand} left</span></div>) : <div className="text-sm text-slate-500">All items above reorder level.</div>}</Card>
        </div>
      </div>
    </div>
  );
}
