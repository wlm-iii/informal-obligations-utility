import { useEffect, useState } from "react";
import { activePayments, loadLedgerHistory, money, utcDate } from "../services/dashboard";
import "./History.css";
export default function History({ friends, loans, demo }) {
 const [events, setEvents] = useState([]);
 const [error, setError] = useState("");
 const [loading, setLoading] = useState(!demo);
 const [retry,setRetry] = useState(0);
 useEffect(() => {
  if (demo) return;
  const controller = new AbortController(); setLoading(true); setError("");
  loadLedgerHistory(friends,controller.signal).then(data => {if(!controller.signal.aborted){setEvents(data);setLoading(false);}}).catch(e=>{if(!controller.signal.aborted){setError(e.message);setLoading(false);}});
  return ()=>controller.abort();
 },[friends,demo,retry]);
 const payments = [...activePayments(demo?.payments || events,loans)].sort((a,b)=>b.effective_at.localeCompare(a.effective_at));
 const records = loans.filter(loan => loan.status !== "voided");
 const settled = loan => loan.status === "completed";
 return <section className="payment-history">
  <section className="borrowing-records" aria-label="Borrowed and returned"><div className="records-heading"><h1>Borrowed and returned</h1></div>
   <div className="records-scroll"><table aria-label="Borrowing history"><thead><tr><th>Borrowed (UTC)</th><th>Type</th><th className="amount">Item/amount</th><th>Due</th><th>Status</th></tr></thead><tbody>{records.map(loan => <tr key={loan.id}><td>{utcDate(loan.lent_at)}</td><td>{loan.kind === "money" ? "Money" : "Item"}</td><td className="amount">{loan.kind === "money" ? money(loan.principal_cents) : loan.description}</td><td>{loan.due_date}</td><td><span className={`recorded-badge ${settled(loan) ? "" : "pending"}`}>{settled(loan) ? "paid/returned" : "unpaid/missing"}</span></td></tr>)}</tbody></table></div>
  </section>
  <section aria-label="Past payments"><div className="records-heading"><h2>Past payments</h2><span>{payments.length} RECORDS</span></div>
   {loading && <p role="status">Loading payment records…</p>}{error && <p role="alert">{error}<button onClick={()=>setRetry(v=>v+1)}>Retry history</button></p>}
   <div className="records-scroll"><table aria-label="Payment history"><thead><tr><th>Date (UTC)</th><th>Type</th><th className="amount">Item/amount</th><th>Status</th></tr></thead><tbody>{payments.map((payment,i) => {const loan = payment.loan || loans.find(l=>l.id===payment.loan_id); return <tr key={payment.id || i}><td>{utcDate(payment.effective_at)}</td><td>{loan?.kind === "item" ? "Item" : "Money"}</td><td className="amount">{loan?.kind === "item" ? loan.description : money(payment.amount_cents)}</td><td><span className="recorded-badge">paid/returned</span></td></tr>;})}</tbody></table></div>
   {!loading&&!error&&!payments.length&&<p className="trend-empty">No recorded payments yet.</p>}
  </section>
 </section>;
}
