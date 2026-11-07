import * as XLSX from "xlsx";
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

// sections: [{ title, columns: [{key,label,num}], rows: [{...}], footer: {...} }]
const cell = (v, num) => (num ? (v === "" || v == null ? "" : Number(v)) : v ?? "");
const pdfCell = (v, num) =>
  num ? (v === "" || v == null ? "" : new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2 }).format(v)) : String(v ?? "");

export function exportExcel(title, subtitle, sections) {
  const aoa = [[title], [subtitle], []];
  sections.forEach((s) => {
    if (s.title) aoa.push([s.title]);
    aoa.push(s.columns.map((c) => c.label));
    s.rows.forEach((r) => aoa.push(s.columns.map((c) => cell(r[c.key], c.num))));
    if (s.footer) aoa.push(s.columns.map((c) => cell(s.footer[c.key], c.num)));
    aoa.push([]);
  });
  const ws = XLSX.utils.aoa_to_sheet(aoa);
  ws["!cols"] = Array(8).fill({ wch: 20 });
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Report");
  XLSX.writeFile(wb, `${title.replace(/\s+/g, "_")}.xlsx`);
}

export function exportPdf(title, subtitle, sections, company) {
  const wide = sections.some((s) => s.columns.length > 6);
  const doc = new jsPDF({ orientation: wide ? "landscape" : "portrait", unit: "pt", format: "a4" });
  doc.setFontSize(14);
  doc.text(company || "Easy Books", 40, 40);
  doc.setFontSize(11);
  doc.text(`${title}  |  ${subtitle}  (Amounts in Rs.)`, 40, 58);
  let y = 72;
  sections.forEach((s) => {
    if (s.title) {
      doc.setFontSize(10);
      doc.text(s.title, 40, y + 12);
      y += 18;
    }
    autoTable(doc, {
      startY: y,
      head: [s.columns.map((c) => c.label)],
      body: s.rows.map((r) => s.columns.map((c) => pdfCell(r[c.key], c.num))),
      foot: s.footer ? [s.columns.map((c) => pdfCell(s.footer[c.key], c.num))] : undefined,
      styles: { fontSize: 8 },
      headStyles: { fillColor: [30, 58, 138] },
      footStyles: { fillColor: [226, 232, 240], textColor: 20 },
      columnStyles: Object.fromEntries(s.columns.map((c, i) => [i, c.num ? { halign: "right" } : {}])),
    });
    y = doc.lastAutoTable.finalY + 20;
  });
  doc.save(`${title.replace(/\s+/g, "_")}.pdf`);
}
