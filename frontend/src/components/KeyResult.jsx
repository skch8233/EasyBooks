import { useState } from "react";
import { toast } from "sonner";
import { Copy, Download, KeyRound, Mail, MonitorCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { dmy } from "@/lib/format";
import { downloadText } from "@/lib/offline";

const EmailNote = ({ r }) => r.email_status && (
  <div className={`flex items-center gap-2 text-sm ${r.email_status === "sent" ? "text-emerald-800" : "text-amber-800"}`} data-testid="result-email-status">
    <Mail className="h-4 w-4" />
    {r.email_status === "sent" ? `Licence key and GST invoice ${r.invoice_no} emailed to ${r.email}.` : `Email could not be sent right now (invoice ${r.invoice_no}). Save the key below; Hannusoft can resend it.`}
  </div>
);

const CodeBox = ({ r, copy }) => {
  const [show, setShow] = useState(false);
  return (
    <>
      <div>
        <div className="text-xs uppercase text-slate-500 mb-1">Activation code for PC {r.machine_id} (paste in the offline app → Licence)</div>
        <div className={`rounded-md bg-white border p-3 font-mono text-xs break-all ${show ? "" : "max-h-14 overflow-hidden"}`} data-testid="result-activation-code">{r.code}</div>
        <button className="text-xs text-primary mt-1" onClick={() => setShow(!show)} data-testid="toggle-activation-code">{show ? "Show less" : "Show full code"}</button>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => copy(r.code)} data-testid="copy-activation-code"><Copy className="h-4 w-4 mr-1" /> Copy activation code</Button>
        <Button variant="outline" onClick={() => downloadText(`EasyBooks-${r.key}.lic`, r.code)} data-testid="download-licence-file"><Download className="h-4 w-4 mr-1" /> Download licence file</Button>
      </div>
    </>
  );
};

export const KeyResult = ({ r }) => {
  const copy = (t) => navigator.clipboard?.writeText(t).then(() => toast.success("Copied"));
  return (
    <div className="rounded-xl border-2 border-emerald-300 bg-emerald-50 p-6 space-y-4" data-testid="key-result">
      <div className="flex items-center gap-2 text-emerald-800 font-heading text-xl font-bold"><KeyRound className="h-5 w-5" /> Your licence is ready</div>
      <EmailNote r={r} />
      <div className="grid gap-2 sm:grid-cols-3 text-sm">
        <div><div className="text-xs uppercase text-slate-500">Licence key</div><div className="font-mono font-semibold" data-testid="result-licence-key">{r.key}</div></div>
        <div><div className="text-xs uppercase text-slate-500">Valid till</div><div className="font-mono font-semibold" data-testid="result-expires">{dmy(r.expires)}</div></div>
        <div><div className="text-xs uppercase text-slate-500">Registered to</div><div className="font-semibold">{r.business_name}</div></div>
      </div>
      {r.code ? <CodeBox r={r} copy={copy} /> : (
        <div className="rounded-md bg-white border p-4 text-sm space-y-1" data-testid="result-activate-steps">
          <div className="font-semibold flex items-center gap-2"><MonitorCheck className="h-4 w-4" /> Works on one computer</div>
          <p>Install the software on the PC you will use, open <b>Licence</b>, enter this key and click <b>Activate online</b>. The key then locks to that PC.</p>
          <p className="text-slate-500">No internet on that PC? Use the <a href="/activate" className="text-primary underline">activation page</a> with the Machine ID shown on the Licence screen.</p>
        </div>
      )}
      <Button variant="outline" onClick={() => copy(r.key)} data-testid="copy-licence-key"><Copy className="h-4 w-4 mr-1" /> Copy key</Button>
      <p className="text-xs text-slate-600">Keep your licence key safe: you need it for next year's renewal.</p>
    </div>
  );
};
