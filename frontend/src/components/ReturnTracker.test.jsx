// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
vi.mock("../services/loans", async importOriginal => ({ ...await importOriginal(), loadLoans: vi.fn() }));
import { loadLoans } from "../services/loans";
import ReturnTracker from "./ReturnTracker";
afterEach(cleanup);
beforeEach(() => vi.resetAllMocks());
it("uses item records for the chart and all loans for debt cards", async () => {
 loadLoans.mockResolvedValue([{kind:"item",status:"open"},{kind:"item",status:"completed"},{kind:"money",status:"open"}]);
 render(<ReturnTracker />);
 expect(await screen.findByRole("img")).toHaveAccessibleName("50% still lent out; 50% returned to you.");
 expect(screen.getByText("2")).toBeInTheDocument();
});
it("handles an empty ledger", async () => {
 loadLoans.mockResolvedValue([]);render(<ReturnTracker />);
 expect(await screen.findByText("No items lent yet")).toBeInTheDocument();
 expect(screen.getByRole("img")).toHaveAccessibleName("0% still lent out; 0% returned to you.");
});
it("retries a backend failure", async () => {
 loadLoans.mockRejectedValueOnce(new Error("Unavailable")).mockResolvedValue([]);
 render(<ReturnTracker />);
 fireEvent.click(await screen.findByRole("button", {name:"Retry lending data"}));
 expect(await screen.findByText("No items lent yet")).toBeInTheDocument();
});

it("shows loading until data arrives and refreshes the displayed totals", async () => {
 let resolveRefresh;
 loadLoans.mockResolvedValueOnce([{ kind: "item", status: "open" }])
  .mockImplementationOnce(() => new Promise(resolve => { resolveRefresh = resolve; }));
 render(<ReturnTracker />);
 expect(screen.getByRole("status")).toHaveTextContent("Loading your lending overview");
 expect(await screen.findByRole("img")).toHaveAccessibleName("100% still lent out; 0% returned to you.");
 fireEvent.click(screen.getByRole("button", { name: "Refresh data" }));
 expect(screen.getByRole("status")).toHaveTextContent("Loading your lending overview");
 resolveRefresh([{ kind: "item", status: "completed" }]);
 expect(await screen.findByRole("img")).toHaveAccessibleName("0% still lent out; 100% returned to you.");
});

it("refreshes on focus and ignores an older request that finishes later", async () => {
 let resolveOld;
 loadLoans.mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }))
  .mockResolvedValueOnce([{ kind: "item", status: "completed" }]);
 render(<ReturnTracker />);
 const oldSignal = loadLoans.mock.calls[0][0];
 fireEvent.focus(window);
 expect(oldSignal.aborted).toBe(true);
 expect(await screen.findByRole("img")).toHaveAccessibleName("0% still lent out; 100% returned to you.");
 await act(async () => { resolveOld([{ kind: "item", status: "open" }]); });
 expect(screen.getByRole("img")).toHaveAccessibleName("0% still lent out; 100% returned to you.");
});

it("cancels loading and removes focus refresh when unmounted", async () => {
 let rejectRequest;
 loadLoans.mockImplementationOnce(() => new Promise((resolve, reject) => { rejectRequest = reject; }));
 const { unmount } = render(<ReturnTracker />);
 const signal = loadLoans.mock.calls[0][0];
 unmount();
 expect(signal.aborted).toBe(true);
 fireEvent.focus(window);
 expect(loadLoans).toHaveBeenCalledTimes(1);
 await act(async () => { rejectRequest(new Error("Request cancelled")); });
});

it("keeps money-only loans out of the item chart while showing debt totals", async () => {
 loadLoans.mockResolvedValue([{ kind: "money", status: "open" }, { kind: "money", status: "completed" }]);
 render(<ReturnTracker />);
 expect(await screen.findByText("No items lent yet")).toBeInTheDocument();
 expect(screen.getByRole("heading", { name: "UNPAID DEBTS" }).closest("article")).toHaveTextContent("1");
 expect(screen.getByRole("heading", { name: "REPAID DEBTS" }).closest("article")).toHaveTextContent("1");
 expect(screen.getByRole("img")).toHaveAccessibleName("0% still lent out; 0% returned to you.");
});
