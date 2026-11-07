import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LedgerSelect } from "@/components/LedgerSelect";
import { SIMPLE } from "./voucherUtils";

export const SimpleForm = ({ type, ledgers, value, onChange }) => {
  const cfg = SIMPLE[type];
  return (
    <div className="grid gap-5 md:grid-cols-[1fr_1fr_220px]" data-testid="simple-voucher-form">
      <div className="space-y-2">
        <Label>{cfg.a}</Label>
        <LedgerSelect ledgers={ledgers} groups={cfg.aGroups} value={value.a} onChange={(a) => onChange({ ...value, a })} testid="simple-ledger-a" placeholder="Select cash / bank" />
      </div>
      <div className="space-y-2">
        <Label>{cfg.b}</Label>
        <LedgerSelect ledgers={ledgers.filter((l) => l.id !== value.a)} groups={cfg.bGroups} value={value.b} onChange={(b) => onChange({ ...value, b })} testid="simple-ledger-b" />
      </div>
      <div className="space-y-2">
        <Label>Amount (₹)</Label>
        <Input type="number" min="0" step="0.01" value={value.amount} onChange={(e) => onChange({ ...value, amount: e.target.value })} className="h-11 text-right num text-lg" data-testid="simple-amount-input" />
      </div>
    </div>
  );
};
