import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
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
import { OFFLINE } from "@/lib/offline";

const Protected = ({ children, write }) => {
  const { user, fy, canWrite } = useApp();
  if (user === null || (user && !fy)) return <div className="min-h-screen flex items-center justify-center text-slate-500">Loading...</div>;
  if (!user) return <Navigate to={OFFLINE ? "/login" : "/welcome"} replace />;
  if (write && !canWrite) return <Navigate to={user.role === "viewer" ? "/" : OFFLINE ? "/licence" : "/subscription"} replace />;
  return children;
};

function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/welcome" element={OFFLINE ? <Navigate to="/login" replace /> : <Landing />} />
          <Route path="/buy" element={<Buy />} />
          <Route path="/download" element={<DownloadPage />} />
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
            <Route path="subscription" element={<Subscription />} />
            <Route path="platform" element={<Platform />} />
            <Route path="licence" element={<OfflineLicence />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="top-right" />
    </AppProvider>
  );
}

export default App;
