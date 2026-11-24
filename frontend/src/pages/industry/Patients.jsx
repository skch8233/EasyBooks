import { useState } from "react";
import { toast } from "sonner";
import { Plus, Printer, Trash2 } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { amt, dmy } from "@/lib/format";
import { printHospitalReceipt } from "@/lib/receipts";
import { Button } from "@/components/ui/button";
import { DateInput } from "@/components/DateInput";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, PageHead, Td, Th, sel, todayIso, useList, useMoneyLedgers, Pick, monthOptions } from "@/components/industry/common";

const PBLANK = { name: "", age: "", gender: "", phone: "", address: "", blood_group: "", guardian: "" };
const KINDS = { opd: "OPD consultation", ipd: "IPD admission", lab: "Laboratory", pharmacy: "Pharmacy" };

const Bill = ({ patients, meds, onDone }) => {
  const { settings } = useApp();
  const money = useMoneyLedgers();
  const [b, setB] = useState({ patient_id: "", kind: "opd", date: todayIso(), doctor: "", admission_date: "", discharge_date: "", ledger_id: "", lines: [{ description: "", amount: "" }] });
  const setL = (i, k, v) => setB({ ...b, lines: b.lines.map((x, j) => (j === i ? { ...x, [k]: v } : x)) });
  const ph = b.kind === "pharmacy";
  const ipd = b.kind === "ipd";
  const okMeds = (meds || []).filter((m) => !m.expired && m.qty > 0);
  const save = async () => {
    const lines = b.lines.map((l) => (ph ? { medicine_id: l.medicine_id, qty: Number(l.qty || 0) } : { description: l.description, amount: Number(l.amount || 0) }));
    try { const { data } = await api.post("/hospital/bills", { ...b, admission_date: ipd ? b.admission_date : "", discharge_date: ipd ? b.discharge_date : "", ledger_id: b.ledger_id || money[0]?.id, lines }); toast.success(`${data.bill_no} saved`); printHospitalReceipt(settings, data);
      setB({ ...b, lines: [{ description: "", amount: "" }] }); onDone(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Card className="space-y-3" data-testid="hospital-bill-form"><div className="font-semibold">New bill / receipt</div>
      <div className="grid gap-3 md:grid-cols-5">
        <div className="space-y-1 md:col-span-2"><Label className="text-xs">Patient</Label><Pick value={b.patient_id} onChange={(v) => setB({ ...b, patient_id: v })} data-testid="bill-patient-select"><option value="">Select patient</option>{(patients || []).map((p) => <option key={p.id} value={p.id}>{p.reg_no} · {p.name}</option>)}</Pick></div>
        <div className="space-y-1"><Label className="text-xs">Type</Label><Pick value={b.kind} onChange={(v) => setB({ ...b, kind: v, lines: [{ description: "", amount: "" }] })} data-testid="bill-kind-select">{Object.entries(KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Pick></div>
        <div className="space-y-1"><Label className="text-xs">Doctor</Label><Input className="h-10" value={b.doctor} onChange={(e) => setB({ ...b, doctor: e.target.value })} data-testid="bill-doctor-input" /></div>
        <div className="space-y-1"><Label className="text-xs">Received in</Label><Pick value={b.ledger_id || money[0]?.id || ""} onChange={(v) => setB({ ...b, ledger_id: v })} data-testid="bill-ledger-select">{money.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</Pick></div>
        {b.kind === "ipd" && <><div className="space-y-1"><Label className="text-xs">Admission</Label><DateInput value={b.admission_date} onChange={(v) => setB({ ...b, admission_date: v })} testid="bill-admission-input" /></div>
          <div className="space-y-1"><Label className="text-xs">Discharge</Label><DateInput value={b.discharge_date} onChange={(v) => setB({ ...b, discharge_date: v })} testid="bill-discharge-input" /></div></>}
      </div>
      {b.lines.map((l, i) => <div key={i} className="grid grid-cols-[2fr_1fr_auto] gap-2">
        {ph ? <Pick value={l.medicine_id || ""} onChange={(v) => setL(i, "medicine_id", v)} data-testid={`bill-med-select-${i}`}><option value="">Select medicine batch</option>{okMeds.map((m) => <option key={m.id} value={m.id}>{m.name} · {m.batch} · exp {m.expiry.slice(0, 7)} · {m.qty} @ ₹{m.mrp}</option>)}</Pick>
          : <Input className="h-10" placeholder={b.kind === "lab" ? "Test name (e.g. CBC)" : "Particulars (e.g. Consultation, Bed charges)"} value={l.description} onChange={(e) => setL(i, "description", e.target.value)} data-testid={`bill-desc-input-${i}`} />}
        <Input className="h-10" type="number" placeholder={ph ? "Qty" : "Amount"} value={ph ? l.qty || "" : l.amount} onChange={(e) => setL(i, ph ? "qty" : "amount", e.target.value)} data-testid={`bill-amount-input-${i}`} />
        <Button size="icon" variant="ghost" onClick={() => setB({ ...b, lines: b.lines.filter((_, j) => j !== i) })} data-testid={`bill-line-remove-${i}`}><Trash2 className="h-4 w-4" /></Button></div>)}
      <div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => setB({ ...b, lines: [...b.lines, { description: "", amount: "" }] })} data-testid="bill-line-add"><Plus className="h-4 w-4 mr-1" />Line</Button>
        <Button size="sm" onClick={save} disabled={!b.patient_id} data-testid="bill-save-button"><Printer className="h-4 w-4 mr-1" />Save & print receipt</Button></div>
    </Card>
  );
};

export default function Patients() {
  const { settings, canWrite } = useApp();
  const [patients, load] = useList("/hospital/patients");
  const [bills, loadBills] = useList("/hospital/bills");
  const [meds, loadMeds] = useList("/hospital/medicines");
  const [f, setF] = useState(PBLANK);
  const add = async () => { try { const { data } = await api.post("/hospital/patients", f); toast.success(`Registered ${data.reg_no}`); setF(PBLANK); load(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <div className="space-y-6" data-testid="patients-page">
      <PageHead title="Patients & Billing" sub="Register patients and issue OPD, IPD, lab and pharmacy receipts." />
      {canWrite && <Card className="grid gap-3 md:grid-cols-7 items-end" data-testid="patient-form">
        {[["name", "Patient name"], ["age", "Age"], ["gender", "Gender (M/F)"], ["phone", "Phone"], ["blood_group", "Blood group"], ["address", "Address"]].map(([k, l]) =>
          <div key={k} className="space-y-1"><Label className="text-xs">{l}</Label><Input value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`patient-${k}-input`} /></div>)}
        <Button onClick={add} disabled={!f.name.trim()} data-testid="patient-register-button"><Plus className="h-4 w-4 mr-1" />Register</Button></Card>}
      {canWrite && <Bill patients={patients} meds={meds} onDone={() => { loadBills(); loadMeds(); }} />}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="overflow-x-auto" data-testid="patients-table"><div className="font-semibold mb-3">Patients</div><table className="w-full text-sm"><thead><tr className="text-left"><Th>UHID</Th><Th>Name</Th><Th>Age/Sex</Th><Th>Phone</Th></tr></thead>
          <tbody>{(patients || []).map((p) => <tr key={p.id} className="border-t" data-testid={`patient-row-${p.reg_no}`}><Td className="font-mono">{p.reg_no}</Td><Td>{p.name}</Td><Td>{p.age}/{p.gender}</Td><Td>{p.phone}</Td></tr>)}</tbody></table></Card>
        <Card className="overflow-x-auto" data-testid="hospital-bills"><div className="font-semibold mb-3">Receipts</div><table className="w-full text-sm"><thead><tr className="text-left"><Th>Bill</Th><Th>Date</Th><Th>Patient</Th><Th r>Amount</Th><Th /></tr></thead>
          <tbody>{(bills || []).map((b) => <tr key={b.id} className="border-t" data-testid={`hospital-bill-row-${b.bill_no}`}><Td className="font-mono">{b.bill_no}</Td><Td>{dmy(b.date)}</Td><Td>{b.patient}</Td><Td r>{amt(b.total)}</Td>
            <Td r><Button size="sm" variant="ghost" onClick={() => printHospitalReceipt(settings, b)} data-testid={`hospital-bill-print-${b.bill_no}`}><Printer className="h-4 w-4" /></Button></Td></tr>)}</tbody></table></Card>
      </div>
    </div>
  );
}
