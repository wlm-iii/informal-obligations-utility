// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { StrictMode } from "react";

const { auth } = vi.hoisted(() => ({ auth: {
	getSession: vi.fn(), onAuthStateChange: vi.fn(), signInWithOAuth: vi.fn(), signInWithPassword: vi.fn(), signOut: vi.fn(),
} }));
vi.mock("./services/supabase", () => ({ supabase: { auth } }));
import App from "./App";

const session = { access_token: "test-access-token", user: { id: "user-1" } };
const profile = { id: "user-1", email: "person@example.com", display_name: "Person", timezone: "UTC" };
let onAuthChange;
async function requestLogin(action = "google", credentials = {}) {
	const frame = await screen.findByTitle("IOU sign in");
	// Session restoration can render the frame before passive effects attach.
	await act(async () => {});
	const reply = vi.spyOn(frame.contentWindow, "postMessage");
	fireEvent(window, new MessageEvent("message", {
		origin: window.location.origin,
		source: frame.contentWindow,
		data: { type: "iou:login", action, ...credentials },
	}));
	return reply;
}

beforeEach(() => {
	vi.resetAllMocks();
	window.history.replaceState({}, "", "/");
	auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
	auth.onAuthStateChange.mockImplementation((callback) => {
		onAuthChange = callback;
		return { data: { subscription: { unsubscribe: vi.fn() } } };
	});
	auth.signInWithOAuth.mockResolvedValue({ error: null });
	auth.signOut.mockImplementation(async () => {
		onAuthChange("SIGNED_OUT", null);
		return { error: null };
	});
	vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => profile }));
});

afterEach(() => {
	cleanup();
	vi.unstubAllGlobals();
});

describe("Level 0 account flow", () => {
	it("shows profile identity and keeps the provider email read-only", async () => {
		auth.getSession.mockResolvedValue({ data: { session }, error: null });
		render(<App />);
		const email = await screen.findByLabelText(/Email address/);
		expect(email).toHaveValue(profile.email);
		expect(email).toHaveAttribute("readonly");
		expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Person");
		expect(screen.queryByRole("link", { name: /Activity/ })).not.toBeInTheDocument();
		expect(screen.queryByLabelText("Timezone")).not.toBeInTheDocument();
	});
	it("signs in with a password and loads the backend profile with the access token", async () => {
		auth.signInWithPassword.mockImplementation(async () => {
			auth.getSession.mockResolvedValue({ data: { session }, error: null });
			onAuthChange("SIGNED_IN", session);
			return { error: null };
		});
		render(<App />);
		await requestLogin("password", { email: "person@example.com", password: "test-password" });
		expect(await screen.findByLabelText("Display name")).toHaveValue("Person");
		expect(auth.signInWithPassword).toHaveBeenCalledWith({ email: "person@example.com", password: "test-password" });
		expect(fetch).toHaveBeenCalledWith("/api/me", expect.objectContaining({ headers: { Authorization: "Bearer test-access-token" } }));
	});

	it("ignores requests from another origin or window", async () => {
		render(<App />);
		const frame = await screen.findByTitle("IOU sign in");
		fireEvent(window, new MessageEvent("message", { origin: "https://other.example", source: frame.contentWindow, data: { type: "iou:login", action: "google" } }));
		fireEvent(window, new MessageEvent("message", { origin: window.location.origin, source: window, data: { type: "iou:login", action: "google" } }));
		expect(auth.signInWithOAuth).not.toHaveBeenCalled();
	});
	it("starts Google sign-in with the frontend callback", async () => {
		render(<App />);
		await requestLogin();
		expect(auth.signInWithOAuth).toHaveBeenCalledWith({
			provider: "google", options: { redirectTo: `${window.location.origin}/auth/callback` },
		});
	});

	it("shows a safe error when OAuth cannot start", async () => {
		auth.signInWithOAuth.mockResolvedValue({ error: new Error("provider detail") });
		render(<App />);
		const reply = await requestLogin();
		await waitFor(() => expect(reply).toHaveBeenCalledWith({ type: "iou:login-result", error: "Unable to start Google sign-in. Please try again." }, window.location.origin));
		expect(screen.queryByText("provider detail")).not.toBeInTheDocument();
	});

	it("restores a callback session in StrictMode and removes the code from the URL", async () => {
		window.history.replaceState({}, "", "/auth/callback?code=one-time-code");
		auth.getSession.mockResolvedValue({ data: { session }, error: null });
		render(<StrictMode><App /></StrictMode>);
		expect(await screen.findByLabelText("Display name")).toHaveValue("Person");
		expect(window.location.pathname).toBe("/");
		expect(window.location.search).toBe("");
		expect(fetch).toHaveBeenCalledWith("/api/me", expect.objectContaining({
			headers: { Authorization: "Bearer test-access-token" },
		}));
	});

	it("updates the profile and signs out", async () => {
		auth.getSession.mockResolvedValue({ data: { session }, error: null });
		render(<App />);
		fireEvent.change(await screen.findByLabelText("Display name"), { target: { value: "New Name" } });
		fireEvent.click(screen.getByRole("button", { name: "Save profile" }));
		expect(await screen.findByText("Profile saved.")).toBeInTheDocument();
		expect(fetch).toHaveBeenCalledWith("/api/me", expect.objectContaining({
			method: "PATCH", body: JSON.stringify({ display_name: "New Name" }),
		}));
		fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
		expect(await screen.findByTitle("IOU sign in")).toBeInTheDocument();
		expect(screen.queryByLabelText("Display name")).not.toBeInTheDocument();
	});

	it("shows an expired-session error rather than displaying private profile data", async () => {
		auth.getSession.mockResolvedValue({ data: { session }, error: null });
		fetch.mockResolvedValue({ ok: false, status: 401 });
		render(<App />);
		expect(await screen.findByRole("alert")).toHaveTextContent("session is no longer valid");
		expect(screen.queryByLabelText("Display name")).not.toBeInTheDocument();
	});

	it("handles a denied OAuth callback without exposing provider details", async () => {
		window.history.replaceState({}, "", "/auth/callback?error=access_denied&error_description=private");
		render(<App />);
		expect(await screen.findByRole("alert")).toHaveTextContent("Google sign-in could not be completed");
		expect(window.location.search).toBe("");
	});

	it("reports an unsuccessful code exchange even when the SDK returns no session", async () => {
		window.history.replaceState({}, "", "/auth/callback?code=expired-code");
		render(<App />);
		expect(await screen.findByRole("alert")).toHaveTextContent("Google sign-in could not be completed");
		expect(window.location.search).toBe("");
	});

	it("can retry loading a profile after a backend outage", async () => {
		auth.getSession.mockResolvedValue({ data: { session }, error: null });
		fetch.mockResolvedValueOnce({ ok: false, status: 503 });
		render(<App />);
		fireEvent.click(await screen.findByRole("button", { name: "Retry profile" }));
		await waitFor(() => expect(screen.getByLabelText("Display name")).toHaveValue("Person"));
	});
});
