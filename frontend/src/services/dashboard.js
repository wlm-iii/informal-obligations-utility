import { supabase } from "./supabase";
import { totalOutstanding } from "./interest";

export async function ledgerRequest(path, { signal, body, key } = {}) {
 const { data, error } = await supabase.auth.getSession();
 if (error || !data.session) throw new Error("Please sign in again.");
 const response = await fetch(`/api${path}`, {
  method: body ? "POST" : "GET", signal, cache: "no-store",
  headers: { Authorization: `Bearer ${data.session.access_token}`, ...(body ? { "Content-Type": "application/json", "Idempotency-Key": key } : {}) },
  ...(body ? { body: JSON.stringify(body) } : {}),
 });
 if (!response.ok) throw new Error(response.status === 401 ? "Your session expired. Please sign in again." : "Unable to load or save your ledger. Please retry.");
 return response.json();
}

export async function loadFriends(signal) {
 const friends = [];
 for (let offset = 0; offset <= 100000; offset += 100) {
  const page = await ledgerRequest(`/friends?archived=include&limit=100&offset=${offset}`, { signal });
  if (!Array.isArray(page.items)) throw new Error("Friend data is unavailable. Please retry.");
  friends.push(...page.items);
  if (!page.has_more) return friends;
 }
 throw new Error("Your friend list is too large to display completely.");
}

export const money = cents => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format((cents || 0) / 100);
export const reminderTones = ["Friendly", "Direct", "Playful"];
// Clipboard drafts only. Gmail sends must use the separate server approval/consent flow.
export function reminderFor(friend, loan, tone) {
 const subject = loan.kind === "item" && !loan.returned_at ? `returning ${loan.description}` : `the ${money(totalOutstanding(loan))} recorded as owing for ${loan.description}`;
 const name = friend.display_name;
 const lines = {
  Friendly: `Hey ${name}! A friendly reminder about ${subject}. Could you check in when you can?`,
  Direct: `Hi ${name}, please follow up on ${subject}. Let me know when you can take care of it.`,
  Playful: `Hey ${name}! Your side quest is still open: ${subject}. Any chance you can wrap it up soon?`,
 };
 return lines[tone] || lines.Friendly;
}

export async function loadLedgerHistory(friends, signal) {
 const pages = await Promise.all(friends.map(async friend => {
  const events = [];
  for (let offset = 0; offset <= 100000; offset += 100) {
   const page = await ledgerRequest(`/friends/${friend.id}/history?limit=100&offset=${offset}`, { signal });
   if (!Array.isArray(page.items)) throw new Error("Payment history is unavailable.");
   events.push(...page.items);
   if (!page.has_more) return events;
  }
  throw new Error("Payment history is too large to display completely.");
 }));
 return pages.flat();
}

export function activePayments(events, loans) {
 const ids = new Set(loans.filter(loan => loan.status !== "voided").map(loan => loan.id));
 return events.filter(event => ["repayment", "fee_payment"].includes(event.action) &&
  !event.reversed_at && ids.has(event.loan_id || event.loan?.id) && event.loan?.status !== "voided");
}

// Offline demos consume static zero-rate/server-snapshot amounts, never calculate accrual.
export function applyDemoPayment(loan, amount) {
 let remaining = amount;
 const fees = Math.min(remaining, loan.fees_cents || 0); remaining -= fees;
 const interest = Math.min(remaining, loan.interest_cents || 0); remaining -= interest;
 const principal = remaining;
 const total = totalOutstanding(loan) - amount;
 const completed = total === 0 && (loan.kind === "money" || loan.returned_at);
 return {...loan, fees_cents:(loan.fees_cents || 0)-fees, interest_cents:(loan.interest_cents || 0)-interest,
  outstanding_cents:loan.kind === "money" ? (loan.outstanding_cents || 0)-principal : null,
  total_outstanding_cents:total, repaid_cents:loan.kind === "money" ? (loan.repaid_cents || 0)+amount : null,
  fees_paid_cents:(loan.fees_paid_cents || 0)+fees, status:completed ? "completed" : "open",
  ...(completed ? {completed_at:new Date().toISOString(),overdue:false} : {})};
}
export const utcDate = value => new Intl.DateTimeFormat("en-US", { month:"short", day:"numeric", year:"numeric", timeZone:"UTC" }).format(new Date(value));
