import { useEffect, useState } from "react";
import { statisticsRequest, summarizePayments } from "../services/statistics";
import "./Statistics.css";

const money = (cents) =>
	new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
		cents / 100,
	);
const dateLabel = (date) =>
	new Date(date).toLocaleDateString("en-US", {
		month: "short",
		day: "numeric",
		year: "numeric",
		timeZone: "UTC",
	});

export default function Statistics({ initialData = null }) {
	const [friends, setFriends] = useState(initialData?.friends ?? []);
	const [selected, setSelected] = useState(initialData?.friends[0]?.id ?? "");
	const [records, setRecords] = useState(initialData ?? { loans: [], history: [] });
	const [days, setDays] = useState(0);
	const [busy, setBusy] = useState(!initialData);
	const [error, setError] = useState("");
	const [retry, setRetry] = useState(0);
	useEffect(() => {
		if (initialData) return;
		const controller = new AbortController();
		statisticsRequest("friends?archived=include", controller.signal)
			.then((list) => {
				setFriends(list);
				setSelected(list[0]?.id ?? "");
				if (!list.length) setBusy(false);
			})
			.catch((error) => {
				if (!controller.signal.aborted) {
					setError(error.message);
					setBusy(false);
				}
			});
		return () => controller.abort();
	}, [initialData, retry]);
	useEffect(() => {
		if (initialData || !selected) return;
		const controller = new AbortController();
		Promise.all([
			statisticsRequest(
				`loans?friend_id=${encodeURIComponent(selected)}`,
				controller.signal,
			),
			statisticsRequest(
				`friends/${encodeURIComponent(selected)}/history`,
				controller.signal,
			),
		])
			.then(([loans, history]) => {
				if (!controller.signal.aborted) {
					setRecords({ loans, history });
					setBusy(false);
					setError("");
				}
			})
			.catch((error) => {
				if (!controller.signal.aborted) {
					setError(error.message);
					setBusy(false);
				}
			});
		return () => controller.abort();
	}, [selected, initialData, retry]);
	const friend = friends.find((person) => person.id === selected);
	const loans = records.loans.filter((loan) => loan.friend_id === selected);
	const summary = summarizePayments(loans, records.history, days);
	const initials =
		friend?.display_name
			.trim()
			.split(/\s+/)
			.slice(0, 2)
			.map((word) => Array.from(word)[0])
			.join("")
			.toUpperCase() || "�";
	const peak = Math.max(summary.repaid, 10000);
	let running = 0;
	const now = new Date();
	const start = days
		? now.getTime() - days * 86400000
		: summary.payments.length
			? new Date(summary.payments[0].effective_at).getTime() - 86400000
			: now.getTime() - 30 * 86400000;
	const points = [
		[70, 270],
		...summary.payments.map((payment) => {
			running += payment.amount_cents;
			return [
				70 +
					((new Date(payment.effective_at).getTime() - start) /
						Math.max(now.getTime() - start, 1)) *
						810,
				270 - (running / peak) * 220,
			];
		}),
		[880, 270 - (summary.repaid / peak) * 220],
	];
	const line = points.map(([x, y], i) => `${i ? "L" : "M"} ${x} ${y}`).join(" ");
	const selectFriend = (event) => {
		setSelected(event.target.value);
		if (!initialData) {
			setBusy(true);
			setError("");
		}
	};
	return (
		<div className="statistics-layout">
			<aside className="stats-sidebar">
				<p className="eyebrow">YOUR WORKSPACE</p>
				<a href="#profile" className="profile-nav">
					<span>01</span> Profile <span>?</span>
				</a>
				<a href="#statistics" className="profile-nav active" aria-current="page">
					<span>02</span> Statistics <span>?</span>
				</a>
				<div className="sidebar-note">
					<span>THE RECEIPTS DEPARTMENT</span>
					<p>
						A record of what came back. Because �I paid you already� deserves a paper
						trail.
					</p>
				</div>
			</aside>
			<div className="stats-content">
				<header className="page-heading">
					<div>
						<p className="eyebrow">YOUR CIRCLE / STATISTICS</p>
						<h2>
							Payment <span className="title-accent">history.</span>
						</h2>
						<p>A closer look at the people who owe you.</p>
					</div>
					<span className="edition">
						{initialData ? "FICTIONAL DEMO DATA" : "PRIVATE RECORDS"}
					</span>
				</header>
				<section className="borrower-panel" aria-label="Person being tracked">
					<div className="avatar" aria-hidden="true">
						{initials}
					</div>
					<div className="borrower-identity">
						<label htmlFor="tracked-person">TRACKING</label>
						<select
							id="tracked-person"
							value={selected}
							onChange={selectFriend}
							disabled={!friends.length}
						>
							{!friends.length && <option value="">No contacts yet</option>}
							{friends.map((person) => (
								<option key={person.id} value={person.id}>
									{person.display_name}
								</option>
							))}
						</select>
						<p>{friend?.email || "Private contact"}</p>
					</div>
					<div className="score-placeholder">
						<span>BRO SCORE</span>
						<strong>
							� <small>/ 100</small>
						</strong>
						<span>Fictional score � not available yet</span>
					</div>
				</section>
				{error && (
					<div className="stats-feedback" role="alert">
						{error}{" "}
						<button
							onClick={() => {
								setBusy(true);
								setError("");
								setRetry((value) => value + 1);
							}}
						>
							Retry statistics
						</button>
					</div>
				)}
				{busy ? (
					<p className="stats-feedback" role="status">
						Loading payment history�
					</p>
				) : (
					!error && (
						<>
							<div className="stats-metrics">
								<div>
									<span>REPAID IN PERIOD</span>
									<strong className="positive">{money(summary.repaid)}</strong>
									<small>{summary.payments.length} recorded payments</small>
								</div>
								<div>
									<span>STILL OWES YOU</span>
									<strong className={summary.outstanding ? "negative" : ""}>
										{money(summary.outstanding)}
									</strong>
									<small>Current balance � all time</small>
								</div>
								<div>
									<span>TOTAL LENT</span>
									<strong>{money(summary.lent)}</strong>
									<small>
										{summary.open} open money {summary.open === 1 ? "loan" : "loans"} �
										all time
									</small>
								</div>
							</div>
							<section className="payment-chart-panel" aria-labelledby="chart-title">
								<div className="chart-heading">
									<div>
										<p className="eyebrow">01 / REPAYMENT TREND</p>
										<h3 id="chart-title">Money finding its way back.</h3>
										<p>Cumulative repayments � USD � dates in UTC</p>
									</div>
									<div
										className="range-controls"
										role="group"
										aria-label="Payment period"
									>
										{[
											[30, "30D"],
											[90, "90D"],
											[0, "ALL"],
										].map(([value, label]) => (
											<button
												key={value}
												aria-pressed={days === value}
												onClick={() => setDays(value)}
											>
												{label}
											</button>
										))}
									</div>
								</div>
								<div className="graph-key">
									<span /> Amount repaid <strong>{money(summary.repaid)}</strong>
								</div>
								<svg
									className="payment-chart"
									viewBox="0 0 920 320"
									role="img"
									aria-label={`${friend?.display_name || "Contact"} repaid ${money(summary.repaid)} across ${summary.payments.length} payments in the selected period. Cumulative repayments increase with each payment.`}
								>
									<defs>
										<linearGradient id="repayment-fill" x1="0" y1="0" x2="0" y2="1">
											<stop stopColor="#879a39" stopOpacity=".18" />
											<stop offset="1" stopColor="#879a39" stopOpacity=".01" />
										</linearGradient>
									</defs>
									{[0, 1, 2, 3, 4].map((i) => (
										<g key={i}>
											<line
												x1="70"
												x2="880"
												y1={270 - i * 55}
												y2={270 - i * 55}
												stroke="#403e3c"
												strokeDasharray="3 6"
											/>
											<text x="55" y={274 - i * 55} textAnchor="end">
												{money((peak * i) / 4)}
											</text>
										</g>
									))}
									<path
										d={`${line} L 880 270 L 70 270 Z`}
										fill="url(#repayment-fill)"
									/>
									<path
										d={line}
										fill="none"
										stroke="#879a39"
										strokeWidth="2.5"
										strokeLinejoin="round"
									/>
									{summary.payments.map((payment, i) => (
										<circle
											key={payment.id}
											cx={points[i + 1][0]}
											cy={points[i + 1][1]}
											r="4"
											fill="#100f0f"
											stroke="#a0af54"
											strokeWidth="2"
										>
											<title>
												{dateLabel(payment.effective_at)}: {money(payment.amount_cents)}
											</title>
										</circle>
									))}
									<text x="70" y="306">
										{dateLabel(start)}
									</text>
									<text x="880" y="306" textAnchor="end">
										{dateLabel(now)}
									</text>
								</svg>
								{!summary.payments.length && (
									<p className="stats-empty">
										No repayments in this period. Recorded repayments will appear on
										this graph.
									</p>
								)}
								<div className="chart-footnote">
									<span>? Recorded repayments only</span>
									<span>Reversed payments and voided loans excluded</span>
								</div>
							</section>
							<section className="payment-table-panel" aria-labelledby="payments-title">
								<div className="chart-heading">
									<div>
										<p className="eyebrow">02 / THE PAPER TRAIL</p>
										<h3 id="payments-title">Past payments</h3>
									</div>
									<span className="table-count">{summary.payments.length} RECORDS</span>
								</div>
								<div className="payment-table-scroll">
									<table>
										<thead>
											<tr>
												<th scope="col">Date (UTC)</th>
												<th scope="col">For</th>
												<th scope="col">Amount</th>
												<th scope="col">Status</th>
											</tr>
										</thead>
										<tbody>
											{[...summary.payments].reverse().map((payment) => (
												<tr key={payment.id}>
													<td>{dateLabel(payment.effective_at)}</td>
													<td>{payment.loan.description}</td>
													<td>{money(payment.amount_cents)}</td>
													<td>
														<span className="payment-badge">? Recorded</span>
													</td>
												</tr>
											))}
										</tbody>
									</table>
									{!summary.payments.length && (
										<p className="stats-empty">No payments recorded for this period.</p>
									)}
								</div>
							</section>
						</>
					)
				)}
				<p className="stats-source">
					{initialData
						? "Design preview � fictional people and payments. No real account data."
						: "Based on your privately recorded USD money loans. Item returns are not included."}
				</p>
			</div>
		</div>
	);
}
