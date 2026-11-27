import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BookMarked, ChevronDown, Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { HannusoftLogo, Copyright } from "@/components/Hannusoft";
import { INDUSTRIES, IND_KEYS } from "@/lib/industry";

const NavA = ({ to, children, testid }) => <Link to={to} className="px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors" data-testid={testid}>{children}</Link>;

const Solutions = () => {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button onClick={() => setOpen(true)} className="flex items-center gap-1 px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900" data-testid="nav-solutions">
        Solutions by Industry <ChevronDown className="h-4 w-4" /></button>
      {open && <div className="absolute left-0 top-full z-30 w-80 rounded-xl border bg-white p-2 shadow-xl" data-testid="nav-solutions-menu">
        {IND_KEYS.map((k) => { const I = INDUSTRIES[k]; return (
          <Link key={k} to={`/solutions/${k}`} onClick={() => setOpen(false)} className="flex gap-3 rounded-lg p-3 hover:bg-slate-50" data-testid={`nav-solution-${k}`}>
            <I.icon className="h-5 w-5 mt-0.5 text-emerald-600" /><div><div className="text-sm font-semibold">{I.label}</div><div className="text-xs text-slate-500">{I.tagline}</div></div></Link>); })}
      </div>}
    </div>
  );
};

export const PublicHeader = () => {
  const [m, setM] = useState(false);
  const nav = useNavigate();
  return (
    <header className="sticky top-0 z-20 border-b bg-white/90 backdrop-blur">
      <div className="max-w-6xl mx-auto flex items-center gap-2 px-5 h-16">
        <Link to="/welcome" className="flex items-center gap-3 mr-4" data-testid="nav-home"><div className="h-9 w-9 rounded-lg bg-emerald-500 flex items-center justify-center"><BookMarked className="h-5 w-5 text-white" /></div>
          <span className="font-heading text-xl font-extrabold whitespace-nowrap">EASYTALLY BOOKS</span></Link>
        <nav className="hidden lg:flex items-center gap-1">
          <Solutions /><NavA to="/features" testid="nav-features">Accounting & ERP Features</NavA><NavA to="/pricing" testid="nav-pricing">Pricing</NavA>
          <NavA to="/demo" testid="nav-demo">Live Demo</NavA><NavA to="/about" testid="nav-about">About Us</NavA>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <Link to="/login" className="hidden sm:block"><Button variant="ghost" data-testid="nav-signin">Login</Button></Link>
          <Button onClick={() => nav("/signup")} className="bg-emerald-600 hover:bg-emerald-700" data-testid="nav-trial">Start Free Trial</Button>
          <button className="lg:hidden p-2" onClick={() => setM(!m)} data-testid="nav-mobile-toggle">{m ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}</button>
        </div>
      </div>
      {m && <div className="lg:hidden border-t bg-white px-5 py-3 grid gap-1" data-testid="nav-mobile-menu">
        {IND_KEYS.map((k) => <NavA key={k} to={`/solutions/${k}`} testid={`nav-mobile-solution-${k}`}>{INDUSTRIES[k].label}</NavA>)}
        <NavA to="/features" testid="nav-mobile-features">Features</NavA><NavA to="/pricing" testid="nav-mobile-pricing">Pricing</NavA><NavA to="/demo" testid="nav-mobile-demo">Live Demo</NavA>
        <NavA to="/about" testid="nav-mobile-about">About Us</NavA><NavA to="/login" testid="nav-mobile-login">Login</NavA>
      </div>}
    </header>
  );
};

export const PublicFooter = () => (
  <footer className="border-t bg-[#0F172A] text-slate-300">
    <div className="max-w-6xl mx-auto px-5 py-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-4 text-sm">
      <div className="space-y-3"><div className="bg-white rounded-lg inline-block px-2 py-1"><HannusoftLogo size={30} /></div><p className="text-slate-400">Complete finance software. Effortless to use. Built for your budget.</p></div>
      <div className="space-y-2"><div className="font-semibold text-white">Solutions</div>{IND_KEYS.map((k) => <Link key={k} to={`/solutions/${k}`} className="block hover:text-white">{INDUSTRIES[k].label}</Link>)}</div>
      <div className="space-y-2"><div className="font-semibold text-white">Product</div><Link to="/features" className="block hover:text-white">Features</Link><Link to="/pricing" className="block hover:text-white">Pricing</Link><Link to="/demo" className="block hover:text-white">Live Demo</Link><Link to="/download" className="block hover:text-white">Windows offline</Link></div>
      <div className="space-y-2"><div className="font-semibold text-white">Company</div><Link to="/about" className="block hover:text-white">About Us & Vision</Link><Link to="/login" className="block hover:text-white">Login</Link><Link to="/signup" className="block hover:text-white">Start Free Trial</Link></div>
    </div>
    <div className="border-t border-white/10"><div className="max-w-6xl mx-auto px-5 py-4"><Copyright /></div></div>
  </footer>
);

export const PublicShell = ({ children }) => (
  <div className="min-h-screen bg-white flex flex-col">
    <PublicHeader />
    <main className="flex-1">{children}</main>
    <PublicFooter />
  </div>
);
