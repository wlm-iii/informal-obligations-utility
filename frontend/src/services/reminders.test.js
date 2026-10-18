import { afterEach, beforeEach, expect, it, vi } from "vitest";
vi.mock("./supabase", () => ({ supabase: { auth: { getSession: vi.fn() } } }));
import { supabase } from "./supabase";
import {
 createReminderPreview, getReminder, getReminderPreferences, listReminders,
 saveReminderPermission, sendReminderPreview,
} from "./reminders";

const now = new Date().toISOString();
const preview = { id: "preview-1", friend_id: "friend-1", recipient_email: "friend@example.com",
 tone: "friendly", subject: "IOU reminder", body: "Hello. Please check in.\nStop: https://example.com/unsubscribe",
 status: "preview", created_at: now, updated_at: now, expires_at: new Date(Date.now() + 600000).toISOString() };
const prefs = { friend_id: "friend-1", recipient_email: "friend@example.com", permission_confirmed: true, opted_out: false };
const ok = value => ({ ok: true, status: 200, json: async () => value });
beforeEach(() => {
 vi.resetAllMocks();
 supabase.auth.getSession.mockResolvedValue({ data: { session: { access_token: "private-session-token" } } });
 vi.stubGlobal("fetch", vi.fn());
});
afterEach(() => vi.unstubAllGlobals());

it("loads owner-scoped preferences and recent history without cache or mutations", async () => {
 fetch.mockResolvedValueOnce(ok(prefs)).mockResolvedValueOnce(ok({items:[preview]}));
 expect(await getReminderPreferences("friend-1")).toEqual(prefs);
 expect(await listReminders("friend-1")).toEqual([preview]);
 expect(fetch.mock.calls.map(([path]) => path)).toEqual([
  "/api/friends/friend-1/reminder-preferences", "/api/reminders?friend_id=friend-1&limit=25&offset=0",
 ]);
 for (const [, options] of fetch.mock.calls) {
  expect(options.method).toBe("GET"); expect(options.cache).toBe("no-store");
  expect(options.headers.Authorization).toBe("Bearer private-session-token");
  expect(options.body).toBeUndefined();
 }
});
it("saves consent and creates only a preset preview with explicit retry keys", async () => {
 fetch.mockResolvedValueOnce(ok(prefs)).mockResolvedValueOnce(ok(preview));
 await saveReminderPermission("friend-1", prefs.recipient_email, true, "permission-key");
 await createReminderPreview("friend-1", "friendly", "preview-key");
 expect(fetch).toHaveBeenNthCalledWith(1, "/api/friends/friend-1/reminder-preferences", expect.objectContaining({
  method:"PUT", body:JSON.stringify({recipient_email:prefs.recipient_email,permission_confirmed:true}),
  headers:expect.objectContaining({"Idempotency-Key":"permission-key"}),
 }));
 expect(fetch).toHaveBeenNthCalledWith(2, "/api/friends/friend-1/reminder-previews", expect.objectContaining({
  method:"POST", body:JSON.stringify({tone:"friendly",template_id:1}), headers:expect.objectContaining({"Idempotency-Key":"preview-key"}),
 }));
});
it("requests the selected template number without supplying message facts",async()=>{
 fetch.mockResolvedValue(ok(preview));
 await createReminderPreview("friend-1","friendly","variant-key",undefined,3);
 expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({tone:"friendly",template_id:3});
 expect(fetch).toHaveBeenCalledTimes(1);
});
it("submits the exact approved preview once, without any editable message payload", async () => {
 fetch.mockResolvedValue(ok({...preview,status:"sent"}));
 await sendReminderPreview(preview, "send-key");
 expect(fetch).toHaveBeenCalledTimes(1);
 expect(fetch).toHaveBeenCalledWith("/api/reminders/preview-1/send", expect.objectContaining({
  method:"POST", body:JSON.stringify({approved:true,recipient_email:preview.recipient_email}),
  headers:expect.objectContaining({"Idempotency-Key":"send-key"}),
 }));
});
it.each([403,409,429,503])("surfaces controlled backend HTTP %s without retries", async status => {
 fetch.mockResolvedValue({ok:false,status,json:async()=>({detail:"Delivery is blocked by server policy."})});
 await expect(sendReminderPreview(preview,"key")).rejects.toMatchObject({status,message:"Delivery is blocked by server policy."});
 expect(fetch).toHaveBeenCalledTimes(1);
});
it("treats connection loss as uncertain and checks status with GET, never another POST", async () => {
 fetch.mockRejectedValueOnce(new TypeError("connection lost")).mockResolvedValueOnce(ok({...preview,status:"sent"}));
 await expect(sendReminderPreview(preview,"key")).rejects.toMatchObject({uncertain:true});
 expect((await getReminder(preview.id)).status).toBe("sent");
 expect(fetch.mock.calls.map(([, options]) => options.method)).toEqual(["POST","GET"]);
});
it("does not mark an unreadable or mismatched successful send response as delivered", async () => {
 for (const value of [{}, {...preview,status:"sent",id:"another"}, {...preview,status:"sent",body:"Different text"}, preview]) {
  fetch.mockResolvedValue(ok(value));
  await expect(sendReminderPreview(preview,"key")).rejects.toMatchObject({uncertain:true});
 }
 expect(fetch).toHaveBeenCalledTimes(4);
});
it("never displays raw proxy errors and performs no send retry", async () => {
 fetch.mockResolvedValue({ok:false,status:502,json:async()=>{throw new Error("private upstream details");}});
 await expect(sendReminderPreview(preview,"key")).rejects.toMatchObject({uncertain:true});
 expect(fetch).toHaveBeenCalledTimes(1);
});
it("fails closed for an invalid history page or another contact's preferences", async () => {
 fetch.mockResolvedValueOnce(ok({items:[{...preview,friend_id:"other"}]})).mockResolvedValueOnce(ok({...prefs,friend_id:"other"}));
 await expect(listReminders("friend-1")).rejects.toThrow("Delivery history could not be read");
 await expect(getReminderPreferences("friend-1")).rejects.toThrow("Reminder preferences could not be read");
});
it("requires a session before accessing email data", async () => {
 supabase.auth.getSession.mockResolvedValue({data:{session:null}});
 await expect(getReminderPreferences("friend-1")).rejects.toMatchObject({status:401});
 expect(fetch).not.toHaveBeenCalled();
});
it("propagates cancellation without retrying", async () => {
 const controller=new AbortController(); controller.abort();
 fetch.mockRejectedValue(new DOMException("Aborted","AbortError"));
 await expect(getReminderPreferences("friend-1",controller.signal)).rejects.toMatchObject({name:"AbortError"});
 expect(fetch).toHaveBeenCalledTimes(1);
});
