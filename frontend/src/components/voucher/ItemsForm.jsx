import { Plus, Trash2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { LedgerSelect } from "@/components/LedgerSelect";
import { useApp } from "@/context/AppContext";
import { amt } from "@/lib/format";
import { computeItems, emptyItem, PARTY_GROUPS } from "./voucherUtils";
import { ItemPicker } from "./ItemPicker";

const Row = ({ it, i, line, rates, set, remove, canRemove, stock, pick, isSale }) => {
  const sel = stock.find((s) => s.id === it.item_id);
  const short = isSale && sel && Number(it.qty) > sel.on_hand;
  return (
  <div className="space-y-1">
  <div className="grid grid-cols-6 md:grid-cols-[1fr_110px_80px_120px_100px_130px_44px] gap-2 items-center">
    <div className="col-span-6 md:col-span-1">
      <ItemPicker stock={stock} item={it} testid={`item-${i}-description`} onPick={(s) => pick(i, s)}
        onText={(t) => set(i, { description: t, item_id: null })} />
    </div>
    <Input className="col-span-2 md:col-span-1 h-11 font-mono" placeholder="HSN/SAC" value={it.hsn} onChange={(e) => set(i, "hsn", e.target.value)} data-testid={`item-${i}-hsn`} />
    <Input className="col-span-2 md:col-span-1 h-11 text-right num" type="number" min="0" step="any" placeholder="Qty" value={it.qty} onChange={(e) => set(i, "qty", e.target.value)} data-testid={`item-${i}-qty`} />
    <Input className="col-span-2 md:col-span-1 h-11 text-right num" type="number" min="0" step="0.01" placeholder="Rate" value={it.rate} onChange={(e) => set(i, "rate", e.target.value)} data-testid={`item-${i}-rate`} />
    <Select value={String(it.gst_rate)} onValueChange={(v) => set(i, "gst_rate", Number(v))}>
      <SelectTrigger className="col-span-2 md:col-span-1 h-11" data-testid={`item-${i}-gst-rate`}><SelectValue /></SelectTrigger>
      <SelectContent>{rates.map((r) => <SelectItem key={r} value={String(r)}>{r}%</SelectItem>)}</SelectContent>
    </Select>
    <div className="col-span-3 md:col-span-1 text-right num font-medium" data-testid={`item-${i}-amount`}>{amt(line?.amount)}</div>
    <button type="button" disabled={!canRemove} onClick={() => remove(i)} className="col-span-1 h-11 w-11 flex items-center justify-center rounded-md text-slate-400 hover:text-red-600 hover:bg-red-50 disabled:opacity-30" data-testid={`item-${i}-remove`}><Trash2 className="h-4 w-4" /></button>
  </div>
  {short && <div className="text-xs text-amber-700 px-1" data-testid={`item-${i}-stock-warning`}>Only {sel.on_hand} {sel.unit} in stock. Stock will go negative.</div>}
  </div>
  );
};

export const ItemsForm = ({ type, ledgers, value, onChange, stock = [] }) => {
  const { settings } = useApp();
  const rates = settings?.gst_rates || [0, 5, 12, 18, 28];
  const calc = computeItems(value.items, value.gstType);
  const isSale = ["sales", "credit_note"].includes(type);
  const set = (i, k, v) => onChange({ ...value, items: value.items.map((it, j) => (j === i ? { ...it, ...(typeof k === "object" ? k : { [k]: v }) } : it)) });
  const pick = (i, s) => set(i, { item_id: s.id, description: s.name, hsn: s.hsn || "", rate: (isSale ? s.sale_rate : s.purchase_rate) || "",
    gst_rate: rates.includes(s.gst_rate) ? s.gst_rate : value.items[i].gst_rate });

  const pickParty = (party) => {
    const p = ledgers.find((l) => l.id === party);
    const cs = settings?.state, ps = p?.state;
    onChange({ ...value, party, gstType: cs && ps ? (cs === ps ? "intra" : "inter") : value.gstType });
  };

  return (
    <div className="space-y-6" data-testid="items-voucher-form">
      <div className="grid gap-5 md:grid-cols-3">
        <div className="space-y-2"><Label>Party (Customer / Supplier / Cash)</Label>
          <LedgerSelect ledgers={ledgers} groups={PARTY_GROUPS} value={value.party} onChange={pickParty} testid="party-ledger-select" placeholder="Select party" /></div>
        <div className="space-y-2"><Label>{isSale ? "Sales Ledger" : "Purchase Ledger"}</Label>
          <LedgerSelect ledgers={ledgers} groups={[isSale ? "sales" : "purchase"]} value={value.account} onChange={(account) => onChange({ ...value, account })} testid="account-ledger-select" /></div>
        <div className="space-y-2"><Label>GST Type</Label>
          <Select value={value.gstType} onValueChange={(gstType) => onChange({ ...value, gstType })}>
            <SelectTrigger className="h-11" data-testid="gst-type-select"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="intra">Within state (CGST + SGST)</SelectItem>
              <SelectItem value="inter">Inter-state (IGST)</SelectItem>
              <SelectItem value="none">No GST</SelectItem>
            </SelectContent>
          </Select></div>
      </div>
      <div className="space-y-2">
        <div className="hidden md:grid grid-cols-[1fr_110px_80px_120px_100px_130px_44px] gap-2 text-xs font-semibold uppercase text-slate-500 px-1">
          <span>Item</span><span>HSN/SAC</span><span className="text-right">Qty</span><span className="text-right">Rate (₹)</span><span>GST</span><span className="text-right">Amount (₹)</span><span />
        </div>
        {value.items.map((it, i) => (
          <Row key={i} it={it} i={i} line={calc.lines[i]} rates={rates} set={set} canRemove={value.items.length > 1} stock={stock} pick={pick} isSale={type === "sales"}
            remove={(j) => onChange({ ...value, items: value.items.filter((_, k) => k !== j) })} />
        ))}
        <Button type="button" variant="outline" onClick={() => onChange({ ...value, items: [...value.items, emptyItem(rates.includes(18) ? 18 : rates[0])] })} data-testid="add-item-button"><Plus className="h-4 w-4 mr-1" /> Add item</Button>
      </div>
      <div className="ml-auto w-full max-w-sm rounded-lg border bg-slate-50 p-4 space-y-2 text-sm" data-testid="gst-summary">
        <div className="flex justify-between"><span>Taxable value</span><span className="num" data-testid="summary-taxable">{amt(calc.taxable)}</span></div>
        {value.gstType === "intra" && <>
          <div className="flex justify-between text-blue-700"><span>CGST</span><span className="num" data-testid="summary-cgst">{amt(calc.cgst)}</span></div>
          <div className="flex justify-between text-violet-700"><span>SGST</span><span className="num" data-testid="summary-sgst">{amt(calc.sgst)}</span></div>
        </>}
        {value.gstType === "inter" && <div className="flex justify-between text-pink-700"><span>IGST</span><span className="num" data-testid="summary-igst">{amt(calc.igst)}</span></div>}
        <div className="flex justify-between border-t pt-2 text-base font-semibold"><span>Invoice Total</span><span className="num" data-testid="summary-total">₹{amt(calc.total)}</span></div>
      </div>
    </div>
  );
};
