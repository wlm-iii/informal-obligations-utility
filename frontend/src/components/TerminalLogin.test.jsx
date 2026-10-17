// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
const { auth } = vi.hoisted(() => ({ auth: { signInWithOAuth: vi.fn(), signInWithPassword: vi.fn() } }));
vi.mock("../services/supabase", () => ({ supabase: { auth } }));
import TerminalLogin from "./TerminalLogin";
beforeEach(() => { vi.resetAllMocks(); auth.signInWithOAuth.mockResolvedValue({ error: null }); auth.signInWithPassword.mockResolvedValue({ error: null }); });
afterEach(cleanup);

describe("React terminal login", () => {
	it("renders the design directly without an iframe or a copied HTML document", () => {
		const { container } = render(<TerminalLogin />);
		expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Friendshipis free. Yourstuff isn't.");
		expect(container.querySelector("iframe")).toBeNull();
	});
	it("shows and hides the controlled password value", () => {
		render(<TerminalLogin />); const input = screen.getByLabelText("Password");
		fireEvent.change(input, { target: { value: "secret" } });
		fireEvent.click(screen.getByRole("button", { name: "Show password" })); expect(input).toHaveAttribute("type", "text");
		fireEvent.click(screen.getByRole("button", { name: "Hide password" })); expect(input).toHaveAttribute("type", "password");
	});
	it("clears a submitted password, prevents duplicate requests, and restores controls on failure", async () => {
		let finish; auth.signInWithPassword.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
		render(<TerminalLogin />);
		fireEvent.change(screen.getByLabelText("Email"), { target: { value: "person@example.com" } });
		fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong-password" } });
		const button = screen.getByRole("button", { name: /^Sign in/ }); fireEvent.click(button);
		expect(screen.getByLabelText("Password")).toHaveValue(""); expect(button).toBeDisabled();
		fireEvent.click(button); expect(auth.signInWithPassword).toHaveBeenCalledTimes(1);
		finish({ error: new Error("private provider details") });
		expect(await screen.findByRole("alert")).toHaveTextContent("Unable to sign in");
		expect(screen.queryByText("private provider details")).not.toBeInTheDocument(); await waitFor(() => expect(button).toBeEnabled());
	});
	it("pauses the decorative background through the React control", () => {
		render(<TerminalLogin />); const control = screen.getByRole("button", { name: "Pause motion", hidden: true });
		fireEvent.click(control); expect(screen.getByRole("button", { name: "Resume motion", hidden: true })).toHaveAttribute("aria-pressed", "true");
	});
});
