// @vitest-environment jsdom
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import Dashboard from "./Dashboard";
import { demoFriends, demoLoans } from "../services/dashboardDemo";
const demo = { friends: demoFriends, loans: demoLoans };
beforeEach(() => {
 HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
 Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: vi.fn().mockResolvedValue() } });
});
afterEach(cleanup);
it("searches loans and opens the selected friend's stats and borrowing history", () => {
 render(<Dashboard demo={demo}/>);
 fireEvent.change(screen.getByRole("textbox", { name: "Search counterparty" }), { target: { value: "Blue hoodie" } });
 expect(screen.queryByRole("button", { name: "Maya Chen" })).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole("button", { name: "Sam Park", exact: true }));
 expect(screen.getByRole("heading", { name: "Sam Park" })).toBeInTheDocument();
 expect(screen.getByText("Emergency snack supplier.")).toBeInTheDocument();
 expect(screen.getByRole("heading", { name: "Blue hoodie" })).toBeInTheDocument();
 expect(screen.queryByRole("heading", { name: /Boba acquisition/ })).not.toBeInTheDocument();
});
it("edits nudge tone and copies the edited message without sending it", async () => {
 render(<Dashboard demo={demo}/>);
 fireEvent.click(screen.getAllByRole("button", { name: "Nudge ↗" })[0]);
 const dialog = screen.getByRole("dialog");
 expect(within(dialog).getByRole("textbox", { name: "Reminder" }).value).toContain("Maya Chen");
 fireEvent.change(within(dialog).getByLabelText("Tone"), { target: { value: "Direct" } });
 expect(within(dialog).getByLabelText("Reminder").value).toContain("$18.50");
 fireEvent.change(within(dialog).getByLabelText("Reminder"), { target: { value: "My own reminder" } });
 fireEvent.click(within(dialog).getByRole("button", { name: "Copy reminder ↗" }));
 expect(await within(dialog).findByText("Reminder copied.")).toBeInTheDocument();
 expect(navigator.clipboard.writeText).toHaveBeenCalledWith("My own reminder");
 fireEvent.click(within(dialog).getByRole("button", { name: "Close dialog" }));
 expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
it("handles clipboard denial with a manual-copy message", async () => {
 navigator.clipboard.writeText.mockRejectedValue(new Error("denied"));
 render(<Dashboard demo={demo}/>);
 fireEvent.click(screen.getAllByRole("button", { name: "Nudge ↗" })[0]);
 fireEvent.click(screen.getByRole("button", { name: "Copy reminder ↗" }));
 expect(await screen.findByText(/Copy unavailable/)).toBeInTheDocument();
});
it("adds a friend through the plus button and shows open and returned history", async () => {
 render(<Dashboard demo={demo}/>);
 fireEvent.click(screen.getByRole("button", { name: "Add friend", exact: true }));
 const dialog = screen.getByRole("dialog");
 fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "Taylor" } });
 fireEvent.click(within(dialog).getByRole("button", { name: "Add friend" }));
 expect(await screen.findByRole("button", { name: /Taylor/ })).toBeInTheDocument();
 fireEvent.click(screen.getByRole("button", { name: "History", exact: true }));
 expect(screen.getByText("Returned", { selector: ".recorded-badge" })).toBeInTheDocument();
 expect(screen.getAllByText("Not returned / open", { selector: ".recorded-badge" })).toHaveLength(3);
});
it("opens the sample progress chart and ranks from the same navigation", async () => {
 render(<Dashboard demo={demo}/>);
 fireEvent.click(screen.getByRole("button", { name: "Progress", exact: true }));
 expect(await screen.findByRole("heading",{name:"Cumulative repayments"})).toBeInTheDocument();
 fireEvent.click(screen.getByRole("button", { name: "Ranks", exact: true }));
 expect(screen.getByRole("region", { name: "Hall of Fame" })).toBeInTheDocument();
 expect(screen.getByRole("region", { name: "Hall of Shame" })).toBeInTheDocument();
});

it("shows the user's account in the same profile layout with ledger stats and settings", () => {
 render(<Dashboard demo={demo} profile={{ display_name: "Anca", email: "anca@example.com" }} account={<button>Sign out</button>}/>);
 fireEvent.click(screen.getByRole("button", { name: "Anca ↗" }));
 const profile = screen.getByRole("region", { name: "Your profile" });
 expect(within(profile).getByRole("heading", { name: "Anca" })).toBeInTheDocument();
 expect(within(profile).getByText("anca@example.com")).toBeInTheDocument();
 expect(within(profile).getByText("$78.50")).toBeInTheDocument();
 for (const [label, value] of [["Friends", "4"], ["Money outstanding", "$78.50"], ["Money repaid", "$25.00"], ["Items still out", "1"], ["Items returned", "1"]]) {
  expect(within(within(profile).getByText(label).closest("article")).getByText(value)).toBeInTheDocument();
 }
 expect(within(profile).getByRole("heading", { name: "Borrowing history" })).toBeInTheDocument();
 expect(within(profile).getByRole("button", { name: "Sign out" })).toBeInTheDocument();
});
