import { supabase } from "./supabase";

export async function profileRequest(method = "GET", body, signal) {
	const { data, error } = await supabase.auth.getSession();
	if (error || !data.session) throw new Error("Please sign in again.");
	const response = await fetch("/api/me", {
		method,
		signal,
		cache: "no-store",
		headers: {
			Authorization: `Bearer ${data.session.access_token}`,
			...(body ? { "Content-Type": "application/json" } : {}),
		},
		...(body ? { body: JSON.stringify(body) } : {}),
	});
	if (response.status === 401) throw new Error("Your session is no longer valid. Please sign in again.");
	if (response.status === 422) throw new Error("Check your name and IANA timezone and try again.");
	if (!response.ok) throw new Error("Your profile is unavailable. Please retry or check the backend setup.");
	return response.json();
}
