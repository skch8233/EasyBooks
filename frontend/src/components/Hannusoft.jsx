export const HannusoftMark = ({ size = 32, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" className={className} aria-hidden="true">
    <defs>
      <linearGradient id="hsg" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#EC1C7A" />
        <stop offset="100%" stopColor="#FF7A00" />
      </linearGradient>
    </defs>
    <circle cx="32" cy="32" r="30" fill="url(#hsg)" />
    <path d="M21 17h7v12h8V17h7v30h-7V35h-8v12h-7z" fill="#fff" />
  </svg>
);

export const HannusoftLogo = ({ size = 36, dark = false, className = "" }) => (
  <div className={`flex items-center gap-2 ${className}`} data-testid="hannusoft-logo">
    <HannusoftMark size={size} />
    <div className="leading-none">
      <div className="font-heading font-extrabold tracking-tight" style={{ fontSize: size * 0.55 }}>
        <span style={{ color: dark ? "#F8FAFC" : "#1B2A4A" }}>Hannu</span><span style={{ color: "#FF7A00" }}>soft</span>
      </div>
      <div className="uppercase font-semibold" style={{ fontSize: Math.max(size * 0.2, 7), letterSpacing: "0.32em", color: "#8A8F98" }}>Private Limited</div>
    </div>
  </div>
);

export const Copyright = ({ dark = false, className = "" }) => (
  <div className={`text-[11px] ${dark ? "text-slate-500" : "text-slate-500"} ${className}`} data-testid="copyright-text">
    © {new Date().getFullYear()} All rights reserved to Hannusoft Private Limited
  </div>
);

export const MadeBy = ({ dark = false }) => (
  <div className="space-y-2" data-testid="made-by-hannusoft">
    <div className={`text-[10px] uppercase tracking-widest ${dark ? "text-slate-500" : "text-slate-400"}`}>A product of</div>
    <HannusoftLogo size={28} dark={dark} />
    <Copyright dark={dark} />
  </div>
);
