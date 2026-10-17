import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
vi.mock("./supabase", () => ({ supabase: { auth: { getSession: vi.fn() } } }));
import { supabase } from "./supabase";
import { loadLoans, summarizeLoans } from "./loans";

beforeEach(() => {
 vi.resetAllMocks();
 supabase.auth.getSession.mockResolvedValue({ data: { session: { access_token: "token" } }, error: null });
 vi.stubGlobal("fetch", vi.fn());
});
afterEach(() => vi.unstubAllGlobals());

it("loads all authenticated pages without caching private data", async () => {
 fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ items: [{ id: 1 }], has_more: true }) })
  .mockResolvedValueOnce({ ok: true, json: async () => ({ items: [{ id: 2 }], has_more: false }) });
 const signal = new AbortController().signal;
 expect(await loadLoans(signal)).toEqual([{ id: 1 }, { id: 2 }]);
 expect(fetch).toHaveBeenCalledTimes(2);
 for (const [index, offset] of [0, 100].entries()) {
  expect(fetch).toHaveBeenNthCalledWith(index + 1, `/api/loans?limit=100&offset=${offset}`, {
   signal, cache: "no-store", headers: { Authorization: "Bearer token" },
  });
 }
});

it.each([
 { data: { session: null }, error: null },
 { data: { session: null }, error: new Error("Auth unavailable") },
])("rejects an unavailable session before requesting private data: %j", async session => {
 supabase.auth.getSession.mockResolvedValue(session);
 await expect(loadLoans()).rejects.toThrow("Please sign in again to view lending data.");
 expect(fetch).not.toHaveBeenCalled();
});

it.each([
 [401, "Your session expired. Please sign in again."],
 [503, "Lending data is unavailable. Please retry."],
])("reports HTTP %s without returning partial data", async (status, message) => {
 fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ items: [{ id: 1 }], has_more: true }) })
  .mockResolvedValueOnce({ ok: false, status });
 await expect(loadLoans()).rejects.toThrow(message);
});

it.each([{}, { items: null }, { items: {} }])("rejects malformed loan pages: %j", async page => {
 fetch.mockResolvedValue({ ok: true, json: async () => page });
 await expect(loadLoans()).rejects.toThrow("Lending data is unavailable. Please retry.");
});

it("propagates request cancellation", async () => {
 const controller = new AbortController();
 controller.abort();
 fetch.mockRejectedValue(new DOMException("Aborted", "AbortError"));
 await expect(loadLoans(controller.signal)).rejects.toMatchObject({ name: "AbortError" });
 expect(fetch).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ signal: controller.signal }));
});

it("stops a ledger that keeps reporting more pages", async () => {
 fetch.mockResolvedValue({ ok: true, json: async () => ({ items: [], has_more: true }) });
 await expect(loadLoans()).rejects.toThrow("Your ledger is too large to display completely.");
 expect(fetch).toHaveBeenCalledTimes(1001);
});

describe("summarizeLoans", () => {
 it("counts item returns separately from money and all-loan debt totals", () => {
  expect(summarizeLoans([
   { kind: "item", status: "open" }, { kind: "item", status: "open" },
   { kind: "item", status: "completed" }, { kind: "money", status: "open" },
   { kind: "money", status: "completed" },
  ])).toEqual({ outstanding: 2, returned: 1, unpaid: 3, repaid: 2 });
 });
 it("returns zero totals for an empty ledger", () => {
  expect(summarizeLoans([])).toEqual({ outstanding: 0, returned: 0, unpaid: 0, repaid: 0 });
 });
});
