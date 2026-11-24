import { useState } from "react";
import { toast } from "sonner";
import { Play, Plus } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { amt, dmy } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { DateInput } from "@/components/DateInput";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, PageHead, Td, Th, sel, todayIso, useList, Pick, monthOptions } from "@/components/industry/common";

const BLANK = { name: "", party_ledger_id: "", description: "", rate: "", gst_rate: 18, gst_type: "intra", every_months: 1, next_date: todayIso() };

export default function Recurring() {
  const { canWrite } = useApp();
  const [rows, load] = useList("/recurring");
  const [ledgers] = useList("/ledgers");
  const [f, setF] = useState(BLANK);
  const parties = (ledgers || []).filter((l) => ["sundry_debtors", "sundry_creditors"].includes(l.group));
  const salesL = (ledgers || []).find((l) => l.group === "sales");
  const name = (id) => (ledgers || []).find((l) => l.id === id)?.name || "";
  const add = async () => {
    try {
      await api.post("/recurring", { name: f.name, party_ledger_id: f.party_ledger_id, account_ledger_id: salesL?.id, gst_type: f.gst_type, every_months: Number(f.every_months), next_date: f.next_date,
        items: [{ description: f.description || f.name, qty: 1, rate: Number(f.rate), gst_rate: Number(f.gst_rate) }] });
      toast.success("Recurring bill saved"); setF(BLANK); load();
    } catch (e) { toast.error(errMsg(e)); }
  };
  const run = async () => { try { const { data } = await api.post("/recurring/run"); toast.success(data.created.length ? `${data.created.length} bill(s) created: ${data.created.map((c) => c.voucher_no).join(", ")}` : "No bills due today"); load(); } catch (e) { toast.error(errMsg(e)); } };
  const toggle = async (r) => { await api.put(`/recurring/${r.id}`, { ...r, active: !r.active }); load(); };
  return (
    <div className="space-y-6" data-testid="recurring-page">
      <PageHead title="Recurring Bills" sub="Retainer and monthly bills. Generate all bills that are due in one click.">
        {canWrite && <Button onClick={run} data-testid="recurring-run-button"><Play className="h-4 w-4 mr-1" />Generate due bills</Button>}
      </PageHead>
      {canWrite && <Card className="grid gap-3 md:grid-cols-8 items-end" data-testid="recurring-form">
        <div className="space-y-1 md:col-span-2"><Label className="text-xs">Name</Label><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Monthly SEO retainer" data-testid="recurring-name-input" /></div>
        <div className="space-y-1 md:col-span-2"><Label className="text-xs">Client</Label><Pick value={f.party_ledger_id} onChange={(v) => setF({ ...f, party_ledger_id: v })} data-testid="recurring-party-select"><option value="">Select client</option>{parties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Pick></div>
        <div className="space-y-1"><Label className="text-xs">Amount (before GST)</Label><Input type="number" value={f.rate} onChange={(e) => setF({ ...f, rate: e.target.value })} data-testid="recurring-rate-input" /></div>
        <div className="space-y-1"><Label className="text-xs">GST</Label><Pick value={f.gst_type} onChange={(v) => setF({ ...f, gst_type: v })} data-testid="recurring-gst-select"><option value="intra">CGST+SGST</option><option value="inter">IGST</option><option value="none">No GST</option></Pick></div>
        <div className="space-y-1"><Label className="text-xs">First bill date</Label><DateInput value={f.next_date} onChange={(v) => setF({ ...f, next_date: v })} testid="recurring-date-input" /></div>
        <Button onClick={add} disabled={!f.name.trim() || !f.party_ledger_id || !(Number(f.rate) > 0) || !salesL} data-testid="recurring-save-button"><Plus className="h-4 w-4 mr-1" />Add</Button>
        <div className="space-y-1 md:col-span-2"><Label className="text-xs">Repeat every (months)</Label><Input type="number" min={1} max={12} value={f.every_months} onChange={(e) => setF({ ...f, every_months: e.target.value })} data-testid="recurring-every-input" /></div>
      </Card>}
      <Card className="overflow-x-auto"><table className="w-full text-sm" data-testid="recurring-table"><thead><tr className="text-left"><Th>Name</Th><Th>Client</Th><Th r>Amount</Th><Th>Every</Th><Th>Next bill</Th><Th>Generated</Th><Th /></tr></thead>
        <tbody>{(rows || []).map((r) => <tr key={r.id} className="border-t" data-testid={`recurring-row-${r.id}`}><Td className="font-semibold">{r.name}</Td><Td>{name(r.party_ledger_id)}</Td><Td r>{amt(r.items[0]?.rate)}</Td><Td>{r.every_months} month(s)</Td>
          <Td>{r.active ? dmy(r.next_date) : "Paused"}</Td><Td className="font-mono text-xs">{r.generated.slice(-3).map((g) => g.voucher_no).join(", ") || "-"}</Td>
          <Td r>{canWrite && <Button size="sm" variant="ghost" onClick={() => toggle(r)} data-testid={`recurring-toggle-${r.id}`}>{r.active ? "Pause" : "Resume"}</Button>}</Td></tr>)}</tbody></table></Card>
    </div>
  );
}
