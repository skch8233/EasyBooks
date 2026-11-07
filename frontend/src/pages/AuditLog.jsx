import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { dmyTime } from "@/lib/format";

export default function AuditLog() {
  const [logs, setLogs] = useState([]);
  const [entity, setEntity] = useState("");
  useEffect(() => { api.get("/audit-logs", { params: entity ? { entity } : {} }).then((r) => setLogs(r.data)); }, [entity]);

  return (
    <div className="space-y-6" data-testid="audit-page">
      <div><h1 className="font-heading text-3xl font-extrabold tracking-tight">Audit Trail</h1><p className="text-slate-500 mt-1">Every create, edit, cancel, backup and restore is recorded. Financial records are never deleted.</p></div>
      <div className="flex flex-wrap gap-2">
        {[["", "All"], ["voucher", "Vouchers"], ["ledger", "Ledgers"], ["user", "Users"], ["financial_year", "Financial Years"], ["settings", "Settings"], ["system", "Backup / Restore"]].map(([k, l]) => (
          <button key={k} onClick={() => setEntity(k)} data-testid={`audit-filter-${k || "all"}`}
            className={`rounded-full border px-4 py-2 text-sm font-medium ${entity === k ? "bg-primary text-white border-primary" : "bg-white hover:bg-slate-50"}`}>{l}</button>
        ))}
      </div>
      <div className="rounded-xl border bg-white overflow-x-auto">
        <table className="w-full eb-table min-w-[700px]" data-testid="audit-table">
          <thead><tr><th>When</th><th>Entity</th><th>Action</th><th>User</th><th>Note</th></tr></thead>
          <tbody>
            {logs.length === 0 && <tr><td colSpan={5} className="text-center py-10 text-slate-500">No audit entries.</td></tr>}
            {logs.map((l) => (
              <tr key={l.id}>
                <td className="font-mono text-xs">{dmyTime(l.timestamp)}</td>
                <td className="capitalize">{l.entity.replace("_", " ")}</td>
                <td><span className={`rounded px-2 py-0.5 text-xs font-semibold ${l.action === "cancel" ? "bg-red-100 text-red-700" : l.action === "update" ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>{l.action}</span></td>
                <td>{l.user_name} <span className="text-xs text-slate-500">{l.user_email}</span></td>
                <td className="text-slate-600">{l.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
