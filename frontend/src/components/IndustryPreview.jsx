const Row = ({ a, b, c, tone = "" }) => (
  <div className="flex items-center justify-between rounded-lg bg-white/5 px-4 py-2.5 text-sm"><span className="text-slate-300">{a}</span><span className="text-slate-400 text-xs">{b}</span><span className={`num font-semibold ${tone}`}>{c}</span></div>
);
const PREVIEWS = {
  retail: { title: "POS Billing · Counter 1", rows: [["Tata Salt 1kg", "2 × ₹28", "₹56.00"], ["Amul Butter 100g", "1 × ₹58", "₹58.00"], ["Parle-G 250g", "4 × ₹25", "₹100.00"]], total: ["Bill total (incl. GST)", "₹214.00"], foot: "Low stock: Parle-G 250g (4 left)" },
  college: { title: "Fee Collection · B.Com 2026-29", rows: [["Aarav Sharma · BC-001", "Term 1", "₹15,000.00"], ["Diya Patel · BC-002", "Term 1 + fine", "₹15,120.00"], ["Kabir Singh · BC-003", "Due 15 Dec", "₹15,000.00"]], total: ["Collected this month", "₹4,82,500.00"], foot: "Payroll: 18 staff · ₹6,42,000 posted" },
  hospital: { title: "OPD Billing · Dr. Mehta", rows: [["UHID/0142 · Ramesh K.", "Consultation", "₹500.00"], ["UHID/0143 · Sita D.", "Lab: CBC, LFT", "₹1,250.00"], ["UHID/0144 · Arjun P.", "Pharmacy", "₹386.00"]], total: ["Today's collection", "₹38,940.00"], foot: "2 batches expire in 60 days" },
  wholesale: { title: "GST Tax Invoice · INV/2026-27/0418", rows: [["Sharma Traders (27AAP…1ZV)", "120 boxes", "₹1,44,000.00"], ["CGST 9% + SGST 9%", "", "₹25,920.00"], ["E-way bill JSON", "Ready", "✓"]], total: ["Invoice value", "₹1,69,920.00"], foot: "Sales register · GSTR-1 updated" },
  services: { title: "Retainer Billing · November", rows: [["Acme Pvt Ltd", "Monthly SEO", "₹45,000.00"], ["Zen Clinics", "Social media", "₹30,000.00"], ["TDS 194J deducted", "10%", "-₹7,500.00"]], total: ["Received net of TDS", "₹67,500.00"], foot: "3 recurring bills generated today" },
};

export const IndustryPreview = ({ k }) => {
  const p = PREVIEWS[k];
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-5 space-y-2.5 shadow-2xl" data-testid={`industry-preview-${k}`}>
      <div className="flex items-center gap-2 pb-2"><span className="h-2.5 w-2.5 rounded-full bg-red-400" /><span className="h-2.5 w-2.5 rounded-full bg-amber-300" /><span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
        <span className="ml-2 text-xs font-semibold text-slate-300">{p.title}</span></div>
      {p.rows.map((r) => <Row key={r[0]} a={r[0]} b={r[1]} c={r[2]} tone={r[2].startsWith("-") ? "text-red-400" : "text-white"} />)}
      <div className="flex items-center justify-between rounded-lg bg-emerald-500/15 px-4 py-3"><span className="text-sm text-emerald-200">{p.total[0]}</span><span className="num text-xl font-semibold text-emerald-400">{p.total[1]}</span></div>
      <div className="text-xs text-amber-200/80 pt-1">{p.foot}</div>
    </div>
  );
};
