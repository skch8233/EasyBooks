import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { BLANK_LINE } from "@/lib/erp";

const COLS = [["description", "Description", "flex-1 min-w-[220px]"], ["hsn", "HSN/SAC", "w-24"], ["unit", "Unit", "w-16"], ["qty", "Qty", "w-20"],
  ["rate", "Rate", "w-28"], ["discount", "Disc %", "w-20"], ["gst_rate", "GST %", "w-20"]];

export const LineItems = ({ lines, setLines, disabled, prefix = "line" }) => {
  const set = (i, k, v) => setLines(lines.map((l, n) => (n === i ? { ...l, [k]: v } : l)));
  return (
    <div className="space-y-2" data-testid="line-items">
      {lines.map((l, i) => (
        <div key={i} className="flex flex-wrap gap-2 items-end rounded-lg border bg-slate-50/60 p-2">
          {COLS.map(([k, label, w]) => (
            <label key={k} className={`${w} space-y-0.5`}><span className="block text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</span>
            <Input className={`h-10 w-full ${k === "description" ? "" : "font-mono"}`} placeholder={label} title={label} disabled={disabled}
              type={["qty", "rate", "discount", "gst_rate"].includes(k) ? "number" : "text"} step="any" min="0" value={l[k]}
              onChange={(e) => set(i, k, e.target.value)} data-testid={`${prefix}-${i}-${k}`} /></label>
          ))}
          <button type="button" className="p-2 text-slate-400 hover:text-red-600 disabled:opacity-30" disabled={disabled || lines.length === 1}
            onClick={() => setLines(lines.filter((_, n) => n !== i))} data-testid={`${prefix}-${i}-remove`}><Trash2 className="h-4 w-4" /></button>
        </div>
      ))}
      {!disabled && <Button type="button" variant="outline" size="sm" onClick={() => setLines([...lines, { ...BLANK_LINE }])} data-testid={`${prefix}-add-button`}><Plus className="h-4 w-4 mr-1" /> Add line</Button>}
    </div>
  );
};

export const cleanLines = (lines) => lines.map((l) => ({ description: String(l.description || "").trim(), hsn: l.hsn || "", unit: l.unit || "",
  qty: Number(l.qty || 0), rate: Number(l.rate || 0), discount: Number(l.discount || 0), gst_rate: Number(l.gst_rate || 0) }));
