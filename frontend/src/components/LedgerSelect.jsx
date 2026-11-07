import { useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { drcr } from "@/lib/format";

export const LedgerSelect = ({ ledgers, value, onChange, placeholder = "Select ledger", testid, groups }) => {
  const [open, setOpen] = useState(false);
  const list = groups ? ledgers.filter((l) => groups.includes(l.group)) : ledgers;
  const sel = ledgers.find((l) => l.id === value);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid={testid}
          className="flex h-11 w-full items-center justify-between rounded-md border border-input bg-white px-3 text-left text-sm hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <span className={sel ? "text-slate-900 truncate" : "text-slate-400"}>{sel ? sel.name : placeholder}</span>
          <ChevronsUpDown className="h-4 w-4 shrink-0 text-slate-400" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="p-0 w-[--radix-popover-trigger-width] min-w-[280px]" align="start">
        <Command filter={(v, s) => (v.toLowerCase().includes(s.toLowerCase()) ? 1 : 0)}>
          <CommandInput placeholder="Type to search..." data-testid={`${testid}-search`} />
          <CommandList>
            <CommandEmpty>No ledger found.</CommandEmpty>
            {list.map((l) => (
              <CommandItem
                key={l.id}
                value={`${l.name} ${l.id}`}
                data-testid={`${testid}-option-${l.name.toLowerCase().replace(/\s+/g, "-")}`}
                onSelect={() => { onChange(l.id); setOpen(false); }}
                className="flex items-center justify-between gap-2"
              >
                <span className="flex items-center gap-2 min-w-0">
                  <Check className={`h-4 w-4 ${value === l.id ? "opacity-100" : "opacity-0"}`} />
                  <span className="truncate">
                    {l.name}
                    <span className="block text-[11px] text-slate-500">{l.group_name}</span>
                  </span>
                </span>
                <span className="num text-xs text-slate-500 shrink-0">{drcr(l.balance_type === "Dr" ? l.balance : -l.balance)}</span>
              </CommandItem>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
};
