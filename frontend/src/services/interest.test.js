import { expect, it } from "vitest";
import { interestLabel, itemReturned, percentToBps, totalOutstanding } from "./interest";

it("uses the authoritative total without adding interest twice", () => {
 expect(totalOutstanding({outstanding_cents:10000,interest_cents:500,fees_cents:200,total_outstanding_cents:10700})).toBe(10700);
 expect(totalOutstanding({outstanding_cents:10000,interest_cents:500,fees_cents:200})).toBe(10700);
 expect(totalOutstanding({kind:"item",outstanding_cents:null,fees_cents:200})).toBe(200);
});
it("formats periodic terms and converts percentages exactly to basis points", () => {
 expect(percentToBps("1.25")).toBe(125);
 expect(percentToBps("0")).toBe(0);
 expect(percentToBps("100")).toBe(10000);
 for (const value of ["1000","-1","1.005","NaN"]) expect(()=>percentToBps(value)).toThrow();
 expect(interestLabel({kind:"money",interest_rate_bps:125,interest_period:"biweekly"})).toBe("1.25% / biweekly");
 expect(interestLabel({kind:"item"})).toBe("No interest");
});
it("distinguishes item return from outstanding fees", () => {
 expect(itemReturned({kind:"item",status:"open",returned_at:"2026-10-15",fees_cents:200})).toBe(true);
 expect(itemReturned({kind:"item",status:"open",returned_at:null})).toBe(false);
});
