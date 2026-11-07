import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Crown, KeyRound, Loader2, MonitorX, ShieldCheck } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { amt, dmy } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { SubscriptionStatus } from "@/components/billing/SubscriptionStatus";
import { LicenceTester } from "@/components/billing/LicenceTester";

const loadScript = () => new Promise((res) => {
  if (window.Razorpay) return res(true);
  const s = document.createElement("script");
  s.src = "https://checkout.razorpay.com/v1/checkout.js";
  s.onload = () => res(true);
  s.onerror = () => res(false);
  document.body.appendChild(s);
});

const PlanCard = ({ p, current, onPay, busy, enabled }) => (
  <div className={`rounded-xl border bg-white p-6 flex flex-col gap-4 ${current ? "ring-2 ring-emerald-500" : ""}`} data-testid={`plan-card-${p.key}`}>
    <div className="flex items-center justify-between"><h3 className="font-heading text-xl font-bold">{p.name}</h3>{p.key === "pro" && <Crown className="h-5 w-5 text-amber-500" />}</div>
    <div className="text-sm text-slate-600">{p.users_label}</div>
    <div><span className="num text-3xl font-semibold">₹{amt(p.price).replace(".00", "")}</span><span className="text-slate-500"> + 18% GST / year</span></div>
    <div className="text-sm text-slate-600 num" data-testid={`plan-total-${p.key}`}>GST ₹{amt(p.gst)} · Total ₹{amt(p.total)}</div>
    <ul className="text-sm space-y-1.5 text-slate-700">
      {["All vouchers, ledgers & reports", "GSTR-1 & GSTR-3B summaries", "Branded invoices with UPI QR", `Up to ${p.max_users} users`].map((t) => <li key={t} className="flex gap-2"><Check className="h-4 w-4 text-emerald-600" />{t}</li>)}
    </ul>
    <Button className="mt-auto h-12" disabled={busy || !enabled} onClick={() => onPay(p.key)} data-testid={`pay-${p.key}-button`}>
      {busy ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}{current ? "Renew for 1 year" : "Pay with UPI / Card"}
    </Button>
  </div>
);

export default function Subscription() {
  const { biz, loadBiz, user } = useApp();
  const [plans, setPlans] = useState(null);
  const [lics, setLics] = useState([]);
  const [pays, setPays] = useState([]);
  const [busy, setBusy] = useState(false);
  const load = () => { api.get("/billing/plans").then((r) => setPlans(r.data)); api.get("/licences").then((r) => setLics(r.data)); api.get("/billing/payments").then((r) => setPays(r.data)); loadBiz(); };
  useEffect(load, []); // eslint-disable-line react-hooks/exhaustive-deps

  const pay = async (plan) => {
    setBusy(true);
    try {
      if (!(await loadScript())) throw new Error("Could not load Razorpay checkout. Check your internet connection.");
      const { data: o } = await api.post("/billing/order", { plan });
      const rzp = new window.Razorpay({
        key: o.key_id, amount: o.amount, currency: "INR", order_id: o.order_id, name: "Easy Books",
        description: `${o.plan.name} - 1 year`, prefill: { name: user.name, email: o.email },
        theme: { color: "#1E3A8A" },
        handler: async (res) => {
          try { const { data } = await api.post("/billing/verify", res); toast.success(`Payment successful. Licence key: ${data.licence_key || "issued"}`); load(); } catch (e) { toast.error(errMsg(e)); }
        },
        modal: { ondismiss: () => setBusy(false) },
      });
      rzp.on("payment.failed", (r) => toast.error(r.error?.description || "Payment failed"));
      rzp.open();
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };

  const unbind = async (l, m) => {
    try { await api.post(`/licences/${l.id}/deactivate-device`, { machine_id: m }); toast.success("Device deactivated"); load(); } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div className="space-y-8" data-testid="subscription-page">
      <div><h1 className="font-heading text-3xl font-extrabold tracking-tight">Subscription & Licence</h1><p className="text-slate-500 mt-1">Annual plans for the online app and the offline version.</p></div>
      <SubscriptionStatus biz={biz} />
      {plans && !plans.payments_enabled && <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800" data-testid="payments-not-configured">Online payments are not configured yet. Contact support to activate your plan.</div>}
      <div className="grid gap-6 md:grid-cols-2">{plans?.plans.map((p) => <PlanCard key={p.key} p={p} current={biz?.status === "active" && biz?.plan === p.key} onPay={pay} busy={busy} enabled={plans.payments_enabled} />)}</div>

      <div className="space-y-3">
        <h2 className="font-heading text-xl font-bold flex items-center gap-2"><KeyRound className="h-5 w-5" /> Offline licence keys</h2>
        <div className="rounded-xl border bg-white overflow-x-auto">
          <table className="w-full eb-table min-w-[720px]" data-testid="licences-table">
            <thead><tr><th>Licence key</th><th>Plan</th><th>Valid till</th><th>Status</th><th>Activated devices</th></tr></thead>
            <tbody>
              {lics.length === 0 && <tr><td colSpan={5} className="text-center py-8 text-slate-500">A licence key is issued automatically when you buy an annual plan.</td></tr>}
              {lics.map((l) => (
                <tr key={l.id} data-testid={`licence-row-${l.key}`}>
                  <td className="font-mono font-semibold">{l.key}</td><td className="capitalize">{l.plan}</td>
                  <td className="font-mono text-xs">{dmy(l.expires_at)}</td>
                  <td>{l.state === "active" ? <span className={`rounded px-2 py-0.5 text-xs font-semibold ${l.alert ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-700"}`} data-testid="licence-state">{l.alert ? `Expires in ${l.days_left} days` : "Active"}</span>
                    : <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700 capitalize" data-testid="licence-state">{l.state}</span>}</td>
                  <td>
                    <div className="text-xs text-slate-500 mb-1">{l.activations.length} / {l.max_devices}</div>
                    {l.activations.map((a) => (
                      <div key={a.machine_id} className="flex items-center gap-2 text-sm">{a.device_name} <span className="font-mono text-xs text-slate-400">{a.machine_id}</span>
                        <button className="text-red-600 p-1 rounded hover:bg-red-50" onClick={() => unbind(l, a.machine_id)} title="Deactivate" data-testid={`deactivate-device-${a.machine_id}`}><MonitorX className="h-4 w-4" /></button></div>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <LicenceTester onDone={load} />
      {pays.length > 0 && (
        <div className="space-y-3">
          <h2 className="font-heading text-xl font-bold flex items-center gap-2"><ShieldCheck className="h-5 w-5" /> Payment history</h2>
          <div className="rounded-xl border bg-white overflow-x-auto">
            <table className="w-full eb-table" data-testid="payments-table">
              <thead><tr><th>Date</th><th>Plan</th><th className="!text-right">Amount (₹)</th><th>Status</th><th>Payment ID</th></tr></thead>
              <tbody>{pays.map((p) => <tr key={p.id}><td className="font-mono text-xs">{dmy(p.created_at)}</td><td className="capitalize">{p.plan}</td><td className="text-right num">{amt(p.amount)}</td><td className="capitalize">{p.status}</td><td className="font-mono text-xs">{p.payment_id || "-"}</td></tr>)}</tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
