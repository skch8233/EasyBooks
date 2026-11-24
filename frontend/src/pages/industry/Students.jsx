import { useState } from "react";
import { toast } from "sonner";
import { Plus, Printer, Trash2 } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { amt, dmy, inr } from "@/lib/format";
import { printFeeReceipt } from "@/lib/receipts";
import { Button } from "@/components/ui/button";
import { DateInput } from "@/components/DateInput";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card, PageHead, Td, Th, sel, todayIso, useList, useMoneyLedgers, Pick, monthOptions } from "@/components/industry/common";

const BLANK = { name: "", roll_no: "", course: "", batch: "", phone: "", guardian: "", address: "", fine_per_day: 0, installments: [{ label: "Term 1", due_date: todayIso(), amount: "" }] };

const nextDue = (list) => {
  const [y, m, dd] = (list[list.length - 1]?.due_date || todayIso()).split("-").map(Number);
  const t = new Date(y, m - 1 + 6, 1), last = new Date(t.getFullYear(), t.getMonth() + 1, 0).getDate();
  return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(Math.min(dd, last)).padStart(2, "0")}`;
};

const StudentDialog = ({ open, student, onClose, onSaved }) => {
  const [f, setF] = useState(BLANK);
  const [init, setInit] = useState(null);
  if (open && init !== (student?.id || "new")) { setInit(student?.id || "new"); setF(student ? { ...BLANK, ...student } : BLANK); }
  if (!open && init) setInit(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const setI = (i, k, v) => setF({ ...f, installments: f.installments.map((x, j) => (j === i ? { ...x, [k]: v } : x)) });
  const save = async () => {
    const body = { ...f, fine_per_day: Number(f.fine_per_day || 0), installments: f.installments.filter((i) => Number(i.amount) > 0).map((i) => ({ label: i.label, due_date: i.due_date, amount: Number(i.amount) })) };
    try { student ? await api.put(`/college/students/${student.id}`, body) : await api.post("/college/students", body); toast.success("Student saved"); onSaved(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl" data-testid="student-dialog">
        <DialogHeader><DialogTitle>{student ? "Edit student" : "Add student"}</DialogTitle></DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          {[["name", "Student name"], ["roll_no", "Roll no"], ["course", "Course"], ["batch", "Batch"], ["phone", "Phone"], ["guardian", "Parent / guardian"], ["fine_per_day", "Late fine per day (₹)"]].map(([k, l]) =>
            <div key={k} className="space-y-1"><Label>{l}</Label><Input value={f[k]} onChange={set(k)} data-testid={`student-${k}-input`} /></div>)}
        </div>
        <div className="space-y-2"><Label>Fee installments</Label>
          {f.installments.map((i, j) => <div key={j} className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2">
            <Input value={i.label} onChange={(e) => setI(j, "label", e.target.value)} placeholder="Label" data-testid={`student-inst-label-${j}`} />
            <DateInput value={i.due_date} onChange={(v) => setI(j, "due_date", v)} testid={`student-inst-date-${j}`} />
            <Input type="number" value={i.amount} onChange={(e) => setI(j, "amount", e.target.value)} placeholder="Amount" data-testid={`student-inst-amount-${j}`} />
            <Button size="icon" variant="ghost" onClick={() => setF({ ...f, installments: f.installments.filter((_, k) => k !== j) })} data-testid={`student-inst-remove-${j}`}><Trash2 className="h-4 w-4" /></Button></div>)}
          <Button size="sm" variant="outline" onClick={() => setF({ ...f, installments: [...f.installments, { label: `Term ${f.installments.length + 1}`, due_date: nextDue(f.installments), amount: "" }] })} data-testid="student-inst-add"><Plus className="h-4 w-4 mr-1" />Installment</Button>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={save} disabled={!f.name.trim()} data-testid="student-save-button">Save student</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const Collect = ({ st, onClose, onDone }) => {
  const { settings } = useApp();
  const money = useMoneyLedgers();
  const [f, setF] = useState({ amount: "", fine: "", date: todayIso(), ledger_id: "", note: "" });
  if (st && f.sid !== st.id) setF({ sid: st.id, amount: st.balance, fine: st.fine_due || 0, date: todayIso(), ledger_id: "", note: "" });
  const save = async () => {
    try {
      const { data } = await api.post("/college/fees", { student_id: st.id, date: f.date, amount: Number(f.amount), fine: Number(f.fine || 0), ledger_id: f.ledger_id || money[0]?.id, note: f.note });
      toast.success(`Receipt ${data.receipt_no} saved`);
      const fresh = (await api.get("/college/students")).data.find((x) => x.id === st.id);
      printFeeReceipt(settings, data, fresh); onDone();
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open={!!st} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="fee-dialog">
        <DialogHeader><DialogTitle>Collect fee · {st?.name}</DialogTitle></DialogHeader>
        <div className="text-sm text-slate-600">Balance {inr(st?.balance)} · Late fine due {inr(st?.fine_due)}</div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1"><Label>Fee amount</Label><Input type="number" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} data-testid="fee-amount-input" /></div>
          <div className="space-y-1"><Label>Late fine</Label><Input type="number" value={f.fine} onChange={(e) => setF({ ...f, fine: e.target.value })} data-testid="fee-fine-input" /></div>
          <div className="space-y-1"><Label>Date</Label><DateInput value={f.date} onChange={(v) => setF({ ...f, date: v })} testid="fee-date-input" /></div>
          <div className="space-y-1"><Label>Received in</Label><Pick value={f.ledger_id || money[0]?.id || ""} onChange={(v) => setF({ ...f, ledger_id: v })} data-testid="fee-ledger-select">{money.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</Pick></div>
          <div className="space-y-1 col-span-2"><Label>Note (installment / month)</Label><Input value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} data-testid="fee-note-input" /></div>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={save} disabled={!(Number(f.amount) > 0)} data-testid="fee-save-button"><Printer className="h-4 w-4 mr-1" />Save & print receipt</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default function Students() {
  const { settings, canWrite } = useApp();
  const [rows, load] = useList("/college/students");
  const [fees, loadFees] = useList("/college/fees");
  const [dlg, setDlg] = useState({ open: false, student: null });
  const [pay, setPay] = useState(null);
  const [q, setQ] = useState("");
  const list = (rows || []).filter((s) => !q || `${s.name} ${s.roll_no} ${s.course} ${s.batch}`.toLowerCase().includes(q.toLowerCase()));
  const sum = (k) => (rows || []).reduce((a, s) => a + s[k], 0);
  return (
    <div className="space-y-6" data-testid="students-page">
      <PageHead title="Students & Fees" sub="Student directory, installment fee plans with late fines, and fee receipts.">
        {canWrite && <Button onClick={() => setDlg({ open: true, student: null })} data-testid="student-add-button"><Plus className="h-4 w-4 mr-1" />Add student</Button>}
      </PageHead>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">{[["Students", (rows || []).length, ""], ["Total fees", inr(sum("total_fee"))], ["Collected", inr(sum("paid"))], ["Balance due", inr(sum("balance"))]].map(([l, v]) =>
        <Card key={l} className="!p-4"><div className="text-xs uppercase text-slate-500">{l}</div><div className="num text-xl font-bold" data-testid={`students-kpi-${l.split(" ")[0].toLowerCase()}`}>{v}</div></Card>)}</div>
      <Card className="overflow-x-auto">
        <Input className="mb-4 max-w-xs" placeholder="Search name, roll no, course" value={q} onChange={(e) => setQ(e.target.value)} data-testid="students-search-input" />
        <table className="w-full text-sm"><thead><tr className="text-left"><Th>Student</Th><Th>Course / batch</Th><Th r>Total</Th><Th r>Paid</Th><Th r>Balance</Th><Th r>Fine due</Th><Th>Next due</Th><Th /></tr></thead>
          <tbody>{list.map((s) => { const nx = s.schedule.find((i) => i.due > 0); return (
            <tr key={s.id} className="border-t" data-testid={`student-row-${s.id}`}>
              <Td><div className="font-semibold">{s.name}</div><div className="text-xs text-slate-500">{s.roll_no}</div></Td><Td>{s.course} {s.batch && `· ${s.batch}`}</Td>
              <Td r>{amt(s.total_fee)}</Td><Td r>{amt(s.paid)}</Td><Td r className="font-semibold">{amt(s.balance)}</Td><Td r className={s.fine_due ? "text-red-600" : ""}>{amt(s.fine_due)}</Td>
              <Td>{nx ? <span className={nx.status === "overdue" ? "text-red-600" : ""}>{dmy(nx.due_date)} · {amt(nx.due)}</span> : <span className="text-emerald-700">Fully paid</span>}</Td>
              <Td r>{canWrite && <div className="flex justify-end gap-1"><Button size="sm" variant="outline" onClick={() => setDlg({ open: true, student: s })} data-testid={`student-edit-${s.id}`}>Edit</Button>
                <Button size="sm" disabled={s.balance <= 0} onClick={() => setPay(s)} data-testid={`student-collect-${s.id}`}>Collect fee</Button></div>}</Td></tr>); })}
            {rows && !list.length && <tr><td colSpan={8} className="py-8 text-center text-slate-400">No students yet</td></tr>}</tbody></table>
      </Card>
      <Card className="overflow-x-auto" data-testid="fee-receipts"><div className="font-semibold mb-3">Fee receipts</div>
        <table className="w-full text-sm"><thead><tr className="text-left"><Th>Receipt</Th><Th>Date</Th><Th>Student</Th><Th r>Fee</Th><Th r>Fine</Th><Th r>Total</Th><Th /></tr></thead>
          <tbody>{(fees || []).map((r) => <tr key={r.id} className="border-t" data-testid={`fee-row-${r.receipt_no}`}><Td className="font-mono">{r.receipt_no}</Td><Td>{dmy(r.date)}</Td><Td>{r.student}</Td><Td r>{amt(r.amount)}</Td><Td r>{amt(r.fine)}</Td><Td r>{amt(r.total)}</Td>
            <Td r><Button size="sm" variant="ghost" onClick={() => printFeeReceipt(settings, r, (rows || []).find((s) => s.id === r.student_id))} data-testid={`fee-print-${r.receipt_no}`}><Printer className="h-4 w-4" /></Button></Td></tr>)}</tbody></table>
      </Card>
      <StudentDialog {...dlg} onClose={() => setDlg({ open: false, student: null })} onSaved={() => { setDlg({ open: false, student: null }); load(); }} />
      <Collect st={pay} onClose={() => setPay(null)} onDone={() => { setPay(null); load(); loadFees(); }} />
    </div>
  );
}
