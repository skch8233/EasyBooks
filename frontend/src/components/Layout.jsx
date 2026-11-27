import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { LayoutDashboard, PlusCircle, ListOrdered, BookUser, BarChart3, Settings, ShieldCheck, LogOut, Menu, X, BookMarked, CreditCard, Building2, AlertTriangle, Landmark, Package, BellRing, Briefcase, Users, ShoppingCart, GraduationCap, Wallet, Stethoscope, Pill, Repeat, Receipt, FileText, ChevronDown, ChevronUp } from "lucide-react";
import { navFor } from "@/lib/industry";
import { BusinessSwitcher } from "@/components/BusinessSwitcher";
import { Link } from "react-router-dom";
import { useApp } from "@/context/AppContext";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useHotkeys } from "@/hooks/useHotkeys";
import { MadeBy, Copyright } from "@/components/Hannusoft";
import { OFFLINE } from "@/lib/offline";
import { toast } from "sonner";
import { errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, id: "dashboard" },
  { to: "/erp", label: "Projects / ERP", icon: Briefcase, id: "erp", match: (p) => p.startsWith("/erp") },
  { to: "/voucher/sales", label: "New Voucher", icon: PlusCircle, id: "new-voucher", write: true },
  { to: "/vouchers", label: "Vouchers / Day Book", icon: ListOrdered, id: "vouchers" },
  { to: "/ledgers", label: "Ledgers", icon: BookUser, id: "ledgers" },
  { to: "/stock", label: "Stock", icon: Package, id: "stock" },
  { to: "/reminders", label: "Payment Reminders", icon: BellRing, id: "reminders" },
  { to: "/reports/trial-balance", label: "Reports", icon: BarChart3, id: "reports", match: (p) => p.startsWith("/reports") && !p.startsWith("/reports/gstr") },
  { to: "/year-end", label: "Depreciation & Tax", icon: BarChart3, id: "year-end" },
  { to: "/final-accounts", label: "Final Accounts", icon: BarChart3, id: "final-accounts" },
  { to: "/ca", label: "CA Clients", icon: Users, id: "ca" },
  { to: "/eway-bill", label: "E-way Bill", icon: Package, id: "eway" },
  { to: "/reports/gstr-3b", label: "GST Returns", icon: Landmark, id: "gst", match: (p) => p.startsWith("/reports/gstr") },
  { to: "/audit", label: "Audit Trail", icon: ShieldCheck, id: "audit", staff: true },
  { to: "/settings", label: "Settings", icon: Settings, id: "settings" },
  { to: "/subscription", label: "Subscription", icon: CreditCard, id: "subscription", admin: true, online: true },
  { to: "/licence", label: "Licence", icon: CreditCard, id: "licence", offline: true },
  { to: "/super-admin", label: "Super Admin", icon: Building2, id: "platform", superadmin: true, online: true },
];

const ICONS = { pos: ShoppingCart, students: GraduationCap, payroll: Wallet, patients: Stethoscope, pharmacy: Pill, recurring: Repeat, tds: Receipt, "sales-register": FileText };
const navItems = (ind) => {
  if (OFFLINE || !ind) return NAV;
  const cfg = navFor(ind.industry_type, ind.industry_mode);
  const list = NAV.filter((n) => !cfg.hide.has(n.id)).map((n) => (cfg.labels[n.id] ? { ...n, label: cfg.labels[n.id] } : n));
  list.splice(1, 0, ...cfg.extra.map((e) => ({ ...e, icon: ICONS[e.id] })));
  return list;
};

const GROUPS = [
  { id: "daily", label: "Daily work", ids: ["dashboard", "pos", "students", "payroll", "patients", "pharmacy", "recurring", "tds", "sales-register", "new-voucher", "vouchers"] },
  { id: "masters", label: "Masters & projects", ids: ["ledgers", "stock", "reminders", "erp"] },
  { id: "reports", label: "Reports & year end", ids: ["reports", "year-end", "final-accounts", "gst", "eway"] },
  { id: "admin", label: "Business & settings", ids: ["ca", "audit", "settings", "subscription", "licence", "platform"] },
];
const isOn = (n, pathname) => (n.match ? n.match(pathname) : n.to === "/" ? pathname === "/" : pathname.startsWith(n.to));

const NavGroup = ({ g, items, pathname, closed, toggle, onNav }) => {
  const open = !closed.includes(g.id);
  const Arrow = open ? ChevronUp : ChevronDown;
  return (
    <div className="pt-2" data-testid={`sidebar-group-${g.id}`}>
      <button onClick={() => toggle(g.id)} aria-expanded={open} data-testid={`sidebar-group-toggle-${g.id}`}
        className="flex w-full items-center justify-between rounded-md px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400 hover:text-white transition-colors">
        {g.label}<Arrow className="h-4 w-4" /></button>
      <div className={`grid transition-[grid-template-rows] duration-200 ${open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
        <div className="overflow-hidden space-y-0.5">
          {items.map((n) => { const on = isOn(n, pathname); return (
            <NavLink key={n.id} to={n.to} end={n.to === "/"} onClick={onNav} data-testid={`sidebar-nav-${n.id}`} tabIndex={open ? 0 : -1}
              className={`relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-[14.5px] font-medium transition-colors ${on ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/5 hover:text-white"}`}>
              {on && <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r bg-emerald-400" />}<n.icon className="h-[18px] w-[18px]" /> {n.label}</NavLink>); })}
        </div>
      </div>
    </div>
  );
};

const SideNav = ({ onNav }) => {
  const { canWrite, settings, user, isAdmin, industry } = useApp();
  const { pathname } = useLocation();
  const show = (n) => (!n.write || canWrite) && (!n.admin || isAdmin) && (!n.superadmin || (user?.is_superadmin && !user?.support_view)) && (!n.staff || user?.role !== "viewer")
    && (!n.online || !OFFLINE) && (!n.offline || OFFLINE);
  const items = navItems(industry).filter(show);
  const [closed, setClosed] = useState(() => { try { return JSON.parse(localStorage.getItem("eb_nav_closed") || "[]"); } catch { return []; } });
  const toggle = (id) => setClosed((c) => { const nx = c.includes(id) ? c.filter((x) => x !== id) : [...c, id]; localStorage.setItem("eb_nav_closed", JSON.stringify(nx)); return nx; });
  useEffect(() => {
    const g = GROUPS.find((x) => items.some((n) => x.ids.includes(n.id) && isOn(n, pathname)));
    // idempotent open (a flip toggle runs twice under React StrictMode and re-closes the group)
    if (g) setClosed((c) => { if (!c.includes(g.id)) return c; const nx = c.filter((x) => x !== g.id); localStorage.setItem("eb_nav_closed", JSON.stringify(nx)); return nx; });
  }, [pathname]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="flex h-full flex-col">
      <div className="px-5 py-6 flex items-center gap-3">
        <div className="h-10 w-10 rounded-lg bg-emerald-500 flex items-center justify-center"><BookMarked className="h-5 w-5 text-white" /></div>
        <div className="min-w-0">
          <div className="font-heading font-extrabold text-white text-lg leading-tight">EASYTALLY BOOKS</div>
          <div className="text-xs text-slate-400 truncate" data-testid="sidebar-company-name">{settings?.company_name}</div>
        </div>
      </div>
      <nav className="flex-1 px-3 pb-4 overflow-y-auto">
        {GROUPS.map((g) => { const list = items.filter((n) => g.ids.includes(n.id)); return list.length ? <NavGroup key={g.id} g={g} items={list} pathname={pathname} closed={closed} toggle={toggle} onNav={onNav} /> : null; })}
      </nav>
      <div className="px-5 py-4 text-[11px] text-slate-500 leading-relaxed space-y-4">
        <div className="hidden md:block">Shortcuts: Alt+S Sales · Alt+P Purchase · Alt+R Receipt · Alt+Y Payment · Alt+C Contra · Alt+J Journal</div>
        <MadeBy dark />
      </div>
    </div>
  );
};

const CompanyYear = () => {
  const { fy, setCompanyFy } = useApp();
  if (!fy || fy.is_active) return <span className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700" data-testid="fy-company-badge">Company year</span>;
  const go = async () => { try { await setCompanyFy(fy); toast.success(`FY ${fy.name} is now the company year`); } catch (e) { toast.error(errMsg(e)); } };
  return <button onClick={go} className="text-xs text-primary underline whitespace-nowrap" data-testid="fy-set-company-button">Make company year</button>;
};

const TopBar = ({ onMenu }) => {
  const { user, logout, fys, fy, setFy } = useApp();
  const nav = useNavigate();
  return (
    <header className="no-print sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-white/90 backdrop-blur px-4 lg:px-8">
      <button className="lg:hidden p-2 rounded-md hover:bg-slate-100" onClick={onMenu} data-testid="mobile-menu-button"><Menu className="h-5 w-5" /></button>
      <div className="flex items-center gap-2">
        <span className="hidden sm:inline text-xs font-semibold uppercase tracking-wide text-slate-500">Financial Year</span>
        <Select value={fy?.id || ""} onValueChange={(id) => setFy(fys.find((f) => f.id === id))}>
          <SelectTrigger className="h-10 w-[130px] font-mono" data-testid="fy-switcher"><SelectValue placeholder="FY" /></SelectTrigger>
          <SelectContent>
            {fys.map((f) => <SelectItem key={f.id} value={f.id} data-testid={`fy-option-${f.name}`}>FY {f.name}{f.is_active ? " ★" : ""}{f.locked ? " (locked)" : ""}</SelectItem>)}
          </SelectContent>
        </Select>
        <CompanyYear />
      </div>
      <div className="ml-auto flex items-center gap-3">
        <BusinessSwitcher />
        <div className="text-right hidden sm:block">
          <div className="text-sm font-semibold" data-testid="topbar-user-name">{user?.name}</div>
          <div className="text-[11px] uppercase tracking-wide text-emerald-700 font-semibold" data-testid="topbar-user-role">{user?.role}</div>
        </div>
        {!OFFLINE && <button onClick={() => { logout(); nav("/login"); }} data-testid="logout-button" className="flex items-center gap-2 h-10 px-3 rounded-md border text-sm hover:bg-slate-50">
          <LogOut className="h-4 w-4" /> <span className="hidden sm:inline">Logout</span>
        </button>}
      </div>
    </header>
  );
};

const SupportBanner = () => {
  const { user, settings, exitSupport } = useApp();
  const nav = useNavigate();
  if (!user?.support_view) return null;
  return (
    <div className="bg-amber-400 text-amber-950 px-4 py-2 text-sm font-medium flex items-center gap-3" data-testid="support-view-banner">
      Support view (read-only) - {settings?.company_name}. Every access is logged.
      <Button size="sm" variant="outline" className="ml-auto h-8 bg-white" onClick={async () => { await exitSupport(); nav("/super-admin"); }} data-testid="support-view-exit">Exit support view</Button>
    </div>
  );
};

const LockGate = ({ children }) => {
  const { biz, user, logout } = useApp();
  const { pathname } = useLocation();
  if (!biz?.locked || user?.is_superadmin || pathname.startsWith("/subscription")) return children;
  const susp = biz.status === "suspended";
  return (
    <div className="mx-auto max-w-lg mt-16 rounded-2xl border bg-white p-8 text-center space-y-4" data-testid="account-locked-screen">
      <h1 className="font-heading text-2xl font-extrabold">{susp ? "Account suspended" : "Subscription Expired"}</h1>
      <p className="text-slate-600">{susp ? "This account has been suspended. Contact Support to restore access." : "Your 7-day read-only grace period has ended. Contact Support to Renew, or renew online now."}</p>
      <div className="flex justify-center gap-2">{!susp && <Link to="/subscription"><Button data-testid="locked-renew-button">Renew now</Button></Link>}
        <Button variant="outline" onClick={logout} data-testid="locked-logout-button">Log out</Button></div>
    </div>
  );
};

const PlanBanner = () => {
  const { biz, isAdmin } = useApp();
  if (!biz?.alert || biz.locked) return null;
  const expired = biz.status === "expired";
  const offMsg = expired ? (biz.reason || "No active licence. Enter a subscription key to continue.")
    : biz.status === "trial" ? `Free trial: ${biz.days_left} day${biz.days_left === 1 ? "" : "s"} left. All features are unlocked. Enter a subscription key before it ends.`
    : `Your licence expires in ${biz.days_left} days. Buy a renewal key.`;
  const msg = OFFLINE ? offMsg
    : expired ? `Your ${biz.plan === "trial" ? "free trial" : "subscription"} has expired. Books are read-only for 7 days, then locked until you renew.`
    : biz.status === "trial" ? `Free trial: ${biz.days_left} day${biz.days_left === 1 ? "" : "s"} left.` : `Your annual subscription expires in ${biz.days_left} days.`;
  return (
    <div className={`no-print flex flex-wrap items-center gap-3 px-4 lg:px-8 py-2.5 text-sm border-b ${expired ? "bg-red-50 text-red-800 border-red-200" : "bg-amber-50 text-amber-900 border-amber-200"}`} data-testid="plan-banner">
      <AlertTriangle className="h-4 w-4" /> <span data-testid="plan-banner-text">{msg}</span>
      {isAdmin ? <Link to={OFFLINE ? "/licence" : "/subscription"} className="font-semibold underline" data-testid="plan-banner-upgrade">{OFFLINE ? "Open Licence" : expired ? "Renew now" : "Choose a plan"}</Link> : <span>Ask your admin to renew.</span>}
    </div>
  );
};

export default function Layout() {
  const [open, setOpen] = useState(false);
  const { canWrite } = useApp();
  useHotkeys(canWrite);
  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="no-print hidden lg:block fixed inset-y-0 left-0 w-64 bg-[#0F172A]"><SideNav /></aside>
      {open && (
        <div className="no-print fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 bg-[#0F172A]">
            <button className="absolute right-3 top-3 p-2 text-white" onClick={() => setOpen(false)} data-testid="mobile-menu-close"><X className="h-5 w-5" /></button>
            <SideNav onNav={() => setOpen(false)} />
          </aside>
        </div>
      )}
      <TopBar onMenu={() => setOpen(true)} />
      <SupportBanner />
      <PlanBanner />
      <main className="px-4 py-6 lg:px-8 lg:py-8 max-w-[1600px]"><LockGate><Outlet /></LockGate></main>
      <footer className="no-print px-4 lg:px-8 py-6 border-t lg:hidden"><MadeBy /></footer>
      <footer className="no-print hidden lg:block px-8 py-4 border-t"><Copyright /></footer>
    </div>
  );
}
