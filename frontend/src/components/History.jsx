import { useEffect, useState } from "react";
import { loadLedgerHistory, money, utcDate } from "../services/dashboard";
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
 const payments = [...(demo?.payments || events.filter(e => e.action === "repayment"))].sort((a,b)=>b.effective_at.localeCompare(a.effective_at));
 return <section className="payment-history"><div className="records-heading"><div><p className="progress-kicker">02 / PAYMENT RECORDS</p><h1>Past payments</h1></div><span>{payments.length} RECORDS</span></div>
 {loading && <p role="status">Loading payment records…</p>}{error && <p role="alert">{error}<button onClick={()=>setRetry(v=>v+1)}>Retry history</button></p>}
 <div className="records-scroll"><table><thead><tr><th>Date (UTC)</th><th>For</th><th className="amount">Amount</th><th>Status</th></tr></thead><tbody>{payments.map((payment,i)=>{const loan=payment.loan || loans.find(l=>l.id===payment.loan_id);return <tr key={payment.id || i}><td>{utcDate(payment.effective_at)}</td><td>{payment.description || loan?.description || "Active IOU repayment"} <span className="record-help" title={loan ? `IOU: ${loan.description}` : "Recorded IOU repayment"} aria-label="Payment details">?</span></td><td className="amount">{money(payment.amount_cents)}</td><td><span className="recorded-badge">Recorded</span></td></tr>;})}</tbody></table></div>
 {!loading&&!error&&!payments.length&&<p className="trend-empty">No recorded payments yet.</p>}
 <section className="borrowing-records"><div className="records-heading"><div><p className="progress-kicker">03 / BORROWING HISTORY</p><h2>Borrowed and returned</h2></div></div><div className="records-scroll"><table><thead><tr><th>Borrowed (UTC)</th><th>For</th><th>Due</th><th>Status</th></tr></thead><tbody>{loans.map(loan=><tr key={loan.id}><td>{utcDate(loan.lent_at)}</td><td>{loan.description}</td><td>{loan.due_date}</td><td><span className={`recorded-badge ${loan.status === "open" ? "pending" : ""}`}>{loan.status === "open" ? "Not returned / open" : loan.kind === "item" ? "Returned" : "Repaid"}</span></td></tr>)}</tbody></table></div></section>
 </section>;
}
