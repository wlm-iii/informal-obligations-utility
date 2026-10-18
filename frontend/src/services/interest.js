// Calendar-day simple interest, rounded once to the nearest cent (half up).
// Live records use the backend balance; this function powers the offline demo.
export function withDailyInterest(loan, at = new Date()) {
 const date = new Intl.DateTimeFormat("en-CA", { timeZone: loan.timezone || "America/Los_Angeles", year:"numeric", month:"2-digit", day:"2-digit" }).format(new Date(loan.completed_at || at));
 const days = Math.max(0, Math.round((Date.parse(`${date}T00:00:00Z`) - Date.parse(`${loan.due_date}T00:00:00Z`)) / 86400000));
 if (loan.kind !== "money") return { ...loan, overdue:loan.status === "open" && days > 0, interest_cents:0, interest_days:0 };
 const enabled = loan.repayment_type !== "item" && loan.interest_percent > 0;
 const interest = enabled ? Math.round(loan.principal_cents * loan.interest_percent * days / 100) : 0;
 const outstanding = Math.max(0, loan.principal_cents + interest - (loan.repaid_cents || 0));
 return { ...loan, interest_cents:interest, interest_days:enabled ? days : 0, outstanding_cents:outstanding, status:outstanding === 0 ? "completed" : "open", overdue:outstanding > 0 && days > 0 };
}
