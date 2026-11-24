import { useState } from "react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { amt, dmy, inr } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { DateInput } from "@/components/DateInput";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, PageHead, Td, Th, sel, todayIso, useList, useMoneyLedgers, Pick, monthOptions } from "@/components/industry/common";

const SECTIONS = ["194J", "194C", "194H", "194I", "194Q", "Other"];

export default function Tds() {
  const { canWrite } = useApp();
  const [rows, load] = useList("/tds/receipts");
  const [ledgers] = useList("/ledgers");
  const money = useMoneyLedgers();
  const [f, setF] = useState({ party_ledger_id: "", ledger_id: "", date: todayIso(), gross: "", base: "", rate: 10, section: "194J", reference: "" });
  const tds = Math.round(Number(f.base || f.gross || 0) * Number(f.rate || 0)) / 100;
  const parties = (ledgers || []).filter((l) => l.group === "sundry_debtors");
  const save = async () => {
    try { const { data } = await api.post("/tds/receipts", { ...f, ledger_id: f.ledger_id || money[0]?.id, gross: Number(f.gross), tds, tds_base: Number(f.base || f.gross) }); toast.success(`Receipt ${data.voucher_no} saved`); setF({ ...f, gross: "", base: "", reference: "" }); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  const total = (rows || []).reduce((a, r) => a + r.tds, 0);
  return (
    <div className="space-y-6" data-testid="tds-page">
      <PageHead title="Payment Receipts & TDS" sub="Record client payments with TDS deducted. TDS goes to the TDS Receivable ledger." />
      {canWrite && <Card className="grid gap-3 md:grid-cols-9 items-end" data-testid="tds-form">
        <div className="space-y-1 md:col-span-2"><Label className="text-xs">Client</Label><Pick value={f.party_ledger_id} onChange={(v) => setF({ ...f, party_ledger_id: v })} data-testid="tds-party-select"><option value="">Select client</option>{parties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Pick></div>
        <div className="space-y-1"><Label className="text-xs">Bill amount settled</Label><Input className="h-10" type="number" value={f.gross} onChange={(e) => setF({ ...f, gross: e.target.value })} data-testid="tds-gross-input" /></div>
        <div className="space-y-1"><Label className="text-xs whitespace-nowrap">TDS on (blank = bill)</Label><Input className="h-10" type="number" value={f.base} placeholder={f.gross ? `= ${f.gross}` : "Value before GST"} onChange={(e) => setF({ ...f, base: e.target.value })} data-testid="tds-base-input" /></div>
        <div className="space-y-1"><Label className="text-xs">TDS %</Label><Input className="h-10" type="number" value={f.rate} onChange={(e) => setF({ ...f, rate: e.target.value })} data-testid="tds-rate-input" /></div>
        <div className="space-y-1"><Label className="text-xs">Section</Label><Pick value={f.section} onChange={(v) => setF({ ...f, section: v })} data-testid="tds-section-select">{SECTIONS.map((s) => <option key={s}>{s}</option>)}</Pick></div>
        <div className="space-y-1"><Label className="text-xs">Received in</Label><Pick value={f.ledger_id || money[0]?.id || ""} onChange={(v) => setF({ ...f, ledger_id: v })} data-testid="tds-ledger-select">{money.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</Pick></div>
        <div className="space-y-1"><Label className="text-xs">Date</Label><DateInput value={f.date} onChange={(v) => setF({ ...f, date: v })} testid="tds-date-input" /></div>
        <Button onClick={save} disabled={!f.party_ledger_id || !(Number(f.gross) > 0)} data-testid="tds-save-button">Save</Button>
        <div className="md:col-span-9 text-sm text-slate-600" data-testid="tds-preview">TDS {inr(tds)} · Net received {inr(Number(f.gross || 0) - tds)}</div>
      </Card>}
      <Card className="overflow-x-auto"><div className="flex justify-between mb-3"><div className="font-semibold">TDS register</div><div className="num font-semibold" data-testid="tds-total">TDS receivable {inr(total)}</div></div>
        <table className="w-full text-sm" data-testid="tds-table"><thead><tr className="text-left"><Th>Date</Th><Th>Client</Th><Th>Section</Th><Th r>Bill amount</Th><Th r>TDS</Th><Th r>Received</Th><Th>Voucher</Th></tr></thead>
          <tbody>{(rows || []).map((r) => <tr key={r.id} className="border-t" data-testid={`tds-row-${r.id}`}><Td>{dmy(r.date)}</Td><Td>{r.party}</Td><Td>{r.section}</Td><Td r>{amt(r.gross)}</Td><Td r>{amt(r.tds)}</Td><Td r>{amt(r.net)}</Td><Td className="font-mono text-xs">{r.voucher_no}</Td></tr>)}</tbody></table></Card>
    </div>
  );
}
