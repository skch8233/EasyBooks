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
  const [repo, setRepo] = useState("");
  const useGithub = () => {
    const r = repo.trim().replace(/^https?:\/\/github\.com\//i, "").replace(/\.git$|\/+$/g, "");
    if (!/^[\w.-]+\/[\w.-]+$/.test(r)) return toast.error("Enter your GitHub user/repo, e.g. ravi/easybooks");
    setF({ ...f, url: `https://github.com/${r}/releases/latest/download/EasyBooksSetup.exe`, version: "Latest", notes: "Auto-built on GitHub" });
    toast.success("Link filled in. Click Save.");
  };
  return (
    <div className="rounded-xl border bg-white p-6 space-y-3" data-testid="platform-download">
      <h2 className="font-heading text-xl font-bold">Offline .exe download link</h2>
      <p className="text-sm text-slate-500">Built automatically on GitHub (see offline/GITHUB-STEPS.md): type your GitHub user/repo and click "Use latest GitHub release". Or paste any direct link to EasyBooksSetup.exe. It appears on the public /download page.</p>
      <div className="flex flex-wrap gap-2">
        <Input className="h-11 flex-1 min-w-[220px] font-mono" placeholder="GitHub user/repo, e.g. ravi/easybooks" value={repo} onChange={(e) => setRepo(e.target.value)} data-testid="github-repo-input" />
        <Button variant="outline" className="h-11" onClick={useGithub} data-testid="github-latest-button">Use latest GitHub release</Button>
      </div>
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
  const [f, setF] = useState({ plan: "offline_first", name: "", email: "", phone: "", business_name: "", licence_key: "", gstin: "" });
  const [res, setRes] = useState(null);
  const load = useCallback(() => api.get("/platform/offline-licences").then((r) => setRows(r.data)), []);
  useEffect(() => { load(); }, [load]);
  const issue = async () => {
    try { setRes((await api.post("/platform/offline-licences", f)).data); load(); toast.success("Offline licence issued"); } catch (e) { toast.error(errMsg(e)); }
  };
  const act = async (r, what, mid = "") => {
    if (what === "reset-pc" && !window.confirm(`${mid ? `Remove PC ${mid} from` : "Remove all PCs from"} ${r.key} so it can be activated on a new PC? The old PC keeps working until its current expiry.`)) return;
    try { await api.post(`/platform/offline-licences/${r.key}/${what}`, what === "reset-pc" ? { machine_id: mid } : undefined); toast.success(what === "reset-pc" ? "PC lock reset" : `Email sent to ${r.email}`); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  const renewal = f.plan.includes("renewal");
  return (
    <div className="space-y-6">
      <DownloadLink />
      <div className="rounded-xl border bg-white p-6 space-y-3" data-testid="platform-offline-issue">
        <h2 className="font-heading text-xl font-bold">Issue offline licence (cash / bank payment received)</h2>
        <div className="flex flex-wrap gap-2">{[["offline_first", "Single-PC first year"], ["offline_renewal", "Single-PC renewal"], ["offline_multi_first", "Multi-PC first year"], ["offline_multi_renewal", "Multi-PC renewal"]].map(([p, l]) => <button key={p} onClick={() => setF({ ...f, plan: p })} data-testid={`issue-plan-${p}`}
          className={`rounded-full border px-4 py-1.5 text-sm ${f.plan === p ? "bg-primary text-white border-primary" : ""}`}>{l}</button>)}</div>
        <div className="grid gap-2 sm:grid-cols-3">
          {[["name", "Name"], ["email", "Email"], ["phone", "Phone"], renewal ? ["licence_key", "Existing key EB-XXXX-..."] : ["business_name", "Business name"], ["gstin", "Buyer GSTIN (optional)"]].map(([k, l]) => (
            <Input key={k} className={`h-11 ${["licence_key", "gstin"].includes(k) ? "font-mono uppercase" : ""}`} placeholder={l} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`issue-${k}-input`} />))}
          <Button className="h-11" onClick={issue} disabled={!f.name || !f.email || (renewal && !f.licence_key)} data-testid="issue-offline-button">Issue key</Button>
        </div>
        {res && <KeyResult r={res} />}
      </div>
      <div className="rounded-xl border bg-white overflow-x-auto">
        <table className="w-full eb-table min-w-[980px]" data-testid="offline-licences-table">
          <thead><tr><th>Key</th><th>Customer</th><th>Business</th><th>Valid till</th><th>PC (Machine ID)</th><th>Email</th><th></th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={7} className="text-center py-8 text-slate-500">No offline licences yet.</td></tr>}
            {rows.map((r) => <tr key={r.id} data-testid={`offline-row-${r.key}`}><td className="font-mono text-xs font-semibold">{r.key}</td><td>{r.name}<div className="text-xs text-slate-500">{r.email}</div></td><td>{r.business_name}</td>
              <td className="font-mono text-xs">{dmy(r.expires)}</td>
              <td className="font-mono text-xs" data-testid={`offline-pc-${r.key}`}>
                <div className="font-sans font-semibold" data-testid={`offline-pcs-count-${r.key}`}>{r.tier === "multi" ? "Multi-PC" : "Single-PC"} · {r.machines.length}/{r.max_pcs}</div>
                {r.machines.length === 0 && <span className="text-slate-400">Not activated</span>}
                {r.machines.map((m) => <div key={m.id} className="flex items-center gap-1">{m.id}
                  <button className="text-red-600 font-sans px-1" title="Remove this PC" onClick={() => act(r, "reset-pc", m.id)} data-testid={`remove-pc-${r.key}-${m.id}`}>×</button></div>)}
              </td>
              <td className="text-xs" data-testid={`offline-email-${r.key}`}>{r.last_email ? <span className={r.last_email.status === "sent" ? "text-emerald-700" : "text-red-600"}>{r.last_email.status === "sent" ? "Sent" : "Failed"}</span> : "-"}<div className="text-slate-400">{r.last_invoice}</div></td>
              <td className="whitespace-nowrap space-x-1">
                <Button size="sm" variant="outline" disabled={!r.machines.length} onClick={() => act(r, "reset-pc")} data-testid={`reset-pc-${r.key}`}>Reset all PCs</Button>
                <Button size="sm" variant="outline" disabled={!r.last_invoice} onClick={() => act(r, "resend")} data-testid={`resend-email-${r.key}`}>Resend email</Button>
              </td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
};
