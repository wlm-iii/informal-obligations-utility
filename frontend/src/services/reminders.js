import { supabase } from "./supabase";

export class ReminderError extends Error {
 constructor(message, status = 0, uncertain = false) {
  super(message);
  this.name = "ReminderError";
  this.status = status;
  this.uncertain = uncertain;
 }
}

const statuses = new Set(["preview", "reserved", "sending", "sent", "failed", "uncertain", "cancelled"]);
function validReminder(row) {
 return row && typeof row.id === "string" && typeof row.friend_id === "string" &&
  typeof row.recipient_email === "string" && typeof row.subject === "string" &&
  typeof row.body === "string" && statuses.has(row.status) &&
  [row.expires_at, row.created_at, row.updated_at].every(value => typeof value === "string" && Number.isFinite(Date.parse(value)));
}

async function request(path, { method = "GET", body, key, signal } = {}) {
 let session;
 try { session = await supabase.auth.getSession(); }
 catch { throw new ReminderError("Your session could not be restored. Please sign in again.", 401); }
 const { data, error } = session || {};
 if (error || !data?.session?.access_token) throw new ReminderError("Your session expired. Please sign in again.", 401);
 let response;
 try {
  response = await fetch(`/api${path}`, {
   method, signal, cache: "no-store", redirect: "error",
   headers: { Authorization: `Bearer ${data.session.access_token}`,
    ...(body ? { "Content-Type": "application/json", "Idempotency-Key": key } : {}) },
   ...(body ? { body: JSON.stringify(body) } : {}),
  });
 } catch (failure) {
  if (failure.name === "AbortError") throw failure;
  throw new ReminderError("The connection was interrupted. Check delivery status before trying anything else.", 0, true);
 }
 let result;
 try { result = await response.json(); } catch { /* Never display a raw proxy/provider response. */ }
 if (!response.ok) {
  const message = response.status === 401 ? "Your session expired. Please sign in again." :
   typeof result?.detail === "string" && result.detail.length <= 400 ? result.detail :
   "The reminder request could not be completed. Check delivery status before another attempt.";
  const knownBlock = response.status === 503 && ["Email sending is disabled.",
   "A public unsubscribe base URL is required for other recipients."].includes(result?.detail);
  throw new ReminderError(message, response.status, (response.status >= 500 && !knownBlock) || response.status === 408);
 }
 return result;
}

function checked(row) {
 if (!validReminder(row)) throw new ReminderError("The server returned an unreadable reminder. Check delivery status; do not resend.", 0, true);
 return row;
}

export async function getReminderPreferences(friendId, signal) {
 const row = await request(`/friends/${encodeURIComponent(friendId)}/reminder-preferences`, { signal });
 if (!row || row.friend_id !== friendId || typeof row.permission_confirmed !== "boolean" ||
     typeof row.opted_out !== "boolean" || !(row.recipient_email === null || typeof row.recipient_email === "string")) {
  throw new ReminderError("Reminder preferences could not be read. Reload them before proceeding.");
 }
 return row;
}

export async function saveReminderPermission(friendId, email, confirmed, key, signal) {
 const row = await request(`/friends/${encodeURIComponent(friendId)}/reminder-preferences`, {
  method: "PUT", body: { recipient_email: email, permission_confirmed: confirmed }, key, signal,
 });
 if (!row || row.friend_id !== friendId || typeof row.permission_confirmed !== "boolean" || typeof row.opted_out !== "boolean" ||
     typeof row.recipient_email !== "string" || row.recipient_email.toLowerCase() !== email.toLowerCase()) {
  throw new ReminderError("Permission confirmation could not be read. Reload before proceeding.");
 }
 return row;
}

export async function createReminderPreview(friendId, tone, key, signal, templateId = 1) {
 const row = checked(await request(`/friends/${encodeURIComponent(friendId)}/reminder-previews`, {
  method: "POST", body: { tone, template_id: templateId }, key, signal,
 }));
 if (row.friend_id !== friendId || row.tone !== tone || row.status !== "preview") {
  throw new ReminderError("Preview does not match this contact and tone. Reload before proceeding.");
 }
 return row;
}

export async function sendReminderPreview(preview, key, signal) {
 const row = checked(await request(`/reminders/${encodeURIComponent(preview.id)}/send`, {
  method: "POST", body: { approved: true, recipient_email: preview.recipient_email }, key, signal,
 }));
 if (row.id !== preview.id || row.friend_id !== preview.friend_id || row.recipient_email !== preview.recipient_email || row.status === "preview" ||
     row.subject !== preview.subject || row.body !== preview.body) {
  throw new ReminderError("The send result could not be verified. Check delivery status; do not resend.", 0, true);
 }
 return row;
}

export async function getReminder(id, signal) {
 const row = checked(await request(`/reminders/${encodeURIComponent(id)}`, { signal }));
 if (row.id !== id) throw new ReminderError("Delivery status could not be verified.");
 return row;
}

export async function listReminders(friendId, signal) {
 const page = await request(`/reminders?friend_id=${encodeURIComponent(friendId)}&limit=25&offset=0`, { signal });
 if (!page || !Array.isArray(page.items) || !page.items.every(row => validReminder(row) && row.friend_id === friendId)) {
  throw new ReminderError("Delivery history could not be read. Reload before proceeding.");
 }
 return page.items;
}
