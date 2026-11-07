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

const Protected = ({ children, write }) => {
  const { user, fy, canWrite } = useApp();
  if (user === null || (user && !fy)) return <div className="min-h-screen flex items-center justify-center text-slate-500">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (write && !canWrite) return <Navigate to="/" replace />;
  return children;
};

function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<Protected><Layout /></Protected>}>
            <Route index element={<Dashboard />} />
            <Route path="voucher/edit/:id" element={<Protected write><VoucherEntry /></Protected>} />
            <Route path="voucher/:type" element={<Protected write><VoucherEntry /></Protected>} />
            <Route path="vouchers" element={<Vouchers />} />
            <Route path="ledgers" element={<Ledgers />} />
            <Route path="reports" element={<Navigate to="/reports/trial-balance" replace />} />
            <Route path="reports/:report" element={<Reports />} />
            <Route path="audit" element={<Protected write><AuditLog /></Protected>} />
            <Route path="settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="top-right" />
    </AppProvider>
  );
}

export default App;
