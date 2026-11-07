import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import QRCode from "qrcode";
import { Smartphone, CheckCircle2 } from "lucide-react";
import { amt, dmy } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { HannusoftLogo, Copyright } from "@/components/Hannusoft";

export default function PayPage() {
  const { token } = useParams();
  const [d, setD] = useState(null);
  const [qr, setQr] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/public/pay/${token}`).then((r) => setD(r.data)).catch(() => setErr("This payment link is invalid or has expired."));
  }, [token]);
  const amount = d ? (d.overdue_amount || d.outstanding) : 0;
  const upi = d?.company.upi_id ? `upi://pay?pa=${encodeURIComponent(d.company.upi_id)}&pn=${encodeURIComponent(d.company.company_name)}&am=${amount.toFixed(2)}&cu=INR&tn=${encodeURIComponent(`Payment from ${d.customer}`)}` : null;
  useEffect(() => { if (upi && amount > 0) QRCode.toDataURL(upi, { width: 220, margin: 1 }).then(setQr); }, [upi, amount]);

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col items-center px-4 py-8" data-testid="pay-page">
      <div className="w-full max-w-md rounded-2xl bg-white border shadow-sm overflow-hidden">
        {err && <div className="p-8 text-center text-red-700" data-testid="pay-error">{err}</div>}
        {!d && !err && <div className="p-10 text-center text-slate-500">Loading...</div>}
        {d && (
          <>
            <div className="bg-[#0F172A] text-white p-6">
              <div className="text-xs uppercase tracking-widest text-slate-400">Payment request from</div>
              <div className="font-heading text-2xl font-bold mt-1" data-testid="pay-company">{d.company.company_name}</div>
              {d.company.gstin && <div className="text-xs text-slate-400 mt-1">GSTIN {d.company.gstin}</div>}
            </div>
            <div className="p-6 space-y-5">
              <div><div className="text-sm text-slate-500">Dear {d.customer},</div>
                {amount > 0 ? <><div className="text-sm text-slate-500 mt-1">{d.overdue_amount > 0 ? "Amount overdue" : "Amount due"}</div>
                  <div className="num text-4xl font-semibold" data-testid="pay-amount">₹{amt(amount)}</div></>
                  : <div className="flex items-center gap-2 mt-2 text-emerald-700 font-semibold" data-testid="pay-cleared"><CheckCircle2 className="h-5 w-5" /> No dues pending. Thank you!</div>}</div>
              {amount > 0 && upi && (
                <div className="space-y-3 text-center">
                  <Button asChild className="w-full h-13 py-3.5 text-base bg-emerald-600 hover:bg-emerald-700"><a href={upi} data-testid="pay-upi-link"><Smartphone className="h-5 w-5 mr-2" /> Pay ₹{amt(amount)} with UPI app</a></Button>
                  {qr && <img src={qr} alt="UPI QR code" className="mx-auto w-48 h-48" data-testid="pay-qr" />}
                  <div className="text-xs text-slate-500">Scan with any UPI app (GPay, PhonePe, Paytm, BHIM)<br />UPI ID: <span className="font-mono">{d.company.upi_id}</span></div>
                </div>
              )}
              {amount > 0 && !upi && d.company.bank_account && (
                <div className="rounded-lg border p-4 text-sm" data-testid="pay-bank"><b>Bank transfer</b><br />{d.company.bank_name}<br />A/c {d.company.bank_account} · IFSC {d.company.bank_ifsc}</div>)}
              {d.bills.length > 0 && (
                <table className="w-full text-sm" data-testid="pay-bills">
                  <thead><tr className="text-left text-xs uppercase text-slate-500"><th className="py-2">Bill</th><th>Due</th><th className="text-right">Pending</th></tr></thead>
                  <tbody>{d.bills.map((b, i) => <tr key={i} className="border-t"><td className="py-2 font-mono text-xs">{b.voucher_no}</td><td className={`text-xs ${b.overdue ? "text-red-600" : ""}`}>{b.due_date ? dmy(b.due_date) : "-"}</td><td className="text-right num">₹{amt(b.pending)}</td></tr>)}</tbody>
                </table>
              )}
              {d.company.phone && <div className="text-xs text-slate-500">Questions? Call {d.company.phone}</div>}
            </div>
          </>
        )}
      </div>
      <footer className="flex flex-col items-center gap-2 py-8"><HannusoftLogo size={24} /><Copyright /></footer>
    </div>
  );
}
