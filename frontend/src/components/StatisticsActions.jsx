import { useRef, useState } from "react";
import InfoDialog from "./InfoDialog";
import { amountToCents, recordRepayment } from "../services/repayments";
import "../styles/terminal.css";
const cash = (cents) =>
	new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
		cents / 100,
	);

export function PaymentReceipt({ payment, onClose }) {
	return (
		<InfoDialog title="Payment receipt" onClose={onClose}>
			<div className="stats-dialog-body">
				<p className="receipt-amount">{cash(payment.amount_cents)}</p>
				<dl className="receipt-details">
					<dt>For</dt>
					<dd>{payment.loan.description}</dd>
					<dt>Effective date</dt>
					<dd>
						{new Date(payment.effective_at).toLocaleString("en-US", {
							timeZone: "UTC",
						})}{" "}
						UTC
					</dd>
					<dt>Status</dt>
					<dd>Recorded repayment</dd>
					<dt>Receipt ID</dt>
					<dd>{payment.event_id || payment.id}</dd>
					<dt>Note</dt>
					<dd>{payment.note || "No note added."}</dd>
				</dl>
				<p className="stats-source">A recorded payment, not a bank transfer.</p>
			</div>
		</InfoDialog>
	);
}

export default function StatisticsActions({
	friend,
	loans,
	summary,
	demo,
	onRecorded,
}) {
	const [mode, setMode] = useState(null),
		[notice, setNotice] = useState(""),
		[celebrate, setCelebrate] = useState(false);
	const allRepaid = loans
		.filter((l) => l.status !== "voided" && l.kind === "money")
		.reduce(
			(sum, l) => sum + (l.repaid_cents ?? l.principal_cents - l.outstanding_cents),
			0,
		);
	const progress =
		allRepaid + summary.outstanding
			? Math.min(100, Math.round((allRepaid / (allRepaid + summary.outstanding)) * 100))
			: 0;
	const openLoans = loans.filter(
		(l) => l.kind === "money" && l.status === "open" && l.outstanding_cents > 0,
	);
	const [loanId, setLoanId] = useState(""),
		[amount, setAmount] = useState(""),
		[note, setNote] = useState(""),
		[saving, setSaving] = useState(false),
		[error, setError] = useState("");
	const [tone, setTone] = useState("friendly"),
		[draft, setDraft] = useState(""),
		[copyStatus, setCopyStatus] = useState("");
	const attempt = useRef(null);
	function openPayment() {
		setLoanId(openLoans[0]?.id || "");
		setAmount("");
		setNote("");
		setError("");
		attempt.current = null;
		setMode("payment");
	}
	function message(style) {
		const name = friend?.display_name.split(" ")[0] || "there",
			balance = cash(summary.outstanding);
		return style === "corporate"
			? `Dear ${name}, the Friendship Finance Department notes an outstanding balance of ${balance}. Please advise on your repayment timeline. Kind regards, Accounts Receivable (your friend).`
			: style === "playful"
				? `Hey ${name}! The ${balance} I lent you is having a lovely vacation. Any idea when it might come home?`
				: `Hey ${name}, a friendly reminder that there's ${balance} left to pay back. Let me know when works for you. Thanks!`;
	}
	async function save(event) {
		event.preventDefault();
		if (saving) return;
		setError("");
		let cents;
		try {
			cents = amountToCents(amount);
			const loan = openLoans.find((l) => l.id === loanId);
			if (!loan || cents > loan.outstanding_cents)
				throw new Error("The amount must not exceed this loan�s outstanding balance.");
		} catch (e) {
			setError(e.message);
			return;
		}
		setSaving(true);
		const body = { amount_cents: cents, note: note.trim() || null };
		const signature = JSON.stringify({ loanId, body });
		if (attempt.current?.signature !== signature)
			attempt.current = { signature, key: crypto.randomUUID() };
		try {
			const loan = openLoans.find((l) => l.id === loanId);
			const result = demo
				? {
						loan: {
							...loan,
							repaid_cents:
								(loan.repaid_cents ?? loan.principal_cents - loan.outstanding_cents) +
								cents,
							outstanding_cents: loan.outstanding_cents - cents,
							status: loan.outstanding_cents === cents ? "completed" : "open",
						},
						event: {
							id: attempt.current.key,
							action: "repayment",
							amount_cents: cents,
							note: body.note,
							effective_at: new Date().toISOString(),
							recorded_at: new Date().toISOString(),
						},
					}
				: await recordRepayment(loanId, body, attempt.current.key);
			onRecorded(result);
			setMode(null);
			setNotice(`${demo ? "Demo repayment" : "Repayment"} of ${cash(cents)} recorded.`);
			setCelebrate(summary.outstanding === cents);
			attempt.current = null;
		} catch (e) {
			setError(e.message);
		} finally {
			setSaving(false);
		}
	}
	async function copy() {
		try {
			await navigator.clipboard.writeText(draft);
			setCopyStatus("Copied. Paste it wherever you want to send it.");
		} catch {
			setCopyStatus("Select and copy the draft manually.");
		}
	}
	return (
		<>
			<section className="repayment-progress" aria-label="Repayment progress">
				<div className="progress-heading">
					<div>
						<span className="eyebrow">REPAYMENT PROGRESS</span>
						<h3>
							{summary.outstanding === 0 && allRepaid > 0
								? "Balance paid in full"
								: `${progress}% of recorded balance repaid`}
						</h3>
					</div>
					<span>
						{cash(allRepaid)} repaid / {cash(summary.outstanding)} remaining
					</span>
				</div>
				<progress max="100" value={progress} aria-label="Overall repayment progress" />
				<div className="statistics-quick-actions">
					<button
						className="primary-button"
						disabled={!openLoans.length}
						onClick={openPayment}
					>
						Record repayment
					</button>
					<button
						disabled={!summary.outstanding}
						onClick={() => {
							setTone("friendly");
							setDraft(message("friendly"));
							setCopyStatus("");
							setMode("reminder");
						}}
					>
						Draft reminder
					</button>
					<span>
						{demo
							? "Try it out. Demo changes reset when you reload."
							: "Log a payment you already received. No money is moved."}
					</span>
				</div>
			</section>
			{notice && (
				<div
					className={`repayment-notice ${celebrate ? "settled-celebration" : ""}`}
					role="status"
				>
					<span aria-hidden="true">{celebrate ? "?" : "?"}</span>{" "}
					{celebrate ? "All settled! " : ""}
					{notice}
					<button
						aria-label="Dismiss notification"
						onClick={() => {
							setNotice("");
							setCelebrate(false);
						}}
					>
						�
					</button>
					{celebrate && (
						<div className="celebration-sparkles" aria-hidden="true">
							? � ? � ?
						</div>
					)}
				</div>
			)}
			{mode === "payment" && (
				<InfoDialog
					title={demo ? "Record demo repayment" : "Record repayment"}
					onClose={() => {
						if (!saving) setMode(null);
					}}
				>
					<form className="stats-dialog-body" onSubmit={save}>
						<p>
							Record money you have already received from {friend?.display_name}. This
							does not transfer funds.
						</p>
						<label htmlFor="repayment-loan">Loan</label>
						<select
							id="repayment-loan"
							value={loanId}
							onChange={(e) => setLoanId(e.target.value)}
							disabled={saving}
						>
							{openLoans.map((loan) => (
								<option key={loan.id} value={loan.id}>
									{loan.description} - {cash(loan.outstanding_cents)} remaining
								</option>
							))}
						</select>
						<label htmlFor="repayment-amount">Amount (USD)</label>
						<input
							id="repayment-amount"
							inputMode="decimal"
							value={amount}
							onChange={(e) => setAmount(e.target.value)}
							placeholder="0.00"
							required
							disabled={saving}
						/>
						<button
							type="button"
							className="pay-full"
							disabled={saving}
							onClick={() =>
								setAmount(
									(
										openLoans.find((l) => l.id === loanId).outstanding_cents / 100
									).toFixed(2),
								)
							}
						>
							Use full remaining balance
						</button>
						<label htmlFor="repayment-note">Note (optional)</label>
						<textarea
							id="repayment-note"
							value={note}
							onChange={(e) => setNote(e.target.value)}
							maxLength={2000}
							disabled={saving}
						/>
						{error && <p role="alert">{error}</p>}
						<button className="signin" disabled={saving} type="submit">
							{saving ? "Recording..." : "Record received payment"}
						</button>
					</form>
				</InfoDialog>
			)}
			{mode === "reminder" && (
				<InfoDialog title="Draft reminder" onClose={() => setMode(null)}>
					<div className="stats-dialog-body">
						<p>Pick a tone, make it yours, then copy. Nothing is sent automatically.</p>
						<div className="reminder-tones" role="group" aria-label="Reminder tone">
							{["friendly", "corporate", "playful"].map((style) => (
								<button
									key={style}
									aria-pressed={tone === style}
									onClick={() => {
										setTone(style);
										setDraft(message(style));
										setCopyStatus("");
									}}
								>
									{style}
								</button>
							))}
						</div>
						<label htmlFor="reminder-draft">Your reminder</label>
						<textarea
							id="reminder-draft"
							value={draft}
							onChange={(e) => {
								setDraft(e.target.value);
								setCopyStatus("");
							}}
							rows={6}
						/>
						<button className="signin" onClick={copy}>
							Copy reminder
						</button>
						{copyStatus && <p role="status">{copyStatus}</p>}
					</div>
				</InfoDialog>
			)}
		</>
	);
}
