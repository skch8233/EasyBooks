import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LayoutDashboard, PlusCircle, ListOrdered, BookUser, BarChart3, Settings, ShieldCheck, LogOut, Menu, X, BookMarked } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useHotkeys } from "@/hooks/useHotkeys";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, id: "dashboard" },
  { to: "/voucher/sales", label: "New Voucher", icon: PlusCircle, id: "new-voucher", write: true },
  { to: "/vouchers", label: "Vouchers / Day Book", icon: ListOrdered, id: "vouchers" },
  { to: "/ledgers", label: "Ledgers", icon: BookUser, id: "ledgers" },
  { to: "/reports/trial-balance", label: "Reports", icon: BarChart3, id: "reports", match: "/reports" },
  { to: "/audit", label: "Audit Trail", icon: ShieldCheck, id: "audit", write: true },
  { to: "/settings", label: "Settings", icon: Settings, id: "settings" },
];

const SideNav = ({ onNav }) => {
  const { canWrite, settings } = useApp();
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
        {NAV.filter((n) => !n.write || canWrite).map((n) => (
          <NavLink
            key={n.id}
            to={n.to}
            end={n.to === "/"}
            onClick={onNav}
            data-testid={`sidebar-nav-${n.id}`}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-3 text-[15px] font-medium transition-colors ${
                isActive || (n.match && window.location.pathname.startsWith(n.match)) ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/5 hover:text-white"
              }`
            }
          >
            <n.icon className="h-5 w-5" /> {n.label}
          </NavLink>
        ))}
      </nav>
      <div className="px-5 py-4 text-[11px] text-slate-500 leading-relaxed">
        Shortcuts: Alt+S Sales · Alt+P Purchase · Alt+R Receipt · Alt+Y Payment · Alt+C Contra · Alt+J Journal
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
      <main className="px-4 py-6 lg:px-8 lg:py-8 max-w-[1600px]"><Outlet /></main>
    </div>
  );
}
