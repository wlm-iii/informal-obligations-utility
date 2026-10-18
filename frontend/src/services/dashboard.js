import { supabase } from "./supabase";

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
export function reminderFor(friend, loan, tone) {
 const subject = loan.kind === "item" ? `returning ${loan.description}` : `the ${money(loan.outstanding_cents)} for ${loan.description}`;
 if (tone === "Direct") return `Hi ${friend.display_name}, please follow up on ${subject}. The due date is ${loan.due_date}. Let me know when you can take care of it.`;
 if (tone === "Playful") return `Hey ${friend.display_name}! Your side quest is still open: ${subject}. Any chance you can wrap it up soon? Thank you!`;
 return `Hey ${friend.display_name}! Little bestie reminder about ${subject}. Whenever you get a chance, could you help me out? Thank you 💙`;
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
export const utcDate = value => new Intl.DateTimeFormat("en-US", { month:"short", day:"numeric", year:"numeric", timeZone:"UTC" }).format(new Date(value));
