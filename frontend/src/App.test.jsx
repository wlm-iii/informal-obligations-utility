// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { StrictMode } from "react";

const { auth } = vi.hoisted(() => ({ auth: {
	getSession: vi.fn(), onAuthStateChange: vi.fn(), signInWithOAuth: vi.fn(), signOut: vi.fn(),
} }));
vi.mock("./services/supabase", () => ({ supabase: { auth } }));
import App from "./App";

const session = { access_token: "test-access-token", user: { id: "user-1" } };
const profile = { id: "user-1", email: "person@example.com", display_name: "Person", timezone: "UTC" };
let onAuthChange;

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
	it("starts Google sign-in with the frontend callback", async () => {
		render(<App />);
		fireEvent.click(await screen.findByRole("button", { name: "Continue with Google" }));
		expect(auth.signInWithOAuth).toHaveBeenCalledWith({
			provider: "google", options: { redirectTo: `${window.location.origin}/auth/callback` },
		});
	});

	it("shows a safe error when OAuth cannot start", async () => {
		auth.signInWithOAuth.mockResolvedValue({ error: new Error("provider detail") });
		render(<App />);
		fireEvent.click(await screen.findByRole("button", { name: "Continue with Google" }));
		expect(await screen.findByRole("alert")).toHaveTextContent("Unable to start Google sign-in");
		expect(screen.queryByText("provider detail")).not.toBeInTheDocument();
	});

	it("restores a callback session in StrictMode and removes the code from the URL", async () => {
		window.history.replaceState({}, "", "/auth/callback?code=one-time-code");
		auth.getSession.mockResolvedValue({ data: { session }, error: null });
		render(<StrictMode><App /></StrictMode>);
		fireEvent.click(await screen.findByRole("button", { name: /Your account|Person/ }));
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
		fireEvent.click(await screen.findByRole("button", { name: /Your account|Person/ }));
		fireEvent.change(await screen.findByLabelText("Display name"), { target: { value: "New Name" } });
		fireEvent.change(screen.getByLabelText("Timezone"), { target: { value: "America/Los_Angeles" } });
		fireEvent.click(screen.getByRole("button", { name: "Save profile" }));
		expect(await screen.findByText("Profile saved.")).toBeInTheDocument();
		expect(fetch).toHaveBeenCalledWith("/api/me", expect.objectContaining({
			method: "PATCH", body: JSON.stringify({ display_name: "New Name", timezone: "America/Los_Angeles" }),
		}));
		fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
		expect(await screen.findByRole("button", { name: "Continue with Google" })).toBeInTheDocument();
		expect(screen.queryByLabelText("Display name")).not.toBeInTheDocument();
	});

	it("shows an expired-session error rather than displaying private profile data", async () => {
		auth.getSession.mockResolvedValue({ data: { session }, error: null });
		fetch.mockResolvedValue({ ok: false, status: 401 });
		render(<App />);
		expect(await screen.findByText("Your session is no longer valid. Please sign in again.")).toBeInTheDocument();
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
		fetch.mockImplementation(async url => ({ ok: true, status: 200, json: async () => url === "/api/me" ? profile : { items: [], has_more: false } }));
  const defaultFetch = fetch.getMockImplementation();
  let profileFailed = false;
  fetch.mockImplementation(async url => {
   if (url === "/api/me" && !profileFailed) { profileFailed = true; return { ok: false, status: 503 }; }
   return defaultFetch(url);
  });
		render(<App />);
		fireEvent.click(await screen.findByRole("button", { name: /Your account|Person/ }));
		fireEvent.click(await screen.findByRole("button", { name: "Retry profile" }));
		await waitFor(() => expect(screen.getByLabelText("Display name")).toHaveValue("Person"));
	});
});

it("lands on the debt ledger after Google login and switches through the main tabs", async () => {
 auth.getSession.mockResolvedValue({ data: { session }, error: null });
 fetch.mockImplementation(async url => ({ ok: true, status: 200, json: async () => url === "/api/me" ? profile : { items: [], has_more: false } }));
 render(<App />);
 expect(await screen.findByRole("heading", { name: /The debt ledger/ })).toBeInTheDocument();
 const nav = screen.getByRole("navigation", { name: "Main navigation" });
 expect(screen.getByRole("button", { name: "IOU dashboard" })).toBeInTheDocument();
 expect(within(nav).getByRole("button", { name: "Dashboard" })).toHaveAttribute("aria-current", "page");
 fireEvent.click(within(nav).getByRole("button", { name: "Progress" }));
 expect(await screen.findByRole("heading", { name: "Still lent out vs. returned to you" })).toBeInTheDocument();
 fireEvent.click(within(nav).getByRole("button", { name: "Ranks" }));
 expect(screen.getByRole("heading", { name: "THE LEADERBOARDS." })).toBeInTheDocument();
 fireEvent.click(within(nav).getByRole("button", { name: "History" }));
 expect(screen.getByRole("heading", { name: "Borrowed. Returned. Remembered." })).toBeInTheDocument();
});
