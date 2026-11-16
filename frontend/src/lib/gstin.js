import { useEffect, useRef } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { STATES } from "@/lib/format";

export const stateFromCode = (code) => STATES.find((s) => s.startsWith(`${code}-`)) || "";

// Calls onFill(fields) once for each newly entered valid GSTIN; fields only fill what is empty
export function useGstinAutofill(gstin, onFill) {
  const last = useRef("");
  const cb = useRef(onFill);
  cb.current = onFill;
  useEffect(() => {
    const g = (gstin || "").trim().toUpperCase();
    if (g.length !== 15) { last.current = ""; return; }
    if (g === last.current) return;
    last.current = g;
    api.get(`/gstin/${g}`).then(({ data }) => {
      if (!data.valid) { toast.error(data.error); return; }
      const s = data.saved || {};
      cb.current({ state: s.state || stateFromCode(data.state_code), pan: data.pan, name: s.name, address: s.address, phone: s.phone, email: s.email, contact_person: s.contact_person, source: s.source, id: s.id, ledger_id: s.ledger_id }, !!data.saved);
      toast.success(data.saved ? `Saved details for ${s.name} filled in` : `State (${data.state_name}) and PAN filled from the GSTIN`);
    }).catch(() => {});
  }, [gstin]);
}

export const fillEmpty = (obj, map) => {
  const out = { ...obj };
  Object.entries(map).forEach(([k, v]) => { if (v && !String(out[k] || "").trim()) out[k] = v; });
  return out;
};
