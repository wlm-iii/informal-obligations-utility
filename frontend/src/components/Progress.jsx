import { useEffect, useState } from "react";
import { activePayments, loadLedgerHistory, money, utcDate } from "../services/dashboard";
import "./Progress.css";
import { totalOutstanding } from "../services/interest";

export default function Progress({ loans, friends, demo, onRefresh, onRecord, onNudge }) {
 const [events, setEvents] = useState([]);
 const [error, setError] = useState("");
 const [loading, setLoading] = useState(!demo);
 const [range, setRange] = useState("ALL");
 const [revision, setRevision] = useState(0);
 useEffect(() => {
  if (demo) return;
  const controller = new AbortController();
  setLoading(true); setError("");
  loadLedgerHistory(friends, controller.signal).then(pages => { if (!controller.signal.aborted) { setEvents(pages); setLoading(false); } })
   .catch(e => { if (!controller.signal.aborted) { setError(e.message); setLoading(false); } });
  return () => controller.abort();
 }, [friends, demo, revision]);
 const validLoans = loans.filter(l => l.status !== "voided");
 const allPayments = activePayments(demo?.payments || events, validLoans);
 const cutoff = range === "ALL" ? -Infinity : Date.now() - Number(range) * 86400000;
 const payments = [...allPayments].filter(e => new Date(e.effective_at).getTime() >= cutoff && new Date(e.effective_at).getTime() <= Date.now()).sort((a,b) => a.effective_at.localeCompare(b.effective_at));
 const moneyLoans = validLoans.filter(l => l.kind === "money");
 const repaid = validLoans.reduce((sum,l) => sum + (l.kind === "money" ? l.repaid_cents || 0 : l.fees_paid_cents || 0),0);
 const outstanding = validLoans.reduce((sum,l) => sum + totalOutstanding(l),0);
 const principal = moneyLoans.reduce((sum,l) => sum + (l.principal_cents || 0),0);
 const waived = validLoans.reduce((sum,l) => sum + (l.interest_waived_cents || 0) + (l.fees_waived_cents || 0),0);
 const gross = repaid + outstanding + waived;
 const percent = gross ? Math.min(100,Math.round(repaid / gross * 100)) : 0;
 const periodTotal = payments.reduce((sum,e) => sum + (e.amount_cents || 0),0);
 let cumulative = 0;
 const values = payments.map(e => ({ date: e.effective_at, value: cumulative += e.amount_cents || 0 }));
 const max = Math.max(periodTotal, 100);
 const first = values.length ? new Date(values[0].date).getTime() - 86400000 : 0;
 const last = values.length ? Math.max(new Date(values.at(-1).date).getTime(), Date.now()) : 1;
 const points = values.map(p => ({ x: first === last ? 410 : 60 + (new Date(p.date).getTime()-first)/(last-first)*700, y: 250 - p.value/max*200 }));
 const line = points.length ? `60,250 ${points.map(p => `${p.x},${p.y}`).join(" ")} 780,${points.at(-1).y}` : "";
 const refresh = () => { onRefresh(); setRevision(v => v + 1); };
 return <section className="progress-page" aria-labelledby="progress-heading">
  <header className="progress-heading"><h1 id="progress-heading">Your lending, at a glance</h1><button onClick={refresh}>Refresh data</button></header>
  <section className="progress-summary" aria-label="Repayment progress"><p className="progress-kicker">REPAYMENT PROGRESS</p><div className="progress-summary-line"><strong>{percent}% of recorded balance repaid</strong><small>{money(repaid)} repaid / {money(outstanding)} remaining</small></div><progress max="100" value={percent} aria-label="Recorded balance repaid"/><div className="progress-actions"><button className="record-payment" onClick={onRecord}>Record repayment</button><button onClick={onNudge}>Draft reminder</button>{demo && <small>Try it out. Demo changes reset when you reload.</small>}</div></section>
  <div className="repayment-stats"><article><small>REPAID IN PERIOD</small><strong>{money(periodTotal)}</strong><p>{payments.length} recorded payments</p></article><article><small>STILL OWES YOU</small><strong>{money(outstanding)}</strong><p>Current balance – all time</p></article><article><small>TOTAL LENT</small><strong>{money(principal)}</strong><p>{moneyLoans.filter(l => l.status === "open").length} Active IOU&apos;s (money) – all time</p></article></div>
  <section className="trend-panel" aria-labelledby="trend-heading"><div className="trend-heading"><div><p className="progress-kicker">01 / REPAYMENT TREND</p><h2 id="trend-heading">Cumulative repayments</h2><p>Cumulative repayments – USD – dates in UTC</p></div><div className="trend-ranges" role="group" aria-label="Repayment period">{["30","90","ALL"].map(r => <button key={r} aria-pressed={range === r} onClick={() => setRange(r)}>{r === "ALL" ? r : `${r}D`}</button>)}</div></div><div className="trend-legend"><span>● Amount repaid</span><strong>{money(periodTotal)}</strong></div>
   {loading ? <p role="status">Loading repayment history…</p> : error ? <p role="alert">{error}</p> : !values.length ? <p className="trend-empty">No recorded repayments in this period.</p> : <svg className="repayment-trend" viewBox="0 0 800 290" role="img" aria-label={`${money(periodTotal)} repaid across ${payments.length} payments`}><defs><linearGradient id="repayment-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#198356" stopOpacity=".18"/><stop offset="100%" stopColor="#198356" stopOpacity=".01"/></linearGradient></defs>{[0,1,2,3,4].map(n => <g key={n}><line x1="60" x2="780" y1={250-n*50} y2={250-n*50} stroke="#D8E6D8" strokeDasharray="3 5"/><text x="48" y={254-n*50} textAnchor="end">{money(max*n/4)}</text></g>)}<polygon points={`60,250 ${line} 780,250`} fill="url(#repayment-fill)"/><polyline points={line} fill="none" stroke="#198356" strokeWidth="2"/>{points.map((p,i) => <circle key={i} cx={p.x} cy={p.y} r="4" fill="#FCFEF9" stroke="#198356" strokeWidth="2"><title>{values[i].date.slice(0,10)}: {money(values[i].value)}</title></circle>)}<text x="60" y="280">{utcDate(first)}</text><text x="780" y="280" textAnchor="end">{utcDate(last)}</text></svg>}
   <footer><span>Recorded repayments only</span><span>Reversed payments and voided Active IOU&apos;s excluded</span></footer></section>
 </section>;
}
