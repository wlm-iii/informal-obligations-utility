import { expect, it } from "vitest";
import { withDailyInterest } from "./interest";
const loan = {kind:"money",principal_cents:10000,repaid_cents:0,due_date:"2026-10-15",interest_percent:2,repayment_type:"money",timezone:"America/Los_Angeles"};
it("starts after the local due date and adds simple interest each day", () => {
 expect(withDailyInterest(loan,"2026-10-16T06:59:00Z").interest_cents).toBe(0);
 expect(withDailyInterest(loan,"2026-10-16T07:00:00Z").interest_cents).toBe(200);
 const third = withDailyInterest(loan,"2026-10-18T12:00:00Z");
 expect(third.interest_cents).toBe(600); expect(third.outstanding_cents).toBe(10600);
 expect(withDailyInterest({...loan,repaid_cents:5000},"2026-10-18T12:00:00Z").outstanding_cents).toBe(5600);
});
it("ignores interest on items and item repayments and freezes settled records", () => {
 expect(withDailyInterest({...loan,kind:"item"},"2026-10-18T12:00:00Z").interest_cents).toBe(0);
 expect(withDailyInterest({...loan,repayment_type:"item"},"2026-10-18T12:00:00Z").interest_cents).toBe(0);
 const closed=withDailyInterest({...loan,repaid_cents:10200,completed_at:"2026-10-16T12:00:00Z"},"2026-11-18T12:00:00Z");
 expect(closed.interest_cents).toBe(200);expect(closed.outstanding_cents).toBe(0);expect(closed.status).toBe("completed");
});
it("rounds fractional cents half up and supports DST calendar boundaries", () => {
 expect(withDailyInterest({...loan,principal_cents:5,interest_percent:10},"2026-10-16T12:00:00Z").interest_cents).toBe(1);
 expect(withDailyInterest({...loan,due_date:"2026-10-31"},"2026-11-02T08:00:00Z").interest_days).toBe(2);
});
