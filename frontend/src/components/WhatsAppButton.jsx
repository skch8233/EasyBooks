import { toast } from "sonner";
import { MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { errMsg } from "@/lib/api";
import { shareOnWhatsApp } from "@/lib/whatsapp";

export const WhatsAppButton = ({ voucher, testid = "whatsapp-share-button", compact = false }) => {
  const { settings } = useApp();
  if (voucher?.voucher_type !== "sales" || voucher.status === "cancelled") return null;
  const share = async (e) => {
    e.stopPropagation();
    try { await shareOnWhatsApp(voucher, settings); } catch (err) { toast.error(errMsg(err)); }
  };
  if (compact) {
    return (
      <button onClick={share} title="Send on WhatsApp" data-testid={testid} className="inline-flex items-center justify-center h-8 w-8 rounded-md text-[#25D366] hover:bg-green-50">
        <MessageCircle className="h-4 w-4" />
      </button>
    );
  }
  return (
    <Button variant="outline" onClick={share} data-testid={testid} className="text-[#128C7E] border-[#25D366]/50 hover:bg-green-50">
      <MessageCircle className="h-4 w-4 mr-1" /> WhatsApp
    </Button>
  );
};
