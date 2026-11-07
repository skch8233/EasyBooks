import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Loader2, Printer, Save, CheckCircle2 } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { VTYPES, VT, ITEM_TYPES, todayIso } from "@/lib/format";
import { printVoucher } from "@/lib/print";
import { WhatsAppButton } from "@/components/WhatsAppButton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { DateInput } from "@/components/DateInput";
import { SimpleForm } from "@/components/voucher/SimpleForm";
import { JournalGrid } from "@/components/voucher/JournalGrid";
import { ItemsForm } from "@/components/voucher/ItemsForm";
import { SIMPLE, emptyItem, emptyLine, fromVoucher } from "@/components/voucher/voucherUtils";

const blank = (type, date, ledgers) => ({
  date, narration: "", reference_no: "", advanced: false,
  simple: { a: ledgers.find((l) => l.system_key === "cash")?.id || "", b: "", amount: "" },
  lines: [emptyLine(), emptyLine()],
  party: "", account: ledgers.find((l) => l.system_key === (["sales", "credit_note"].includes(type) ? "sales" : "purchase"))?.id || "",
  gstType: "intra", items: [emptyItem()],
});

function buildPayload(type, f) {
  const base = { voucher_type: type, date: f.date, narration: f.narration, reference_no: f.reference_no };
  if (ITEM_TYPES.includes(type)) {
    return { ...base, party_ledger_id: f.party, account_ledger_id: f.account, gst_type: f.gstType,
      items: f.items.map((i) => ({ ...i, qty: Number(i.qty) || 0, rate: Number(i.rate) || 0, gst_rate: Number(i.gst_rate) || 0 })) };
  }
  if (SIMPLE[type] && !f.advanced) {
    const a = Number(f.simple.amount) || 0, side = SIMPLE[type].aSide, other = side === "debit" ? "credit" : "debit";
    return { ...base, entries: [{ ledger_id: f.simple.a, [side]: a }, { ledger_id: f.simple.b, [other]: a }] };
  }
  return { ...base, entries: f.lines.filter((l) => l.ledger_id).map((l) => ({ ledger_id: l.ledger_id, debit: Number(l.debit) || 0, credit: Number(l.credit) || 0 })) };
}

export default function VoucherEntry() {
  const { type: pType, id } = useParams();
  const nav = useNavigate();
  const { settings } = useApp();
  const [ledgers, setLedgers] = useState(null);
  const [type, setType] = useState(pType || "sales");
  const [f, setF] = useState(null);
  const [vno, setVno] = useState("");
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState(null);
  const [stock, setStock] = useState([]);
  const loadStock = () => api.get("/stock-items").then((r) => setStock(r.data.items)).catch(() => {});
  useEffect(() => { loadStock(); }, []);

  useEffect(() => { api.get("/ledgers").then((r) => setLedgers(r.data)); }, []);
  useEffect(() => setLast(null), [pType]);
  useEffect(() => {
    if (!ledgers) return;
    if (id) {
      api.get(`/vouchers/${id}`).then((r) => { setType(r.data.voucher_type); setVno(r.data.voucher_no); setF({ ...blank(r.data.voucher_type, r.data.date, ledgers), ...fromVoucher(r.data) }); });
    } else {
      setType(pType || "sales");
      setF((old) => blank(pType || "sales", old?.date || todayIso(), ledgers));
    }
  }, [id, pType, ledgers]);
  useEffect(() => {
    if (!id && f?.date) api.get("/vouchers/next-number", { params: { voucher_type: type, date: f.date } }).then((r) => setVno(r.data.voucher_no)).catch(() => setVno("—"));
  }, [type, f?.date, id, last]);

  const save = useCallback(async () => {
    if (!f || busy) return;
    setBusy(true);
    try {
      const payload = buildPayload(type, f);
      const { data } = id ? await api.put(`/vouchers/${id}`, payload) : await api.post("/vouchers", payload);
      toast.success(`${VT[type].label} ${data.voucher_no} saved`);
      const fresh = await api.get("/ledgers");
      setLedgers(fresh.data);
      loadStock();
      if (id) nav("/vouchers");
      else { setLast(data); setF(blank(type, f.date, fresh.data)); }
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  }, [f, busy, type, id, nav]);

  useEffect(() => {
    const h = (e) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); save(); } };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [save]);

  if (!ledgers || !f) return <div className="text-slate-500">Loading...</div>;
  const isItem = ITEM_TYPES.includes(type);

  return (
    <div className="space-y-6" data-testid="voucher-entry-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight">{id ? "Edit" : "New"} {VT[type].label} Voucher</h1>
          <p className="text-slate-500 mt-1">Ctrl+S to save. Debit and credit must match.</p>
        </div>
      </div>
      {!id && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2" data-testid="voucher-type-select">
          {VTYPES.map((v) => (
            <button key={v.key} onClick={() => nav(`/voucher/${v.key}`)} data-testid={`voucher-type-${v.key}`}
              className={`flex flex-col items-start gap-1 rounded-lg border px-3 py-3 text-sm font-semibold transition-[background-color,box-shadow] ${type === v.key ? `${v.color} ring-2 ring-offset-1 ring-current` : "bg-white text-slate-700 hover:bg-slate-50"}`}>
              <v.icon className="h-4 w-4" /> {v.label}
              {v.hotkey && <span className="text-[10px] font-mono font-normal opacity-60">Alt+{v.hotkey.toUpperCase()}</span>}
            </button>
          ))}
        </div>
      )}
      {last && !id && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm" data-testid="last-saved-banner">
          <CheckCircle2 className="h-5 w-5 text-emerald-600" /> Saved <b className="font-mono">{last.voucher_no}</b> for {last.party_name}
          <span className="ml-auto flex gap-2"><WhatsAppButton voucher={last} testid="whatsapp-last-voucher-button" />
          <Button variant="outline" onClick={() => printVoucher(last, settings)} data-testid="print-last-voucher-button"><Printer className="h-4 w-4 mr-1" /> Print</Button></span>
        </div>
      )}
      <div className="rounded-xl border bg-white p-5 sm:p-6 space-y-6">
        <div className="grid gap-5 sm:grid-cols-3">
          <div className="space-y-2"><Label>Voucher No.</Label><div className="h-11 flex items-center rounded-md bg-slate-100 px-3 font-mono text-sm" data-testid="voucher-number">{vno}</div></div>
          <div className="space-y-2"><Label>Date</Label><DateInput value={f.date} onChange={(date) => setF({ ...f, date })} testid="voucher-date-input" /></div>
          <div className="space-y-2"><Label>{isItem ? "Invoice / Ref No." : "Reference No."}</Label><Input className="h-11" value={f.reference_no} onChange={(e) => setF({ ...f, reference_no: e.target.value })} data-testid="voucher-reference-input" /></div>
        </div>
        {SIMPLE[type] && (
          <label className="flex items-center gap-2 text-sm text-slate-600 w-fit">
            <Switch checked={f.advanced} onCheckedChange={(advanced) => setF({ ...f, advanced })} data-testid="advanced-mode-switch" /> Multi-line entry
          </label>
        )}
        {isItem ? <ItemsForm type={type} ledgers={ledgers} value={f} onChange={setF} stock={stock} />
          : SIMPLE[type] && !f.advanced ? <SimpleForm type={type} ledgers={ledgers} value={f.simple} onChange={(simple) => setF({ ...f, simple })} />
          : <JournalGrid ledgers={ledgers} lines={f.lines} setLines={(lines) => setF({ ...f, lines })} />}
        <div className="space-y-2"><Label>Narration</Label><Textarea rows={2} value={f.narration} onChange={(e) => setF({ ...f, narration: e.target.value })} placeholder="Being..." data-testid="voucher-narration-input" /></div>
        <div className="flex flex-wrap justify-end gap-3">
          {id && <Button variant="outline" className="h-12 px-6" onClick={() => nav("/vouchers")} data-testid="voucher-cancel-edit-button">Back</Button>}
          <Button onClick={save} disabled={busy} className="h-12 px-8 text-base" data-testid="voucher-submit-button">
            {busy ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />} {id ? "Update Voucher" : "Save Voucher"}
          </Button>
        </div>
      </div>
    </div>
  );
}
