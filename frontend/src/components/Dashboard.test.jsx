// @vitest-environment jsdom
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import Dashboard from "./Dashboard";
import { demoFriends, demoLoans } from "../services/dashboardDemo";
vi.mock("../services/dashboard", async importOriginal => ({ ...await importOriginal(), ledgerRequest: vi.fn(), loadFriends: vi.fn() }));
vi.mock("../services/loans", async importOriginal => ({ ...await importOriginal(), loadLoans: vi.fn() }));
import { ledgerRequest, loadFriends } from "../services/dashboard";
import { loadLoans } from "../services/loans";
const demo = { friends: demoFriends, loans: demoLoans };
beforeEach(() => {
 vi.clearAllMocks();
 HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
 Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: vi.fn().mockResolvedValue() } });
});
afterEach(cleanup);
it.each([["Boba acquisition", "Repaid"], ["Blue hoodie", "Returned"]])("settles %s, opens History and removes it from the dashboard", async (description, status) => {
 render(<Dashboard demo={demo}/>);
 const row = screen.getAllByText(new RegExp(description))[0].closest("article");
 fireEvent.click(within(row).getByRole("button",{name:"Settle",exact:true}));
 expect(screen.getByRole("button",{name:"History",exact:true})).toHaveAttribute("aria-current","page");
 const historyRow = screen.getAllByRole("row").find(row => row.textContent.includes(description) && row.textContent.includes(status));
 expect(historyRow).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Dashboard",exact:true}));
 expect(screen.queryByText(new RegExp(description))).not.toBeInTheDocument();
 expect(screen.getAllByRole("button",{name:"Settle",exact:true})).toHaveLength(2);
});

it("keeps an IOU visible after a failed settlement and retries with the same key", async () => {
 loadFriends.mockResolvedValue(demoFriends); loadLoans.mockResolvedValue(demoLoans);
 ledgerRequest.mockRejectedValueOnce(new Error("Unable to save settlement")).mockResolvedValueOnce({loan:{...demoLoans[0],status:"completed",outstanding_cents:0,repaid_cents:1850}});
 render(<Dashboard/>);
 const settle = (await screen.findAllByRole("button",{name:"Settle",exact:true}))[0];
 fireEvent.click(settle);
 expect(await screen.findByRole("alert")).toHaveTextContent("Unable to save settlement");
 expect(screen.getByRole("button",{name:"Dashboard",exact:true})).toHaveAttribute("aria-current","page");
 fireEvent.click(settle);
 await screen.findByRole("heading",{name:"Past payments"});
 expect(ledgerRequest.mock.calls[0][0]).toBe("/loans/1/repayments");
 expect(ledgerRequest.mock.calls[0][1].body).toEqual({amount_cents:1850});
 expect(ledgerRequest.mock.calls[1][1].key).toBe(ledgerRequest.mock.calls[0][1].key);
});
it("hides and clears daily interest when repayment changes to item", () => {
 render(<Dashboard demo={demo}/>);
 fireEvent.click(screen.getByRole("button",{name:"Add friend",exact:true}));
 fireEvent.change(screen.getByLabelText("Type"),{target:{value:"amount"}});
 fireEvent.change(screen.getByLabelText("Repayment type"),{target:{value:"money"}});
 fireEvent.change(screen.getByRole("slider"),{target:{value:"25"}});
 fireEvent.change(screen.getByLabelText("Repayment type"),{target:{value:"item"}});
 expect(screen.queryByRole("slider")).not.toBeInTheDocument();
 expect(screen.queryByText(/Interest is not automatically/)).not.toBeInTheDocument();
 fireEvent.change(screen.getByLabelText("Repayment type"),{target:{value:"money"}});
 expect(screen.getByRole("slider")).toHaveValue("0");
});
it("preserves a saved friend and retries a failed IOU without creating a duplicate", async () => {
 loadFriends.mockResolvedValue([]); loadLoans.mockResolvedValue([]);
 ledgerRequest.mockResolvedValueOnce({id:"saved",display_name:"Riley"}).mockRejectedValueOnce(new Error("Offline")).mockResolvedValueOnce({id:"iou",friend_id:"saved",kind:"money",description:"Money lent",status:"open",outstanding_cents:1234,principal_cents:1234,repaid_cents:0,due_date:"2099-12-01"});
 render(<Dashboard/>);
 await screen.findByText("Your ledger is clear. Add a friend to start your circle.");
 fireEvent.click(screen.getByRole("button", { name:"Add friend", exact:true }));
 const dialog = screen.getByRole("dialog");
 for (const [label,value] of [["Name","Riley"],["Email","riley@example.com"],["Type","amount"],["Amount (USD)","12.34"],["Due date","2099-12-01"],["Repayment type","other"],["Repayment details","Dinner"]]) {
  fireEvent.change(within(dialog).getByLabelText(label),{target:{value}});
 }
 fireEvent.click(within(dialog).getByRole("button",{name:"Add friend"}));
 expect(await within(dialog).findByRole("alert")).toHaveTextContent("Your friend was saved");
 expect(within(dialog).getByLabelText("Name")).toHaveAttribute("readonly");
 const firstSave = ledgerRequest.mock.calls[1];
 expect(firstSave[0]).toBe("/loans");
 expect(firstSave[1].body).toEqual({friend_id:"saved",kind:"money",description:"Money lent",principal_cents:1234,due_date:"2099-12-01",repayment_type:"other",repayment_other:"Dinner",interest_percent:0});
 fireEvent.click(within(dialog).getByRole("button",{name:"Add friend"}));
 await screen.findByRole("button",{name:"Riley",exact:true});
 expect(ledgerRequest.mock.calls.filter(([path])=>path==="/friends")).toHaveLength(1);
 expect(ledgerRequest.mock.calls[2][1].key).toBe(firstSave[1].key);
 expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("changes the avatar color when the active IOU count reaches zero", async () => {
 render(<Dashboard demo={demo}/>);
 const sidebar = screen.getByRole("navigation", {name:"Friends"});
 const avatar = () => within(sidebar).getByRole("button",{name:/Maya Chen/}).querySelector(".friend-avatar").style.getPropertyValue("--avatar-bg");
 const before = avatar();
 fireEvent.click(screen.getByRole("button",{name:"Progress",exact:true}));
 fireEvent.click(screen.getByRole("button",{name:/Record repayment/}));
 fireEvent.change(screen.getByLabelText("Amount (USD)"),{target:{value:"18.50"}});
 fireEvent.click(screen.getByRole("button",{name:"Record payment"}));
 expect(within(sidebar).getByRole("button",{name:/Maya Chen/})).toHaveTextContent("0 Active IOU's");
 expect(avatar()).not.toBe(before);
});
it("requires valid money details and saves the amount and repayment preference", async () => {
 render(<Dashboard demo={demo}/>);
 fireEvent.click(screen.getByRole("button", { name: "Add friend", exact: true }));
 const dialog = screen.getByRole("dialog");
 const change = (label, value) => fireEvent.change(within(dialog).getByLabelText(label), { target: { value } });
 change("Name", "Riley"); change("Email", "riley@example.com"); change("Type", "amount");
 change("Due date", "2099-12-01"); change("Repayment type", "money");
 const submit = within(dialog).getByRole("button", { name: "Add friend" });
 change("Amount (USD)", "0"); expect(submit).toBeDisabled();
 change("Amount (USD)", "12.345"); expect(submit).toBeDisabled();
 change("Amount (USD)", "12.34"); expect(submit).toBeEnabled();
 change("Email", "invalid"); expect(submit).toBeDisabled();
 change("Email", "riley@example.com"); expect(submit).toBeEnabled();
 fireEvent.click(submit);
 expect(await screen.findByRole("button", { name: "Riley", exact: true })).toBeInTheDocument();
 expect(screen.getByText("$12.34")).toBeInTheDocument();
 expect(screen.getByText("Repay: money")).toBeInTheDocument();
 const row = screen.getByRole("button", { name: "Riley", exact: true }).closest("article");
 const sidebar = screen.getByRole("navigation", { name: "Friends" });
 const avatar = within(sidebar).getByRole("button", { name: /Riley/ }).querySelector(".friend-avatar");
 expect(avatar.style.getPropertyValue("--avatar-bg")).toBe(row.querySelector(".friend-avatar").style.getPropertyValue("--avatar-bg"));
});
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
 expect(within(dialog).getByRole("button", { name: "Add friend" })).toBeDisabled();
 fireEvent.change(within(dialog).getByLabelText("Email"), { target: { value: "taylor@example.com" } });
 fireEvent.change(within(dialog).getByLabelText("Type"), { target: { value: "item" } });
 fireEvent.change(within(dialog).getByLabelText("Item"), { target: { value: "Camera" } });
 fireEvent.change(within(dialog).getByLabelText("Due date"), { target: { value: "2099-12-01" } });
 fireEvent.change(within(dialog).getByLabelText("Repayment type"), { target: { value: "other" } });
 expect(within(dialog).getByRole("button", { name: "Add friend" })).toBeDisabled();
 fireEvent.change(within(dialog).getByLabelText("Repayment details"), { target: { value: "Dinner" } });
 expect(within(dialog).queryByRole("slider")).not.toBeInTheDocument();
 expect(within(dialog).getByRole("button", { name: "Add friend" })).toBeEnabled();
 fireEvent.click(within(dialog).getByRole("button", { name: "Add friend" }));
 expect(await screen.findByRole("button", { name: "Taylor", exact: true })).toBeInTheDocument();
 expect(screen.getByText("Repay: Dinner")).toBeInTheDocument();
 expect(screen.getAllByText("Camera").length).toBeGreaterThan(0);
 fireEvent.click(screen.getByRole("button", { name: "History", exact: true }));
 expect(screen.getByText("Returned", { selector: ".recorded-badge" })).toBeInTheDocument();
 expect(screen.getAllByText("Not returned / open", { selector: ".recorded-badge" })).toHaveLength(4);
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
