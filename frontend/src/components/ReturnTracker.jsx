import { useEffect, useState } from "react";
import { loadLoans, summarizeLoans } from "../services/loans";
import "./ReturnTracker.css";



export default function ReturnTracker() {
 const [summary, setSummary] = useState(null);
 const [error, setError] = useState("");
 const [revision, setRevision] = useState(0);
 useEffect(() => {
  const controller = new AbortController();
  loadLoans(controller.signal).then(loans => {
   if (!controller.signal.aborted) { setSummary(summarizeLoans(loans)); setError(""); }
  }).catch(error => {
   if (!controller.signal.aborted) { setSummary(null); setError(error.message); }
  });
  const refresh = () => { setSummary(null); setRevision(value => value + 1); };
  window.addEventListener("focus", refresh);
  return () => { controller.abort(); window.removeEventListener("focus", refresh); };
 }, [revision]);
 function refresh() { setSummary(null); setError(""); setRevision(value => value + 1); }
 if (!summary) return <section className="return-overview" aria-label="Return tracker"><p role="status">{error || "Loading your lending overview…"}</p>{error && <button onClick={refresh}>Retry lending data</button>}</section>;
 const total = summary.outstanding + summary.returned;
 const returnedPercent = total ? Math.round(summary.returned / total * 100) : 0;
 const circumference = 2 * Math.PI * 90;
 const categories = [
  { label: "Still lent out", count: summary.outstanding, color: "#D0A215" },
  { label: "Returned to you", count: summary.returned, color: "#879A39" },
 ];
 return <section className="return-overview" aria-labelledby="return-heading">
  <header className="return-heading"><div><p className="return-eyebrow">YOUR LENDING, AT A GLANCE</p><h2 id="return-heading">THE RETURN BREAKDOWN.</h2><p>A clearer picture of what is still out, and what made it back.</p></div><button className="return-sample" onClick={refresh}>Refresh data</button></header>
  <section className="return-panel" aria-labelledby="return-chart-heading">
   <h3 id="return-chart-heading">Still lent out vs. returned to you</h3><p className="return-description">The share of all items you have lent out that are still out or returned to you.</p>
   <div className="return-chart-area">
    <div className="return-chart-wrap"><svg viewBox="0 0 240 240" role="img" aria-labelledby="return-chart-title"><title id="return-chart-title">{total ? 100 - returnedPercent : 0}% still lent out; {returnedPercent}% returned to you.</title>
     <g transform="rotate(-90 120 120)"><circle cx="120" cy="120" r="90" fill="none" stroke={total ? "#879A39" : "#343331"} strokeWidth="28"/><circle cx="120" cy="120" r="90" fill="none" stroke="#D0A215" strokeWidth="28" strokeDasharray={`${(total ? summary.outstanding / total : 0) * circumference} ${circumference}`}/></g>
     <circle cx="120" cy="120" r="104" fill="none" stroke="#CECDC3" strokeWidth="1.5"/><circle cx="120" cy="120" r="76" fill="none" stroke="#CECDC3" strokeWidth="1.5"/>
    </svg><div className="return-chart-center" aria-hidden="true"><strong>{total ? `${returnedPercent}%` : "—"}</strong><span>{total ? "returned to you" : "No items lent yet"}</span></div></div>
   </div>
   <ul className="return-legend">{categories.map(category => <li key={category.label}><span className="return-category"><i style={{ background: category.color }} aria-hidden="true"/>{category.label}</span><span className="return-count">{category.count} items</span><strong>{total ? Math.round(category.count / total * 100) : 0}%</strong></li>)}</ul>
   <p className="return-chart-foot">{total} items lent in total · {summary.returned} returned + {summary.outstanding} still lent out.</p>
  </section>
  <div className="return-cards"><article><h3>UNPAID DEBTS</h3><strong>{summary.unpaid}</strong><p>Still on your tab</p></article><article><h3>REPAID DEBTS</h3><strong>{summary.repaid}</strong><p>Faith restored</p></article></div>
  <p className="return-note">Based on your private ledger. The chart counts item loans only; debt cards count all open or completed loans. Each item loan is counted as one item.</p>
 </section>;
}
