// The parent owns the Supabase session; tokens never enter the design frame.
export async function loginRequest(auth, request, origin) {
	if (!auth) throw new Error("Sign-in is not configured. Please contact the IOU team.");
	if (request.action === "google") {
		try {
			const { error } = await auth.signInWithOAuth({ provider: "google", options: { redirectTo: `${origin}/auth/callback` } });
			if (error) throw error;
		} catch { throw new Error("Unable to start Google sign-in. Please try again."); }
		return;
	}
	if (request.action !== "password" || typeof request.email !== "string" || typeof request.password !== "string" || !request.email.trim() || request.email.length > 160 || !request.password || request.password.length > 128) throw new Error("Enter your email and password, or continue with Google.");
	try {
		const { error } = await auth.signInWithPassword({ email: request.email.trim(), password: request.password });
		if (error) throw error;
	} catch { throw new Error("Unable to sign in. Check your details, or continue with Google."); }
}
