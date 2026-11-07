import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";

const EMPTY = { name: "", hsn: "", unit: "Nos", gst_rate: 18, sale_rate: "", purchase_rate: "", opening_qty: 0, opening_rate: "", reorder_level: 0 };
const FIELDS = [
  ["name", "Item name", "text", "sm:col-span-2"], ["hsn", "HSN / SAC", "text"], ["unit", "Unit (Nos, Kg, Ltr, Box...)", "text"],
  ["sale_rate", "Sale rate (₹)", "number"], ["purchase_rate", "Purchase rate (₹)", "number"],
  ["opening_qty", "Opening quantity", "number"], ["opening_rate", "Opening rate (₹ per unit)", "number"], ["reorder_level", "Low stock alert at (qty)", "number"],
];

export const StockDialog = ({ open, item, onClose, onSaved }) => {
  const { settings } = useApp();
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setF(item ? { ...EMPTY, ...item } : EMPTY); }, [open, item]);
  const rates = settings?.gst_rates || [0, 5, 12, 18, 28];

  const save = async () => {
    setBusy(true);
    const num = (k) => Number(f[k]) || 0;
    const body = { ...f, gst_rate: Number(f.gst_rate), sale_rate: num("sale_rate"), purchase_rate: num("purchase_rate"), opening_qty: num("opening_qty"), opening_rate: num("opening_rate"), reorder_level: num("reorder_level") };
    try {
      item ? await api.put(`/stock-items/${item.id}`, body) : await api.post("/stock-items", body);
      toast.success(`Item "${f.name}" saved`);
      onSaved();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="stock-dialog">
        <DialogHeader><DialogTitle className="font-heading text-xl">{item ? "Edit Stock Item" : "New Stock Item"}</DialogTitle></DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          {FIELDS.map(([k, l, t, cls]) => (
            <div key={k} className={`space-y-1.5 ${cls || ""}`}><Label>{l}</Label>
              <Input className={`h-11 ${t === "number" ? "num text-right" : ""} ${k === "hsn" ? "font-mono" : ""}`} type={t} step="any" min={k === "opening_qty" ? undefined : "0"} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`stock-${k}-input`} /></div>
          ))}
          <div className="space-y-1.5"><Label>GST rate</Label>
            <div className="flex flex-wrap gap-2" data-testid="stock-gst-rate">
              {rates.map((r) => <button type="button" key={r} onClick={() => setF({ ...f, gst_rate: r })} data-testid={`stock-gst-${r}`}
                className={`h-11 px-4 rounded-md border text-sm font-mono ${Number(f.gst_rate) === r ? "bg-primary text-white border-primary" : "bg-white hover:bg-slate-50"}`}>{r}%</button>)}
            </div></div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={busy || !f.name.trim()} className="px-6" data-testid="stock-save-button">Save Item</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
