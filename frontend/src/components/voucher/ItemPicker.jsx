import { useState } from "react";
import { ChevronsUpDown, Package, PenLine } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";

export const ItemPicker = ({ stock, item, onPick, onText, testid }) => {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const sel = stock.find((s) => s.id === item.item_id);
  const label = sel ? sel.name : item.description;

  return (
    <Popover open={open} onOpenChange={(o) => { setOpen(o); if (o) setQ(item.item_id ? "" : item.description); }}>
      <PopoverTrigger asChild>
        <button type="button" data-testid={testid} className="flex h-11 w-full items-center justify-between gap-2 rounded-md border border-input bg-white px-3 text-left text-sm hover:border-slate-400">
          <span className={`truncate ${label ? "" : "text-slate-400"}`}>{label || "Select stock item or type"}</span>
          {sel && <span className={`num text-[11px] shrink-0 ${sel.on_hand <= 0 ? "text-red-600" : "text-slate-500"}`}>{sel.on_hand} {sel.unit}</span>}
          <ChevronsUpDown className="h-4 w-4 shrink-0 text-slate-400" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="p-0 w-[--radix-popover-trigger-width] min-w-[300px]" align="start">
        <Command filter={(v, s) => (v.toLowerCase().includes(s.toLowerCase()) ? 1 : 0)}>
          <CommandInput placeholder="Search item..." value={q} onValueChange={setQ} data-testid={`${testid}-search`} />
          <CommandList>
            <CommandEmpty>No stock item found.</CommandEmpty>
            {q.trim() && (
              <CommandGroup>
                <CommandItem value={`__text ${q}`} onSelect={() => { onText(q.trim()); setOpen(false); }} data-testid={`${testid}-use-text`}>
                  <PenLine className="h-4 w-4 mr-2" /> Use "{q.trim()}" (not tracked in stock)
                </CommandItem>
              </CommandGroup>
            )}
            <CommandGroup heading="Stock items">
              {stock.map((s) => (
                <CommandItem key={s.id} value={`${s.name} ${s.hsn} ${s.id}`} onSelect={() => { onPick(s); setOpen(false); }}
                  data-testid={`${testid}-option-${s.name.toLowerCase().replace(/\s+/g, "-")}`} className="flex justify-between gap-2">
                  <span className="flex items-center gap-2 min-w-0"><Package className="h-4 w-4 text-slate-400" /><span className="truncate">{s.name}<span className="block text-[11px] text-slate-500">HSN {s.hsn || "-"} · GST {s.gst_rate}%</span></span></span>
                  <span className={`num text-xs shrink-0 ${s.on_hand <= 0 ? "text-red-600" : s.low ? "text-amber-600" : "text-slate-500"}`}>{s.on_hand} {s.unit}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
};
