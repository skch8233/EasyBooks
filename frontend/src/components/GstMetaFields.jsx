import { STATES } from "@/lib/format";
import { fillEmpty, useGstinAutofill } from "@/lib/gstin";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const F = [["place_of_supply", "Place of supply", "state"], ["reverse_charge", "Reverse charge (RCM)", "rcm"], ["transport_mode", "Transport mode (goods)"], ["eway_bill_no", "E-way bill no."],
  ["vehicle_no", "Vehicle / LR no."], ["contract_ref", "Contract / SOW ref. (services)"], ["billing_period", "Billing period (services)"], ["ship_name", "Consignee (ship to) name"],
  ["ship_gstin", "Consignee GSTIN"], ["ship_state", "Consignee state", "state"], ["ship_address", "Consignee address", "wide"]];

export const FormatPicker = ({ value, onChange, testid = "invoice-format" }) => (
  <div className="flex gap-2" data-testid={testid}>
    {[["goods", "Goods format (GST tax invoice)"], ["service", "Service provider format"]].map(([k, l]) =>
      <button type="button" key={k} onClick={() => onChange(k)} data-testid={`${testid}-${k}`}
        className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${value === k ? "bg-slate-900 text-white" : "bg-white"}`}>{l}</button>)}
  </div>
);

export const GstMetaFields = ({ value = {}, onChange, disabled, prefix = "gst-meta" }) => {
  const set = (k, v) => onChange({ ...value, [k]: k === "ship_gstin" ? v.toUpperCase() : v });
  useGstinAutofill(value.ship_gstin, (d) => onChange({ ...fillEmpty(value, { ship_name: d.name, ship_address: d.address }), ship_state: d.state || value.ship_state }));
  return (
    <details className="rounded-lg border bg-slate-50 p-3 sm:col-span-2" data-testid={`${prefix}-panel`}>
      <summary className="cursor-pointer text-sm font-semibold">GST invoice details (place of supply, reverse charge, transport, e-way bill, consignee)</summary>
      <div className="grid gap-3 sm:grid-cols-3 mt-3">
        {F.map(([k, l, t]) => <div key={k} className={`space-y-1 ${t === "wide" ? "sm:col-span-3" : ""}`}><Label className="text-xs">{l}</Label>
          {t === "state" ? <select disabled={disabled} className="h-10 w-full rounded-md border px-2 bg-white text-sm" value={value[k] || ""} onChange={(e) => set(k, e.target.value)} data-testid={`${prefix}-${k}`}>
            <option value="">{k === "place_of_supply" ? "Buyer's state (automatic)" : "Not set"}</option>{STATES.map((s) => <option key={s} value={s}>{s}</option>)}</select>
            : t === "rcm" ? <select disabled={disabled} className="h-10 w-full rounded-md border px-2 bg-white text-sm" value={value[k] || "no"} onChange={(e) => set(k, e.target.value)} data-testid={`${prefix}-${k}`}>
              <option value="no">No</option><option value="yes">Yes</option></select>
            : <Input disabled={disabled} className="h-10" value={value[k] || ""} onChange={(e) => set(k, e.target.value)} data-testid={`${prefix}-${k}`} />}</div>)}
      </div>
    </details>
  );
};
