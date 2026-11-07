import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Printer, Pencil, Ban } from "lucide-react";
import { WhatsAppButton } from "@/components/WhatsAppButton";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { amt, dmy, dmyTime, VT } from "@/lib/format";
import { printVoucher } from "@/lib/print";

export const VoucherDialog = ({ id, onClose, onChanged }) => {
  const { canWrite, settings } = useApp();
  const [v, setV] = useState(null);
  const [reason, setReason] = useState("");
  const [confirm, setConfirm] = useState(false);
  const nav = useNavigate();
  useEffect(() => { setV(null); setConfirm(false); if (id) api.get(`/vouchers/${id}`).then((r) => setV(r.data)); }, [id]);

  const cancel = async () => {
    try {
      await api.post(`/vouchers/${id}/cancel`, { reason });
      toast.success("Voucher cancelled. Audit trail recorded.");
      onChanged?.();
      onClose();
    } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <Dialog open={!!id} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="voucher-dialog">
        {!v ? <div className="py-10 text-center text-slate-500">Loading...</div> : (
          <>
            <DialogHeader>
              <DialogTitle className="font-heading text-xl flex flex-wrap items-center gap-3">
                {VT[v.voucher_type]?.label} <span className="font-mono text-base text-slate-500" data-testid="dialog-voucher-no">{v.voucher_no}</span>
                {v.status === "cancelled" && <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700" data-testid="dialog-cancelled-badge">CANCELLED</span>}
              </DialogTitle>
            </DialogHeader>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <div><div className="text-xs text-slate-500">Date</div><div className="font-mono">{dmy(v.date)}</div></div>
              <div><div className="text-xs text-slate-500">Party</div><div className="font-medium">{v.party_name}</div></div>
              <div><div className="text-xs text-slate-500">Amount</div><div className="num font-semibold">₹{amt(v.amount)}</div></div>
              <div><div className="text-xs text-slate-500">Ref No.</div><div>{v.reference_no || "-"}</div></div>
            </div>
            {v.items?.length > 0 && (
              <table className="w-full eb-table">
                <thead><tr><th>Item</th><th>HSN</th><th className="!text-right">Qty</th><th className="!text-right">Rate</th><th className="!text-right">GST%</th><th className="!text-right">Amount</th></tr></thead>
                <tbody>{v.items.map((i, n) => <tr key={n}><td>{i.description}</td><td className="font-mono">{i.hsn}</td><td className="text-right num">{i.qty}</td><td className="text-right num">{amt(i.rate)}</td><td className="text-right num">{i.gst_rate}</td><td className="text-right num">{amt(i.amount)}</td></tr>)}</tbody>
              </table>
            )}
            <table className="w-full eb-table" data-testid="dialog-entries-table">
              <thead><tr><th>Ledger</th><th className="!text-right">Debit</th><th className="!text-right">Credit</th></tr></thead>
              <tbody>{v.entries.map((e, n) => <tr key={n}><td>{e.ledger_name}</td><td className="text-right num">{e.debit ? amt(e.debit) : ""}</td><td className="text-right num">{e.credit ? amt(e.credit) : ""}</td></tr>)}</tbody>
              <tfoot><tr><td>Total</td><td className="text-right num">{amt(v.amount)}</td><td className="text-right num">{amt(v.amount)}</td></tr></tfoot>
            </table>
            {v.narration && <p className="text-sm"><b>Narration:</b> {v.narration}</p>}
            {v.cancel_reason && <p className="text-sm text-red-700"><b>Cancel reason:</b> {v.cancel_reason}</p>}
            <div>
              <div className="text-xs font-semibold uppercase text-slate-500 mb-2">History</div>
              <ul className="space-y-1 text-sm" data-testid="dialog-history">
                {v.history.map((h) => <li key={h.id} className="flex gap-3"><span className="font-mono text-xs text-slate-500 w-36">{dmyTime(h.timestamp)}</span><span className="capitalize font-medium">{h.action}</span><span className="text-slate-500">by {h.user_name}</span></li>)}
              </ul>
            </div>
            {confirm && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 space-y-3">
                <div className="text-sm font-medium text-red-800">Cancel this voucher? It stays in records (marked cancelled) and is excluded from balances.</div>
                <Input placeholder="Reason for cancellation" value={reason} onChange={(e) => setReason(e.target.value)} data-testid="cancel-reason-input" />
                <div className="flex gap-2"><Button variant="destructive" onClick={cancel} data-testid="confirm-cancel-voucher-button">Confirm Cancel</Button><Button variant="outline" onClick={() => setConfirm(false)}>Keep</Button></div>
              </div>
            )}
            <div className="flex flex-wrap justify-end gap-2 pt-2">
              <WhatsAppButton voucher={v} testid="dialog-whatsapp-button" />
              <Button variant="outline" onClick={() => printVoucher(v, settings)} data-testid="dialog-print-button"><Printer className="h-4 w-4 mr-1" /> Print</Button>
              {canWrite && v.status === "active" && <>
                <Button variant="outline" onClick={() => nav(`/voucher/edit/${v.id}`)} data-testid="dialog-edit-button"><Pencil className="h-4 w-4 mr-1" /> Edit</Button>
                <Button variant="outline" className="text-red-600 hover:text-red-700" onClick={() => setConfirm(true)} data-testid="dialog-cancel-voucher-button"><Ban className="h-4 w-4 mr-1" /> Cancel Voucher</Button>
              </>}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};
