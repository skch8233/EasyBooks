import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, errMsg } from "@/lib/api";
import { STATES } from "@/lib/format";
import { fillEmpty, useGstinAutofill } from "@/lib/gstin";

const EMPTY = { name: "", group: "sundry_debtors", opening_balance: 0, opening_type: "Dr", gstin: "", state: "", phone: "", email: "", address: "", credit_days: "", dep_method: "none", dep_rate: 0, dep_cost: 0 };
const NATURE_DEFAULT = { asset: "Dr", expense: "Dr", liability: "Cr", income: "Cr" };

const F = ({ label, children }) => <div className="space-y-1.5"><Label>{label}</Label>{children}</div>;

export const LedgerDialog = ({ open, ledger, groups, onClose, onSaved }) => {
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  useEffect(() => { setF(open && ledger ? { ...EMPTY, ...ledger } : EMPTY); }, [open, ledger]);
  const set = (k) => (e) => setF({ ...f, [k]: e?.target ? e.target.value : e });
  useGstinAutofill(!open || (ledger && f.gstin === ledger.gstin) ? "" : f.gstin, (d) => setF((x) => ({ ...fillEmpty(x, { name: d.name, address: d.address, phone: d.phone, email: d.email }), state: d.state || x.state })));
  const party = ["sundry_debtors", "sundry_creditors"].includes(f.group);

  const save = async () => {
    setBusy(true);
    try {
      const body = { ...f, opening_balance: Number(f.opening_balance) || 0, credit_days: f.credit_days === "" || f.credit_days == null ? null : Number(f.credit_days), dep_method: f.dep_method || "none", dep_rate: Number(f.dep_rate) || 0, dep_cost: Number(f.dep_cost) || 0 };
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
            {f.group === "fixed_assets" && <>
              <F label="Depreciation method"><select className="h-11 w-full rounded-md border px-3 bg-white text-sm" value={f.dep_method || "none"} onChange={set("dep_method")} data-testid="ledger-dep-method">
                <option value="none">No depreciation (e.g. land)</option><option value="wdv">Written down value (WDV)</option><option value="slm">Straight line (SLM)</option></select></F>
              {f.dep_method && f.dep_method !== "none" && <F label="Rate % per year (e.g. 15 plant, 40 computers, 10 furniture)"><Input className="h-11 num" type="number" min="0" max="100" step="any" value={f.dep_rate ?? 0} onChange={set("dep_rate")} data-testid="ledger-dep-rate" /></F>}
              {f.dep_method === "slm" && <F label="Original cost of the opening balance (blank = opening value; later purchases and sales are tracked automatically)"><Input className="h-11 num" type="number" min="0" step="any" value={f.dep_cost || ""} onChange={set("dep_cost")} data-testid="ledger-dep-cost" /></F>}
            </>}
          {party && <>
            <F label="GSTIN (optional)"><Input className="h-11 font-mono uppercase" maxLength={15} value={f.gstin} onChange={(e) => setF({ ...f, gstin: e.target.value.toUpperCase() })} data-testid="ledger-gstin-input" /></F>
            <F label="State">
              <Select value={f.state || "none"} onValueChange={(v) => setF({ ...f, state: v === "none" ? "" : v })}>
                <SelectTrigger className="h-11" data-testid="ledger-state-select"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="none">Not set</SelectItem>{STATES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            </F>
            <F label="Phone (WhatsApp)"><Input className="h-11" value={f.phone} onChange={set("phone")} data-testid="ledger-phone-input" /></F>
            {f.group === "sundry_debtors" && <F label="Credit days (blank = company default)"><Input className="h-11 num" type="number" min="0" max="365" value={f.credit_days ?? ""} onChange={set("credit_days")} data-testid="ledger-credit-days-input" /></F>}
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
