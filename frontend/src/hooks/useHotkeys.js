import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { VTYPES } from "@/lib/format";

export function useHotkeys(enabled) {
  const nav = useNavigate();
  useEffect(() => {
    if (!enabled) return;
    const h = (e) => {
      if (!e.altKey || e.ctrlKey || e.metaKey) return;
      const t = VTYPES.find((v) => v.hotkey && v.hotkey === e.key.toLowerCase());
      if (t) { e.preventDefault(); nav(`/voucher/${t.key}`); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [enabled, nav]);
}
