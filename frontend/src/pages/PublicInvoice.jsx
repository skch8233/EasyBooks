import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Printer, Download } from "lucide-react";
import axios from "axios";
import { renderInvoice, upiQr, blobToDataUrl } from "@/lib/invoice";
import { Button } from "@/components/ui/button";
import { HannusoftLogo, Copyright } from "@/components/Hannusoft";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/public/invoice`;

export default function PublicInvoice() {
  const { token } = useParams();
  const [html, setHtml] = useState(null);
  const [title, setTitle] = useState("Invoice");
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const { data } = await axios.get(`${API}/${token}`);
        const logo = data.settings.has_logo ? await axios.get(`${API}/${token}/logo`, { responseType: "blob" }).then((r) => blobToDataUrl(r.data)).catch(() => null) : null;
        const qr = await upiQr(data.settings, data.voucher);
        setTitle(`${data.settings.company_name} · Invoice ${data.voucher.voucher_no}`);
        setHtml(renderInvoice({ v: data.voucher, s: data.settings, party: data.party, logo, qr }));
      } catch { setErr("This invoice link is invalid or has been removed."); }
    })();
  }, [token]);

  const print = () => { const f = document.getElementById("inv-frame"); f?.contentWindow?.print(); };

  return (
    <div className="min-h-screen bg-slate-100" data-testid="public-invoice-page">
      <header className="bg-white border-b px-4 py-3 flex flex-wrap items-center gap-3">
        <span className="font-heading font-bold truncate" data-testid="public-invoice-title">{title}</span>
        {html && <div className="ml-auto flex gap-2">
          <Button variant="outline" onClick={print} data-testid="public-invoice-print"><Printer className="h-4 w-4 mr-1" /> Print</Button>
          <Button onClick={print} data-testid="public-invoice-download"><Download className="h-4 w-4 mr-1" /> Save as PDF</Button>
        </div>}
      </header>
      <main className="max-w-4xl mx-auto p-4">
        {err && <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-red-700" data-testid="public-invoice-error">{err}</div>}
        {!html && !err && <div className="p-10 text-center text-slate-500">Loading invoice...</div>}
        {html && <iframe id="inv-frame" title="Invoice" srcDoc={html} className="w-full bg-white rounded-lg shadow-sm border" style={{ height: "1100px" }} data-testid="public-invoice-frame" />}
      </main>
      <footer className="flex flex-col items-center gap-2 py-8"><HannusoftLogo size={26} /><Copyright /></footer>
    </div>
  );
}
