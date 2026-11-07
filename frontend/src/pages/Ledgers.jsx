import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Plus, Search, Pencil, FileBarChart, Trash2 } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { amt } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LedgerDialog } from "@/components/LedgerDialog";

const TABS = [
  { id: "all", label: "All", groups: null },
  { id: "customers", label: "Customers", groups: ["sundry_debtors"] },
  { id: "suppliers", label: "Suppliers", groups: ["sundry_creditors"] },
  { id: "cashbank", label: "Cash & Bank", groups: ["cash", "bank"] },
  { id: "income", label: "Income", groups: ["sales", "direct_income", "indirect_income"] },
  { id: "expense", label: "Expenses", groups: ["purchase", "direct_expense", "indirect_expense"] },
  { id: "others", label: "Others", groups: ["duties_taxes", "capital", "loans", "current_liabilities", "fixed_assets", "current_assets"] },
];

export default function Ledgers() {
  const { canWrite } = useApp();
  const [ledgers, setLedgers] = useState([]);
  const [groups, setGroups] = useState([]);
  const [tab, setTab] = useState("all");
  const [q, setQ] = useState("");
  const [dlg, setDlg] = useState({ open: false, ledger: null });

  const load = useCallback(() => api.get("/ledgers").then((r) => setLedgers(r.data)), []);
  useEffect(() => { load(); api.get("/groups").then((r) => setGroups(r.data)); }, [load]);

  const remove = async (l) => {
    if (!window.confirm(`Remove ledger "${l.name}"?`)) return;
    try { await api.delete(`/ledgers/${l.id}`); toast.success("Ledger removed"); load(); } catch (e) { toast.error(errMsg(e)); }
  };

  const t = TABS.find((x) => x.id === tab);
  const rows = ledgers.filter((l) => (!t.groups || t.groups.includes(l.group)) && l.name.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="space-y-6" data-testid="ledgers-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="font-heading text-3xl font-extrabold tracking-tight">Ledgers</h1><p className="text-slate-500 mt-1">{ledgers.length} accounts · balances update automatically from vouchers.</p></div>
        {canWrite && <Button className="h-11 px-5" onClick={() => setDlg({ open: true, ledger: null })} data-testid="create-ledger-button"><Plus className="h-4 w-4 mr-1" /> New Ledger</Button>}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {TABS.map((x) => (
          <button key={x.id} onClick={() => setTab(x.id)} data-testid={`ledger-tab-${x.id}`}
            className={`rounded-full px-4 py-2 text-sm font-medium border transition-colors ${tab === x.id ? "bg-primary text-white border-primary" : "bg-white hover:bg-slate-50"}`}>{x.label}</button>
        ))}
        <div className="relative ml-auto w-full sm:w-72"><Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" /><Input className="h-11 pl-9" placeholder="Search ledgers" value={q} onChange={(e) => setQ(e.target.value)} data-testid="ledger-search-input" /></div>
      </div>
      <div className="rounded-xl border bg-white overflow-x-auto">
        <table className="w-full eb-table min-w-[760px]" data-testid="ledgers-table">
          <thead><tr><th>Ledger</th><th>Group</th><th>GSTIN</th><th className="!text-right">Opening (₹)</th><th className="!text-right">Current Balance (₹)</th><th className="!text-right">Actions</th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={6} className="text-center py-10 text-slate-500">No ledgers found.</td></tr>}
            {rows.map((l) => (
              <tr key={l.id} data-testid={`ledger-row-${l.name.toLowerCase().replace(/\s+/g, "-")}`}>
                <td className="font-medium">{l.name}{l.system_key && <span className="ml-2 text-[10px] uppercase text-slate-400">system</span>}</td>
                <td className="text-slate-600">{l.group_name}</td>
                <td className="font-mono text-xs">{l.gstin || "-"}</td>
                <td className="text-right num">{l.opening_balance ? `${amt(l.opening_balance)} ${l.opening_type}` : "-"}</td>
                <td className={`text-right num font-semibold ${l.balance_type === "Dr" ? "text-slate-900" : "text-indigo-700"}`} data-testid="ledger-balance">{amt(l.balance)} {l.balance_type}</td>
                <td className="text-right whitespace-nowrap">
                  <Link to={`/reports/ledger?ledger=${l.id}`} className="inline-flex p-2 rounded hover:bg-slate-100" title="Statement" data-testid="ledger-statement-link"><FileBarChart className="h-4 w-4" /></Link>
                  {canWrite && <button className="p-2 rounded hover:bg-slate-100" onClick={() => setDlg({ open: true, ledger: l })} title="Edit" data-testid="ledger-edit-button"><Pencil className="h-4 w-4" /></button>}
                  {canWrite && !l.system_key && <button className="p-2 rounded hover:bg-red-50 text-red-600" onClick={() => remove(l)} title="Remove" data-testid="ledger-delete-button"><Trash2 className="h-4 w-4" /></button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <LedgerDialog open={dlg.open} ledger={dlg.ledger} groups={groups} onClose={() => setDlg({ open: false, ledger: null })} onSaved={() => { setDlg({ open: false, ledger: null }); load(); }} />
    </div>
  );
}
