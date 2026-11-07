import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { toast } from "sonner";
import { useApp } from "@/context/AppContext";
import { OfflineLicencesAdmin } from "@/components/OfflineLicencesAdmin";
import { api, errMsg } from "@/lib/api";
import { dmy } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const Row = ({ b, onDone }) => {
  const [plan, setPlan] = useState(b.plan === "pro" ? "pro" : "basic");
  const [days, setDays] = useState(365);
  const extend = async () => {
    try { const { data } = await api.post(`/platform/businesses/${b.id}/extend`, { plan, days: Number(days) }); toast.success(`Extended. Licence ${data.licence_key}`); onDone(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <tr data-testid={`business-row-${b.id}`}>
      <td className="font-medium">{b.name}<div className="text-xs text-slate-500">{b.owner_email}</div></td>
      <td className="capitalize">{b.status}</td><td className="capitalize">{b.plan}</td>
      <td className="font-mono text-xs">{dmy(b.ends_at)}</td><td>{b.users}</td>
      <td>
        <div className="flex gap-2 items-center">
          <Select value={plan} onValueChange={setPlan}><SelectTrigger className="h-9 w-28" data-testid={`extend-plan-${b.id}`}><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="basic">Basic</SelectItem><SelectItem value="pro">Pro</SelectItem></SelectContent></Select>
          <Input className="h-9 w-20 num" type="number" value={days} onChange={(e) => setDays(e.target.value)} data-testid={`extend-days-${b.id}`} />
          <Button size="sm" onClick={extend} data-testid={`extend-button-${b.id}`}>Extend + key</Button>
        </div>
      </td>
    </tr>
  );
};

export default function Platform() {
  const { user } = useApp();
  const [rows, setRows] = useState([]);
  const load = useCallback(() => api.get("/platform/businesses").then((r) => setRows(r.data)).catch((e) => toast.error(errMsg(e))), []);
  useEffect(() => { if (user?.is_superadmin) load(); }, [load, user]);
  if (!user?.is_superadmin) return <Navigate to="/" replace />;
  return (
    <div className="space-y-6" data-testid="platform-page">
      <div><h1 className="font-heading text-3xl font-extrabold tracking-tight">Platform Admin</h1><p className="text-slate-500 mt-1">All trader businesses. Extend plans manually (e.g. cash/UPI payments received offline) and issue offline licence keys.</p></div>
      <div className="rounded-xl border bg-white overflow-x-auto">
        <table className="w-full eb-table min-w-[900px]" data-testid="businesses-table">
          <thead><tr><th>Business</th><th>Status</th><th>Plan</th><th>Valid till</th><th>Users</th><th>Extend</th></tr></thead>
          <tbody>{rows.map((b) => <Row key={b.id} b={b} onDone={load} />)}</tbody>
        </table>
      </div>
      <OfflineLicencesAdmin />
    </div>
  );
}
