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
			<p>Signed in as {profile.email ?? "a Google user"}.</p>
			<label htmlFor="display-name">Display name</label>
			<input id="display-name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} />
			<label htmlFor="timezone">Timezone</label>
			<input id="timezone" value={timezone} onChange={(e) => setTimezone(e.target.value)} required maxLength={100} aria-describedby="timezone-help" />
			<small id="timezone-help">Use an IANA timezone, such as America/Los_Angeles or UTC.</small>
			<button disabled={busy} type="submit">{busy ? "Saving…" : "Save profile"}</button>
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
		profileRequest("GET", undefined, controller.signal).then((result) => {
			if (!controller.signal.aborted) {
				setProfile(result);
				setError("");
			}
		}).catch((error) => {
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
		<>
			<h2>Your account</h2>
			{!profile && !error && <p role="status">Loading your profile…</p>}
			{profile && <ProfileForm key={profile.id} profile={profile} onSaved={setProfile} />}
			{error && <><p role="alert">{error}</p><button onClick={() => setRetry((value) => value + 1)}>Retry profile</button></>}
			<button disabled={signingOut} onClick={signOut}>{signingOut ? "Signing out…" : "Sign out"}</button>
			<p>Friends and borrowing history are coming next.</p>
		</>
	);
}

function App() {
	const { session, loading, error: sessionError } = useSession();
	if (!loading && !session) {
		return <><TerminalLogin />{sessionError && <p className="session-error" role="alert">{sessionError}</p>}</>;
	}
	return (
		<main>
			<p className="eyebrow">Informal Obligations Utility</p>
			<h1>IOU</h1>
			<section className="card" aria-label="Account">
				{loading ? <p role="status">Restoring your session.</p> : session ? <Account key={session.user.id} session={session} /> : null}
			</section>
		</main>
	);
}
export default App;
