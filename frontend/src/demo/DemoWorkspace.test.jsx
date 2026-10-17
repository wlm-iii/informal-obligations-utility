// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import "@testing-library/jest-dom/vitest";
import DemoWorkspace from "./DemoWorkspace";
import * as M from "./model";
beforeEach(() => localStorage.clear());
afterEach(cleanup);

describe("native React local demo", () => {
	it("records a partial repayment and retains the audit entry in the existing demo schema", () => {
		render(<DemoWorkspace onClose={() => {}} />);
		fireEvent.click(screen.getAllByRole("button", { name: "View receipt" })[0]);
		const dialog = screen.getByRole("dialog");
		fireEvent.change(within(dialog).getByLabelText("Repayment amount (USD)"), { target: { value: "5.00" } });
		fireEvent.click(within(dialog).getByRole("button", { name: "Record repayment" }));
		const saved = JSON.parse(localStorage.getItem("iou-demo-v1"));
		expect(M.balance(saved.loans.find(loan => loan.id === "demo-boba"))).toBe(1500);
		expect(saved.activity[0].description).toBe("Repayment recorded");
		expect(screen.getByRole("dialog")).toHaveTextContent("$15.00 outstanding");
	});
	it("adds an item reminder through labeled React form controls", () => {
		render(<DemoWorkspace onClose={() => {}} />);
		fireEvent.click(screen.getByRole("button", { name: "Add reminder" }));
		const form = screen.getByRole("dialog");
		fireEvent.change(within(form).getByLabelText("Friend's name"), { target: { value: "Taylor" } });
		fireEvent.change(within(form).getByLabelText("Friend's email"), { target: { value: "taylor@example.com" } });
		fireEvent.change(within(form).getByLabelText("What was borrowed?"), { target: { value: "item" } });
		fireEvent.change(within(form).getByLabelText("Item"), { target: { value: "Spare charger" } });
		fireEvent.change(within(form).getByLabelText("Repayment method"), { target: { value: "return" } });
		fireEvent.click(within(form).getByRole("button", { name: "Save reminder" }));
		expect(screen.getByText("Spare charger")).toBeInTheDocument();
		const saved = JSON.parse(localStorage.getItem("iou-demo-v1"));
		expect(saved.loans[0]).toMatchObject({ type: "item", item: "Spare charger", principal: 0, method: "return" });
	});
	it("does not overwrite unreadable saved demo data until the user resets it", () => {
		localStorage.setItem("iou-demo-v1", "bad-data");
		render(<DemoWorkspace onClose={() => {}} />);
		expect(screen.getByRole("alert")).toHaveTextContent("could not be read");
		expect(localStorage.getItem("iou-demo-v1")).toBe("bad-data");
		fireEvent.click(screen.getByRole("button", { name: "Reset demo" }));
		expect(JSON.parse(localStorage.getItem("iou-demo-v1")).loans.length).toBeGreaterThan(0);
	});
	it("preserves integer-cent settlement and rejects overpayment", () => {
		const loan = M.demo().loans[0];
		expect(() => M.settle(loan, M.balance(loan) + 1, M.date())).toThrow(/outstanding balance/);
		expect(loan.payments).toHaveLength(0);
		M.settle(loan, M.balance(loan), M.date());
		expect(M.balance(loan)).toBe(0); expect(M.status(loan)).toBe("closed");
	});
});
