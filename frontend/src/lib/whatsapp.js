import { api } from "@/lib/api";

const digits = (p) => {
  const d = (p || "").replace(/\D/g, "").replace(/^0+/, "");
  if (d.length === 10) return `91${d}`;
  return d.length >= 11 ? d : "";
};

export async function sendReminder(ledgerId, s = {}) {
  const w = window.open("about:blank", "_blank");
  try {
    const { data } = await api.post(`/reminders/${ledgerId}/send`);
    const link = `${window.location.origin}/pay/${data.token}`;
    const fmt = (n) => n.toLocaleString("en-IN", { minimumFractionDigits: 2 });
    const bills = data.bills.slice(0, 5).map((b) => `• ${b.voucher_no}${b.due_date ? ` (due ${b.due_date.split("-").reverse().join("-")})` : ""}: ₹${fmt(b.pending)}`);
    const lines = [
      `Dear ${data.customer},`,
      `This is a friendly reminder from *${data.company_name}*. Payment of *₹${fmt(data.overdue_amount)}* is overdue:`,
      ...bills, data.bills.length > 5 ? `...and ${data.bills.length - 5} more` : "",
      data.upi_id ? `Pay instantly by UPI: ${link}` : `View details: ${link}`,
      "Please ignore if already paid. Thank you!",
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
