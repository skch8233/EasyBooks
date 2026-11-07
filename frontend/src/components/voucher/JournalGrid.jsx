import { Plus, Trash2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { LedgerSelect } from "@/components/LedgerSelect";
import { amt } from "@/lib/format";
import { emptyLine, linesTotals } from "./voucherUtils";

export const JournalGrid = ({ ledgers, lines, setLines }) => {
  const t = linesTotals(lines);
  const set = (i, k, v) => setLines(lines.map((l, j) => (j === i ? { ...l, [k]: v, ...(k === "debit" && v ? { credit: "" } : {}), ...(k === "credit" && v ? { debit: "" } : {}) } : l)));
  const balanced = t.diff === 0 && t.dr > 0;

  return (
    <div className="space-y-3" data-testid="journal-grid">
      <div className="hidden md:grid grid-cols-[1fr_180px_180px_44px] gap-3 text-xs font-semibold uppercase text-slate-500 px-1">
        <span>Ledger / Particulars</span><span className="text-right">Debit (₹)</span><span className="text-right">Credit (₹)</span><span />
      </div>
      {lines.map((l, i) => (
        <div key={i} className="grid grid-cols-2 md:grid-cols-[1fr_180px_180px_44px] gap-3 items-center">
          <div className="col-span-2 md:col-span-1">
            <LedgerSelect ledgers={ledgers} value={l.ledger_id} onChange={(v) => set(i, "ledger_id", v)} testid={`line-${i}-ledger`} />
          </div>
          <Input type="number" min="0" step="0.01" placeholder="Dr" value={l.debit} onChange={(e) => set(i, "debit", e.target.value)} className="h-11 text-right num" data-testid={`line-${i}-debit`} />
          <Input type="number" min="0" step="0.01" placeholder="Cr" value={l.credit} onChange={(e) => set(i, "credit", e.target.value)} className="h-11 text-right num" data-testid={`line-${i}-credit`} />
          <button type="button" disabled={lines.length <= 2} onClick={() => setLines(lines.filter((_, j) => j !== i))} className="h-11 w-11 hidden md:flex items-center justify-center rounded-md text-slate-400 hover:text-red-600 hover:bg-red-50 disabled:opacity-30" data-testid={`line-${i}-remove`}>
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      ))}
      <Button type="button" variant="outline" onClick={() => setLines([...lines, emptyLine()])} data-testid="add-line-button"><Plus className="h-4 w-4 mr-1" /> Add line</Button>
      <div className={`flex flex-wrap items-center justify-end gap-6 rounded-lg px-4 py-3 border ${balanced ? "bg-emerald-50 border-emerald-200" : "bg-amber-50 border-amber-200"}`} data-testid="balance-indicator">
        <span className="text-sm">Total Dr <b className="num ml-1" data-testid="total-debit">{amt(t.dr)}</b></span>
        <span className="text-sm">Total Cr <b className="num ml-1" data-testid="total-credit">{amt(t.cr)}</b></span>
        <span className={`text-sm font-semibold ${balanced ? "text-emerald-700" : "text-amber-700"}`} data-testid="balance-status">
          {balanced ? "Balanced" : `Difference ${amt(Math.abs(t.diff))} ${t.diff > 0 ? "Dr" : "Cr"}`}
        </span>
      </div>
    </div>
  );
};
