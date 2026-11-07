import { api } from "@/lib/api";

const digits = (p) => {
  const d = (p || "").replace(/\D/g, "").replace(/^0+/, "");
  if (d.length === 10) return `91${d}`;
  return d.length >= 11 ? d : "";
};

export async function shareOnWhatsApp(v, s = {}) {
  const w = window.open("about:blank", "_blank");
  try {
    const { data } = await api.post(`/vouchers/${v.id}/share`);
    const link = `${window.location.origin}/i/${data.token}`;
    const total = (v.totals?.total || v.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 });
    const lines = [
      `Dear ${v.party_name},`,
      `Please find your invoice *${v.voucher_no}* dated ${v.date.split("-").reverse().join("-")} from *${s.company_name || ""}*.`,
      `Amount: *₹${total}*`,
      `View / download: ${link}`,
      s.upi_id ? `Pay by UPI: ${s.upi_id}` : "",
      "Thank you for your business!",
    ].filter(Boolean);
    const url = `https://wa.me/${digits(data.phone)}?text=${encodeURIComponent(lines.join("\n"))}`;
    if (w) w.location.href = url;
    else window.location.href = url;
    return url;
  } catch (e) {
    if (w) w.close();
    throw e;
  }
}
