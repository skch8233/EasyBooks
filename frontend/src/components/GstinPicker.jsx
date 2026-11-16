import { useState } from "react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useGstinAutofill } from "@/lib/gstin";

// Type a buyer GSTIN: picks the saved buyer, or creates one with state/PAN from the number
export const GstinPicker = ({ mode, onPicked, disabled, testid = "buyer-gstin" }) => {
  const [g, setG] = useState("");
  const [fresh, setFresh] = useState(null);
  const [name, setName] = useState("");
  useGstinAutofill(g, (d, saved) => {
    setFresh(null);
    const id = mode === "party" ? (d.source === "party" ? d.id : null) : d.ledger_id;
    if (saved && id) return onPicked(id);
    setFresh(d);
    setName(d.name || "");
  });
  const create = async () => {
    try {
      const { data } = mode === "party"
        ? await api.post("/erp/parties", { kind: "client", company_name: name.trim(), gstin: g, pan: fresh.pan, state: fresh.state, address: fresh.address || "", mobile: fresh.phone || "", email: fresh.email || "" })
        : await api.post("/ledgers", { name: name.trim(), group: "sundry_debtors", gstin: g, state: fresh.state, address: fresh.address || "", phone: fresh.phone || "", email: fresh.email || "" });
      toast.success(`${data.company_name || data.name} saved - next time this GSTIN fills everything`);
      setFresh(null);
      onPicked(data.id, data);
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="space-y-1" data-testid={testid}>
      <Input disabled={disabled} className="h-10 font-mono uppercase" maxLength={15} placeholder="Buyer GSTIN (fills saved buyer)" value={g} onChange={(e) => setG(e.target.value.toUpperCase())} data-testid={`${testid}-input`} />
      {fresh && <div className="flex gap-2 items-center text-xs" data-testid={`${testid}-new`}>
        <span className="text-slate-500 whitespace-nowrap">New buyer · {fresh.state} · PAN {fresh.pan}</span>
        <Input className="h-8 text-xs" placeholder="Buyer name" value={name} onChange={(e) => setName(e.target.value)} data-testid={`${testid}-name`} />
        <Button type="button" size="sm" disabled={!name.trim()} onClick={create} data-testid={`${testid}-create`}>Save buyer</Button></div>}
    </div>
  );
};
