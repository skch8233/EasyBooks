import { CalendarClock, Users } from "lucide-react";
import { dmy } from "@/lib/format";

const LABEL = { trial: "Free Trial", active: "Active", expired: "Expired" };
const TONE = { trial: "bg-sky-50 border-sky-200 text-sky-900", active: "bg-emerald-50 border-emerald-200 text-emerald-900", expired: "bg-red-50 border-red-200 text-red-900" };

export const SubscriptionStatus = ({ biz }) => {
  if (!biz) return null;
  return (
    <div className={`rounded-xl border p-5 grid gap-4 sm:grid-cols-4 ${TONE[biz.status]}`} data-testid="subscription-status">
      <div><div className="text-xs font-semibold uppercase opacity-70">Status</div><div className="text-xl font-heading font-bold" data-testid="subscription-state">{LABEL[biz.status]}</div></div>
      <div><div className="text-xs font-semibold uppercase opacity-70">Plan</div><div className="text-lg font-semibold capitalize" data-testid="subscription-plan">{biz.plan === "basic" ? "Single User" : biz.plan === "pro" ? "Multi User" : "Trial"}</div></div>
      <div className="flex items-start gap-2"><CalendarClock className="h-5 w-5 mt-1 opacity-60" /><div><div className="text-xs font-semibold uppercase opacity-70">{biz.status === "expired" ? "Ended on" : "Valid till"}</div>
        <div className="font-mono font-semibold" data-testid="subscription-ends">{dmy(biz.ends_at)}</div>{biz.status !== "expired" && <div className="text-sm" data-testid="subscription-days-left">{biz.days_left} days left</div>}</div></div>
      <div className="flex items-start gap-2"><Users className="h-5 w-5 mt-1 opacity-60" /><div><div className="text-xs font-semibold uppercase opacity-70">Users</div><div className="font-semibold" data-testid="subscription-users">{biz.active_users} / {biz.max_users}</div></div></div>
    </div>
  );
};
