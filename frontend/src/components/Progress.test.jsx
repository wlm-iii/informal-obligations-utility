// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import Progress from "./Progress";
import { demoFriends, demoLoans, demoPayments } from "../services/dashboardDemo";
afterEach(() => { cleanup(); vi.useRealTimers(); });
it("shows the simplified headline, recorded totals and repayment chart", async () => {
 render(<Progress loans={demoLoans} friends={demoFriends} demo={{ payments: demoPayments }} onRefresh={vi.fn()}/>);
 expect(screen.getByRole("heading", {name:"Your lending, at a glance"})).toBeInTheDocument();
 expect(screen.queryByText("THE RETURN BREAKDOWN.")).not.toBeInTheDocument();
 expect(screen.getByRole("progressbar")).toHaveAttribute("value", "24");
 expect(screen.getByRole("img", {name:"$25.00 repaid across 3 payments"})).toBeInTheDocument();
 expect(screen.getByText("3 recorded payments")).toBeInTheDocument();
 expect(screen.queryByRole("heading", {name:"Still lent out vs. returned to you"})).not.toBeInTheDocument();
});
it("filters by repayment dates and invokes refresh without inventing empty data", () => {
 vi.useFakeTimers(); vi.setSystemTime(new Date("2026-12-01T00:00:00Z"));
 const refresh=vi.fn();
 render(<Progress loans={demoLoans} friends={demoFriends} demo={{payments:demoPayments}} onRefresh={refresh}/>);
 fireEvent.click(screen.getByRole("button", {name:"30D"}));
 expect(screen.getByText("No recorded repayments in this period.")).toBeInTheDocument();
 expect(screen.getByRole("button",{name:"30D"})).toHaveAttribute("aria-pressed","true");
 fireEvent.click(screen.getByRole("button",{name:"90D"}));
 expect(screen.getByRole("img", {name:"$25.00 repaid across 3 payments"})).toBeInTheDocument();
 fireEvent.click(screen.getByRole("button",{name:"Refresh data"}));
 expect(refresh).toHaveBeenCalledTimes(1);
});
