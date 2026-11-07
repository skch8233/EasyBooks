import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const ROLES = { admin: "Admin (full access)", accountant: "Accountant (entries)", viewer: "Viewer (read only)" };

export const UsersSettings = () => {
  const { user: me } = useApp();
  const [users, setUsers] = useState([]);
  const [f, setF] = useState({ name: "", email: "", password: "", role: "accountant" });
  const load = useCallback(() => api.get("/users").then((r) => setUsers(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try { await api.post("/users", f); toast.success("User created"); setF({ name: "", email: "", password: "", role: "accountant" }); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  const update = async (id, body) => { try { await api.put(`/users/${id}`, body); toast.success("User updated"); load(); } catch (e) { toast.error(errMsg(e)); } };

  return (
    <div className="rounded-xl border bg-white p-6 space-y-6" data-testid="users-settings">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr_200px_auto]">
        <Input className="h-11" placeholder="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="new-user-name-input" />
        <Input className="h-11" placeholder="Email" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} data-testid="new-user-email-input" />
        <Input className="h-11" placeholder="Password (min 6)" type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} data-testid="new-user-password-input" />
        <Select value={f.role} onValueChange={(role) => setF({ ...f, role })}>
          <SelectTrigger className="h-11" data-testid="new-user-role-select"><SelectValue /></SelectTrigger>
          <SelectContent>{Object.entries(ROLES).map(([k, l]) => <SelectItem key={k} value={k}>{l}</SelectItem>)}</SelectContent>
        </Select>
        <Button className="h-11" onClick={create} disabled={!f.name || !f.email || !f.password} data-testid="create-user-button">Add User</Button>
      </div>
      <table className="w-full eb-table" data-testid="users-table">
        <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th></tr></thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} data-testid={`user-row-${u.email}`}>
              <td className="font-medium">{u.name}</td><td>{u.email}</td>
              <td>
                <Select value={u.role} onValueChange={(role) => update(u.id, { role })} disabled={u.id === me.id}>
                  <SelectTrigger className="h-9 w-52" data-testid={`user-role-${u.email}`}><SelectValue /></SelectTrigger>
                  <SelectContent>{Object.entries(ROLES).map(([k, l]) => <SelectItem key={k} value={k}>{l}</SelectItem>)}</SelectContent>
                </Select>
              </td>
              <td>{u.id === me.id ? <span className="text-xs text-slate-500">You</span> : (
                <Button size="sm" variant="outline" onClick={() => update(u.id, { active: !u.active })} data-testid={`user-toggle-${u.email}`}>{u.active ? "Disable" : "Enable"}</Button>)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
