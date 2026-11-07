import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { dmy } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { KeyResult } from "@/components/KeyResult";

const DownloadLink = () => {
  const [f, setF] = useState({ url: "", version: "1.0.0", size: "", notes: "" });
  useEffect(() => { api.get("/shop/download").then((r) => r.data.url && setF({ url: r.data.url, version: r.data.version || "", size: r.data.size || "", notes: r.data.notes || "" })); }, []);
  const save = async () => { try { await api.put("/platform/download", f); toast.success("Download link saved"); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <div className="rounded-xl border bg-white p-6 space-y-3" data-testid="platform-download">
      <h2 className="font-heading text-xl font-bold">Offline .exe download link</h2>
      <p className="text-sm text-slate-500">Upload EasyBooksSetup.exe to GitHub Releases, Google Drive or any file host, then paste the direct link. It appears on the public /download page.</p>
      <div className="grid gap-2 sm:grid-cols-[2fr_100px_110px_1fr_auto]">
        <Input className="h-11" placeholder="https://..." value={f.url} onChange={(e) => setF({ ...f, url: e.target.value })} data-testid="download-url-input" />
        <Input className="h-11" placeholder="Version" value={f.version} onChange={(e) => setF({ ...f, version: e.target.value })} data-testid="download-version-input" />
        <Input className="h-11" placeholder="Size" value={f.size} onChange={(e) => setF({ ...f, size: e.target.value })} data-testid="download-size-input" />
        <Input className="h-11" placeholder="Notes" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} data-testid="download-notes-input" />
        <Button className="h-11" onClick={save} data-testid="download-save-button">Save</Button>
      </div>
    </div>
  );
};

export const OfflineLicencesAdmin = () => {
  const [rows, setRows] = useState([]);
  const [f, setF] = useState({ plan: "offline_first", name: "", email: "", phone: "", business_name: "", licence_key: "" });
  const [res, setRes] = useState(null);
  const load = useCallback(() => api.get("/platform/offline-licences").then((r) => setRows(r.data)), []);
  useEffect(() => { load(); }, [load]);
  const issue = async () => {
    try { setRes((await api.post("/platform/offline-licences", f)).data); load(); toast.success("Offline licence issued"); } catch (e) { toast.error(errMsg(e)); }
  };
  const renewal = f.plan === "offline_renewal";
  return (
    <div className="space-y-6">
      <DownloadLink />
      <div className="rounded-xl border bg-white p-6 space-y-3" data-testid="platform-offline-issue">
        <h2 className="font-heading text-xl font-bold">Issue offline licence (cash / bank payment received)</h2>
        <div className="flex gap-2">{["offline_first", "offline_renewal"].map((p) => <button key={p} onClick={() => setF({ ...f, plan: p })} data-testid={`issue-plan-${p}`}
          className={`rounded-full border px-4 py-1.5 text-sm ${f.plan === p ? "bg-primary text-white border-primary" : ""}`}>{p === "offline_first" ? "First year" : "Renewal"}</button>)}</div>
        <div className="grid gap-2 sm:grid-cols-3">
          {[["name", "Name"], ["email", "Email"], ["phone", "Phone"], renewal ? ["licence_key", "Existing key EB-XXXX-..."] : ["business_name", "Business name"]].map(([k, l]) => (
            <Input key={k} className={`h-11 ${k === "licence_key" ? "font-mono uppercase" : ""}`} placeholder={l} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`issue-${k}-input`} />))}
          <Button className="h-11" onClick={issue} disabled={!f.name || !f.email || (renewal && !f.licence_key)} data-testid="issue-offline-button">Issue key</Button>
        </div>
        {res && <KeyResult r={res} />}
      </div>
      <div className="rounded-xl border bg-white overflow-x-auto">
        <table className="w-full eb-table min-w-[760px]" data-testid="offline-licences-table">
          <thead><tr><th>Key</th><th>Customer</th><th>Business</th><th>Valid till</th><th>Issued</th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={5} className="text-center py-8 text-slate-500">No offline licences yet.</td></tr>}
            {rows.map((r) => <tr key={r.id}><td className="font-mono text-xs font-semibold">{r.key}</td><td>{r.name}<div className="text-xs text-slate-500">{r.email}</div></td><td>{r.business_name}</td>
              <td className="font-mono text-xs">{dmy(r.expires)}</td><td className="font-mono text-xs">{dmy(r.created_at)}</td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
};
