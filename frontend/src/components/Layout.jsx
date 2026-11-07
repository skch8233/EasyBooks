import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { LayoutDashboard, PlusCircle, ListOrdered, BookUser, BarChart3, Settings, ShieldCheck, LogOut, Menu, X, BookMarked, CreditCard, Building2, AlertTriangle, Landmark, Package, BellRing } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "@/context/AppContext";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useHotkeys } from "@/hooks/useHotkeys";
import { MadeBy, Copyright } from "@/components/Hannusoft";
import { OFFLINE } from "@/lib/offline";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, id: "dashboard" },
  { to: "/voucher/sales", label: "New Voucher", icon: PlusCircle, id: "new-voucher", write: true },
  { to: "/vouchers", label: "Vouchers / Day Book", icon: ListOrdered, id: "vouchers" },
  { to: "/ledgers", label: "Ledgers", icon: BookUser, id: "ledgers" },
  { to: "/stock", label: "Stock", icon: Package, id: "stock" },
  { to: "/reminders", label: "Payment Reminders", icon: BellRing, id: "reminders" },
  { to: "/reports/trial-balance", label: "Reports", icon: BarChart3, id: "reports", match: (p) => p.startsWith("/reports") && !p.startsWith("/reports/gstr") },
  { to: "/reports/gstr-3b", label: "GST Returns", icon: Landmark, id: "gst", match: (p) => p.startsWith("/reports/gstr") },
  { to: "/audit", label: "Audit Trail", icon: ShieldCheck, id: "audit", staff: true },
  { to: "/settings", label: "Settings", icon: Settings, id: "settings" },
  { to: "/subscription", label: "Subscription", icon: CreditCard, id: "subscription", admin: true, online: true },
  { to: "/licence", label: "Licence", icon: CreditCard, id: "licence", offline: true },
  { to: "/platform", label: "Platform Admin", icon: Building2, id: "platform", superadmin: true, online: true },
];

const SideNav = ({ onNav }) => {
  const { canWrite, settings, user, isAdmin } = useApp();
  const { pathname } = useLocation();
  const show = (n) => (!n.write || canWrite) && (!n.admin || isAdmin) && (!n.superadmin || user?.is_superadmin) && (!n.staff || user?.role !== "viewer")
    && (!n.online || !OFFLINE) && (!n.offline || OFFLINE);
  return (
    <div className="flex h-full flex-col">
      <div className="px-5 py-6 flex items-center gap-3">
        <div className="h-10 w-10 rounded-lg bg-emerald-500 flex items-center justify-center"><BookMarked className="h-5 w-5 text-white" /></div>
        <div className="min-w-0">
          <div className="font-heading font-extrabold text-white text-lg leading-tight">Easy Books</div>
          <div className="text-xs text-slate-400 truncate" data-testid="sidebar-company-name">{settings?.company_name}</div>
        </div>
      </div>
      <nav className="flex-1 px-3 space-y-1">
        {NAV.filter(show).map((n) => (
          <NavLink
            key={n.id}
            to={n.to}
            end={n.to === "/"}
            onClick={onNav}
            data-testid={`sidebar-nav-${n.id}`}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-3 text-[15px] font-medium transition-colors ${
                (n.match ? n.match(pathname) : isActive) ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/5 hover:text-white"
              }`
            }
          >
            <n.icon className="h-5 w-5" /> {n.label}
          </NavLink>
        ))}
      </nav>
      <div className="px-5 py-4 text-[11px] text-slate-500 leading-relaxed space-y-4">
        <div>Shortcuts: Alt+S Sales · Alt+P Purchase · Alt+R Receipt · Alt+Y Payment · Alt+C Contra · Alt+J Journal</div>
        <MadeBy dark />
      </div>
    </div>
  );
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
            {fys.map((f) => <SelectItem key={f.id} value={f.id} data-testid={`fy-option-${f.name}`}>FY {f.name}{f.locked ? " (locked)" : ""}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div className="ml-auto flex items-center gap-3">
        <div className="text-right hidden sm:block">
          <div className="text-sm font-semibold" data-testid="topbar-user-name">{user?.name}</div>
          <div className="text-[11px] uppercase tracking-wide text-emerald-700 font-semibold" data-testid="topbar-user-role">{user?.role}</div>
        </div>
        <button onClick={() => { logout(); nav("/login"); }} data-testid="logout-button" className="flex items-center gap-2 h-10 px-3 rounded-md border text-sm hover:bg-slate-50">
          <LogOut className="h-4 w-4" /> <span className="hidden sm:inline">Logout</span>
        </button>
      </div>
    </header>
  );
};

const PlanBanner = () => {
  const { biz, isAdmin } = useApp();
  if (!biz?.alert) return null;
  const expired = biz.status === "expired";
  const msg = OFFLINE ? (expired ? "No active licence. The software is read-only until you activate or renew your licence." : `Your licence expires in ${biz.days_left} days. Buy a renewal key.`)
    : expired ? `Your ${biz.plan === "trial" ? "free trial" : "subscription"} has expired. Books are read-only.`
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
      <PlanBanner />
      <main className="px-4 py-6 lg:px-8 lg:py-8 max-w-[1600px]"><Outlet /></main>
      <footer className="no-print px-4 lg:px-8 py-6 border-t lg:hidden"><MadeBy /></footer>
      <footer className="no-print hidden lg:block px-8 py-4 border-t"><Copyright /></footer>
    </div>
  );
}
