import { useState } from "react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CompanySettings, BrandingSettings } from "@/components/settings/CompanySettings";
import { FinancialYears } from "@/components/settings/FinancialYears";
import { UsersSettings } from "@/components/settings/UsersSettings";
import { BackupRestore } from "@/components/settings/BackupRestore";

const Password = () => {
  const [f, setF] = useState({ current_password: "", new_password: "" });
  const save = async () => {
    try { await api.post("/auth/change-password", f); toast.success("Password changed"); setF({ current_password: "", new_password: "" }); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="rounded-xl border bg-white p-6 space-y-3 max-w-md" data-testid="password-settings">
      <Input className="h-11" type="password" placeholder="Current password" value={f.current_password} onChange={(e) => setF({ ...f, current_password: e.target.value })} data-testid="current-password-input" />
      <Input className="h-11" type="password" placeholder="New password (min 6)" value={f.new_password} onChange={(e) => setF({ ...f, new_password: e.target.value })} data-testid="new-password-input" />
      <Button className="h-11" onClick={save} data-testid="change-password-button">Change Password</Button>
    </div>
  );
};

export default function Settings() {
  const { isAdmin } = useApp();
  return (
    <div className="space-y-6" data-testid="settings-page">
      <h1 className="font-heading text-3xl font-extrabold tracking-tight">Settings</h1>
      <Tabs defaultValue="company">
        <TabsList className="h-auto flex-wrap">
          <TabsTrigger value="company" className="px-4 py-2" data-testid="settings-tab-company">Company & GST</TabsTrigger>
          <TabsTrigger value="branding" className="px-4 py-2" data-testid="settings-tab-branding">Invoice Branding</TabsTrigger>
          <TabsTrigger value="fy" className="px-4 py-2" data-testid="settings-tab-fy">Financial Years</TabsTrigger>
          {isAdmin && <TabsTrigger value="users" className="px-4 py-2" data-testid="settings-tab-users">Users & Roles</TabsTrigger>}
          {isAdmin && <TabsTrigger value="backup" className="px-4 py-2" data-testid="settings-tab-backup">Backup & Restore</TabsTrigger>}
          <TabsTrigger value="password" className="px-4 py-2" data-testid="settings-tab-password">My Password</TabsTrigger>
        </TabsList>
        <TabsContent value="company" className="mt-5"><CompanySettings /></TabsContent>
        <TabsContent value="branding" className="mt-5"><BrandingSettings /></TabsContent>
        <TabsContent value="fy" className="mt-5"><FinancialYears /></TabsContent>
        {isAdmin && <TabsContent value="users" className="mt-5"><UsersSettings /></TabsContent>}
        {isAdmin && <TabsContent value="backup" className="mt-5"><BackupRestore /></TabsContent>}
        <TabsContent value="password" className="mt-5"><Password /></TabsContent>
      </Tabs>
    </div>
  );
}
