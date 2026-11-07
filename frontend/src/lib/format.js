import { ShoppingCart, Truck, HandCoins, Wallet, ArrowLeftRight, BookOpen, FileMinus, FilePlus } from "lucide-react";

const nf = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const amt = (n) => nf.format(Number(n || 0));
export const inr = (n) => (Number(n) < 0 ? "-₹" : "₹") + amt(Math.abs(Number(n || 0)));
export const drcr = (n) => `${amt(Math.abs(n || 0))} ${Number(n || 0) >= 0 ? "Dr" : "Cr"}`;
export const dmy = (iso) => (iso ? iso.slice(0, 10).split("-").reverse().join("-") : "");
export const dmyTime = (iso) => (iso ? `${dmy(iso)} ${new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}` : "");

export function toIso(s) {
  const m = /^(\d{1,2})-(\d{1,2})-(\d{4})$/.exec((s || "").trim());
  if (!m) return null;
  const iso = `${m[3]}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}`;
  const d = new Date(iso + "T00:00:00");
  return isNaN(d) || d.getDate() !== Number(m[1]) ? null : iso;
}

export const isoOf = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export const todayIso = () => isoOf(new Date());

export const round2 = (n) => Math.round((Number(n) + Number.EPSILON) * 100) / 100;

export const VTYPES = [
  { key: "sales", label: "Sales", icon: ShoppingCart, hotkey: "s", color: "text-emerald-700 bg-emerald-50 border-emerald-200" },
  { key: "purchase", label: "Purchase", icon: Truck, hotkey: "p", color: "text-amber-700 bg-amber-50 border-amber-200" },
  { key: "receipt", label: "Receipt", icon: HandCoins, hotkey: "r", color: "text-teal-700 bg-teal-50 border-teal-200" },
  { key: "payment", label: "Payment", icon: Wallet, hotkey: "y", color: "text-rose-700 bg-rose-50 border-rose-200" },
  { key: "contra", label: "Contra", icon: ArrowLeftRight, hotkey: "c", color: "text-sky-700 bg-sky-50 border-sky-200" },
  { key: "journal", label: "Journal", icon: BookOpen, hotkey: "j", color: "text-indigo-700 bg-indigo-50 border-indigo-200" },
  { key: "debit_note", label: "Debit Note", icon: FileMinus, hotkey: null, color: "text-orange-700 bg-orange-50 border-orange-200" },
  { key: "credit_note", label: "Credit Note", icon: FilePlus, hotkey: null, color: "text-violet-700 bg-violet-50 border-violet-200" },
];
export const VT = Object.fromEntries(VTYPES.map((v) => [v.key, v]));
export const ITEM_TYPES = ["sales", "purchase", "credit_note", "debit_note"];

export const STATES = [
  "01-Jammu & Kashmir", "02-Himachal Pradesh", "03-Punjab", "04-Chandigarh", "05-Uttarakhand", "06-Haryana", "07-Delhi",
  "08-Rajasthan", "09-Uttar Pradesh", "10-Bihar", "11-Sikkim", "12-Arunachal Pradesh", "13-Nagaland", "14-Manipur",
  "15-Mizoram", "16-Tripura", "17-Meghalaya", "18-Assam", "19-West Bengal", "20-Jharkhand", "21-Odisha",
  "22-Chhattisgarh", "23-Madhya Pradesh", "24-Gujarat", "26-Dadra & Nagar Haveli and Daman & Diu", "27-Maharashtra",
  "29-Karnataka", "30-Goa", "31-Lakshadweep", "32-Kerala", "33-Tamil Nadu", "34-Puducherry",
  "35-Andaman & Nicobar Islands", "36-Telangana", "37-Andhra Pradesh", "38-Ladakh",
];
