import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { BookMarked, Loader2, CheckCircle2 } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { errMsg } from "@/lib/api";
import { STATES } from "@/lib/format";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const FIELDS = [
  ["business_name", "Business / Shop name", "text"], ["name", "Your name", "text"], ["email", "Email", "email"],
  ["phone", "Mobile number", "tel"], ["password", "Password (min 6 characters)", "password"], ["gstin", "GSTIN (optional)", "text"],
];

export default function Signup() {
  const { user, signup } = useApp();
  const [f, setF] = useState({ business_name: "", name: "", email: "", phone: "", password: "", gstin: "", state: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try { await signup(f); } catch (err) { setError(errMsg(err)); } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-[1fr_1.1fr]">
      <div className="hidden lg:flex flex-col justify-center gap-8 bg-[#0F172A] p-14 text-white">
        <div className="flex items-center gap-3">
          <div className="h-11 w-11 rounded-lg bg-emerald-500 flex items-center justify-center"><BookMarked className="h-6 w-6" /></div>
          <span className="font-heading text-2xl font-extrabold">Easy Books</span>
        </div>
        <h1 className="font-heading text-5xl font-extrabold leading-[1.1] tracking-tight">Start your <span className="text-emerald-400">30-day free trial</span></h1>
        <ul className="space-y-3 text-slate-300">
          {["Your own separate, private books", "GST invoices with your logo and UPI QR", "GSTR-1 and GSTR-3B summaries every month", "No card needed for the trial"].map((t) => (
            <li key={t} className="flex items-center gap-3"><CheckCircle2 className="h-5 w-5 text-emerald-400" /> {t}</li>
          ))}
        </ul>
        <p className="text-sm text-slate-400">After the trial: ₹6,500 + GST / year (1 + 1 free user) or ₹10,000 + GST / year (3 to 8 users).</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-xl fade-up" data-testid="signup-form">
          <h2 className="font-heading text-3xl font-bold tracking-tight">Create your business account</h2>
          <p className="mt-2 text-slate-500">Already have an account? <Link to="/login" className="text-primary font-medium hover:underline" data-testid="goto-login-link">Sign in</Link></p>
          <div className="mt-8 grid gap-4 sm:grid-cols-2">
            {FIELDS.map(([k, label, type]) => (
              <div key={k} className="space-y-1.5">
                <Label htmlFor={k}>{label}</Label>
                <Input id={k} type={type} required={!["gstin", "phone"].includes(k)} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })}
                  className={`h-12 ${k === "gstin" ? "font-mono uppercase" : ""}`} maxLength={k === "gstin" ? 15 : undefined} data-testid={`signup-${k}-input`} />
              </div>
            ))}
            <div className="space-y-1.5 sm:col-span-2">
              <Label>State</Label>
              <Select value={f.state || "none"} onValueChange={(v) => setF({ ...f, state: v === "none" ? "" : v })}>
                <SelectTrigger className="h-12" data-testid="signup-state-select"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="none">Select state</SelectItem>{STATES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          {error && <div className="mt-4 rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700" data-testid="signup-error">{error}</div>}
          <Button type="submit" disabled={busy} className="mt-6 w-full h-12 text-base" data-testid="signup-submit-button">
            {busy && <Loader2 className="h-4 w-4 animate-spin mr-2" />} Start Free Trial
          </Button>
        </form>
      </div>
    </div>
  );
}
