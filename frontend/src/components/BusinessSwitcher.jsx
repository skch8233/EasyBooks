import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Building2 } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const BusinessSwitcher = () => {
  const { user, switchBusiness } = useApp();
  const [list, setList] = useState([]);
  const nav = useNavigate();
  useEffect(() => {
    const load = () => api.get("/ca/businesses").then((r) => setList(r.data)).catch(() => {});
    load();
    window.addEventListener("eb-businesses", load);
    return () => window.removeEventListener("eb-businesses", load);
  }, [user?.business_id]);
  if (list.length < 2) return null;
  const go = async (id) => {
    try { const u = await switchBusiness(id); toast.success(`Now working in ${list.find((b) => b.id === id)?.name} as ${u.role}`); nav("/"); }
    catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Select value={user?.business_id || ""} onValueChange={go}>
      <SelectTrigger className="h-10 w-[220px]" data-testid="business-switcher"><Building2 className="h-4 w-4 mr-1 text-slate-500" /><SelectValue /></SelectTrigger>
      <SelectContent>
        {list.map((b) => <SelectItem key={b.id} value={b.id} data-testid={`business-option-${b.id}`}>{b.name}{b.home ? " (my firm)" : ""}</SelectItem>)}
      </SelectContent>
    </Select>
  );
};
