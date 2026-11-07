import { useEffect, useState } from "react";
import { CalendarDays } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import { dmy, toIso, isoOf } from "@/lib/format";

export const DateInput = ({ value, onChange, testid, className = "" }) => {
  const [text, setText] = useState(dmy(value));
  const [open, setOpen] = useState(false);
  useEffect(() => setText(dmy(value)), [value]);

  const commit = () => {
    const iso = toIso(text);
    if (iso) onChange(iso);
    else setText(dmy(value));
  };

  return (
    <div className={`relative ${className}`}>
      <Input
        data-testid={testid}
        value={text}
        placeholder="DD-MM-YYYY"
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === "Enter" && commit()}
        className="h-11 pr-10 font-mono"
      />
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button type="button" data-testid={`${testid}-picker`} className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded text-slate-500 hover:bg-slate-100">
            <CalendarDays className="h-4 w-4" />
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="end">
          <Calendar
            mode="single"
            selected={value ? new Date(value + "T00:00:00") : undefined}
            defaultMonth={value ? new Date(value + "T00:00:00") : undefined}
            onSelect={(d) => { if (d) { onChange(isoOf(d)); setOpen(false); } }}
          />
        </PopoverContent>
      </Popover>
    </div>
  );
};
