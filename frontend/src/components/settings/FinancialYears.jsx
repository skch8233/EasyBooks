import { useState } from "react";
import { toast } from "sonner";
import { Lock, Unlock, Star } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { dmy } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const FinancialYears = () => {
  const { fys, loadMeta, isAdmin } = useApp();
  const [year, setYear] = useState(String((fys[0] ? Number(fys[0].start_date.slice(0, 4)) : new Date().getFullYear()) + 1));
  const act = async (fn, msg) => { try { await fn(); await loadMeta(); toast.success(msg); } catch (e) { toast.error(errMsg(e)); } };

  return (
    <div className="rounded-xl border bg-white p-6 space-y-5" data-testid="fy-settings">
      {isAdmin && (
        <div className="flex flex-wrap items-end gap-2">
          <div><div className="text-xs font-semibold text-slate-500 mb-1">Start year (April)</div><Input className="h-11 w-32 font-mono" type="number" value={year} onChange={(e) => setYear(e.target.value)} data-testid="fy-start-year-input" /></div>
          <Button className="h-11" onClick={() => act(() => api.post("/financial-years", { start_year: Number(year) }), "Financial year created")} data-testid="create-fy-button">Create FY {year}-{String(Number(year) + 1).slice(-2)}</Button>
        </div>
      )}
      <table className="w-full eb-table" data-testid="fy-table">
        <thead><tr><th>Year</th><th>Period</th><th>Status</th>{isAdmin && <th className="!text-right">Actions</th>}</tr></thead>
        <tbody>
          {fys.map((f) => (
            <tr key={f.id} data-testid={`fy-row-${f.name}`}>
              <td className="font-mono font-semibold">FY {f.name}</td>
              <td className="font-mono text-xs">{dmy(f.start_date)} to {dmy(f.end_date)}</td>
              <td className="space-x-2">{f.is_active && <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-700">Default</span>}
                {f.locked ? <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">Locked</span> : <span className="rounded bg-slate-100 px-2 py-0.5 text-xs">Open</span>}</td>
              {isAdmin && <td className="text-right whitespace-nowrap space-x-2">
                {!f.is_active && <Button size="sm" variant="outline" onClick={() => act(() => api.put(`/financial-years/${f.id}`, { is_active: true }), "Default year changed")} data-testid={`fy-activate-${f.name}`}><Star className="h-3 w-3 mr-1" /> Set default</Button>}
                <Button size="sm" variant="outline" onClick={() => act(() => api.put(`/financial-years/${f.id}`, { locked: !f.locked }), f.locked ? "Year unlocked" : "Year locked")} data-testid={`fy-lock-${f.name}`}>
                  {f.locked ? <><Unlock className="h-3 w-3 mr-1" /> Unlock</> : <><Lock className="h-3 w-3 mr-1" /> Lock</>}</Button>
              </td>}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-slate-500">Locked years cannot receive new, edited or cancelled vouchers. Balances carry forward automatically.</p>
    </div>
  );
};
