import { useEffect, useRef, useState } from "react";
import {
 createReminderPreview, getReminder, getReminderPreferences, listReminders,
 saveReminderPermission, sendReminderPreview,
} from "../services/reminders";
import "./EmailReminder.css";

const tones = [["friendly", "Friendly"], ["playful", "Playful"], ["direct", "Direct but polite"]];
const templateLabels = {
 friendly: ["Friendly check-in", "Ask for an update", "Thank-you note"],
 playful: ["Side quest", "Plot twist", "Tiny drumroll"],
 direct: ["Clear reminder", "Repayment or return plans", "Follow-up"],
};
const sameEmail = (a, b) => a?.toLowerCase() === b?.toLowerCase();
const time = value => Date.parse(value) || 0;
const dateLabel = value => value ? new Date(value).toLocaleString() : "Not submitted";
const statusLabel = {
 preview: "Preview only", reserved: "Preparing email", sending: "Submission in progress",
 sent: "Accepted by Gmail", failed: "Failed", uncertain: "Delivery uncertain", cancelled: "Cancelled before submission",
};
const resultMessage = row => {
 if (row.status === "sent") return "Gmail accepted this email. Inbox delivery is not guaranteed; check Inbox or Spam. No follow-up was scheduled.";
 if (row.status === "failed") return row.error_code === "authorization_failed" ?
  "Gmail authorization failed before submission. Nothing was sent. Fix the sender setup before creating another preview." :
  "Gmail explicitly rejected the email. No retry was performed. Review the setup before creating another preview.";
 if (row.status === "uncertain") return "Gmail may have accepted this email. Check the sender’s Sent folder and the recipient’s inbox. Do not resend.";
 if (row.status === "cancelled") return "Submission was cancelled because eligibility, permission, or settings changed. Nothing was submitted by this attempt.";
 if (["reserved", "sending"].includes(row.status)) return "An attempt is in progress. Check delivery status; do not submit another email.";
 return "No submission is recorded yet. If a request was interrupted, do not assume that means it is safe to resend.";
};

export default function EmailReminder({ friend, eligible, onBusyChange }) {
 const [preferences, setPreferences] = useState(null);
 const [history, setHistory] = useState([]);
 const [tone, setTone] = useState("friendly");
 const [templateId, setTemplateId] = useState(1);
 const [consent, setConsent] = useState(false);
 const [preview, setPreview] = useState(null);
 const [approved, setApproved] = useState(false);
 const [attempted, setAttempted] = useState(false);
 const [unresolved, setUnresolved] = useState(false);
 const [error, setError] = useState("");
 const [notice, setNotice] = useState("");
 const [loading, setLoading] = useState(true);
 const [busy, setBusy] = useState("");
 const [reload, setReload] = useState(0);
 const [now, setNow] = useState(Date.now);
 const lifecycle = useRef(null);
 const operation = useRef(false);
 const permissionAttempt = useRef(null);
 const previewAttempt = useRef(null);
 const sendAttempt = useRef(null);

 useEffect(() => {
  const scope = { alive: true, controller: new AbortController() };
  lifecycle.current = scope;
  operation.current = false;
  permissionAttempt.current = previewAttempt.current = sendAttempt.current = null;
  setLoading(true); setPreferences(null); setPreview(null); setApproved(false);
  setAttempted(false); setUnresolved(false); setError(""); setNotice(""); setHistory([]); setTone("friendly"); setTemplateId(1);
  setBusy(""); onBusyChange?.(false);
  Promise.all([getReminderPreferences(friend.id, scope.controller.signal), listReminders(friend.id, scope.controller.signal)])
   .then(([prefs, entries]) => {
    if (!scope.alive) return;
    setPreferences(prefs); setConsent(prefs.permission_confirmed); setHistory(entries);
   }).catch(failure => {
    if (scope.alive && failure.name !== "AbortError") setError(failure.message);
   }).finally(() => { if (scope.alive) setLoading(false); });
  return () => { scope.alive = false; scope.controller.abort(); };
 }, [friend.id, friend.email, friend.display_name, friend.archived_at, reload, onBusyChange]);

 useEffect(() => {
  const interval = setInterval(() => setNow(Date.now()), 1000);
  return () => clearInterval(interval);
 }, []);

 const entries = history.filter(row => row.status !== "preview");
 const activeBlock = entries.find(row => sameEmail(row.recipient_email, preferences?.recipient_email) &&
  (row.status === "reserved" ? now < time(row.updated_at) + 5 * 60_000 :
   ["sending", "sent", "uncertain"].includes(row.status) && now < time(row.attempted_at || row.updated_at) + 24 * 60 * 60_000));
 const pending = activeBlock && ["reserved", "sending"].includes(activeBlock.status);
 const expired = preview && now >= time(preview.expires_at);
 const contactReady = preferences?.recipient_email && !preferences.opted_out && !friend.archived_at && eligible;
 const terminal = preview && ["failed", "cancelled"].includes(preview.status);
 const canGenerate = contactReady && consent && !loading && !busy && !activeBlock && !unresolved && (!attempted || terminal || preview?.status === "preview");
 const canSend = contactReady && consent && approved && preview?.status === "preview" && !expired &&
  !attempted && !loading && !busy && !activeBlock && sameEmail(preview.recipient_email, preferences.recipient_email);

 function begin(action) {
  if (operation.current || !lifecycle.current?.alive) return null;
  operation.current = true; setBusy(action); setError(""); setNotice("");
  onBusyChange?.(true);
  return lifecycle.current;
 }
 function end(scope) {
  if (!scope.alive || lifecycle.current !== scope) return;
  operation.current = false; setBusy(""); onBusyChange?.(false);
 }
 function updateHistory(row) {
  setHistory(previous => [row, ...previous.filter(item => item.id !== row.id)]);
 }
 function validScope(scope) { return scope.alive && lifecycle.current === scope; }

 async function generate() {
  if (!canGenerate) return;
  const scope = begin("preview");
  if (!scope) return;
  setApproved(false); setPreview(null);
  try {
   // Read current consent/address before saving any attestation or generating text.
   let prefs = await getReminderPreferences(friend.id, scope.controller.signal);
   if (!validScope(scope)) return;
   setPreferences(prefs);
   if (!sameEmail(prefs.recipient_email, preferences.recipient_email)) {
    setConsent(false); permissionAttempt.current = previewAttempt.current = null;
    throw new Error("The contact’s email changed. Review the new address and confirm permission again.");
   }
   if (prefs.opted_out) throw new Error("This recipient opted out. You cannot override their choice.");
   if (!prefs.permission_confirmed && preferences.permission_confirmed) {
    setConsent(false); previewAttempt.current = null;
    throw new Error("Permission confirmation changed. Review the recipient and explicitly confirm again.");
   }
   if (!prefs.permission_confirmed) {
    const signature = `${prefs.recipient_email}:true`;
    if (permissionAttempt.current?.signature !== signature) permissionAttempt.current = { signature, key: crypto.randomUUID() };
    prefs = await saveReminderPermission(friend.id, prefs.recipient_email, true, permissionAttempt.current.key, scope.controller.signal);
    if (!validScope(scope)) return;
    setPreferences(prefs);
    if (prefs.opted_out || !prefs.permission_confirmed) throw new Error("Recipient permission is not available. Reload preferences.");
   }
   const signature = `${friend.id}:${prefs.recipient_email}:${tone}:${templateId}`;
   if (attempted || preview || previewAttempt.current?.signature !== signature) previewAttempt.current = { signature, key: crypto.randomUUID() };
   const row = await createReminderPreview(friend.id, tone, previewAttempt.current.key, scope.controller.signal, templateId);
   if (!validScope(scope)) return;
   if (!sameEmail(row.recipient_email, prefs.recipient_email)) throw new Error("The preview recipient changed. Reload before proceeding.");
   setPreview(row); setAttempted(false); setUnresolved(false); sendAttempt.current = null;
   updateHistory(row); setNow(Date.now());
  } catch (failure) {
   if (validScope(scope) && failure.name !== "AbortError") setError(failure.message);
  } finally { end(scope); }
 }

 async function revoke() {
  if (!preferences?.recipient_email || busy) return;
  const scope = begin("permission");
  if (!scope) return;
  try {
   const signature = `${preferences.recipient_email}:false`;
   if (permissionAttempt.current?.signature !== signature) permissionAttempt.current = { signature, key: crypto.randomUUID() };
   const prefs = await saveReminderPermission(friend.id, preferences.recipient_email, false, permissionAttempt.current.key, scope.controller.signal);
   if (!validScope(scope)) return;
   setPreferences(prefs); setConsent(false); setApproved(false);
   if (!attempted) { setPreview(null); previewAttempt.current = null; }
   setNotice("Your permission confirmation was revoked. This does not undo a previous submission.");
  } catch (failure) { if (validScope(scope) && failure.name !== "AbortError") setError(failure.message); }
  finally { end(scope); }
 }

 async function send() {
  if (!canSend || operation.current || sendAttempt.current) return;
  const scope = begin("send");
  if (!scope) return;
  const attempt = { preview, key: crypto.randomUUID() };
  sendAttempt.current = attempt;
  setAttempted(true); setApproved(false);
  try {
   // Exactly one POST from this action. Ambiguous failures only permit read-only status checks.
   const row = await sendReminderPreview(attempt.preview, attempt.key, scope.controller.signal);
   if (!validScope(scope)) return;
   setPreview(row); updateHistory(row); setNotice(resultMessage(row));
   setUnresolved(["reserved", "sending", "uncertain"].includes(row.status));
  } catch (failure) {
   if (validScope(scope)) {
    setUnresolved(failure.uncertain !== false);
    setError(failure.message);
    setNotice("No retry was performed. Check delivery status before any new attempt.");
   }
  } finally { end(scope); }
 }

 async function checkStatus() {
  const id = sendAttempt.current?.preview.id || activeBlock?.id || preview?.id;
  if (!id) return;
  const scope = begin("status");
  if (!scope) return;
  try {
   const row = await getReminder(id, scope.controller.signal);
   if (!validScope(scope)) return;
   if (row.friend_id !== friend.id) throw new Error("Delivery status did not match this contact.");
   updateHistory(row);
   if (preview?.id === row.id) setPreview(row);
   setNotice(resultMessage(row));
   // A still-preview row after an interrupted send is not proof of non-delivery.
   if (row.status !== "preview") setUnresolved(["reserved", "sending", "uncertain"].includes(row.status));
  } catch (failure) { if (validScope(scope) && failure.name !== "AbortError") setError(failure.message); }
  finally { end(scope); }
 }

 return <section className="email-reminder" aria-label="Email reminder">
  <p>One email covers this friend’s current outstanding obligations. Nothing is sent until you approve the exact preview and click Send.</p>
  {loading && <p role="status">Loading recipient permission and delivery history…</p>}
  {error && <p role="alert">{error}</p>}
  {error.includes("allowlist") && <small>For a controlled demo, the app operator must explicitly allow this test recipient. The configured sender’s own inbox is allowed by default.</small>}
  {error.includes("public unsubscribe") && <small>Other recipients need a public HTTPS unsubscribe base URL; a localhost link only works on this computer.</small>}
  {error === "Email sending is disabled." && <small>The operator must enable Gmail delivery and restart the backend after changing its environment.</small>}
  {error.includes("09:00") && <small>Quiet hours use your profile timezone. For consenting demo recipients, the operator can explicitly change REMINDER_QUIET_HOURS_ENABLED and restart the backend.</small>}
  {!loading && !preferences && <button onClick={() => setReload(value => value + 1)}>Reload reminder settings</button>}
  {preferences && <>
   <p className="email-recipient"><strong>To:</strong> {preferences.recipient_email || "No email on this contact"}</p>
   {!eligible && <p role="alert">This friend no longer has an outstanding obligation. Refresh the tracker.</p>}
   {friend.archived_at && <p role="alert">Archived contacts cannot receive reminders.</p>}
   {!preferences.recipient_email && <p>Add an email address to this contact before sending.</p>}
   {preferences.opted_out && <p role="alert">This recipient opted out of IOU reminders. You cannot re-enable them.</p>}
   {activeBlock && <p role="status">{pending ? "An earlier email attempt is still pending." : "A recent email attempt is within the 24-hour recipient cooldown."} Check its status; do not resend.</p>}
   <label className="email-checkbox"><input type="checkbox" checked={consent} disabled={!!busy || !contactReady}
    onChange={event => { setConsent(event.target.checked); setApproved(false); }} />
    I confirm this recipient agreed to receive IOU email reminders.</label>
   <small>Owing something is not email consent. Unsubscribe stops future IOU reminders to this address.</small>
   {preferences.permission_confirmed && !preferences.opted_out && <button className="email-secondary" disabled={!!busy} onClick={revoke}>Revoke my permission confirmation</button>}
   <label htmlFor="email-reminder-tone">Message tone</label>
   <select id="email-reminder-tone" value={tone} disabled={!!busy || attempted} onChange={event => {
    setTone(event.target.value); setTemplateId(1); setPreview(null); setApproved(false); setError(""); previewAttempt.current = null;
   }}>{tones.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
   <label htmlFor="email-reminder-template">Message template</label>
   <select id="email-reminder-template" value={templateId} disabled={!!busy || attempted} onChange={event => {
    setTemplateId(Number(event.target.value)); setPreview(null); setApproved(false); setError(""); previewAttempt.current = null;
   }}>{templateLabels[tone].map((label,index) => <option key={label} value={index+1}>{label}</option>)}</select>
   <small>Names, money owed, and unreturned-item counts are filled from current ledger data when you generate the preview.</small>
   <button className="primary-action" disabled={!canGenerate} onClick={generate}>
    {busy === "preview" ? "Preparing preview…" : attempted ? "Create a new preview" : "Generate email preview"}
   </button>
  </>}
  {preview && <div className="email-preview">
   <p><strong>Preview recipient:</strong> {preview.recipient_email}</p>
   <label htmlFor="email-reminder-subject">Email subject</label>
   <input id="email-reminder-subject" value={preview.subject} readOnly />
   <label htmlFor="email-reminder-body">Email body</label>
   <textarea id="email-reminder-body" value={preview.body} readOnly rows={9} />
   <small>Includes the unsubscribe footer. This exact server-generated text is not editable.</small>
   {!attempted && <>
    <p>{expired ? "Preview expired. Generate a new preview." : `Preview expires ${dateLabel(preview.expires_at)} (your local time).`}</p>
    <label className="email-checkbox"><input type="checkbox" checked={approved} disabled={!!busy || expired || !contactReady}
     onChange={event => setApproved(event.target.checked)} />
     I approve this exact subject and message to {preview.recipient_email}.</label>
    <button className="primary-action" disabled={!canSend} onClick={send}>{busy === "send" ? "Submitting…" : "Send this email"}</button>
   </>}
  </div>}
  {busy === "send" && <p role="status">Submitting this email once. No automatic retry will be made.</p>}
  {notice && <p role="status">{notice}</p>}
  {(attempted || activeBlock) && <button disabled={!!busy} onClick={checkStatus}>{busy === "status" ? "Checking…" : "Check delivery status"}</button>}
  {!!entries.length && <div className="email-history"><h3>Recent email attempts</h3><ul>{entries.slice(0, 5).map(row =>
   <li key={row.id}><strong>{statusLabel[row.status]}</strong> · {row.recipient_email}<br /><small>{dateLabel(row.attempted_at || row.updated_at)}</small></li>
  )}</ul></div>}
  <small className="email-safety-note">No automatic send retries. Sender allowlists, permission, quiet hours, expiry, current balances, unsubscribe, and cooldown are checked by the backend.</small>
 </section>;
}
