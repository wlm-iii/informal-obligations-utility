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
export const reminderTones = ["Sweet bestie", "Direct", "Playful", "Sarcastic", "Passive aggressive", "Flirty", "Mean", "Angry", "Brain rot", "Dramatic", "Anxious", "Disappointed", "Hopeful", "Excited", "Formal", "Poetic", "Deadpan", "Grateful"];
export function reminderFor(friend, loan, tone) {
 const subject = loan.kind === "item" ? `returning ${loan.description}` : `the ${money(loan.outstanding_cents)} for ${loan.description}`;
 const name = friend.display_name;
 const lines = {
  "Sweet bestie": `Hey ${name}! Little bestie reminder about ${subject}. Whenever you get a chance, could you help me out? Thank you 💙`,
  Direct: `Hi ${name}, please follow up on ${subject}. The due date is ${loan.due_date}. Let me know when you can take care of it.`,
  Playful: `Hey ${name}! Your side quest is still open: ${subject}. Any chance you can wrap it up soon? Thank you!`,
  Sarcastic: `Hi ${name}, I love the suspense around ${subject}. Truly a gripping series. Can we get a finale by ${loan.due_date}?`,
  "Passive aggressive": `Hey ${name}, just circling back on ${subject}. Again. I'm sure it simply slipped your mind. A date would be lovely.`,
  Flirty: `Hey ${name}, you've been on my mind… and so has ${subject}. Make my day and settle our little tab? 😉`,
  Mean: `${name}, this IOU isn't a souvenir. Please sort out ${subject} and stop making me chase it.`,
  Angry: `${name}, I'm frustrated that I still have to ask about ${subject}. Please take care of it and tell me when it's done.`,
  "Brain rot": `${name}, the ${subject} lore is getting wild. This IOU has main character energy. Time to lock in and finish the side quest fr.`,
  Dramatic: `${name}! Another sunrise, another chapter in the saga of ${subject}. Will ${loan.due_date} bring our long-awaited resolution?`,
  Anxious: `Hey ${name}, I feel a little awkward asking, but could we check in about ${subject}? Knowing when to expect it would really help.`,
  Disappointed: `${name}, I was hoping we'd have sorted out ${subject} by now. Can you give me a clear plan?`,
  Hopeful: `Hey ${name}, hoping we can wrap up ${subject} soon. Would ${loan.due_date} work for you?`,
  Excited: `${name}! Ready to cross ${subject} off our list? Let's close this tab!`,
  Formal: `Hello ${name}. Please arrange ${subject} by ${loan.due_date}, or confirm an alternative date. Thank you.`,
  Poetic: `${name}, tabs may linger like leaves in the breeze, but ${subject} would put my mind at ease. Shall we settle by ${loan.due_date}?`,
  Deadpan: `${name}. ${subject}. Due ${loan.due_date}. That is the reminder.`,
  Grateful: `Hey ${name}, thanks for helping me keep our tabs tidy. Could you take care of ${subject}? I appreciate you.`,
 };
 return lines[tone] || lines["Sweet bestie"];
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
