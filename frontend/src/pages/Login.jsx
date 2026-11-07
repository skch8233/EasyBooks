import { useState } from "react";
import { Navigate } from "react-router-dom";
import { BookMarked, Loader2, ShieldCheck, IndianRupee, Scale } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { errMsg } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

export default function Login() {
  const { user, login } = useApp();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try { await login(email, password); } catch (err) { setError(errMsg(err)); } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.1fr_1fr]">
      <div className="hidden lg:flex flex-col justify-between bg-[#0F172A] p-14 text-white">
        <div className="flex items-center gap-3">
          <div className="h-11 w-11 rounded-lg bg-emerald-500 flex items-center justify-center"><BookMarked className="h-6 w-6" /></div>
          <span className="font-heading text-2xl font-extrabold">Easy Books</span>
        </div>
        <div className="fade-up">
          <h1 className="font-heading text-5xl font-extrabold leading-[1.1] tracking-tight">Bookkeeping for Indian businesses, <span className="text-emerald-400">without the jargon.</span></h1>
          <p className="mt-6 text-slate-300 text-lg max-w-lg">Vouchers, ledgers, GST and every report your CA asks for. Double-entry checked on every save.</p>
          <div className="mt-10 grid grid-cols-3 gap-4 max-w-xl">
            {[[Scale, "Always balanced"], [IndianRupee, "GST ready"], [ShieldCheck, "Full audit trail"]].map(([I, t]) => (
              <div key={t} className="rounded-lg border border-white/10 bg-white/5 p-4"><I className="h-5 w-5 text-emerald-400" /><div className="mt-2 text-sm font-medium">{t}</div></div>
            ))}
          </div>
        </div>
        <div className="text-xs text-slate-500">₹ INR · DD-MM-YYYY · CGST / SGST / IGST</div>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-md fade-up" data-testid="login-form">
          <h2 className="font-heading text-3xl font-bold tracking-tight">Sign in</h2>
          <p className="mt-2 text-slate-500">Enter your email and password to open your books.</p>
          <div className="mt-8 space-y-5">
            <div className="space-y-2"><Label htmlFor="email">Email</Label><Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="h-12 text-base" data-testid="login-email-input" /></div>
            <div className="space-y-2"><Label htmlFor="password">Password</Label><Input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="h-12 text-base" data-testid="login-password-input" /></div>
            {error && <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700" data-testid="login-error">{error}</div>}
            <Button type="submit" disabled={busy} className="w-full h-12 text-base" data-testid="login-submit-button">
              {busy && <Loader2 className="h-4 w-4 animate-spin mr-2" />} Sign in
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
