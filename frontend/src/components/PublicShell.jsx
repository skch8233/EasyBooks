import { Link } from "react-router-dom";
import { BookMarked } from "lucide-react";
import { Button } from "@/components/ui/button";
import { HannusoftLogo, Copyright } from "@/components/Hannusoft";

export const PublicShell = ({ children }) => (
  <div className="min-h-screen bg-white flex flex-col">
    <header className="sticky top-0 z-20 border-b bg-white/90 backdrop-blur">
      <div className="max-w-6xl mx-auto flex items-center gap-3 px-5 h-16">
        <Link to="/welcome" className="flex items-center gap-3"><div className="h-9 w-9 rounded-lg bg-emerald-500 flex items-center justify-center"><BookMarked className="h-5 w-5 text-white" /></div>
          <span className="font-heading text-xl font-extrabold">Easy Books</span></Link>
        <nav className="ml-auto flex items-center gap-1">
          <Link to="/download" className="hidden sm:inline px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900" data-testid="nav-download">Download</Link>
          <Link to="/buy" className="hidden sm:inline px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900" data-testid="nav-buy">Buy</Link>
          <Link to="/login"><Button variant="ghost" data-testid="nav-signin">Sign in</Button></Link>
          <Link to="/signup"><Button data-testid="nav-trial">Free trial</Button></Link>
        </nav>
      </div>
    </header>
    <main className="flex-1">{children}</main>
    <footer className="border-t"><div className="max-w-6xl mx-auto px-5 py-8 flex flex-wrap items-center justify-between gap-4"><HannusoftLogo size={34} /><Copyright className="!text-sm" /></div></footer>
  </div>
);
