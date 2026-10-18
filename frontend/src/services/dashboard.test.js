import { afterEach, beforeEach, expect, it, vi } from "vitest";
vi.mock("./supabase", () => ({ supabase: { auth: { getSession: vi.fn() } } }));
import { supabase } from "./supabase";
import { activePayments, ledgerRequest, loadFriends, reminderFor, reminderTones } from "./dashboard";
beforeEach(() => {
 vi.resetAllMocks();
 supabase.auth.getSession.mockResolvedValue({ data: { session: { access_token: "private-token" } } });
 vi.stubGlobal("fetch", vi.fn());
});
afterEach(() => vi.unstubAllGlobals());
it("offers distinct reminder voices for money and items", () => {
 for (const kind of ["money", "item"]) {
  const messages = reminderTones.map(tone => reminderFor({display_name:"Taylor"}, {kind,description:"Camera",outstanding_cents:1250,due_date:"2099-12-01"},tone));
  expect(new Set(messages).size).toBe(reminderTones.length);
  for (const message of messages) { expect(message).toContain("Taylor"); expect(message).toContain("Camera"); }
 }
});
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
it("excludes reversals, waivers, and voided obligations from cash history",()=>{
 const loans=[{id:"a",status:"open"},{id:"v",status:"voided"}];
 const events=[{id:"cash",action:"repayment",loan:{id:"a"}},
 {id:"fees",action:"fee_payment",loan_id:"a"},
 {id:"reversed",action:"repayment",loan_id:"a",reversed_at:"2026-01-02"},
 {id:"waived",action:"waiver",loan_id:"a"},{id:"void",action:"repayment",loan_id:"v"}];
 expect(activePayments(events,loans).map(event=>event.id)).toEqual(["cash","fees"]);
});
it("formats item reminders as returns instead of money debt", () => {
 const text = reminderFor({ display_name: "Sam" }, { kind: "item", description: "Blue hoodie", due_date: "2026-10-20" }, "Direct");
 expect(text).toContain("returning Blue hoodie");
 expect(text).not.toContain("$");
});
