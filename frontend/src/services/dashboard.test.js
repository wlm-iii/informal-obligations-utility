import { afterEach, beforeEach, expect, it, vi } from "vitest";
vi.mock("./supabase", () => ({ supabase: { auth: { getSession: vi.fn() } } }));
import { supabase } from "./supabase";
import { ledgerRequest, loadFriends, reminderFor } from "./dashboard";
beforeEach(() => {
 vi.resetAllMocks();
 supabase.auth.getSession.mockResolvedValue({ data: { session: { access_token: "private-token" } } });
 vi.stubGlobal("fetch", vi.fn());
});
afterEach(() => vi.unstubAllGlobals());
it("loads every friend page including archived names with authentication and no caching", async () => {
 fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ items: [{ id: "1" }], has_more: true }) }).mockResolvedValueOnce({ ok: true, json: async () => ({ items: [{ id: "2" }], has_more: false }) });
 const signal = new AbortController().signal;
 expect(await loadFriends(signal)).toEqual([{ id: "1" }, { id: "2" }]);
 expect(fetch).toHaveBeenNthCalledWith(2, "/api/friends?archived=include&limit=100&offset=100", expect.objectContaining({ signal, cache: "no-store", headers: { Authorization: "Bearer private-token" } }));
});
it("does not request private records without a session", async () => {
 supabase.auth.getSession.mockResolvedValue({ data: { session: null } });
 await expect(loadFriends()).rejects.toThrow("Please sign in again.");
 expect(fetch).not.toHaveBeenCalled();
});
it("creates friends with the supplied idempotency key and serialized fields", async () => {
 fetch.mockResolvedValue({ ok: true, json: async () => ({ id: "friend" }) });
 const body = { display_name: "Taylor", email: null, notes: null };
 await ledgerRequest("/friends", { body, key: "same-retry-key" });
 expect(fetch).toHaveBeenCalledWith("/api/friends", expect.objectContaining({ method: "POST", body: JSON.stringify(body), headers: expect.objectContaining({ "Idempotency-Key": "same-retry-key" }) }));
});
it("rejects malformed friend data and failed requests", async () => {
 fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ items: {} }) });
 await expect(loadFriends()).rejects.toThrow("Friend data is unavailable");
 fetch.mockResolvedValueOnce({ ok: false, status: 401 });
 await expect(loadFriends()).rejects.toThrow("Your session expired");
});
it("formats item reminders as returns instead of money debt", () => {
 const text = reminderFor({ display_name: "Sam" }, { kind: "item", description: "Blue hoodie", due_date: "2026-10-20" }, "Direct");
 expect(text).toContain("returning Blue hoodie");
 expect(text).not.toContain("$");
});
