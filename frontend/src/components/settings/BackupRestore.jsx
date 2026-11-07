import { useRef, useState } from "react";
import { toast } from "sonner";
import { Download, Upload } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { todayIso } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const BackupRestore = () => {
  const { loadMeta } = useApp();
  const ref = useRef();
  const [busy, setBusy] = useState(false);

  const backup = async () => {
    try {
      const { data } = await api.get("/backup");
      const url = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `easybooks-backup-${todayIso()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Backup downloaded");
    } catch (e) { toast.error(errMsg(e)); }
  };

  const restore = async (file) => {
    if (!file || !window.confirm("Restore will REPLACE all current ledgers, vouchers and settings with the backup. Continue?")) return;
    setBusy(true);
    try {
      const json = JSON.parse(await file.text());
      await api.post("/restore", { collections: json.collections || {} });
      await loadMeta();
      toast.success("Data restored from backup");
    } catch (e) { toast.error(e instanceof SyntaxError ? "Invalid backup file" : errMsg(e)); } finally { setBusy(false); ref.current.value = ""; }
  };

  return (
    <div className="grid gap-4 md:grid-cols-2" data-testid="backup-settings">
      <div className="rounded-xl border bg-white p-6 space-y-3">
        <h3 className="font-heading font-semibold text-lg">Backup</h3>
        <p className="text-sm text-slate-500">Download all ledgers, vouchers, financial years, settings and the audit trail as one file. Keep it safe.</p>
        <Button className="h-11" onClick={backup} data-testid="download-backup-button"><Download className="h-4 w-4 mr-1" /> Download Backup</Button>
      </div>
      <div className="rounded-xl border bg-white p-6 space-y-3">
        <h3 className="font-heading font-semibold text-lg">Restore</h3>
        <p className="text-sm text-slate-500">Upload a backup file. Current data will be replaced. User accounts are not changed.</p>
        <Input ref={ref} type="file" accept="application/json,.json" disabled={busy} onChange={(e) => restore(e.target.files[0])} data-testid="restore-file-input" className="h-11" />
        <div className="flex items-center gap-2 text-xs text-slate-500"><Upload className="h-3 w-3" /> Restore is recorded in the audit trail.</div>
      </div>
    </div>
  );
};
