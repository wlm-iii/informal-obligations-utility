import { lazy, Suspense, useRef, useState } from "react";
import { supabase } from "../services/supabase";
import { loginRequest } from "../services/login";
import MarketChart from "./MarketChart";
import logo from "../assets/iou-logo.png";
import InfoDialog from "./InfoDialog";
import "../styles/terminal.css";

const DemoWorkspace = lazy(() => import("../demo/DemoWorkspace"));
const panels = {
	how: { title: "Less awkward, in three steps.", content: <><p><strong>01 / Log it.</strong><br />Record who borrowed what: a little money, a hoodie, or your last functioning charger.</p><p><strong>02 / Nudge them.</strong><br />Write a funny reminder and copy it into the group chat. No surprise messages.</p><p><strong>03 / Settle up.</strong><br />Record repayments or mark items returned. Keep the friendship. Keep the receipts.</p></> },
	features: { title: "A terminal for tiny debts.", content: <><p>Sign in with Google or an existing email/password account to access your private profile.</p><p>The separate demo lets you try fictional money/item records, repayments, reminders, reports, and rankings. Demo records stay in this browser.</p></> },
	halls: { title: "The Halls.", content: <><p><strong>Hall of Fame</strong><br />Walking ATM. Speedrun Champion. Certified Green Flag.</p><p><strong>Hall of Shame</strong><br />Professional Ghoster. A very private investigation into very small debts.</p><p>Explore the demo to see fictional rankings. Nothing is posted publicly.</p></> },
};

function Coin() {
	return <svg className="coin" viewBox="0 0 64 64" fill="none" aria-hidden="true"><circle cx="32" cy="32" r="29" fill="#8e6b01" stroke="#dfb431" /><circle cx="32" cy="32" r="25" fill="#d0a215" stroke="#664d01" /><circle cx="32" cy="32" r="21" stroke="#eccb60" strokeWidth=".8" /><path d="M24 14h16M24 50h16M14 24v16M50 24v16" stroke="#664d01" /><text x="32" y="36" textAnchor="middle" fill="#3a2d04" fontSize="12" fontWeight="700">IOU</text></svg>;
}

function BackgroundPattern({ pattern, paused }) {
	if (pattern === "market" || pattern === "none") return null;
	return <svg className={`terminal-pattern pattern-${pattern}`} viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice" aria-hidden="true" style={{ animationPlayState: paused ? "paused" : "running" }}>
		{pattern === "grid" ? Array.from({ length: 30 }, (_, i) => <path key={i} d={`M${i * 80} 0V1000 M0 ${i * 80}H1600`} />) : pattern === "contours" ? Array.from({ length: 28 }, (_, i) => <path key={i} d={`M${400 + i * 16} -100 C${250 + i * 20} 300,${1300 + i * 14} 550,${700 + i * 25} 1100`} />) : Array.from({ length: 6 }, (_, i) => <path key={i} d={`M-100 ${140 + i * 130}H${300 + i * 130}V${80 + i * 110}H1700`} />)}
	</svg>;
}

export default function TerminalLogin() {
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [revealed, setRevealed] = useState(false);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState("");
	const [panel, setPanel] = useState(null);
	const [demo, setDemo] = useState(false);
	const [pattern, setPattern] = useState("market");
	const [paused, setPaused] = useState(false);
	const submitting = useRef(false);
	async function signIn(action) {
		if (submitting.current) return;
		submitting.current = true;
		setBusy(true);
		setError("");
		const credentials = { action, email, password };
		setPassword("");
		try { await loginRequest(supabase?.auth, credentials, window.location.origin); }
		catch (failure) { setError(failure.message); }
		finally { submitting.current = false; setBusy(false); }
	}
	if (demo) return <Suspense fallback={<p role="status" className="loading-screen">Opening fictional accounts…</p>}><DemoWorkspace onClose={() => setDemo(false)} /></Suspense>;
	return <div className="terminal-login">
		<BackgroundPattern pattern={pattern} paused={paused} />
		<div className="page">
			<header className="terminal-header"><a className="brand" href="#" aria-label="IOU Friendship Finance home"><img className="brand-logo" src={logo} alt="IOU" width="85" height="51" /></a><nav className="terminal-nav" aria-label="Main navigation"><button onClick={() => setPanel("how")}>How it works</button><button onClick={() => setPanel("features")}>Features</button><button onClick={() => setPanel("halls")}>The Halls</button></nav></header>
			<main className="login-main">
				<section className="intro" aria-labelledby="hero-title"><div className="eyebrow">PERSONAL PAYMENTS. PERSONAL RELATIONSHIPS.</div><div className="hero-visual"><MarketChart paused={paused} enabled={pattern === "market"} /><h1 id="hero-title">Friendship<br />is free. <span>Your<br />stuff isn&apos;t.</span></h1></div><p className="intro-copy">Track borrowed money and things, send hilariously polite reminders, and hold your homies accountable.</p>
					<article className="receipt" aria-label="Sample IOU: Alex Rivera owes 60 dollars, 3 days overdue"><div className="receipt-top"><div className="avatar" aria-hidden="true">AR</div><div><div className="borrower">Alex Rivera</div><div className="memo">Concert financing. Emotionally necessary.</div></div><span className="receipt-id">IOU / 0042</span></div><div className="receipt-bottom"><span className="amount">$60.00<small>USD</small></span><span className="overdue">Overdue 3 days</span></div><div className="receipt-caption"><span>SAMPLE POSITION / NOT YOUR ACTUAL DEBT</span><span>RECEIPT ON FILE</span></div></article>
				</section>
				<section className="access" aria-label="Sign in to IOU"><Coin /><div className="access-card"><div className="access-meta"><span>CLIENT ACCESS / 01</span><span>SECURE ACCOUNT ACCESS</span></div>
					<button className="google secondary-button" disabled={busy} onClick={() => signIn("google")}><svg viewBox="0 0 20 20" aria-hidden="true"><path fill="currentColor" d="M18.5 10.2c0-.6 0-1.2-.1-1.8H10v3.4h4.8a4.1 4.1 0 0 1-1.8 2.7c-.8.5-1.8.9-3 .9-2.3 0-4.3-1.6-5-3.7a5.4 5.4 0 0 1 0-3.4c.7-2.1 2.7-3.7 5-3.7 1.3 0 2.5.4 3.4 1.3L16 3.3A8.6 8.6 0 0 0 10 1a9 9 0 1 0 0 18c2.4 0 4.4-.8 5.9-2.2 1.7-1.6 2.6-3.8 2.6-6.6Z" /></svg>Continue with Google</button><div className="divider">or</div>
					<form onSubmit={event => { event.preventDefault(); signIn("password"); }} aria-busy={busy}>
						<div className="field"><label htmlFor="email">Email</label><input id="email" name="email" type="email" autoComplete="email" placeholder="JohnDoe@uci.edu" maxLength={160} required value={email} onChange={event => setEmail(event.target.value)} /></div>
						<div className="field"><label htmlFor="password">Password</label><div className="input-wrap"><input id="password" name="password" type={revealed ? "text" : "password"} autoComplete="current-password" placeholder="Enter your password" maxLength={128} required value={password} onChange={event => setPassword(event.target.value)} /><button type="button" className="reveal" aria-label={revealed ? "Hide password" : "Show password"} aria-pressed={revealed} onClick={() => setRevealed(value => !value)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" /><circle cx="12" cy="12" r="2.5" /></svg></button></div></div>
						{error && <p className="inline-error" role="alert">{error}</p>}<button className="primary-button signin" type="submit" disabled={busy}>{busy ? "Connecting…" : "Sign in"}<span aria-hidden="true">→</span></button>
					</form>
					<div className="access-links"><button disabled={busy} onClick={() => setDemo(true)}>Explore demo</button><button disabled={busy} onClick={() => signIn("google")}>Open an account</button></div>
				</div><div className="outside-caption"><span>IOU / WEB</span></div></section>
			</main>
			<footer className="terminal-footer"><span><strong>IOU</strong> &nbsp; FRIENDSHIP FINANCE</span><span>SMALL DEBTS. UNNECESSARILY SERIOUS SOFTWARE.</span><span className="legal">Not a bank. Just a very organized friend.</span></footer>
		</div>
		<details className="pattern-controls"><summary>Background study</summary><div className="pattern-body"><h3>Background study</h3><p>Decorative patterns. No actual stock-market wisdom.</p><div className="pattern-options">{["market", "contours", "grid", "signals", "none"].map((value, i) => <button key={value} aria-pressed={pattern === value} onClick={() => setPattern(value)}>{String(i + 1).padStart(2, "0")} / {value === "market" ? "Debt ticker" : value}</button>)}</div><button className="secondary-button motion-toggle" aria-pressed={paused} onClick={() => setPaused(value => !value)}>{paused ? "Resume motion" : "Pause motion"}</button></div></details>
		{panel && <InfoDialog title={panels[panel].title} onClose={() => setPanel(null)}><div className="dialog-content">{panels[panel].content}</div><div className="dialog-actions"><button className="secondary-button" onClick={() => setPanel(null)}>Back</button><button className="primary-button" onClick={() => { setPanel(null); setDemo(true); }}>Explore demo →</button></div></InfoDialog>}
	</div>;
}
