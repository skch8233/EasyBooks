import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Download, ExternalLink, FileJson } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { amt, dmy, STATES, todayIso } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fillEmpty, useGstinAutofill } from "@/lib/gstin";

const PORTAL = "https://ewaybillgst.gov.in/";
const UQC = { nos: "NOS", no: "NOS", pcs: "PCS", pc: "PCS", kg: "KGS", kgs: "KGS", mtr: "MTR", m: "MTR", ltr: "LTR", l: "LTR", box: "BOX", bag: "BAG", bags: "BAG", sqft: "SQF", sqm: "SQM", ton: "TON", mt: "MTS", set: "SET", rmt: "MTR", cum: "CBM" };
const stCode = (s) => { const h = STATES.find((x) => x === s || x.slice(3).toLowerCase() === String(s || "").toLowerCase()); return h ? Number(h.slice(0, 2)) : 0; };
const SUB = [[1, "Supply"], [3, "Export"], [4, "Job Work"], [5, "For Own Use"], [8, "Others"]];
const MODES = [["1", "Road"], ["2", "Rail"], ["3", "Air"], ["4", "Ship"]];
const blankForm = { supplyType: "O", subSupplyType: 1, docType: "INV", docNo: "", docDate: todayIso(), fromPincode: "", fromPlace: "", toName: "", toGstin: "", toAddr: "", toPlace: "", toPincode: "", toState: "", shipState: "",
  transMode: "1", transDistance: "", transporterId: "", transporterName: "", vehicleNo: "", vehicleType: "R", transDocNo: "", transDocDate: "", items: [], totals: { taxable: 0, cgst: 0, sgst: 0, igst: 0, total: 0 } };

const hsnNum = (h) => Number(String(h || "").replace(/\D/g, "")) || 0;
const mainHsn = (items) => { const by = {}; items.forEach((i) => { by[i.hsn] = (by[i.hsn] || 0) + Number(i.taxable || 0); }); return Object.entries(by).sort((a, b) => b[1] - a[1])[0]?.[0] || ""; };

export function buildEwayJson(f, s) {
  const d = (x) => (x ? dmy(x).replace(/-/g, "/") : "");
  const ft = stCode(s.state), tt = stCode(f.toState), at = stCode(f.shipState) || tt, intra = ft && ft === tt;
  return { version: "1.0.0621", billLists: [{
    userGstin: s.gstin, supplyType: f.supplyType, subSupplyType: Number(f.subSupplyType), subSupplyDesc: "", docType: f.docType, docNo: f.docNo, docDate: d(f.docDate),
    fromGstin: s.gstin, fromTrdName: s.company_name, fromAddr1: (s.address || "").slice(0, 120), fromAddr2: "", fromPlace: f.fromPlace, fromPincode: Number(f.fromPincode), fromStateCode: ft, actualFromStateCode: ft,
    toGstin: f.toGstin || "URP", toTrdName: f.toName, toAddr1: (f.toAddr || "").slice(0, 120), toAddr2: "", toPlace: f.toPlace, toPincode: Number(f.toPincode), toStateCode: tt, actualToStateCode: at,
    transType: 1, totalValue: f.totals.taxable, cgstValue: f.totals.cgst, sgstValue: f.totals.sgst, igstValue: f.totals.igst, cessValue: 0, TotNonAdvolVal: 0, OthValue: 0, totInvValue: f.totals.total,
    transporterId: f.transporterId, transporterName: f.transporterName, transDocNo: f.transDocNo, transMode: f.transMode, transDistance: String(f.transDistance || 0), transDocDate: d(f.transDocDate),
    vehicleNo: f.vehicleNo.replace(/\s|-/g, "").toUpperCase(), vehicleType: f.vehicleType, mainHsnCode: hsnNum(mainHsn(f.items)),
    itemList: f.items.map((i, n) => ({ itemNo: n + 1, productName: i.description.split("\n")[0].slice(0, 100), productDesc: i.description.slice(0, 100), hsnCode: hsnNum(i.hsn),
      quantity: Number(i.qty || 0), qtyUnit: UQC[String(i.unit || "").toLowerCase()] || "NOS", taxableAmount: i.taxable, sgstRate: intra ? i.gst_rate / 2 : 0, cgstRate: intra ? i.gst_rate / 2 : 0, igstRate: intra ? 0 : i.gst_rate, cessRate: 0, cessNonAdvol: 0 })),
  }] };
}

export function validateEway(f, s) {
  const e = [];
  if (!/^[0-9]{2}[A-Z0-9]{13}$/.test(s.gstin || "")) e.push("Add a valid company GSTIN in Settings");
  if (!stCode(s.state)) e.push("Set your company state in Settings");
  if (!f.docNo) e.push("Document number is required");
  if (!/^\d{6}$/.test(f.fromPincode)) e.push("From pincode must be 6 digits");
  if (!/^\d{6}$/.test(f.toPincode)) e.push("To pincode must be 6 digits");
  if (!f.toName) e.push("Recipient name is required");
  if (!stCode(f.toState)) e.push("Select the recipient state");
  if (f.toGstin && !/^[0-9]{2}[A-Z0-9]{13}$/.test(f.toGstin)) e.push("Recipient GSTIN is not valid (leave blank for unregistered)");
  if (!(Number(f.transDistance) > 0 && Number(f.transDistance) <= 4000)) e.push("Approximate distance must be 1 to 4000 km");
  if (f.transMode === "1" && !f.transporterId && !/^([A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}|[0-9]{2}BH[0-9]{4}[A-Z]{1,2}|TM[0-9]{6}|TR[0-9A-Z]{6,13})$/.test(f.vehicleNo.replace(/\s|-/g, "").toUpperCase())) e.push("Enter a vehicle number (e.g. MH12AB1234) or a transporter ID");
  if (!f.items.length) e.push("Add at least one item");
  if (f.items.some((i) => !String(i.hsn || "").replace(/\D/g, ""))) e.push("Every item needs an HSN code");
  return e;
}

const Field = ({ l, children }) => <div className="space-y-1"><Label className="text-xs">{l}</Label>{children}</div>;

export default function EwayBill() {
  const { settings, canWrite } = useApp();
  const [src, setSrc] = useState({ vouchers: [], invoices: [] });
  const [pick, setPick] = useState("");
  const [f, setF] = useState(blankForm);
  const [list, setList] = useState([]);
  const [ewb, setEwb] = useState({});
  const loadList = () => api.get("/eway-bills").then((r) => setList(r.data));
  useEffect(() => {
    loadList();
    Promise.all([api.get("/vouchers", { params: { voucher_type: "sales", status: "active", limit: 300 } }).then((r) => r.data).catch(() => []),
      api.get("/erp/invoices", { params: { status: "finalized" } }).then((r) => r.data).catch(() => [])]).then(([vouchers, invoices]) => setSrc({ vouchers, invoices }));
  }, []);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  useGstinAutofill(f.toGstin, (d) => setF((x) => ({ ...fillEmpty(x, { toName: d.name, toAddr: d.address }), toState: d.state || x.toState })));
  const choose = async (val) => {
    setPick(val);
    if (!val) return setF(blankForm);
    const [kind, id] = val.split(":");
    const meta = (m = {}) => ({ vehicleNo: m.vehicle_no || "", transMode: { road: "1", rail: "2", air: "3", ship: "4" }[String(m.transport_mode || "").toLowerCase()] || "1" });
    if (kind === "v") {
      const { data: v } = await api.get(`/vouchers/${id}`);
      const { data: leds } = await api.get("/ledgers", { params: { include_inactive: true } });
      const p = leds.find((l) => l.id === v.party_ledger_id) || {};
      const m = v.gst_meta || {};
      setF({ ...blankForm, source: "voucher", source_id: v.id, docNo: v.voucher_no, docDate: v.date, toName: v.party_name, toGstin: p.gstin || "",
        toAddr: m.ship_name ? m.ship_address || "" : p.address || "", toState: p.state || "", shipState: m.ship_state || p.state || "", ...meta(m),
        items: v.items.map((i) => ({ ...i, taxable: i.amount })), totals: v.totals });
    } else {
      const { data: d } = await api.get(`/erp/invoices/${id}`);
      const c = d.client || {}, m = d.gst_meta || {};
      setF({ ...blankForm, source: "erp_invoice", source_id: d.id, docNo: d.number, docDate: d.date, toName: c.company_name, toGstin: c.gstin || "",
        toAddr: m.ship_name ? m.ship_address || "" : c.address || "", toState: c.state || "", shipState: m.ship_state || c.state || "", toPlace: d.project_location || "", ...meta(m),
        items: d.items.map((i) => ({ ...i, taxable: i.amount })), totals: d.totals });
    }
  };
  const errors = validateEway(f, settings || {});
  const generate = async () => {
    if (errors.length) return toast.error(errors[0]);
    const json = buildEwayJson(f, settings);
    const blob = new Blob([JSON.stringify(json, null, 2)], { type: "application/json" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `EWB_${f.docNo.replace(/[^\w-]/g, "_")}.json`; a.click();
    try { await api.post("/eway-bills", { source: f.source || "manual", source_id: f.source_id || null, data: json.billLists[0], ewb_json: json }); toast.success("E-way bill JSON downloaded. Upload it on the e-way bill portal."); loadList(); } catch (e) { toast.error(errMsg(e)); }
  };
  const saveNo = async (e) => {
    const no = (ewb[e.id] || "").trim();
    if (!/^\d{12}$/.test(no)) { toast.error("E-way bill number must be exactly 12 digits"); return; }
    try { await api.put(`/eway-bills/${e.id}/number`, { ewb_no: (ewb[e.id] || "").trim(), ewb_date: todayIso() }); toast.success("E-way bill number saved on the invoice"); loadList(); } catch (er) { toast.error(errMsg(er)); }
  };
  const redownload = (e) => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(e.ewb_json, null, 2)], { type: "application/json" })); a.download = `EWB_${e.doc_no}.json`; a.click(); };
  const big = f.totals.total >= 50000;
  return (
    <div className="space-y-6" data-testid="eway-bill-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="font-heading text-3xl font-extrabold tracking-tight">E-way Bill</h1>
          <p className="text-slate-500 mt-1">Prepare the e-way bill from an invoice, download the JSON and upload it on the government portal (Generate New EWB → Bulk Upload).</p></div>
        <a href={PORTAL} target="_blank" rel="noreferrer" data-testid="eway-portal-link"><Button variant="outline"><ExternalLink className="h-4 w-4 mr-1" /> Open e-way bill portal</Button></a>
      </div>
      <div className="rounded-xl border bg-white p-5 space-y-4">
        <Field l="Prefill from invoice">
          <select className="h-11 w-full rounded-md border px-3 bg-white text-sm" value={pick} onChange={(e) => choose(e.target.value)} data-testid="eway-source-select">
            <option value="">Enter manually / choose an invoice</option>
            <optgroup label="Sales vouchers">{src.vouchers.map((v) => <option key={v.id} value={`v:${v.id}`}>{v.voucher_no} · {v.party_name} · ₹{amt(v.amount)}</option>)}</optgroup>
            <optgroup label="ERP invoices">{src.invoices.map((i) => <option key={i.id} value={`e:${i.id}`}>{i.number} · {i.client_name} · ₹{amt(i.totals.total)}</option>)}</optgroup>
          </select></Field>
        <div className="grid gap-3 sm:grid-cols-4">
          <Field l="Supply type"><select className="h-10 w-full rounded-md border px-2 bg-white text-sm" value={f.supplyType} onChange={set("supplyType")} data-testid="eway-supply-type"><option value="O">Outward</option><option value="I">Inward</option></select></Field>
          <Field l="Sub type"><select className="h-10 w-full rounded-md border px-2 bg-white text-sm" value={f.subSupplyType} onChange={set("subSupplyType")} data-testid="eway-sub-type">{SUB.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
          <Field l="Document type"><select className="h-10 w-full rounded-md border px-2 bg-white text-sm" value={f.docType} onChange={set("docType")} data-testid="eway-doc-type"><option value="INV">Tax Invoice</option><option value="BIL">Bill of Supply</option><option value="CHL">Delivery Challan</option></select></Field>
          <Field l="Document no. / date"><div className="flex gap-1"><Input className="h-10 font-mono" value={f.docNo} onChange={set("docNo")} data-testid="eway-doc-no" /><Input type="date" className="h-10 w-40" value={f.docDate} onChange={set("docDate")} data-testid="eway-doc-date" /></div></Field>
          <Field l="Dispatch from - place"><Input className="h-10" value={f.fromPlace} onChange={set("fromPlace")} data-testid="eway-from-place" /></Field>
          <Field l="Dispatch from - pincode"><Input className="h-10 font-mono" maxLength={6} value={f.fromPincode} onChange={set("fromPincode")} data-testid="eway-from-pincode" /></Field>
          <Field l="Recipient name"><Input className="h-10" value={f.toName} onChange={set("toName")} data-testid="eway-to-name" /></Field>
          <Field l="Recipient GSTIN (blank = URP)"><Input className="h-10 font-mono uppercase" maxLength={15} value={f.toGstin} onChange={(e) => setF({ ...f, toGstin: e.target.value.toUpperCase() })} data-testid="eway-to-gstin" /></Field>
          <div className="sm:col-span-2"><Field l="Ship to address"><Input className="h-10" value={f.toAddr} onChange={set("toAddr")} data-testid="eway-to-address" /></Field></div>
          <Field l="Ship to place"><Input className="h-10" value={f.toPlace} onChange={set("toPlace")} data-testid="eway-to-place" /></Field>
          <Field l="Ship to pincode"><Input className="h-10 font-mono" maxLength={6} value={f.toPincode} onChange={set("toPincode")} data-testid="eway-to-pincode" /></Field>
          <Field l="Recipient (bill to) state"><select className="h-10 w-full rounded-md border px-2 bg-white text-sm" value={f.toState} onChange={set("toState")} data-testid="eway-to-state"><option value="">Select</option>{STATES.map((s) => <option key={s} value={s}>{s}</option>)}</select></Field>
          <Field l="Ship to state (actual)"><select className="h-10 w-full rounded-md border px-2 bg-white text-sm" value={f.shipState} onChange={set("shipState")} data-testid="eway-ship-state"><option value="">Select</option>{STATES.map((s) => <option key={s} value={s}>{s}</option>)}</select></Field>
          <Field l="Transport mode"><select className="h-10 w-full rounded-md border px-2 bg-white text-sm" value={f.transMode} onChange={set("transMode")} data-testid="eway-mode">{MODES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
          <Field l="Approx. distance (km)"><Input type="number" className="h-10 font-mono" value={f.transDistance} onChange={set("transDistance")} data-testid="eway-distance" /></Field>
          <Field l="Vehicle no."><Input className="h-10 font-mono uppercase" value={f.vehicleNo} onChange={set("vehicleNo")} data-testid="eway-vehicle" /></Field>
          <Field l="Transporter ID (GSTIN / TRANSIN)"><Input className="h-10 font-mono uppercase" value={f.transporterId} onChange={(e) => setF({ ...f, transporterId: e.target.value.toUpperCase() })} data-testid="eway-transporter-id" /></Field>
          <Field l="Transporter name"><Input className="h-10" value={f.transporterName} onChange={set("transporterName")} data-testid="eway-transporter-name" /></Field>
          <Field l="Transport doc / LR no."><Input className="h-10" value={f.transDocNo} onChange={set("transDocNo")} data-testid="eway-lr-no" /></Field>
          <Field l="Transport doc date"><Input type="date" className="h-10" value={f.transDocDate} onChange={set("transDocDate")} data-testid="eway-lr-date" /></Field>
        </div>
        <div className="overflow-x-auto"><table className="w-full eb-table text-sm" data-testid="eway-items"><thead><tr><th>Item</th><th>HSN</th><th className="text-right">Qty</th><th>Unit</th><th className="text-right">Taxable</th><th className="text-right">GST %</th></tr></thead>
          <tbody>{f.items.length === 0 && <tr><td colSpan={6} className="text-center py-6 text-slate-500">Choose an invoice above to load items.</td></tr>}
            {f.items.map((i, n) => <tr key={n}><td>{i.description}</td><td className="font-mono">{i.hsn || <span className="text-red-600">missing</span>}</td><td className="text-right">{i.qty}</td><td>{UQC[String(i.unit || "").toLowerCase()] || "NOS"}</td><td className="text-right font-mono">{amt(i.taxable)}</td><td className="text-right">{i.gst_rate}%</td></tr>)}</tbody>
          <tfoot><tr className="font-semibold"><td colSpan={4}>Invoice value (taxable {amt(f.totals.taxable)} + GST {amt(f.totals.cgst + f.totals.sgst + f.totals.igst)})</td><td colSpan={2} className="text-right font-mono" data-testid="eway-total">₹{amt(f.totals.total)}</td></tr></tfoot></table></div>
        {f.items.length > 0 && !big && <div className="text-xs text-slate-500" data-testid="eway-threshold-note">Consignment value is below ₹50,000 - an e-way bill is usually optional (check your state's rules).</div>}
        {errors.length > 0 && f.items.length > 0 && <ul className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800 list-disc list-inside" data-testid="eway-errors">{errors.map((e) => <li key={e}>{e}</li>)}</ul>}
        {canWrite && <Button onClick={generate} disabled={!f.items.length} data-testid="eway-generate-button"><FileJson className="h-4 w-4 mr-1" /> Download e-way bill JSON</Button>}
      </div>
      <div className="rounded-xl border bg-white overflow-x-auto">
        <div className="px-4 py-3 font-semibold">Prepared e-way bills</div>
        <table className="w-full eb-table text-sm" data-testid="eway-list"><thead><tr><th>Document</th><th>Recipient</th><th className="text-right">Value</th><th>Prepared</th><th>E-way bill no.</th><th></th></tr></thead>
          <tbody>{list.length === 0 && <tr><td colSpan={6} className="text-center py-6 text-slate-500">None yet.</td></tr>}
            {list.map((e) => <tr key={e.id} data-testid={`eway-row-${e.doc_no}`}><td className="font-mono">{e.doc_no}</td><td>{e.data?.toTrdName}</td><td className="text-right font-mono">{amt(e.data?.totInvValue)}</td><td>{dmy(e.created_at?.slice(0, 10))}</td>
              <td>{e.ewb_no ? <b className="font-mono" data-testid={`eway-number-${e.doc_no}`}>{e.ewb_no}</b> : canWrite && <div className="flex gap-1"><Input className="h-9 w-40 font-mono" maxLength={12} placeholder="12-digit EWB no." value={ewb[e.id] || ""} onChange={(x) => setEwb({ ...ewb, [e.id]: x.target.value })} data-testid={`eway-number-input-${e.doc_no}`} />
                <Button size="sm" variant="outline" onClick={() => saveNo(e)} data-testid={`eway-number-save-${e.doc_no}`}>Save</Button></div>}</td>
              <td><Button size="sm" variant="ghost" onClick={() => redownload(e)} data-testid={`eway-redownload-${e.doc_no}`}><Download className="h-4 w-4" /></Button></td></tr>)}</tbody></table>
      </div>
    </div>
  );
}
