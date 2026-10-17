import { useState } from "react";
import InfoDialog from "../components/InfoDialog";
import * as M from "./model";
import "./demo.css";

const STORAGE_KEY = "iou-demo-v1";
const cash = value => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value / 100);
const tones = ["Politely persistent", "Corporate", "Bestie", "Dramatic", "Legal-ish", "Brain rot", "Very British"];
function validState(data) {
	if (!data || data.version !== 1 || !data.profile || typeof data.profile.name !== "string" || !Array.isArray(data.contacts) || !Array.isArray(data.loans) || !Array.isArray(data.activity) || !Array.isArray(data.circles)) throw Error("This is not an IOU demo backup.");
	for (const person of data.contacts) if (typeof person.id !== "string" || typeof person.name !== "string" || typeof person.email !== "string") throw Error("A contact in this backup is invalid.");
	for (const loan of data.loans) {
		if (typeof loan.id !== "string" || !data.contacts.some(person => person.id === loan.contactId) || !["money", "item"].includes(loan.type) || !["lent", "borrowed"].includes(loan.direction) || !Number.isSafeInteger(loan.principal) || loan.principal < 0 || !Number.isFinite(loan.rate) || loan.rate < 0 || loan.rate > 100 || !/^\d{4}-\d{2}-\d{2}$/.test(loan.due) || !Array.isArray(loan.payments) || loan.payments.some(payment => !Number.isSafeInteger(payment.amount) || payment.amount <= 0)) throw Error("A loan in this backup is invalid.");
		if (!Number.isFinite(Date.parse(loan.due)) || typeof loan.created !== "string" || !Number.isFinite(Date.parse(loan.created)) || (loan.completed !== null && (typeof loan.completed !== "string" || !Number.isFinite(Date.parse(loan.completed)))) || !["pending", "accepted", "disputed"].includes(loan.acceptance) || !["money", "return", "other"].includes(loan.method) || !Array.isArray(loan.reminders) || typeof loan.item !== "string" || typeof loan.memo !== "string") throw Error("A loan in this backup has invalid dates or details.");
	}
	if (data.activity.some(entry => typeof entry.id !== "string" || typeof entry.description !== "string") || new Set(data.loans.map(loan => loan.id)).size !== data.loans.length || new Set(data.contacts.map(person => person.id)).size !== data.contacts.length) throw Error("This backup contains invalid history or duplicate records.");
	return data;
}
function initialState() {
	try { const saved = localStorage.getItem(STORAGE_KEY); return { data: saved ? validState(JSON.parse(saved)) : M.demo(), error: "" }; }
	catch { return { data: null, error: "Saved demo records could not be read. Restore a valid backup or reset the demo." }; }
}
function reminder(loan, person, tone) {
	const thing = loan.type === "money" ? cash(M.balance(loan)) : loan.item;
	const target = loan.direction === "lent" ? `you still have ${thing}` : `I still owe you ${thing}`;
	return [
		`Hey ${person.name}! Quick reminder: ${target}. Due ${loan.due}. Friendship remains fully funded.`,
		`Dear ${person.name}, our Friendship Finance Department notes that ${target}. Please advise on settlement by ${loan.due}. Regards, a very organized friend.`,
		`Bestie ${person.name}, ${target}. Due ${loan.due}. This is your friendly side quest.`,
		`${person.name}, the saga continues: ${target}. The deadline (${loan.due}) approaches. Our friendship deserves a happy ending.`,
		`NOTICE OF EXTREMELY INFORMAL OBLIGATION: ${person.name}, ${target}. Due ${loan.due}. This message has zero legal credentials.`,
		`${person.name}, ${target}. The repayment arc is overdue for character development. Due ${loan.due}.`,
		`Terribly sorry to bother you, ${person.name}, but ${target}. Due ${loan.due}. A most splendid settlement would be appreciated.`,
	][tones.indexOf(tone)];
}

function LoanForm({ record, contacts, onSave, onClose }) {
	const person = contacts.find(contact => contact.id === record?.contactId);
	const [kind, setKind] = useState(record?.type ?? "money"), [error, setError] = useState("");
	function submit(event) {
		event.preventDefault();
		try {
			const fields = Object.fromEntries(new FormData(event.currentTarget));
			const principal = kind === "money" ? M.cents(fields.amount) : 0;
			const rate = Number(fields.rate);
			if (!fields.name.trim() || (kind === "item" && !fields.item.trim())) throw Error("Add a name and what was borrowed.");
			if (!Number.isFinite(rate) || rate < 0 || rate > 100) throw Error("Choose a valid interest percentage.");
			onSave({ ...fields, type: kind, principal, rate });
		} catch (failure) { setError(failure.message); }
	}
	return <InfoDialog title={record ? "Edit the receipt." : "Add reminder"} onClose={onClose}><form className="demo-form" onSubmit={submit}>
		<label htmlFor="demo-name">Friend&apos;s name</label><input id="demo-name" name="name" defaultValue={person?.name} maxLength={100} required />
		<label htmlFor="demo-email">Friend&apos;s email</label><input id="demo-email" name="email" type="email" defaultValue={person?.email} maxLength={160} required />
		<label htmlFor="demo-direction">Your role</label><select id="demo-direction" name="direction" defaultValue={record?.direction ?? "lent"}><option value="lent">I lent this</option><option value="borrowed">I borrowed this</option></select>
		<label htmlFor="demo-kind">What was borrowed?</label><select id="demo-kind" value={kind} onChange={event => setKind(event.target.value)}><option value="money">Money</option><option value="item">An item</option></select>
		{kind === "money" ? <><label htmlFor="demo-amount">Amount (USD)</label><input id="demo-amount" name="amount" type="number" min=".01" max="1000000" step=".01" defaultValue={record ? record.principal / 100 : ""} required /><label htmlFor="demo-rate">Flat interest (%)</label><select id="demo-rate" name="rate" defaultValue={record?.rate ?? 0}>{Array.from({ length: 101 }, (_, i) => <option key={i} value={i}>{i}%</option>)}</select></> : <><label htmlFor="demo-item">Item</label><input id="demo-item" name="item" defaultValue={record?.item} maxLength={160} required /><input type="hidden" name="rate" value="0" /></>}
		<label htmlFor="demo-due">Due date</label><input id="demo-due" name="due" type="date" defaultValue={record?.due ?? M.offset(7)} required />
		<label htmlFor="demo-method">Repayment method</label><select id="demo-method" name="method" defaultValue={record?.method ?? (kind === "money" ? "money" : "return")}><option value="money">Money</option><option value="return">Return the item</option><option value="other">Other</option></select>
		<label htmlFor="demo-custom">Other repayment / notes</label><input id="demo-custom" name="custom" defaultValue={record?.custom} maxLength={300} />
		<label htmlFor="demo-memo">Memo</label><input id="demo-memo" name="memo" defaultValue={record?.memo} maxLength={300} />
		{error && <p className="inline-error" role="alert">{error}</p>}<div className="dialog-actions"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button className="primary-button">Save reminder</button></div>
	</form></InfoDialog>;
}

function LoanDetails({ loan, person, onClose, onEdit, change, activity }) {
	const [amount, setAmount] = useState(""), [tone, setTone] = useState(tones[0]);
	const [text, setText] = useState(() => reminder(loan, person, tones[0])), [notice, setNotice] = useState("");
	const open = M.live(loan);
	return <InfoDialog title={loan.type === "money" ? `${cash(M.balance(loan))} outstanding` : loan.item} onClose={onClose}><div className="dialog-content"><p>{person.name} · {loan.direction === "lent" ? "You lent this" : "You borrowed this"}</p><p>Due {loan.due} · {M.status(loan)} · {loan.method === "other" ? loan.custom : loan.method}</p><p>{loan.memo}</p>
		{open && loan.acceptance !== "accepted" && <><button className="primary-button" onClick={() => change(draft => { draft.acceptance = "accepted"; }, "Record accepted")}>Accept record</button><button className="secondary-button" onClick={() => change(draft => { draft.acceptance = "disputed"; }, "Record disputed")}>Dispute</button></>}
		{open && loan.acceptance === "accepted" && (loan.type === "money" && loan.method === "money" ? <form className="demo-form" onSubmit={event => { event.preventDefault(); change(draft => M.settle(draft, M.cents(amount), M.date()), "Repayment recorded"); setAmount(""); }}><label htmlFor="payment-amount">Repayment amount (USD)</label><input id="payment-amount" type="number" step=".01" min=".01" max={M.balance(loan) / 100} value={amount} onChange={event => setAmount(event.target.value)} required /><button className="primary-button">Record repayment</button></form> : <button className="primary-button" onClick={() => change(draft => { draft.completed = M.date(); }, "Item or alternative settlement completed")}>Mark returned / settled</button>)}
		{open && <div className="dialog-actions"><button className="secondary-button" onClick={onEdit}>Edit record</button><button className="secondary-button" onClick={() => change(draft => { draft.cancelled = true; }, "Record cancelled; history retained")}>Cancel record</button></div>}
		<h3>Friendly reminder</h3><label htmlFor="reminder-tone">Tone</label><select id="reminder-tone" value={tone} onChange={event => { setTone(event.target.value); setText(reminder(loan, person, event.target.value)); }}>{tones.map(value => <option key={value}>{value}</option>)}</select><label htmlFor="reminder-text">Edit before copying</label><textarea id="reminder-text" rows={5} value={text} onChange={event => setText(event.target.value)} /><button className="secondary-button" onClick={async () => { try { await navigator.clipboard.writeText(text); setNotice("Copied. No message was sent."); change(draft => { draft.reminders.push({ id: crypto.randomUUID(), at: new Date().toISOString(), tone, text }); }, "Reminder copied"); } catch { setNotice("Clipboard unavailable. Select and copy the reminder text."); } }}>Copy reminder</button>{notice && <p role="status">{notice}</p>}
		<h3>Receipt history</h3><ul>{loan.payments.map(payment => <li key={payment.id}>{payment.date}: {cash(payment.amount)} repaid</li>)}{activity.filter(entry => entry.loanId === loan.id).slice(0,15).map(entry => <li key={entry.id}>{entry.description}</li>)}</ul>
	</div></InfoDialog>;
}

export default function DemoWorkspace({ onClose }) {
	const [store, setStore] = useState(initialState), [page, setPage] = useState("Your Circle"), [search, setSearch] = useState(""), [filter, setFilter] = useState("all"), [selected, setSelected] = useState(null), [editing, setEditing] = useState(null), [adding, setAdding] = useState(false), [notice, setNotice] = useState("");
	const data = store.data;
	function save(next) {
		try { validState(next); localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); setStore({ data: next, error: "" }); return true; }
		catch (error) { setNotice(error.message || "Browser storage is unavailable. No changes were saved."); return false; }
	}
	function update(mutator, description, loanId) {
		try { const next = structuredClone(data); mutator(next); M.event(next, { id: loanId }, "updated", description); return save(next); }
		catch (error) { setNotice(error.message); return false; }
	}
	function saveLoan(fields) {
		const id = editing?.id ?? crypto.randomUUID();
		const ok = update(next => {
			let person = next.contacts.find(contact => contact.email.toLowerCase() === fields.email.trim().toLowerCase());
			if (!person) { person = { id: crypto.randomUUID(), name: fields.name.trim(), email: fields.email.trim(), avatar: fields.name.trim().split(/\s+/).map(part => part[0]).join("").slice(0,2) }; next.contacts.push(person); }
			const record = next.loans.find(loan => loan.id === id);
			const loan = { ...(record ?? { id, created: new Date().toISOString(), acceptance: "accepted", payments: [], completed: null, cancelled: false, reminders: [] }), contactId: person.id, direction: fields.direction, type: fields.type, principal: fields.principal, rate: fields.rate, item: fields.item?.trim() ?? "", due: fields.due, method: fields.method, custom: fields.custom, memo: fields.memo, updated: new Date().toISOString() };
			if (fields.method === "other" && !fields.custom.trim()) throw Error("Describe the alternative repayment.");
			if (record && M.paid(record) > 0 && (loan.type !== record.type || loan.direction !== record.direction || loan.contactId !== record.contactId || M.total(loan) < M.paid(record))) throw Error("Keep the original parties and a total that covers recorded repayments.");
			if (record) next.loans[next.loans.indexOf(record)] = loan; else next.loans.unshift(loan);
		}, editing ? "Record edited" : "New reminder recorded", id);
		if (!ok) throw Error("Could not save. Check the workspace notice.");
		setAdding(false); setEditing(null);
	}
	const totals = data ? M.summary(data.loans) : null;
	const current = data?.loans.find(loan => loan.id === selected);
	const filtered = data?.loans.filter(loan => (filter === "all" || M.status(loan) === filter) && `${data.contacts.find(person => person.id === loan.contactId)?.name} ${loan.item} ${loan.memo}`.toLowerCase().includes(search.toLowerCase()));
	return <div className="demo-workspace"><header className="demo-header"><button className="secondary-button" onClick={onClose}>← Back to sign in</button><span>DEMO / FICTIONAL RECORDS / SAVED IN THIS BROWSER</span><strong>IOU</strong></header><div className="demo-layout"><nav className="demo-nav" aria-label="Demo pages">{["Your Circle", "My Report", "The Halls", "My Account"].map(value => <button className="secondary-button" key={value} aria-current={page === value ? "page" : undefined} onClick={() => setPage(value)}>{value}</button>)}</nav><main className="demo-content"><div className="demo-title"><div><p className="eyebrow">FRIENDSHIP FINANCE / DEMO</p><h1>{page}</h1></div>{data && <button className="primary-button" onClick={() => setAdding(true)}>Add reminder</button>}</div>{(store.error || notice) && <p className="inline-error" role="alert">{store.error || notice}</p>}
		{data && <>
			<div className="demo-stats"><article className="demo-panel"><span>Owed to you</span><strong>{cash(totals.owed)}</strong></article><article className="demo-panel"><span>You owe</span><strong>{cash(totals.owe)}</strong></article><article className="demo-panel"><span>Items out there</span><strong>{totals.items}</strong></article><article className="demo-panel"><span>Overdue</span><strong>{totals.overdue}</strong></article></div>
			{page === "Your Circle" && <><div className="demo-toolbar"><label htmlFor="demo-search">Search receipts<input id="demo-search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Friend, item, or memo" /></label><label htmlFor="demo-filter">Status<select id="demo-filter" value={filter} onChange={event => setFilter(event.target.value)}>{["all", "active", "overdue", "partial", "pending", "disputed", "closed", "cancelled"].map(value => <option key={value}>{value}</option>)}</select></label></div><div className="demo-table-wrap"><table><caption>Private demo receipts</caption><thead><tr><th>Friend</th><th>Position</th><th>You</th><th>Due</th><th>Status</th><th>Action</th></tr></thead><tbody>{filtered.map(loan => <tr key={loan.id}><td>{data.contacts.find(person => person.id === loan.contactId)?.name}</td><td>{loan.type === "money" ? cash(M.balance(loan)) : loan.item}</td><td>{loan.direction}</td><td>{loan.due}</td><td><span className={M.status(loan) === "overdue" ? "overdue" : "demo-status"}>{M.status(loan)}</span></td><td><button className="secondary-button" onClick={() => { setSelected(loan.id); setNotice(""); }}>View receipt</button></td></tr>)}</tbody></table>{filtered.length === 0 && <p>No receipts match. Try another search or add a reminder.</p>}</div></>}
			{page === "My Report" && <section className="demo-panel"><h2>Your receipts, in numbers.</h2><p>{totals.closed} completed obligations. {totals.overdue} overdue. Small debts, unnecessarily serious analysis.</p><dl><dt>Total money lent</dt><dd>{cash(totals.lent)}</dd><dt>Total money borrowed</dt><dd>{cash(totals.borrowed)}</dd><dt>Your fictional Bro Score</dt><dd>{M.score(data.loans) ?? "Unrated (3 completed records required)"}</dd></dl><h3>Recent activity</h3><ul>{data.activity.slice(0,20).map(entry => <li key={entry.id}>{entry.description}</li>)}</ul></section>}
			{page === "The Halls" && <section className="demo-panel"><h2>The friendship credit committee.</h2><p>Fictional, private rankings. At least three completed records are required for a score.</p>{data.contacts.map(person => { const score = M.score(data.loans, person.id); return <article className="demo-rank" key={person.id}><strong>{person.name}</strong><span>{score ?? "Unrated"} / {M.tier(score)}</span></article>; })}</section>}
			{page === "My Account" && <section className="demo-panel"><h2>Demo profile</h2><form className="demo-form" onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); update(next => { next.profile.name = form.get("name").trim(); next.profile.email = form.get("email").trim(); }, "Demo profile updated"); }}><label htmlFor="demo-profile-name">Name</label><input id="demo-profile-name" name="name" defaultValue={data.profile.name} maxLength={100} required /><label htmlFor="demo-profile-email">Email</label><input id="demo-profile-email" name="email" type="email" defaultValue={data.profile.email} maxLength={160} required /><button className="primary-button">Save demo profile</button></form><p>These settings belong to the local demo and do not change your authenticated account.</p><button className="secondary-button" onClick={() => { const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" })); const anchor = document.createElement("a"); anchor.href = url; anchor.download = "iou-demo-backup.json"; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); }}>Export demo backup</button></section>}
		</>}
		{(!data || page === "My Account") && <section className="demo-panel"><label htmlFor="demo-backup">Restore a demo backup (replaces this demo only)</label><input id="demo-backup" type="file" accept="application/json,.json" onChange={async event => { try { const file = event.target.files[0]; if (!file) return; if (file.size > 5_000_000) throw Error("Choose a backup under 5 MB."); save(validState(JSON.parse(await file.text()))); } catch (error) { setNotice(error.message); } event.target.value = ""; }} /><p>Resetting replaces the local demo with fictional sample records.</p><button className="secondary-button" onClick={() => save(M.demo())}>Reset demo</button></section>}
	</main></div>{(adding || editing) && <LoanForm key={editing?.id ?? "new"} record={editing} contacts={data.contacts} onSave={saveLoan} onClose={() => { setAdding(false); setEditing(null); }} />}{current && !editing && <LoanDetails key={current.id} loan={current} person={data.contacts.find(person => person.id === current.contactId)} onClose={() => setSelected(null)} onEdit={() => setEditing(current)} activity={data.activity} change={(mutator, text) => update(next => mutator(next.loans.find(loan => loan.id === selected)), text, selected)} />}</div>;
}
