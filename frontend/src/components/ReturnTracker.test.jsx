// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
