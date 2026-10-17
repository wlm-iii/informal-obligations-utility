import { useEffect, useRef, useState } from "react";
import ReturnTracker from "./ReturnTracker";
import Leaderboards from "./Leaderboards";
import { loadLoans } from "../services/loans";
import { ledgerRequest, loadFriends, money, reminderFor } from "../services/dashboard";
import "./Dashboard.css";

function Modal({ title, onClose, children }) {
 const ref = useRef(null);
 useEffect(() => { const previous = document.activeElement; ref.current.showModal(); return () => previous?.focus(); }, []);
 return <dialog ref={ref} className="dash-modal" onCancel={onClose} aria-label={title}><button className="close-modal" aria-label="Close dialog" onClick={onClose}>×</button><h2>{title}</h2>{children}</dialog>;
}

export default function Dashboard({ account, profile, demo, accountError }) {
 const [view, setView] = useState("Dashboard");
 const [friends, setFriends] = useState(demo?.friends || []);
 const [loans, setLoans] = useState(demo?.loans || []);
 const [loading, setLoading] = useState(!demo);
 const [error, setError] = useState("");
 const [revision, setRevision] = useState(0);
 const [search, setSearch] = useState("");
 const [selected, setSelected] = useState(null);
 const [nudge, setNudge] = useState(null);
 const [tone, setTone] = useState("Sweet bestie");
 const [message, setMessage] = useState("");
 const [copyStatus, setCopyStatus] = useState("");
 const [adding, setAdding] = useState(false);
 const [busy, setBusy] = useState(false);
 const friendKey = useRef(null);
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
 const openNudge = loan => { setNudge(loan); setTone("Sweet bestie"); setMessage(reminderFor(person(loan.friend_id), loan, "Sweet bestie")); setCopyStatus(""); };
 async function copy() {
  try { await navigator.clipboard.writeText(message); setCopyStatus("Reminder copied."); }
  catch { setCopyStatus("Copy unavailable. Select and copy the reminder text manually."); }
 }
 async function addFriend(event) {
  event.preventDefault(); setBusy(true); setError("");
  const data = new FormData(event.currentTarget);
  const body = { display_name: data.get("name").trim(), email: data.get("email").trim() || null, notes: data.get("notes").trim() || null };
  try {
   const friend = demo ? { ...body, id: crypto.randomUUID() } : await ledgerRequest("/friends", { body, key: friendKey.current });
   setFriends(previous => [friend, ...previous]); setAdding(false);
  } catch (e) { setError(e.message); }
  finally { setBusy(false); }
 }
 const filtered = loans.filter(loan => `${person(loan.friend_id).display_name} ${loan.description}`.toLowerCase().includes(search.toLowerCase()));
 const ownLoans = selected ? loans.filter(loan => loan.friend_id === selected.id) : loans;
 function history(records) {
  return <div className="history-list">{[...records].sort((a,b) => String(b.lent_at).localeCompare(String(a.lent_at))).map(loan => <article key={loan.id}><span className={`status-pill ${loan.status}`}>{loan.status === "completed" ? (loan.kind === "item" ? "Returned" : "Repaid") : "Not returned / open"}</span><h3>{loan.description}</h3><p>{person(loan.friend_id).display_name} · Borrowed {String(loan.lent_at).slice(0,10)} · Due {loan.due_date}</p>{loan.completed_at || loan.returned_at ? <p>Completed {String(loan.completed_at || loan.returned_at).slice(0,10)}</p> : null}</article>)}{!records.length && <p>No borrowing history yet.</p>}</div>;
 }
 return <div className="home-dashboard">
  <header className="dash-top"><button className="dash-logo" aria-label="IOU dashboard" onClick={() => navigate("Dashboard")}>I<span>O</span>U</button><button className="add-friend" aria-label="Add friend" onClick={() => { friendKey.current = crypto.randomUUID(); setError(""); setAdding(true); }}>+</button><button className="account-link" onClick={() => navigate("Account")}>{profile?.display_name || "Your account"} ↗</button></header>
  <aside className="friend-sidebar"><p className="tiny-label">YOUR CIRCLE <span>{friends.length}</span></p><nav aria-label="Friends">{friends.map(friend => <button key={friend.id} className={selected?.id === friend.id ? "selected" : ""} onClick={() => { setSelected(friend); setView("Profile"); }}><span className="friend-avatar">{friend.display_name.slice(0,1)}</span><span>{friend.display_name}<small>{loans.filter(loan => loan.friend_id === friend.id && loan.status === "open").length} open loans</small></span></button>)}</nav><p className="sidebar-footer">A little clarity.<br/>A lot less awkward.</p></aside>
  <div className="dash-main"><nav className="dash-tabs" aria-label="Main navigation">{["Dashboard", "Progress", "Ranks", "History"].map(tab => <button key={tab} aria-current={view === tab ? "page" : undefined} onClick={() => navigate(tab)}>{tab}</button>)}</nav>
   {demo && <p className="demo-banner">Interactive preview · sample records · changes stay in this preview session</p>}
   {loading && <p role="status">Loading your ledger…</p>}
   {error && !adding && <div role="alert">{error}<button onClick={() => setRevision(v => v + 1)}>Retry ledger</button></div>}
   {view === "Dashboard" && <section aria-label="Debt ledger"><div className="ledger-heading"><div><p className="tiny-label">YOUR PRIVATE LEDGER</p><h1>The debt ledger<span className="record-count">{loans.length}</span></h1></div><input aria-label="Search counterparty" placeholder="Search counterparty…" value={search} onChange={e => setSearch(e.target.value)}/></div><div className="ledger-labels"><span>COUNTERPARTY / MEMO</span><span>OPEN BALANCE</span><span>OPERATIONS</span></div><div className="ledger-rows">{filtered.map(loan => <article className="ledger-row" key={loan.id}><div className="counterparty"><span className="friend-avatar">{person(loan.friend_id).display_name[0]}</span><div><button className="person-link" onClick={() => { setSelected(person(loan.friend_id)); setView("Profile"); }}>{person(loan.friend_id).display_name}</button><p>{loan.description}</p><small className={loan.overdue ? "overdue" : ""}>{loan.status === "completed" ? "✓ Position closed" : loan.overdue ? "Overdue · the plot thickens" : "Still lent out"} · {loan.due_date}</small></div></div><div className="loan-balance"><strong>{loan.kind === "money" ? money(loan.outstanding_cents) : loan.status === "completed" ? "Returned" : "1 item"}</strong><small>{loan.kind === "money" ? `${money(loan.repaid_cents)} repaid of ${money(loan.principal_cents)}` : loan.description}</small></div><div>{loan.status === "open" && <button onClick={() => openNudge(loan)}>Nudge ↗</button>}</div></article>)}</div>{!loading && !error && !filtered.length && <p className="empty-ledger">{search ? "No matching loans." : "Your ledger is clear. Add a friend to start your circle."}</p>}<footer className="ledger-footer">USD DENOMINATED. EMOTIONALLY COMPLICATED.<span>{loans.length} records · private to you</span></footer></section>}
   {view === "Progress" && <ReturnTracker previewLoans={demo?.loans}/>}
   {view === "Ranks" && <Leaderboards/>}
   {view === "History" && <section><p className="tiny-label">YOUR ACCOUNT HISTORY</p><h1>Borrowed. Returned. Remembered.</h1><p className="muted">Loans recorded in your private ledger: who borrowed, what remains open, and what came back.</p>{history(loans)}</section>}
   {view === "Profile" && selected && <section className="friend-profile"><button onClick={() => navigate("Dashboard")}>← Back to ledger</button><div className="profile-heading"><span className="friend-avatar large">{selected.display_name[0]}</span><div><p className="tiny-label">FRIEND PROFILE</p><h1>{selected.display_name}</h1><p>{selected.email || "No email added"}</p></div></div><p>{selected.notes || "No notes added yet."}</p><div className="friend-stats"><article><small>Open loans</small><strong>{ownLoans.filter(l => l.status === "open").length}</strong></article><article><small>Returned / repaid</small><strong>{ownLoans.filter(l => l.status === "completed").length}</strong></article><article><small>Outstanding</small><strong>{money(ownLoans.reduce((sum,l) => sum + (l.outstanding_cents || 0),0))}</strong></article></div><h2>Borrowing history</h2>{history(ownLoans)}</section>}
   {view !== "Account" && accountError && <div role="alert">{accountError}<button onClick={() => navigate("Account")}>Open account</button></div>}
   {view === "Account" && <section className="friend-profile" aria-label="Your profile"><button onClick={() => navigate("Dashboard")}>← Back to ledger</button><div className="profile-heading"><span className="friend-avatar large">{(profile?.display_name || "You")[0]}</span><div><p className="tiny-label">YOUR PROFILE</p><h1>{profile?.display_name || "Your account"}</h1><p>{profile?.email || "Your private IOU account"}</p></div></div><div className="friend-stats account-stats"><article><small>Friends</small><strong>{friends.filter(friend => !friend.archived_at).length}</strong></article><article><small>Money outstanding</small><strong>{money(loans.filter(l => l.kind === "money").reduce((sum,l) => sum + (l.outstanding_cents || 0),0))}</strong></article><article><small>Money repaid</small><strong>{money(loans.filter(l => l.kind === "money").reduce((sum,l) => sum + (l.repaid_cents || 0),0))}</strong></article><article><small>Items still out</small><strong>{loans.filter(l => l.kind === "item" && l.status === "open").length}</strong></article><article><small>Items returned</small><strong>{loans.filter(l => l.kind === "item" && l.status === "completed").length}</strong></article></div><h2>Borrowing history</h2>{history(loans)}<h2>Account settings</h2>{account}</section>}
  </div>
  {nudge && <Modal title="Diplomatic communications." onClose={() => setNudge(null)}><p className="muted">Copy it. Send it when the vibe is right.</p><label htmlFor="nudge-tone">Tone</label><select id="nudge-tone" value={tone} onChange={e => { setTone(e.target.value); setMessage(reminderFor(person(nudge.friend_id), nudge, e.target.value)); setCopyStatus(""); }}>{["Sweet bestie","Direct","Playful"].map(t => <option key={t}>{t}</option>)}</select><label htmlFor="nudge-message">Reminder</label><textarea id="nudge-message" rows={6} value={message} onChange={e => { setMessage(e.target.value); setCopyStatus(""); }}/><button className="primary-action" onClick={copy}>Copy reminder ↗</button><p role="status">{copyStatus}</p><small>Nothing is sent automatically. You control the group chat.</small></Modal>}
  {adding && <Modal title="Add to your circle" onClose={() => !busy && setAdding(false)}><form onSubmit={addFriend}><label htmlFor="friend-name">Name</label><input id="friend-name" name="name" required maxLength={100}/><label htmlFor="friend-email">Email (optional)</label><input id="friend-email" name="email" type="email"/><label htmlFor="friend-notes">About them (optional)</label><textarea id="friend-notes" name="notes" maxLength={2000}/>{error && <p role="alert">{error}</p>}<button className="primary-action" disabled={busy}>{busy ? "Adding…" : "Add friend"}</button></form></Modal>}
 </div>;
}
