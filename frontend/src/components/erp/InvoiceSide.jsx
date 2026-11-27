import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { amt, dmy, todayIso } from "@/lib/format";
import { BLANK_LINE } from "@/lib/erp";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { LineItems, cleanLines } from "@/components/erp/LineItems";
import { useErp } from "@/pages/erp/ErpShell";

export const ReasonDialog = ({ open, onClose, onOk, title, note }) => {
  const [r, setR] = useState("");
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}><DialogContent><DialogHeader><DialogTitle>{title}</DialogTitle></DialogHeader>
      <p className="text-sm text-slate-600">{note}</p>
      <Label>Reason *</Label><textarea rows={3} className="w-full rounded-md border p-2 text-sm" value={r} onChange={(e) => setR(e.target.value)} data-testid="cancel-reason-input" />
      <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Back</Button>
        <Button className="bg-red-600 hover:bg-red-700" disabled={r.trim().length < 3} onClick={() => onOk(r.trim())} data-testid="cancel-confirm-button">Confirm cancel</Button></div>
    </DialogContent></Dialog>
  );
};

const PayDialog = ({ doc, open, onClose, reload }) => {
  const [banks, setBanks] = useState([]);
  const [f, setF] = useState({ date: todayIso(), amount: "", ledger_id: "", reference: "" });
  useEffect(() => { if (open) api.get("/ledgers").then((r) => { const b = r.data.filter((l) => ["cash", "bank"].includes(l.group)); setBanks(b); setF((x) => ({ ...x, amount: doc.balance, ledger_id: x.ledger_id || b[0]?.id || "" })); }); }, [open, doc.balance]);
  const save = async () => {
    try { await api.post(`/erp/invoices/${doc.id}/payments`, { ...f, amount: Number(f.amount) }); toast.success("Payment recorded and posted as a receipt"); onClose(); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}><DialogContent><DialogHeader><DialogTitle>Record payment · balance ₹{amt(doc.balance)}</DialogTitle></DialogHeader>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1"><Label>Date</Label><Input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} data-testid="payment-date-input" /></div>
        <div className="space-y-1"><Label>Amount (₹)</Label><Input type="number" step="any" className="font-mono" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} data-testid="payment-amount-input" /></div>
        <div className="space-y-1"><Label>Received in</Label><select className="h-10 w-full rounded-md border px-2 bg-white" value={f.ledger_id} onChange={(e) => setF({ ...f, ledger_id: e.target.value })} data-testid="payment-ledger-select">
          {banks.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></div>
        <div className="space-y-1"><Label>Reference (UTR / cheque)</Label><Input value={f.reference} onChange={(e) => setF({ ...f, reference: e.target.value })} data-testid="payment-reference-input" /></div>
      </div>
      <div className="flex justify-end"><Button onClick={save} data-testid="payment-save-button">Save payment</Button></div>
    </DialogContent></Dialog>
  );
};

const NoteDialog = ({ doc, kind, onClose, reload }) => {
  const [f, setF] = useState({ date: todayIso(), reason: "", items: [{ ...BLANK_LINE, gst_rate: doc.items?.[0]?.gst_rate ?? 18 }] });
  const save = async () => {
    try { const { data } = await api.post(`/erp/invoices/${doc.id}/notes`, { kind, ...f, items: cleanLines(f.items) }); toast.success(`${data.number} posted as ${data.voucher_no}`); onClose(); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open={!!kind} onOpenChange={(o) => !o && onClose()}><DialogContent className="max-w-3xl"><DialogHeader><DialogTitle>{kind === "credit" ? "Credit note (reduce amount)" : "Debit note (add amount)"} against {doc.number}</DialogTitle></DialogHeader>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1"><Label>Date</Label><Input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} data-testid="note-date-input" /></div>
        <div className="space-y-1"><Label>Reason *</Label><Input value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} data-testid="note-reason-input" /></div>
        <div className="sm:col-span-2"><LineItems prefix="note-line" lines={f.items} setLines={(items) => setF({ ...f, items })} /></div>
      </div>
      <div className="flex justify-end"><Button onClick={save} data-testid="note-save-button">Issue {kind} note</Button></div>
    </DialogContent></Dialog>
  );
};

export const InvoiceSide = ({ doc, reload }) => {
  const { perm } = useErp();
  const [pay, setPay] = useState(false);
  const [note, setNote] = useState(null);
  return (
    <div className="rounded-xl border bg-white p-4 space-y-3 text-sm" data-testid="invoice-payments-panel">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div><div className="text-xs uppercase text-slate-500">Net payable</div><div className="font-mono font-bold">₹{amt(doc.totals.net_payable)}</div></div>
        <div><div className="text-xs uppercase text-slate-500">Received</div><div className="font-mono font-bold" data-testid="invoice-paid">₹{amt(doc.paid)}</div></div>
        <div><div className="text-xs uppercase text-slate-500">Credit / debit notes</div><div className="font-mono">−{amt(doc.credit_total || 0)} / +{amt(doc.debit_total || 0)}</div></div>
        <div><div className="text-xs uppercase text-slate-500">Balance</div><div className="font-mono font-bold text-red-700" data-testid="invoice-balance">₹{amt(doc.balance)}</div></div>
      </div>
      <div className="text-xs text-slate-500">Posted in EASYTALLY BOOKS as <b>{doc.voucher_no}</b> (sales voucher).</div>
      {perm("finalize") && <div className="flex flex-wrap gap-2">
        <Button size="sm" disabled={doc.balance <= 0} onClick={() => setPay(true)} data-testid="invoice-add-payment">Record payment</Button>
        <Button size="sm" variant="outline" disabled={doc.balance <= 0} onClick={() => setNote("credit")} data-testid="invoice-credit-note">Credit note</Button>
        <Button size="sm" variant="outline" onClick={() => setNote("debit")} data-testid="invoice-debit-note">Debit note</Button></div>}
      {doc.payments?.map((p) => <div key={p.id} className="flex gap-2 border-t pt-2" data-testid={`payment-${p.id}`}><span className="font-mono">{dmy(p.date)}</span><span>₹{amt(p.amount)} via {p.mode}</span><span className="text-slate-500">{p.reference}</span><span className="ml-auto text-xs">{p.voucher_no}</span></div>)}
      {doc.notes_list?.map((n) => <div key={n.id} className="flex gap-2 border-t pt-2"><span className="font-mono">{n.number}</span><span>{n.kind} ₹{amt(n.totals.total)}: {n.reason}</span><span className="ml-auto text-xs">{n.voucher_no}</span></div>)}
      <PayDialog doc={doc} open={pay} onClose={() => setPay(false)} reload={reload} />
      {note && <NoteDialog doc={doc} kind={note} onClose={() => setNote(null)} reload={reload} />}
    </div>
  );
};
