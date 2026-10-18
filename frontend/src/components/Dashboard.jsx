import { useEffect, useRef, useState } from "react";
import Progress from "./Progress";
import AddFriendForm from "./AddFriendForm";
import EmailReminder from "./EmailReminder";
import { interestLabel, itemReturned, percentToBps, totalOutstanding } from "../services/interest";
import { amountToCents } from "../services/repayments";
import History from "./History";
import Leaderboards from "./Leaderboards";
import { loadLoans } from "../services/loans";
import { applyDemoPayment, ledgerRequest, loadFriends, money, reminderFor, reminderTones } from "../services/dashboard";
import "./Dashboard.css";
import "./ReferenceTheme.css";

function Modal({ title, onClose, children, busy = false }) {
 const ref = useRef(null);
 useEffect(() => { const previous = document.activeElement; ref.current.showModal(); return () => previous?.focus(); }, []);
 return <dialog ref={ref} className="dash-modal" onCancel={event => { event.preventDefault(); if (!busy) onClose(); }} aria-label={title}><button className="close-modal" aria-label="Close dialog" disabled={busy} onClick={onClose}>×</button><h2>{title}</h2>{children}</dialog>;
}

export default function Dashboard({ account, profile, demo, accountError }) {
 const [payments, setPayments] = useState(demo?.payments || []);
 const [recording, setRecording] = useState(false);
 const repaymentKey = useRef(null);
 const [view, setView] = useState("Dashboard");
 const [friends, setFriends] = useState(demo?.friends || []);
 const [rawLoans, setLoans] = useState(demo?.loans || []);
 const loans = rawLoans.filter(loan => loan.status !== "voided");
 useEffect(() => {
  const timer = setInterval(() => { if (!demo) setRevision(v => v + 1); }, 60000);
  return () => clearInterval(timer);
 }, [demo]);
 const [loading, setLoading] = useState(!demo);
 const [error, setError] = useState("");
 const [revision, setRevision] = useState(0);
 const [search, setSearch] = useState("");
 const [selected, setSelected] = useState(null);
 const [nudge, setNudge] = useState(null);
 const [nudgeBusy, setNudgeBusy] = useState(false);
 const [tone, setTone] = useState("Friendly");
 const [message, setMessage] = useState("");
 const [copyStatus, setCopyStatus] = useState("");
 const [adding, setAdding] = useState(false);
 const [busy, setBusy] = useState(false);
 const [settling, setSettling] = useState(null);
 const settlementLock = useRef(false);
 const settlementKeys = useRef(new Map());
 const friendKey = useRef(null);
 const loanKey = useRef(null);
 const savedFriend = useRef(null);
 const draft = useRef(null);
 const submitting = useRef(false);
 const activeCount = id => loans.filter(l => l.friend_id === id && l.status === "open").length;
 const avatarStyle = id => ({ "--avatar-bg": ["#DDF1E4", "#D2E7F2", "#E2D9F1", "#FAEEC6", "#FFE7CE", "#FFE1D5"][Math.min(activeCount(id), 5)], "--avatar-ink": ["#24837B", "#205EA6", "#5E409D", "#806000", "#9D4310", "#942822"][Math.min(activeCount(id), 5)] });
 useEffect(() => {
  if (demo) return;
  const controller = new AbortController();
  setLoading(true); setError("");
  Promise.all([loadFriends(controller.signal), loadLoans(controller.signal)]).then(([people, records]) => {
   if (!controller.signal.aborted) { setFriends(people); setLoans(records); setLoading(false); }
  }).catch(e => { if (!controller.signal.aborted) { setError(e.message); setLoading(false); } });
  return () => controller.abort();
 }, [demo, revision]);
 const person = id => friends.find(friend => friend.id === id) || { display_name: "Archived friend", id };
 const navigate = tab => { setView(tab); setSelected(null); };
 const openNudge = loan => { setNudgeBusy(false); setNudge(loan); setTone("Friendly"); setMessage(reminderFor(person(loan.friend_id), loan, "Friendly")); setCopyStatus(""); };
 async function copy() {
  try { await navigator.clipboard.writeText(message); setCopyStatus("Reminder copied."); }
  catch { setCopyStatus("Copy unavailable. Select and copy the reminder text manually."); }
 }
 async function addFriend(event) {
  event.preventDefault();
  if (submitting.current || !event.currentTarget.checkValidity()) return;
  submitting.current = true; setBusy(true); setError("");
  try {
   if (!draft.current) {
    const data = new FormData(event.currentTarget);
    const kind = data.get("type") === "amount" ? "money" : "item";
    const rate = kind === "money" ? percentToBps(data.get("interest") || "0") : 0;
    if (demo && rate) throw new Error("Offline samples do not calculate interest. Use the signed-in tracker for interest-bearing loans.");
    draft.current = {body:{display_name:data.get("name").trim(),email:data.get("email").trim()},
     terms:{kind,description:kind === "item" ? data.get("item").trim() : "Money lent",due_date:data.get("due_date"),
      repayment_type:data.get("repayment_type"),repayment_other:data.get("repayment_type") === "other" ? data.get("repayment_other").trim() : null,
      ...(kind === "money" ? {principal_cents:amountToCents(String(data.get("amount"))),interest_rate_bps:rate,interest_period:data.get("interest_period")} : {})}};
   }
   const {body,terms} = draft.current;
   const {kind,principal_cents:cents} = terms;
   const friend = savedFriend.current || (demo ? { ...body, id: crypto.randomUUID() } : await ledgerRequest("/friends", { body, key: friendKey.current }));
   if (!savedFriend.current) { savedFriend.current = friend; setFriends(previous => [friend, ...previous]); }
   const loan = demo ? { ...terms, id: crypto.randomUUID(), friend_id: friend.id, lent_at: new Date().toISOString(), status: "open", overdue: false, repaid_cents: kind === "money" ? 0 : null, outstanding_cents: kind === "money" ? cents : null } : await ledgerRequest("/loans", { body: { ...terms, friend_id: friend.id }, key: loanKey.current });
   setLoans(previous => [loan, ...previous]); setAdding(false); savedFriend.current = null; draft.current = null;
  } catch (e) { setError(`${e.message}${savedFriend.current ? " Your friend was saved; retry to finish adding their IOU." : ""}`); }
  finally { submitting.current = false; setBusy(false); }
 }
 async function settleLoan(loan) {
  if (settlementLock.current) return;
  settlementLock.current = true; setSettling(loan.id); setError("");
  const action = loan.kind === "money" ? "repayments" : itemReturned(loan) ? "fee-payments" : "return";
  if (!settlementKeys.current.has(loan.id)) settlementKeys.current.set(loan.id,
   {key:crypto.randomUUID(),path:`/loans/${loan.id}/${action}`,body:action === "return" ? {} : {amount_cents:totalOutstanding(loan)}});
  try {
   const at = new Date().toISOString();
   let settled;
   if (demo) {
    settled = action === "return" ? {...loan,returned_at:at,borrowing_status:"returned",overdue:false,status:totalOutstanding(loan) ? "open" : "completed",completed_at:totalOutstanding(loan) ? null : at} : applyDemoPayment(loan,totalOutstanding(loan));
    if (action !== "return") setPayments(previous => [...previous, {id:crypto.randomUUID(),loan_id:loan.id,description:loan.description,action:action === "fee-payments" ? "fee_payment" : "repayment",amount_cents:totalOutstanding(loan),effective_at:at}]);
   } else {
    const result = await ledgerRequest(settlementKeys.current.get(loan.id).path, settlementKeys.current.get(loan.id));
    settled = result.loan;
   }
   setLoans(previous => previous.map(record => record.id === loan.id ? settled : record));
   settlementKeys.current.delete(loan.id);
   if (settled.status === "completed") navigate("History");
   else setError("The borrowing or charges remain open. Review the current balance before the next action.");
  } catch (e) { setError(e.message); }
  finally { settlementLock.current = false; setSettling(null); }
 }
 async function recordRepayment(event) {
  event.preventDefault(); const form = new FormData(event.currentTarget); const loan = loans.find(l => l.id === form.get("loan"));
  const text = String(form.get("amount"));
  if (!/^\d+(\.\d{1,2})?$/.test(text)) {setError("Enter a valid amount with at most two decimal places.");return;}
  const [dollars, fraction = ""] = text.split("."); const cents = Number(dollars) * 100 + Number(fraction.padEnd(2,"0"));
  if (!loan || cents <= 0 || cents > totalOutstanding(loan)) {setError("Enter an amount no greater than the outstanding balance.");return;}
  setBusy(true);setError("");
  try {
   if (demo) {
    setLoans(previous=>previous.map(l=>l.id===loan.id?applyDemoPayment(l,cents):l));
    setPayments(previous=>[...previous,{id:crypto.randomUUID(),loan_id:loan.id,description:loan.description,action:"repayment",amount_cents:cents,effective_at:new Date().toISOString()}]);
   } else {await ledgerRequest(`/loans/${loan.id}/repayments`,{body:{amount_cents:cents},key:repaymentKey.current});setRevision(v=>v+1);}
   setRecording(false);
  } catch(e){setError(e.message);} finally{setBusy(false);}
 }
 const activeLoans = loans.filter(loan => loan.status === "open");
 const filtered = activeLoans.filter(loan => `${person(loan.friend_id).display_name} ${loan.description}`.toLowerCase().includes(search.toLowerCase()));
 const ownLoans = selected ? loans.filter(loan => loan.friend_id === selected.id) : loans;
 function history(records) {
  return <div className="history-list">{[...records].sort((a,b) => String(b.lent_at).localeCompare(String(a.lent_at))).map(loan => <article key={loan.id}><span className={`status-pill ${loan.status}`}>{itemReturned(loan) ? (loan.status === "open" ? "Returned / fees unpaid" : "Returned") : loan.status === "completed" ? "Repaid" : "Not returned / open"}</span><h3>{loan.description}</h3><p>{person(loan.friend_id).display_name} · Borrowed {String(loan.lent_at).slice(0,10)} · Due {loan.due_date}</p>{loan.completed_at || loan.returned_at ? <p>Completed {String(loan.completed_at || loan.returned_at).slice(0,10)}</p> : null}</article>)}{!records.length && <p>No borrowing history yet.</p>}</div>;
 }
 return <div className="home-dashboard">
  <header className="dash-top"><button className="dash-logo" aria-label="IOU dashboard" onClick={() => navigate("Dashboard")}>I<span>O</span>U</button><button className="add-friend" aria-label="Add friend" onClick={() => { friendKey.current = crypto.randomUUID(); loanKey.current = crypto.randomUUID(); savedFriend.current = null; draft.current = null; setError(""); setAdding(true); }}>+</button><button className="account-link" onClick={() => navigate("Account")}>{profile?.display_name || "Your account"} ↗</button></header>
  <aside className="friend-sidebar"><p className="tiny-label">YOUR CIRCLE <span>{friends.length}</span></p><nav aria-label="Friends">{friends.map(friend => <button key={friend.id} className={selected?.id === friend.id ? "selected" : ""} onClick={() => { setSelected(friend); setView("Profile"); }}><span className="friend-avatar" style={avatarStyle(friend.id)}>{friend.display_name.slice(0,1)}</span><span>{friend.display_name}<small>{loans.filter(loan => loan.friend_id === friend.id && loan.status === "open").length} Active IOU&apos;s</small></span></button>)}</nav></aside>
  <div className="dash-main"><nav className="dash-tabs" aria-label="Main navigation">{["Dashboard", "Progress", "Ranks", "History"].map(tab => <button key={tab} aria-current={view === tab ? "page" : undefined} onClick={() => navigate(tab)}>{tab}</button>)}</nav>
   {loading && <p role="status">Loading your ledger…</p>}
   {error && !adding && <div role="alert">{error}<button onClick={() => setRevision(v => v + 1)}>Retry ledger</button></div>}
   {view === "Dashboard" && <section aria-label="IOU Tracker"><div className="ledger-heading"><div><p className="tiny-label">Friendship Tabs</p><h1>IOU Tracker<span className="record-count">{activeLoans.length}</span></h1><p className="tracker-tagline">Hold your friends accountable. Don’t let it slide. Get repaid.</p></div><input aria-label="Search counterparty" placeholder="Search counterparty…" value={search} onChange={e => setSearch(e.target.value)}/></div><div className="ledger-labels"><span>COUNTERPARTY / MEMO</span><span>ITEM / AMOUNT OWED</span><span>DUE DATE</span><span>INTEREST</span><span>OPERATIONS</span></div><div className="ledger-rows">{filtered.map(loan => <article className={`ledger-row ${loan.overdue && loan.status === "open" ? "is-overdue" : ""}`} key={loan.id}><div className="counterparty"><span className="friend-avatar" style={avatarStyle(loan.friend_id)}>{person(loan.friend_id).display_name[0]}</span><div><button className="person-link" onClick={() => { setSelected(person(loan.friend_id)); setView("Profile"); }}>{person(loan.friend_id).display_name}</button><p>{loan.description}</p><small className={loan.overdue ? "overdue" : ""}>{loan.status === "completed" ? "✓ Position closed" : itemReturned(loan) ? "Returned · fees remain" : loan.overdue ? "Overdue · the plot thickens" : "Still lent out"} · {loan.due_date}</small></div></div><div className="loan-balance"><strong>{loan.kind === "money" ? money(totalOutstanding(loan)) : itemReturned(loan) ? `Returned · ${money(totalOutstanding(loan))} fees` : "1 item"}</strong><small>{loan.kind === "money" ? `${money(loan.repaid_cents)} repaid · ${money(loan.principal_cents)} original` : loan.description}</small>{loan.repayment_type && <small className="iou-terms">Repay: {loan.repayment_type === "other" ? loan.repayment_other : loan.repayment_type}</small>}</div><div className="iou-due" data-label="Due date"><time dateTime={loan.due_date}>{loan.due_date}</time></div><div className="iou-interest" data-label="Interest"><strong>{loan.kind === "item" ? "—" : money(loan.interest_cents)}</strong><small>{interestLabel(loan)}</small></div><div className="iou-operations"><button disabled={settling !== null} onClick={() => openNudge(loan)}>Nudge ↗</button><button className="settle-iou" disabled={settling !== null} onClick={() => settleLoan(loan)}>{settling === loan.id ? "Settling…" : "Settle"}</button></div></article>)}</div>{!loading && !error && !filtered.length && <p className="empty-ledger">{search ? "No matching Active IOU's." : "Your ledger is clear. Add a friend to start your circle."}</p>}<footer className="ledger-footer">USD DENOMINATED. EMOTIONALLY COMPLICATED.<span>{activeLoans.length} active records · private to you</span></footer></section>}
   {view === "Progress" && <Progress loans={loans} friends={friends} demo={demo ? { ...demo, payments } : undefined} onRefresh={() => setRevision(v => v + 1)} onRecord={() => { repaymentKey.current = crypto.randomUUID(); setError(""); setRecording(true); }} onNudge={() => { const loan = loans.find(l => l.status === "open"); if (loan) openNudge(loan); else setError("No Active IOU's to remind anyone about."); }}/>}
   {view === "Ranks" && <Leaderboards/>}
   {view === "History" && <History friends={friends} loans={loans} demo={demo ? { ...demo, payments } : undefined}/>}
   {view === "Profile" && selected && <section className="friend-profile"><button onClick={() => navigate("Dashboard")}>← Back to ledger</button><div className="profile-heading"><span className="friend-avatar large" style={avatarStyle(selected.id)}>{selected.display_name[0]}</span><div><p className="tiny-label">FRIEND PROFILE</p><h1>{selected.display_name}</h1><p>{selected.email || "No email added"}</p></div></div><p>{selected.notes || "No notes added yet."}</p><div className="friend-stats"><article><small>Active IOU&apos;s</small><strong>{ownLoans.filter(l => l.status === "open").length}</strong></article><article><small>Financially settled</small><strong>{ownLoans.filter(l => l.status === "completed").length}</strong></article><article><small>Outstanding</small><strong>{money(ownLoans.reduce((sum,l) => sum + totalOutstanding(l),0))}</strong></article></div><h2>Borrowing history</h2>{history(ownLoans)}</section>}
   {view !== "Account" && accountError && <div role="alert">{accountError}<button onClick={() => navigate("Account")}>Open account</button></div>}
   {view === "Account" && <section className="friend-profile" aria-label="Your profile"><button onClick={() => navigate("Dashboard")}>← Back to ledger</button><div className="profile-heading"><span className="friend-avatar large">{(profile?.display_name || "You")[0]}</span><div><p className="tiny-label">YOUR PROFILE</p><h1>{profile?.display_name || "Your account"}</h1><p>{profile?.email || "Your private IOU account"}</p></div></div><div className="friend-stats account-stats"><article><small>Friends</small><strong>{friends.filter(friend => !friend.archived_at).length}</strong></article><article><small>Money outstanding</small><strong>{money(loans.filter(l => l.kind === "money").reduce((sum,l) => sum + totalOutstanding(l),0))}</strong></article><article><small>Money repaid</small><strong>{money(loans.filter(l => l.kind === "money").reduce((sum,l) => sum + (l.repaid_cents || 0),0))}</strong></article><article><small>Items still out</small><strong>{loans.filter(l => l.kind === "item" && !itemReturned(l)).length}</strong></article><article><small>Items returned</small><strong>{loans.filter(l => l.kind === "item" && itemReturned(l)).length}</strong></article></div><h2>Borrowing history</h2>{history(loans)}<h2>Account settings</h2>{account}</section>}
  </div>
  {nudge && <Modal title={demo ? "Diplomatic communications." : "Email reminder"} busy={nudgeBusy} onClose={() => { setNudge(null); setNudgeBusy(false); }}>
   {demo ? <><label htmlFor="nudge-tone">Tone</label><select id="nudge-tone" value={tone} onChange={e => { setTone(e.target.value); setMessage(reminderFor(person(nudge.friend_id), nudge, e.target.value)); setCopyStatus(""); }}>{reminderTones.map(t => <option key={t}>{t}</option>)}</select><label htmlFor="nudge-message">Reminder</label><textarea id="nudge-message" rows={6} value={message} onChange={e => { setMessage(e.target.value); setCopyStatus(""); }}/><button className="primary-action" onClick={copy}>Copy reminder ↗</button><p role="status">{copyStatus}</p><small>Offline demo: clipboard only. Sign in and open Tracker to preview and approve a real email.</small></> :
    <EmailReminder key={nudge.friend_id} friend={person(nudge.friend_id)}
     eligible={loans.some(loan => loan.friend_id === nudge.friend_id && loan.status === "open" && (totalOutstanding(loan) > 0 || (loan.kind === "item" && !itemReturned(loan))))}
     onBusyChange={setNudgeBusy} />}
  </Modal>}
  {recording && <Modal title="Record repayment" onClose={() => !busy && setRecording(false)}><form onSubmit={recordRepayment}><label htmlFor="repayment-loan">Active IOU&apos;s</label><select id="repayment-loan" name="loan" required>{loans.filter(l=>l.kind==="money"&&l.status==="open").map(l=><option key={l.id} value={l.id}>{person(l.friend_id).display_name} – {l.description} ({money(totalOutstanding(l))} remaining)</option>)}</select><label htmlFor="repayment-amount">Amount (USD)</label><input id="repayment-amount" name="amount" inputMode="decimal" required placeholder="0.00"/>{error && <p role="alert">{error}</p>}<button disabled={busy || !loans.some(l=>l.kind==="money"&&l.status==="open")} className="primary-action">{busy?"Recording…":"Record payment"}</button></form></Modal>}
  {adding && <Modal title="Add to your circle" onClose={() => !busy && setAdding(false)}><AddFriendForm onSubmit={addFriend} busy={busy} error={error} friendSaved={!!savedFriend.current} locked={!!draft.current}/></Modal>}
 </div>;
}
