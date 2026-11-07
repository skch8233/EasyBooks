import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, errMsg } from "@/lib/api";
import { STATES } from "@/lib/format";

const EMPTY = { name: "", group: "sundry_debtors", opening_balance: 0, opening_type: "Dr", gstin: "", state: "", phone: "", email: "", address: "" };
const NATURE_DEFAULT = { asset: "Dr", expense: "Dr", liability: "Cr", income: "Cr" };

const F = ({ label, children }) => <div className="space-y-1.5"><Label>{label}</Label>{children}</div>;

export const LedgerDialog = ({ open, ledger, groups, onClose, onSaved }) => {
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setF(ledger ? { ...EMPTY, ...ledger } : EMPTY); }, [open, ledger]);
  const set = (k) => (e) => setF({ ...f, [k]: e?.target ? e.target.value : e });
  const party = ["sundry_debtors", "sundry_creditors"].includes(f.group);

  const save = async () => {
    setBusy(true);
    try {
      const body = { ...f, opening_balance: Number(f.opening_balance) || 0 };
      ledger ? await api.put(`/ledgers/${ledger.id}`, body) : await api.post("/ledgers", body);
      toast.success(`Ledger "${f.name}" saved`);
      onSaved();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="ledger-dialog">
        <DialogHeader><DialogTitle className="font-heading text-xl">{ledger ? "Edit Ledger" : "Create Ledger"}</DialogTitle></DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <F label="Ledger name"><Input className="h-11" value={f.name} onChange={set("name")} data-testid="ledger-name-input" autoFocus /></F>
          <F label="Group (Under)">
            <Select value={f.group} onValueChange={(g) => setF({ ...f, group: g, opening_type: ledger ? f.opening_type : NATURE_DEFAULT[groups.find((x) => x.key === g)?.nature] || "Dr" })} disabled={!!ledger?.system_key}>
              <SelectTrigger className="h-11" data-testid="ledger-group-select"><SelectValue /></SelectTrigger>
              <SelectContent>{groups.map((g) => <SelectItem key={g.key} value={g.key} data-testid={`ledger-group-option-${g.key}`}>{g.name}</SelectItem>)}</SelectContent>
            </Select>
          </F>
          <F label="Opening balance (₹)"><Input className="h-11 num text-right" type="number" min="0" step="0.01" value={f.opening_balance} onChange={set("opening_balance")} data-testid="ledger-opening-input" /></F>
          <F label="Dr / Cr">
            <Select value={f.opening_type} onValueChange={set("opening_type")}>
              <SelectTrigger className="h-11" data-testid="ledger-opening-type-select"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="Dr">Dr (Debit)</SelectItem><SelectItem value="Cr">Cr (Credit)</SelectItem></SelectContent>
            </Select>
          </F>
          {party && <>
            <F label="GSTIN (optional)"><Input className="h-11 font-mono uppercase" maxLength={15} value={f.gstin} onChange={set("gstin")} data-testid="ledger-gstin-input" /></F>
            <F label="State">
              <Select value={f.state || "none"} onValueChange={(v) => setF({ ...f, state: v === "none" ? "" : v })}>
                <SelectTrigger className="h-11" data-testid="ledger-state-select"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="none">Not set</SelectItem>{STATES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            </F>
            <F label="Phone"><Input className="h-11" value={f.phone} onChange={set("phone")} data-testid="ledger-phone-input" /></F>
            <F label="Email"><Input className="h-11" value={f.email} onChange={set("email")} data-testid="ledger-email-input" /></F>
            <div className="sm:col-span-2"><F label="Address"><Input className="h-11" value={f.address} onChange={set("address")} data-testid="ledger-address-input" /></F></div>
          </>}
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onClose} data-testid="ledger-dialog-cancel">Cancel</Button>
          <Button onClick={save} disabled={busy || !f.name.trim()} className="px-6" data-testid="ledger-save-button">Save Ledger</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
