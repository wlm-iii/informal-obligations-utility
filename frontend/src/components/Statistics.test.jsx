// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import Statistics from "./Statistics";
import { amountToCents } from "../services/repayments";
afterEach(cleanup);
const loan = {
	id: "loan",
	friend_id: "alex",
	kind: "money",
	status: "open",
	description: "Lunch",
	principal_cents: 10000,
	repaid_cents: 2500,
	outstanding_cents: 7500,
};
const initialData = {
	friends: [
		{ id: "alex", display_name: "Alex Morgan", email: "alex@example.com" },
		{ id: "jamie", display_name: "Jamie Chen" },
	],
	loans: [loan],
	history: [
		{
			id: "payment",
			action: "repayment",
			amount_cents: 2500,
			effective_at: new Date(Date.now() - 86400000).toISOString(),
			loan,
			note: "Lunch paid back",
		},
	],
};
describe("interactive statistics", () => {
	it("opens a keyboard-accessible payment receipt", () => {
		render(<Statistics initialData={initialData} />);
		fireEvent.click(screen.getByRole("button", { name: /View receipt for Lunch/ }));
		expect(screen.getByRole("dialog")).toHaveTextContent("Lunch paid back");
		fireEvent.click(screen.getByRole("button", { name: "Close dialog" }));
		expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
	});
	it("records a demo repayment and celebrates a settled balance", async () => {
		render(<Statistics initialData={initialData} />);
		fireEvent.click(screen.getByRole("button", { name: "Record repayment" }));
		fireEvent.click(screen.getByRole("button", { name: "Use full remaining balance" }));
		fireEvent.click(screen.getByRole("button", { name: "Record received payment" }));
		expect(await screen.findByRole("status")).toHaveTextContent("All settled!");
		expect(screen.getByRole("progressbar")).toHaveAttribute("value", "100");
		expect(screen.getByRole("button", { name: "Record repayment" })).toBeDisabled();
	});
	it("rejects overpayment and preserves the balance", async () => {
		render(<Statistics initialData={initialData} />);
		fireEvent.click(screen.getByRole("button", { name: "Record repayment" }));
		fireEvent.change(screen.getByLabelText("Amount (USD)"), {
			target: { value: "76.00" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Record received payment" }));
		expect(await screen.findByRole("alert")).toHaveTextContent("must not exceed");
		expect(screen.getByRole("progressbar")).toHaveAttribute("value", "25");
	});
	it("changes reminder tone and lets the user edit the message", () => {
		render(<Statistics initialData={initialData} />);
		fireEvent.click(screen.getByRole("button", { name: "Draft reminder" }));
		fireEvent.click(screen.getByRole("button", { name: "corporate" }));
		expect(screen.getByLabelText("Your reminder").value).toContain(
			"Friendship Finance Department",
		);
		fireEvent.change(screen.getByLabelText("Your reminder"), {
			target: { value: "My own message" },
		});
		expect(screen.getByLabelText("Your reminder")).toHaveValue("My own message");
	});
	it("switches contact without retaining another contact balance", () => {
		render(<Statistics initialData={initialData} />);
		fireEvent.change(screen.getByLabelText("TRACKING"), { target: { value: "jamie" } });
		expect(screen.getByRole("button", { name: "Draft reminder" })).toBeDisabled();
		expect(
			within(screen.getByLabelText("Person being tracked")).getByText("JC"),
		).toBeInTheDocument();
	});
	it("parses exact cents and rejects extra decimals", () => {
		expect(amountToCents("12.34")).toBe(1234);
		expect(() => amountToCents("1.005")).toThrow();
		expect(() => amountToCents("-5")).toThrow();
	});
});
