import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Check, Monitor, Cloud, RefreshCw, Loader2 } from "lucide-react";
import { amt } from "@/lib/format";
import { errMsg } from "@/lib/api";
import { loadRazorpay } from "@/lib/offline";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { KeyResult } from "@/components/KeyResult";
import { PublicShell } from "@/components/PublicShell";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const price = (p) => `₹${amt(p.price).replace(".00", "")}`;

const OfflineForm = ({ plan, enabled, onDone }) => {
  const [f, setF] = useState({ name: "", email: "", phone: "", business_name: "", licence_key: "", gstin: "" });
  const [busy, setBusy] = useState(false);
  const renewal = plan.key === "offline_renewal";
  const pay = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (!(await loadRazorpay())) throw new Error("Could not load Razorpay checkout");
      const { data: o } = await axios.post(`${API}/shop/order`, { ...f, plan: plan.key });
      new window.Razorpay({
        key: o.key_id, amount: o.amount, currency: "INR", order_id: o.order_id, name: "Easy Books by Hannusoft",
        description: plan.name, prefill: { name: f.name, email: f.email, contact: f.phone }, theme: { color: "#1E3A8A" },
        handler: async (res) => { try { onDone((await axios.post(`${API}/shop/verify`, res)).data); } catch (er) { toast.error(errMsg(er)); } },
        modal: { ondismiss: () => setBusy(false) },
      }).open();
    } catch (er) { toast.error(errMsg(er)); setBusy(false); }
  };
  const fields = [["name", "Your name", true], ["email", "Email", true], ["phone", "Mobile", false], ...(renewal ? [["licence_key", "Existing licence key (EB-XXXX-...)", true]] : [["business_name", "Business name (printed on licence)", false], ["gstin", "GSTIN for invoice (optional)", false]])];
  return (
    <form onSubmit={pay} className="grid gap-3 sm:grid-cols-2" data-testid={`buy-form-${plan.key}`}>
      {fields.map(([k, l, req]) => (
        <div key={k} className={`space-y-1 ${k === "licence_key" ? "sm:col-span-2" : ""}`}><Label>{l}</Label>
          <Input required={req} type={k === "email" ? "email" : "text"} className={`h-11 ${k === "licence_key" ? "font-mono uppercase" : ""}`} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`buy-${plan.key}-${k}`} /></div>
      ))}
      <Button type="submit" disabled={!enabled || busy} className="sm:col-span-2 h-12 text-base" data-testid={`buy-${plan.key}-pay`}>
        {busy && <Loader2 className="h-4 w-4 animate-spin mr-2" />} Pay ₹{amt(plan.total)} & get key
      </Button>
    </form>
  );
};

const Card = ({ p, icon: I, children, highlight }) => (
  <div className={`rounded-2xl border bg-white p-6 space-y-4 ${highlight ? "border-primary shadow-lg" : ""}`} data-testid={`buy-plan-${p.key}`}>
    <div className="flex items-center gap-2"><I className="h-5 w-5 text-primary" /><h3 className="font-heading text-xl font-bold">{p.name}</h3></div>
    <div className="text-sm text-slate-600">{p.users_label}</div>
    <div><span className="num text-3xl font-semibold">{price(p)}</span><span className="text-slate-500"> + 18% GST / year</span></div>
    <div className="text-sm text-slate-500 num" data-testid={`buy-total-${p.key}`}>₹{amt(p.gst)} GST · ₹{amt(p.total)} total</div>
    {children}
  </div>
);

export default function Buy() {
  const [sp] = useSearchParams();
  const [d, setD] = useState(null);
  const [result, setResult] = useState(null);
  const [tab, setTab] = useState(sp.get("plan") === "offline_renewal" ? "offline_renewal" : "offline_first");
  useEffect(() => { axios.get(`${API}/public/plans`).then((r) => setD(r.data)).catch(() => toast.error("Could not load plans. Please refresh.")); }, []);
  if (!d) return <PublicShell><div className="p-10 text-slate-500">Loading...</div></PublicShell>;
  const off = Object.fromEntries(d.offline_plans.map((p) => [p.key, p]));

  return (
    <PublicShell>
      <div className="max-w-6xl mx-auto px-5 py-14 space-y-12" data-testid="buy-page">
        <div><h1 className="font-heading text-4xl sm:text-5xl font-extrabold tracking-tight">Buy Easy Books</h1>
          <p className="text-slate-500 mt-3 text-lg">Pick online (browser and mobile) or the standalone offline Windows software. Your annual key appears right after payment and is emailed to you with a GST invoice.</p></div>
        {!d.payments_enabled && <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900" data-testid="buy-payments-disabled">Online payment is being set up. To buy a key today, contact Hannusoft. Keys can be issued manually.</div>}
        {result && <KeyResult r={result} />}
        <section className="space-y-4">
          <h2 className="font-heading text-2xl font-bold flex items-center gap-2"><Cloud className="h-6 w-6" /> Online plans</h2>
          <div className="grid gap-6 md:grid-cols-2">
            {d.plans.map((p) => (
              <Card key={p.key} p={p} icon={Cloud}>
                <ul className="text-sm space-y-1.5">{["Works on mobile & desktop browser", `${d.trial_days}-day free trial first`, "Licence key issued on payment"].map((t) => <li key={t} className="flex gap-2"><Check className="h-4 w-4 text-emerald-600" />{t}</li>)}</ul>
                <div className="flex gap-2"><Link to="/signup" className="flex-1"><Button className="w-full h-11" data-testid={`buy-online-${p.key}-trial`}>Start free trial</Button></Link>
                  <Link to="/login" className="flex-1"><Button variant="outline" className="w-full h-11" data-testid={`buy-online-${p.key}-login`}>Sign in to pay</Button></Link></div>
              </Card>
            ))}
          </div>
        </section>
        <section className="space-y-4">
          <h2 className="font-heading text-2xl font-bold flex items-center gap-2"><Monitor className="h-6 w-6" /> Offline Windows software</h2>
          <p className="text-slate-500 text-sm">Standalone and separate from the online version, with no internet needed. The first year is {price(off.offline_first)} + GST. From year 2, an annual renewal key ({price(off.offline_renewal)} + GST) is compulsory to keep using it. <Link to="/download" className="text-primary font-medium underline">Download the software</Link></p>
          <div className="flex gap-2">
            {["offline_first", "offline_renewal"].map((k) => <button key={k} onClick={() => setTab(k)} data-testid={`buy-tab-${k}`}
              className={`rounded-full border px-4 py-2 text-sm font-medium ${tab === k ? "bg-primary text-white border-primary" : "bg-white"}`}>{k === "offline_first" ? "Buy first year" : "Renew my key"}</button>)}
          </div>
          <Card p={off[tab]} icon={tab === "offline_first" ? Monitor : RefreshCw} highlight>
            <OfflineForm key={tab} plan={off[tab]} enabled={d.payments_enabled} onDone={(r) => { setResult(r); window.scrollTo({ top: 0, behavior: "smooth" }); }} />
          </Card>
        </section>
      </div>
    </PublicShell>
  );
}
