import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AppProvider, useApp } from "@/context/AppContext";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import VoucherEntry from "@/pages/VoucherEntry";
import Vouchers from "@/pages/Vouchers";
import Ledgers from "@/pages/Ledgers";
import Reports from "@/pages/Reports";
import Settings from "@/pages/Settings";
import AuditLog from "@/pages/AuditLog";
import Signup from "@/pages/Signup";
import Subscription from "@/pages/Subscription";
import Platform from "@/pages/Platform";
import Landing from "@/pages/Landing";
import PublicInvoice from "@/pages/PublicInvoice";
import Stock from "@/pages/Stock";
import Reminders from "@/pages/Reminders";
import PayPage from "@/pages/PayPage";
import Buy from "@/pages/Buy";
import DownloadPage from "@/pages/Download";
import OfflineLicence from "@/pages/OfflineLicence";
import Activate from "@/pages/Activate";
import ErpShell from "@/pages/erp/ErpShell";
import ErpDashboard from "@/pages/erp/ErpDashboard";
import Projects from "@/pages/erp/Projects";
import ProjectView from "@/pages/erp/ProjectView";
import Parties from "@/pages/erp/Parties";
import DocRegister from "@/pages/erp/DocRegister";
import DocEditor from "@/pages/erp/DocEditor";
import ErpSettings from "@/pages/erp/ErpSettings";
import Purchases from "@/pages/erp/Purchases";
import RfqView from "@/pages/erp/RfqView";
import PoEditor from "@/pages/erp/PoEditor";
import BillEditor from "@/pages/erp/BillEditor";
import Expenses from "@/pages/erp/Expenses";
import FinalAccounts from "@/pages/FinalAccounts";
import EwayBill from "@/pages/EwayBill";
import YearEnd from "@/pages/YearEnd";
import ErpReports from "@/pages/erp/ErpReports";
import { OFFLINE } from "@/lib/offline";

const Protected = ({ children, write }) => {
  const { user, fy, canWrite, biz } = useApp();
  const loc = useLocation();
  if (user === null || (user && !fy)) return <div className="min-h-screen flex items-center justify-center text-slate-500">Loading...</div>;
  if (!user) return OFFLINE ? <div className="min-h-screen flex items-center justify-center text-slate-500" data-testid="offline-start-error">Easy Books could not start. Close and open it again.</div> : <Navigate to="/welcome" replace />;
  if (OFFLINE && biz?.status === "expired" && loc.pathname !== "/licence") return <Navigate to="/licence" replace />;
  if (write && !canWrite) return <Navigate to={user.role === "viewer" ? "/" : OFFLINE ? "/licence" : "/subscription"} replace />;
  return children;
};

function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={OFFLINE ? <Navigate to="/" replace /> : <Login />} />
          <Route path="/signup" element={OFFLINE ? <Navigate to="/" replace /> : <Signup />} />
          <Route path="/welcome" element={OFFLINE ? <Navigate to="/login" replace /> : <Landing />} />
          <Route path="/buy" element={<Buy />} />
          <Route path="/download" element={<DownloadPage />} />
          <Route path="/activate" element={<Activate />} />
          <Route path="/i/:token" element={<PublicInvoice />} />
          <Route path="/pay/:token" element={<PayPage />} />
          <Route element={<Protected><Layout /></Protected>}>
            <Route index element={<Dashboard />} />
            <Route path="voucher/edit/:id" element={<Protected write><VoucherEntry /></Protected>} />
            <Route path="voucher/:type" element={<Protected write><VoucherEntry /></Protected>} />
            <Route path="vouchers" element={<Vouchers />} />
            <Route path="ledgers" element={<Ledgers />} />
            <Route path="stock" element={<Stock />} />
            <Route path="reminders" element={<Reminders />} />
            <Route path="reports" element={<Navigate to="/reports/trial-balance" replace />} />
            <Route path="reports/:report" element={<Reports />} />
            <Route path="audit" element={<AuditLog />} />
            <Route path="settings" element={<Settings />} />
            <Route path="final-accounts" element={<FinalAccounts />} />
            <Route path="eway-bill" element={<EwayBill />} />
            <Route path="year-end" element={<YearEnd />} />
            <Route path="subscription" element={<Subscription />} />
            <Route path="platform" element={<Platform />} />
            <Route path="licence" element={<OfflineLicence />} />
            <Route path="erp" element={<ErpShell />}>
              <Route index element={<ErpDashboard />} />
              <Route path="projects" element={<Projects />} />
              <Route path="projects/:id" element={<ProjectView />} />
              <Route path="parties" element={<Parties />} />
              <Route path="quotations" element={<DocRegister kind="quotations" />} />
              <Route path="quotations/new" element={<DocEditor key="qn" kind="quotation" />} />
              <Route path="quotations/:id" element={<DocEditor key="qe" kind="quotation" />} />
              <Route path="invoices" element={<DocRegister kind="invoices" />} />
              <Route path="invoices/new" element={<DocEditor key="in" kind="invoice" />} />
              <Route path="invoices/:id" element={<DocEditor key="ie" kind="invoice" />} />
              <Route path="purchases" element={<Navigate to="/erp/purchases/prs" replace />} />
              <Route path="purchases/prs" element={<Purchases tab="prs" />} />
              <Route path="purchases/rfqs" element={<Purchases tab="rfqs" />} />
              <Route path="purchases/rfqs/:id" element={<RfqView />} />
              <Route path="purchases/pos" element={<Purchases tab="pos" />} />
              <Route path="purchases/pos/:id" element={<PoEditor />} />
              <Route path="purchases/grns" element={<Purchases tab="grns" />} />
              <Route path="purchases/bills" element={<Purchases tab="bills" />} />
              <Route path="purchases/bills/:id" element={<BillEditor />} />
              <Route path="expenses" element={<Expenses />} />
              <Route path="reports" element={<ErpReports />} />
              <Route path="settings" element={<ErpSettings />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="top-right" />
    </AppProvider>
  );
}

export default App;
