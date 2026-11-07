import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { Download as DlIcon, Monitor, ShieldCheck, WifiOff, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { dmy } from "@/lib/format";
import { PublicShell } from "@/components/PublicShell";

const STEPS = ["Buy the first-year licence on the Buy page. Your key and GST invoice are emailed to you.",
  "Click Download for Windows and open EasyBooksSetup.exe. If Windows says \"Windows protected your PC\", click More info → Run anyway.",
  "It installs in one click (no questions), adds a desktop shortcut and opens Easy Books. Create your admin login.", "Go to Licence, enter your key and click Activate online. The key locks to this one PC.",
  "Every year, buy a renewal key with your existing licence key and click Activate online again."];

export default function DownloadPage() {
  const [d, setD] = useState(null);
  useEffect(() => { axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/shop/download`).then((r) => setD(r.data)).catch(() => setD({ url: null })); }, []);
  return (
    <PublicShell>
      <div className="max-w-5xl mx-auto px-5 py-14 space-y-10" data-testid="download-page">
        <div className="grid gap-8 lg:grid-cols-[1.3fr_1fr] items-center">
          <div>
            <h1 className="font-heading text-4xl sm:text-5xl font-extrabold tracking-tight">Easy Books for Windows</h1>
            <p className="mt-4 text-lg text-slate-600">Standalone offline accounting software like Tally, with no internet needed. All features of Easy Books, and your data stays on your PC.</p>
            <div className="mt-8 flex flex-wrap gap-3">
              {d?.url ? <a href={d.url} download="EasyBooksSetup.exe"><Button className="h-12 px-8 text-base" data-testid="download-exe-button"><DlIcon className="h-5 w-5 mr-2" /> Download for Windows</Button></a>
                : <Button disabled className="h-12 px-8 text-base" data-testid="download-exe-button">Download coming soon</Button>}
              <Link to="/buy"><Button variant="outline" className="h-12 px-8 text-base" data-testid="download-buy-button"><KeyRound className="h-5 w-5 mr-2" /> Buy licence key</Button></Link>
            </div>
            {d?.url && <p className="mt-3 text-sm text-slate-500" data-testid="download-version">Version {d.version}{d.size ? ` · ${d.size}` : ""} · Updated {dmy(d.updated_at)}{d.notes ? ` · ${d.notes}` : ""}</p>}
          </div>
          <div className="grid gap-3">
            {[[WifiOff, "Works fully offline", "Data is stored securely on your own computer"], [ShieldCheck, "Licence protected", "Annual activation key, verified on your PC"], [Monitor, "Windows 10 / 11 (64-bit)", "4 GB RAM, 1 GB free disk space"]].map(([I, t, s]) => (
              <div key={t} className="flex gap-3 rounded-xl border p-4"><I className="h-5 w-5 text-primary mt-0.5" /><div><div className="font-semibold">{t}</div><div className="text-sm text-slate-500">{s}</div></div></div>))}
          </div>
        </div>
        <div className="rounded-2xl border bg-slate-50 p-6">
          <h2 className="font-heading text-xl font-bold">How to install</h2>
          <ol className="mt-4 space-y-2 list-decimal list-inside text-slate-700">{STEPS.map((s) => <li key={s}>{s}</li>)}</ol>
          <p className="mt-4 text-sm text-slate-500">The offline software is a separate product. It does not sync with the online version. Back up regularly from Settings → Backup.</p>
        </div>
      </div>
    </PublicShell>
  );
}
