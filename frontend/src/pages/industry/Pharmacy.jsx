import { useState } from "react";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { amt, dmy } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DateInput } from "@/components/DateInput";
import { Label } from "@/components/ui/label";
import { Card, PageHead, Td, Th, useList } from "@/components/industry/common";

const BLANK = { name: "", batch: "", expiry: "", qty: "", mrp: "", gst_rate: 12 };
const tag = (m) => (m.expired ? ["Expired", "bg-red-100 text-red-700"] : m.expiring ? [`Expires in ${m.days_to_expiry} days`, "bg-amber-100 text-amber-800"] : ["OK", "bg-emerald-50 text-emerald-700"]);

export default function Pharmacy() {
  const { canWrite } = useApp();
  const [meds, load] = useList("/hospital/medicines");
  const [f, setF] = useState(BLANK);
  const [edit, setEdit] = useState(null);
  const save = async () => {
    const body = { ...f, qty: Number(f.qty || 0), mrp: Number(f.mrp || 0), gst_rate: Number(f.gst_rate || 0) };
    try { edit ? await api.put(`/hospital/medicines/${edit}`, body) : await api.post("/hospital/medicines", body); toast.success("Batch saved"); setF(BLANK); setEdit(null); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  const alerts = (meds || []).filter((m) => m.expired || m.expiring);
  return (
    <div className="space-y-6" data-testid="pharmacy-page">
      <PageHead title="Pharmacy Stock" sub="Medicines by batch and expiry. Expired batches cannot be billed." />
      {alerts.length > 0 && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" data-testid="pharmacy-expiry-alert"><b>{alerts.length} batch(es) expired or expiring within 90 days:</b> {alerts.map((m) => `${m.name} (${m.batch})`).join(", ")}</div>}
      {canWrite && <Card className="grid gap-3 md:grid-cols-7 items-end" data-testid="medicine-form">
        {[["name", "Medicine", "text"], ["batch", "Batch no", "text"], ["expiry", "Expiry date", "date"], ["qty", "Quantity", "number"], ["mrp", "MRP per unit", "number"], ["gst_rate", "GST %", "number"]].map(([k, l, t]) =>
          <div key={k} className="space-y-1"><Label className="text-xs">{l}</Label>{t === "date" ? <DateInput value={f[k]} onChange={(v) => setF({ ...f, [k]: v })} testid={`medicine-${k}-input`} />
            : <Input className="h-10" type={t} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`medicine-${k}-input`} />}</div>)}
        <Button onClick={save} disabled={!f.name.trim() || !f.batch.trim() || !f.expiry} data-testid="medicine-save-button"><Plus className="h-4 w-4 mr-1" />{edit ? "Update" : "Add batch"}</Button></Card>}
      <Card className="overflow-x-auto"><table className="w-full text-sm" data-testid="medicines-table"><thead><tr className="text-left"><Th>Medicine</Th><Th>Batch</Th><Th>Expiry</Th><Th r>Qty</Th><Th r>MRP</Th><Th>Status</Th><Th /></tr></thead>
        <tbody>{(meds || []).map((m) => { const [t, c] = tag(m); return <tr key={m.id} className="border-t" data-testid={`medicine-row-${m.id}`}><Td className="font-semibold">{m.name}</Td><Td className="font-mono">{m.batch}</Td><Td>{dmy(m.expiry)}</Td>
          <Td r>{m.qty}</Td><Td r>{amt(m.mrp)}</Td><Td><span className={`rounded px-2 py-0.5 text-xs font-semibold ${c}`} data-testid={`medicine-status-${m.id}`}>{t}</span></Td>
          <Td r>{canWrite && <Button size="sm" variant="outline" onClick={() => { setEdit(m.id); setF({ name: m.name, batch: m.batch, expiry: m.expiry, qty: m.qty, mrp: m.mrp, gst_rate: m.gst_rate }); }} data-testid={`medicine-edit-${m.id}`}>Edit</Button>}</Td></tr>; })}</tbody></table></Card>
    </div>
  );
}
