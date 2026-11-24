import { useState } from "react";
import { toast } from "sonner";
import { Plus, Printer } from "lucide-react";
import { printPayslip } from "@/lib/receipts";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { amt, inr } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { DateInput } from "@/components/DateInput";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, PageHead, Td, Th, sel, todayIso, useList, useMoneyLedgers, Pick, monthOptions } from "@/components/industry/common";

const BLANK = { name: "", designation: "", phone: "", basic: "", allowances: "", deductions: "", active: true };

export default function Payroll() {
  const { canWrite, settings } = useApp();
  const [staff, load] = useList("/payroll/staff");
  const [runs, loadRuns] = useList("/payroll/runs");
  const money = useMoneyLedgers();
  const [f, setF] = useState(BLANK);
  const [edit, setEdit] = useState(null);
  const [run, setRun] = useState({ month: todayIso().slice(0, 7), date: todayIso(), ledger_id: "" });
  const save = async () => {
    const body = { ...f, basic: Number(f.basic || 0), allowances: Number(f.allowances || 0), deductions: Number(f.deductions || 0) };
    try { edit ? await api.put(`/payroll/staff/${edit}`, body) : await api.post("/payroll/staff", body); toast.success("Staff saved"); setF(BLANK); setEdit(null); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  const post = async () => {
    try { const { data } = await api.post("/payroll/runs", { ...run, ledger_id: run.ledger_id || money[0]?.id }); toast.success(`Salary for ${data.month} posted (${data.voucher_no})`); loadRuns(); } catch (e) { toast.error(errMsg(e)); }
  };
  const net = (s) => s.basic + s.allowances - s.deductions;
  return (
    <div className="space-y-6" data-testid="payroll-page">
      <PageHead title="Staff Payroll" sub="Monthly salary for all staff, posted to your books in one entry." />
      {canWrite && <Card className="grid gap-3 md:grid-cols-7 items-end" data-testid="staff-form">
        {[["name", "Name"], ["designation", "Designation"], ["phone", "Phone"], ["basic", "Basic"], ["allowances", "Allowances"], ["deductions", "Deductions (PF/ESI/TDS)"]].map(([k, l]) =>
          <div key={k} className="space-y-1"><Label className="text-xs">{l}</Label><Input value={f[k]} type={["basic", "allowances", "deductions"].includes(k) ? "number" : "text"} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`staff-${k}-input`} /></div>)}
        <Button onClick={save} disabled={!f.name.trim()} data-testid="staff-save-button"><Plus className="h-4 w-4 mr-1" />{edit ? "Update" : "Add staff"}</Button>
      </Card>}
      <Card className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left"><Th>Staff</Th><Th r>Basic</Th><Th r>Allowances</Th><Th r>Deductions</Th><Th r>Net pay</Th><Th>Status</Th><Th /></tr></thead>
        <tbody>{(staff || []).map((s) => <tr key={s.id} className="border-t" data-testid={`staff-row-${s.id}`}><Td><div className="font-semibold">{s.name}</div><div className="text-xs text-slate-500">{s.designation}</div></Td>
          <Td r>{amt(s.basic)}</Td><Td r>{amt(s.allowances)}</Td><Td r>{amt(s.deductions)}</Td><Td r className="font-semibold">{amt(net(s))}</Td><Td>{s.active ? "Active" : "Inactive"}</Td>
          <Td r>{canWrite && <div className="flex justify-end gap-1"><Button size="sm" variant="outline" onClick={() => { setEdit(s.id); setF({ ...s }); }} data-testid={`staff-edit-${s.id}`}>Edit</Button>
            <Button size="sm" variant="ghost" onClick={async () => { await api.put(`/payroll/staff/${s.id}`, { ...s, active: !s.active }); load(); }} data-testid={`staff-toggle-${s.id}`}>{s.active ? "Deactivate" : "Activate"}</Button></div>}</Td></tr>)}</tbody></table></Card>
      {canWrite && <Card className="grid gap-3 md:grid-cols-4 items-end" data-testid="payroll-run-form">
        <div className="space-y-1"><Label className="text-xs">Salary month</Label><Pick value={run.month} onChange={(v) => setRun({ ...run, month: v })} data-testid="payroll-month-input">{monthOptions().map((m) => <option key={m} value={m}>{new Date(`${m}-01`).toLocaleDateString("en-IN", { month: "long", year: "numeric" })}</option>)}</Pick></div>
        <div className="space-y-1"><Label className="text-xs">Payment date</Label><DateInput value={run.date} onChange={(v) => setRun({ ...run, date: v })} testid="payroll-date-input" /></div>
        <div className="space-y-1"><Label className="text-xs">Paid from</Label><Pick value={run.ledger_id || money[0]?.id || ""} onChange={(v) => setRun({ ...run, ledger_id: v })} data-testid="payroll-ledger-select">{money.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</Pick></div>
        <Button onClick={post} data-testid="payroll-run-button">Post salary for {run.month} ({inr((staff || []).filter((s) => s.active).reduce((a, s) => a + net(s), 0))})</Button>
      </Card>}
      <Card data-testid="payroll-runs"><div className="font-semibold mb-3">Payroll history & payslips</div>
        {(runs || []).map((r) => <details key={r.id} className="border-t py-2" data-testid={`payroll-run-${r.month}`}><summary className="cursor-pointer text-sm flex gap-4 items-center"><b>{r.month}</b><span className="text-primary text-xs underline">View payslips</span><span>{r.slips.length} staff</span><span className="num">Gross {inr(r.gross)}</span><span className="num">Net {inr(r.net)}</span><span className="font-mono text-slate-500">{r.voucher_no}</span></summary>
          <table className="w-full text-sm mt-2"><tbody>{r.slips.map((p) => <tr key={p.staff_id}><Td>{p.name}</Td><Td r>{amt(p.gross)}</Td><Td r>-{amt(p.deductions)}</Td><Td r className="font-semibold">{amt(p.net)}</Td><Td r><Button size="sm" variant="ghost" onClick={() => printPayslip(settings, r, p)} data-testid={`payslip-print-${r.month}-${p.staff_id}`}><Printer className="h-4 w-4" /></Button></Td></tr>)}</tbody></table></details>)}
        {runs && !runs.length && <div className="text-sm text-slate-500">No salary posted yet.</div>}
      </Card>
    </div>
  );
}
