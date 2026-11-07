import { amt } from "@/lib/format";

export const ReportTable = ({ section, onRowClick, testid }) => (
  <div className="rounded-xl border bg-white overflow-x-auto print-area">
    {section.title && <div className="px-4 py-3 border-b font-heading font-semibold">{section.title}</div>}
    <table className="w-full eb-table" data-testid={testid}>
      <thead><tr>{section.columns.map((c) => <th key={c.key} className={c.num ? "!text-right" : ""}>{c.label}</th>)}</tr></thead>
      <tbody>
        {section.rows.length === 0 && <tr><td colSpan={section.columns.length} className="text-center text-slate-500 py-10">No data for this period.</td></tr>}
        {section.rows.map((r, i) => (
          <tr key={i} onClick={() => r.voucher_id && onRowClick?.(r.voucher_id)} className={`${r._bold ? "font-semibold" : ""} ${r.voucher_id ? "cursor-pointer" : ""}`}>
            {section.columns.map((c) => (
              <td key={c.key} className={`${c.num ? "text-right num" : ""} ${["date", "voucher_no", "balance", "gstin"].includes(c.key) ? "font-mono text-xs" : ""} whitespace-pre`}>
                {c.num ? (r[c.key] === "" || r[c.key] == null ? "" : amt(r[c.key])) : r[c.key]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
      {section.footer && (
        <tfoot><tr>{section.columns.map((c) => <td key={c.key} className={c.num ? "text-right num" : ""}>{c.num ? (section.footer[c.key] == null ? "" : amt(section.footer[c.key])) : section.footer[c.key]}</td>)}</tr></tfoot>
      )}
    </table>
  </div>
);
