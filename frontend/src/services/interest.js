// Formatting only. Live balances and interest always come from the backend calculator.
export function totalOutstanding(loan) {
 return loan.total_outstanding_cents ?? ((loan.outstanding_cents || 0) + (loan.interest_cents || 0) + (loan.fees_cents || 0));
}

export function percentToBps(value) {
 const text = String(value);
 if (!/^\d+(\.\d{1,2})?$/.test(text)) throw new Error("Use a percentage with up to two decimal places.");
 const [whole, fraction = ""] = text.split(".");
 const bps = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
 if (!Number.isSafeInteger(bps) || bps < 0 || bps > 10000) throw new Error("Interest must be between 0% and 100% per period.");
 return bps;
}

export function interestLabel(loan) {
 return loan.kind === "item" ? "No interest" : `${(loan.interest_rate_bps || 0) / 100}% / ${loan.interest_period || "weekly"}`;
}

export function itemReturned(loan) {
 return loan.kind === "item" && ((loan.returned_at !== null && loan.returned_at !== undefined) || loan.borrowing_status === "returned" || loan.status === "completed");
}
