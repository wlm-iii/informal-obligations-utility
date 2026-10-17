import { useEffect, useState } from "react";
import { supabase } from "./supabase";

export function useSession() {
	const [session, setSession] = useState(null);
	const [loading, setLoading] = useState(Boolean(supabase));
	const [error, setError] = useState("");

	useEffect(() => {
		if (!supabase) return;
		let active = true;
		const callback = window.location.pathname === "/auth/callback";
		const callbackError = new URLSearchParams(window.location.search).has("error");
		const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, next) => {
			if (active) setSession(next);
		});
		// SDK initialization exchanges a PKCE callback code exactly once, including in StrictMode.
		supabase.auth.getSession().then(({ data, error: sessionError }) => {
			if (!active) return;
			if (sessionError || callbackError || (callback && !data?.session)) {
				setError("Google sign-in could not be completed. Please try again.");
			}
			setSession(data?.session ?? null);
			setLoading(false);
			if (callback) {
				window.history.replaceState({}, "", "/");
			}
		}).catch(() => {
			if (active) {
				setError("Unable to restore your session. Please try signing in again.");
				setLoading(false);
				if (callback) window.history.replaceState({}, "", "/");
			}
		});
		return () => {
			active = false;
			subscription.unsubscribe();
		};
	}, []);

	return { session, loading, error };
}
