import { useEffect, useState } from "react";
import "./App.css";
import TerminalLogin from "./components/TerminalLogin";
import { supabase } from "./services/supabase";
import { useSession } from "./services/useSession";
import { profileRequest } from "./services/api";

function ProfileForm({ profile, onSaved }) {
	const [name, setName] = useState(profile.display_name);
	const [timezone, setTimezone] = useState(profile.timezone);
	const [busy, setBusy] = useState(false);
	const [message, setMessage] = useState("");
	const [error, setError] = useState("");

	async function save(event) {
		event.preventDefault();
		setBusy(true);
		setError("");
		setMessage("");
		try {
			const updated = await profileRequest("PATCH", { display_name: name, timezone });
			onSaved(updated);
			setMessage("Profile saved.");
		} catch (error) {
			setError(error.message);
		} finally {
			setBusy(false);
		}
	}

	return (
		<form onSubmit={save} className="profile-form">
			<div className="section-heading">
				<span className="section-number">01 /</span>
				<div>
					<h2>Personal details</h2>
					<p>A little about the person behind the IOUs.</p>
				</div>
			</div>
			<label htmlFor="profile-email">
				Email address <span className="field-note">Managed by Google</span>
			</label>
			<input
				id="profile-email"
				value={profile.email ?? ""}
				readOnly
				placeholder="No email available"
			/>
			<label htmlFor="display-name">Display name</label>
			<input
				id="display-name"
				value={name}
				onChange={(e) => setName(e.target.value)}
				required
				maxLength={100}
			/>
			<label htmlFor="timezone">Timezone</label>
			<input
				id="timezone"
				value={timezone}
				onChange={(e) => setTimezone(e.target.value)}
				required
				maxLength={100}
				aria-describedby="timezone-help"
			/>
			<small id="timezone-help">
				Use an IANA timezone, such as America/Los_Angeles or UTC.
			</small>
			<div className="form-footer">
				<span>Your details stay private.</span>
				<button className="primary-button" disabled={busy} type="submit">
					{busy ? "Saving…" : "Save profile"}
					<span aria-hidden="true"> ↗</span>
				</button>
			</div>
			{message && <p role="status">{message}</p>}
			{error && <p role="alert">{error}</p>}
		</form>
	);
}

function Account({ session }) {
	const [profile, setProfile] = useState(null);
	const [error, setError] = useState("");
	const [retry, setRetry] = useState(0);
	const [signingOut, setSigningOut] = useState(false);

	useEffect(() => {
		const controller = new AbortController();
		profileRequest("GET", undefined, controller.signal)
			.then((result) => {
				if (!controller.signal.aborted) {
					setProfile(result);
					setError("");
				}
			})
			.catch((error) => {
				if (!controller.signal.aborted) setError(error.message);
			});
		return () => controller.abort();
	}, [session.access_token, retry]);

	async function signOut() {
		setSigningOut(true);
		try {
			const { error } = await supabase.auth.signOut();
			if (error) setError("Unable to sign out. Please try again.");
		} catch {
			setError("Unable to sign out. Please try again.");
		} finally {
			setSigningOut(false);
		}
	}

	return (
		<div className="profile-layout">
			<aside className="profile-sidebar">
				<div className="avatar" aria-hidden="true">
					{profile?.display_name?.trim().slice(0, 2).toUpperCase() || "IO"}
					<span>✳</span>
				</div>
				<p className="eyebrow">YOUR PERSONAL LEDGER</p>
				<h1>
					{profile?.display_name || "Your account"}
					<span className="name-dot">.</span>
				</h1>
				<p className="sidebar-description">
					Good friends.
					<br />
					Clear accounts.
				</p>
				<span className="member-badge">● Personal account</span>
				<div className="sidebar-divider" />
				<a className="profile-nav active" href="#details" aria-current="page">
					<span>01</span> Profile <span>↗</span>
				</a>
				<a className="profile-nav" href="#activity">
					<span>02</span> Activity <span>↓</span>
				</a>
				<div className="sidebar-note">
					<span>THE IOU WAY</span>
					<p>A little accountability goes a long way.</p>
				</div>
			</aside>
			<div className="profile-content">
				<header className="page-heading">
					<div>
						<p className="eyebrow">ACCOUNT / PROFILE</p>
						<h2>Make yourself at home.</h2>
						<p>Your details, all in one place.</p>
					</div>
					<span className="edition">IOU / 001</span>
				</header>
				<section className="details-panel" id="details" aria-label="Personal details">
					{!profile && !error && <p role="status">Loading your profile…</p>}
					{profile && (
						<ProfileForm key={profile.id} profile={profile} onSaved={setProfile} />
					)}
					{error && (
						<>
							<p role="alert">{error}</p>
							<button onClick={() => setRetry((value) => value + 1)}>
								Retry profile
							</button>
						</>
					)}
				</section>
				<section
					className="activity-panel"
					id="activity"
					aria-labelledby="activity-title"
				>
					<div className="section-heading">
						<span className="section-number">02 /</span>
						<div>
							<h2 id="activity-title">Your activity</h2>
							<p>Every favor has a story.</p>
						</div>
						<span className="coming-soon">COMING SOON</span>
					</div>
					<div className="empty-state">
						<span className="empty-icon" aria-hidden="true">
							↔
						</span>
						<div>
							<h3>A fresh page.</h3>
							<p>
								Friends and borrowing history are coming next.
								<br />
								This is where your shared stories will live.
							</p>
						</div>
					</div>
				</section>
				<section className="signout-panel">
					<div>
						<h3>All settled for now?</h3>
						<p>You can pick up right where you left off.</p>
					</div>
					<button disabled={signingOut} onClick={signOut}>
						{signingOut ? "Signing out…" : "Sign out"}
					</button>
				</section>
			</div>
		</div>
	);
}

function App() {
	const { session, loading, error: sessionError } = useSession();
	if (!loading && !session) {
		return (
			<>
				<TerminalLogin />
				{sessionError && (
					<p className="session-error" role="alert">
						{sessionError}
					</p>
				)}
			</>
		);
	}
	return (
		<main className="account-shell">
			<header className="topbar">
				<a href="/" className="wordmark" aria-label="IOU home">
					iou<span>✳</span>
				</a>
				<span className="brand-caption">INFORMAL OBLIGATIONS UTILITY</span>
				<span className="topbar-label">A FRIENDLY ACCOUNT OF THINGS.</span>
			</header>
			<section aria-label="Account">
				{loading ? (
					<p role="status">Restoring your session.</p>
				) : session ? (
					<Account key={session.user.id} session={session} />
				) : null}
			</section>
			<footer className="site-footer">
				<span>IOU — KEEP FRIENDSHIP IN THE BLACK.</span>
				<span>
					Made for the people you count on. <span aria-hidden="true">↗</span>
				</span>
			</footer>
		</main>
	);
}
export default App;
