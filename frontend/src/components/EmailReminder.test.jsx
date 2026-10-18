// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
vi.mock("../services/reminders", () => ({
 createReminderPreview:vi.fn(),getReminder:vi.fn(),getReminderPreferences:vi.fn(),
 listReminders:vi.fn(),saveReminderPermission:vi.fn(),sendReminderPreview:vi.fn(),
}));
import EmailReminder from "./EmailReminder";
import * as api from "../services/reminders";

const friend = {id:"f",display_name:"Alex",email:"alex@example.com"};
const prefs = {friend_id:"f",recipient_email:friend.email,permission_confirmed:false,opted_out:false};
const row = (changes={}) => ({id:"p",friend_id:"f",recipient_email:friend.email,tone:"friendly",subject:"IOU reminder",
 body:"Hi Alex, please check in.\nStop IOU reminders: https://api.example/unsubscribe?token=test",
 status:"preview",created_at:new Date().toISOString(),updated_at:new Date().toISOString(),
 expires_at:new Date(Date.now()+600000).toISOString(),attempted_at:null,sent_at:null,error_code:null,...changes});
const failure = (message, uncertain=false, status=409) => Object.assign(new Error(message),{uncertain,status});
const consentLabel = /I confirm this recipient agreed/;
const approvalLabel = /I approve this exact subject and message/;
beforeEach(()=>{
 vi.resetAllMocks();
 api.getReminderPreferences.mockResolvedValue({...prefs});
 api.listReminders.mockResolvedValue([]);
 api.saveReminderPermission.mockImplementation(async(id,email,confirmed)=>{
  const result={...prefs,permission_confirmed:confirmed};
  api.getReminderPreferences.mockResolvedValue(result);
  return result;
 });
 api.createReminderPreview.mockResolvedValue(row());
 api.sendReminderPreview.mockImplementation(async preview=>({...preview,status:"sent",attempted_at:new Date().toISOString()}));
});
afterEach(cleanup);
async function open(props={}) {
 render(<EmailReminder friend={friend} eligible {...props}/>);
 await screen.findByLabelText(consentLabel);
}
async function generate() {
 const checkbox=screen.getByLabelText(consentLabel);
 if (!checkbox.checked) fireEvent.click(checkbox);
 fireEvent.click(screen.getByRole("button",{name:"Generate email preview"}));
 await screen.findByLabelText("Email body");
}
async function approveSend() {
 fireEvent.click(screen.getByLabelText(approvalLabel));
 fireEvent.click(screen.getByRole("button",{name:"Send this email"}));
}

it("loads permission/history only and does not mutate or send on opening",async()=>{
 await open();
 expect(screen.getByRole("button",{name:"Generate email preview"})).toBeDisabled();
 expect(api.saveReminderPermission).not.toHaveBeenCalled();
 expect(api.createReminderPreview).not.toHaveBeenCalled();
 expect(api.sendReminderPreview).not.toHaveBeenCalled();
 expect(Array.from(screen.getByLabelText("Message tone").options).map(option=>option.textContent)).toEqual(["Friendly","Playful","Direct but polite"]);
 expect(screen.getByLabelText("Message template").options).toHaveLength(3);
});
it("confirms permission, previews exact immutable text, and sends once only after explicit approval",async()=>{
 await open(); await generate();
 expect(api.saveReminderPermission).toHaveBeenCalledWith("f",friend.email,true,expect.any(String),expect.any(AbortSignal));
 expect(screen.getByLabelText("Email body")).toHaveAttribute("readonly");
 expect(screen.getByLabelText("Email subject")).toHaveValue("IOU reminder");
 expect(screen.getByLabelText("Email body").value).toContain("Stop IOU reminders:");
 expect(screen.getByRole("button",{name:"Send this email"})).toBeDisabled();
 expect(api.sendReminderPreview).not.toHaveBeenCalled();
 fireEvent.click(screen.getByLabelText(approvalLabel));
 const button=screen.getByRole("button",{name:"Send this email"});
 fireEvent.click(button); fireEvent.click(button);
 await screen.findByText(/Gmail accepted this email/);
 expect(api.sendReminderPreview).toHaveBeenCalledTimes(1);
 expect(api.sendReminderPreview.mock.calls[0][0]).toMatchObject({id:"p",recipient_email:friend.email,subject:"IOU reminder"});
 expect(screen.queryByRole("button",{name:"Send this email"})).not.toBeInTheDocument();
 expect(screen.getByRole("button",{name:"Create a new preview"})).toBeDisabled();
});
it("changing tone discards the old approval and requires a fresh server preview",async()=>{
 await open(); await generate();
 fireEvent.click(screen.getByLabelText(approvalLabel));
 fireEvent.change(screen.getByLabelText("Message tone"),{target:{value:"playful"}});
 expect(screen.queryByLabelText("Email body")).not.toBeInTheDocument();
 api.createReminderPreview.mockResolvedValue(row({id:"p2",tone:"playful"}));
 fireEvent.click(screen.getByRole("button",{name:"Generate email preview"}));
 await screen.findByLabelText("Email body");
 expect(screen.getByLabelText(approvalLabel)).not.toBeChecked();
 expect(api.createReminderPreview.mock.calls[1][1]).toBe("playful");
 expect(api.createReminderPreview.mock.calls[1][2]).not.toBe(api.createReminderPreview.mock.calls[0][2]);
 expect(api.sendReminderPreview).not.toHaveBeenCalled();
});
it("selects a different filled template with a new key and fresh approval",async()=>{
 await open(); await generate();
 fireEvent.click(screen.getByLabelText(approvalLabel));
 fireEvent.change(screen.getByLabelText("Message template"),{target:{value:"2"}});
 expect(screen.queryByLabelText("Email body")).not.toBeInTheDocument();
 api.createReminderPreview.mockResolvedValue(row({id:"p2",body:"Second server-filled message"}));
 fireEvent.click(screen.getByRole("button",{name:"Generate email preview"}));
 await screen.findByLabelText("Email body");
 expect(api.createReminderPreview.mock.calls[1][4]).toBe(2);
 expect(api.createReminderPreview.mock.calls[1][2]).not.toBe(api.createReminderPreview.mock.calls[0][2]);
 expect(screen.getByLabelText("Email body")).toHaveValue("Second server-filled message");
 expect(screen.getByLabelText(approvalLabel)).not.toBeChecked();
 expect(api.sendReminderPreview).not.toHaveBeenCalled();
 fireEvent.change(screen.getByLabelText("Message tone"),{target:{value:"direct"}});
 expect(screen.getByLabelText("Message template")).toHaveValue("1");
 expect(screen.getByLabelText("Message template").options).toHaveLength(3);
});
it("expires an old preview and generates a genuinely new key instead of replaying it forever",async()=>{
 api.createReminderPreview.mockResolvedValueOnce(row({expires_at:new Date(Date.now()-1000).toISOString()})).mockResolvedValueOnce(row({id:"p2"}));
 await open(); await generate();
 expect(screen.getByText("Preview expired. Generate a new preview.")).toBeInTheDocument();
 expect(screen.getByRole("button",{name:"Send this email"})).toBeDisabled();
 fireEvent.click(screen.getByRole("button",{name:"Generate email preview"}));
 await waitFor(()=>expect(api.createReminderPreview).toHaveBeenCalledTimes(2));
 await screen.findByLabelText("Email body");
 expect(api.createReminderPreview.mock.calls[1][2]).not.toBe(api.createReminderPreview.mock.calls[0][2]);
});
it.each([
 [{opted_out:true}, {}, true, /recipient opted out/],
 [{recipient_email:null}, {}, true, /Add an email address/],
 [{}, {}, false, /no longer has an outstanding/],
 [{}, {archived_at:"2026-01-01"}, true, /Archived contacts/],
])("blocks unavailable contacts without creating a preview or sending",async(patch,contact,eligible,message)=>{
 api.getReminderPreferences.mockResolvedValue({...prefs,...patch});
 await open({friend:{...friend,...contact},eligible});
 expect(screen.getByText(message)).toBeInTheDocument();
 expect(screen.getByRole("button",{name:"Generate email preview"})).toBeDisabled();
 expect(api.createReminderPreview).not.toHaveBeenCalled();
 expect(api.sendReminderPreview).not.toHaveBeenCalled();
});
it("blocks pending or recent uncertain history before another send can be approved",async()=>{
 api.listReminders.mockResolvedValue([row({status:"uncertain",attempted_at:new Date().toISOString()})]);
 await open();
 fireEvent.click(screen.getByLabelText(consentLabel));
 expect(screen.getByText(/24-hour recipient cooldown/)).toBeInTheDocument();
 expect(screen.getByRole("button",{name:"Generate email preview"})).toBeDisabled();
 expect(api.sendReminderPreview).not.toHaveBeenCalled();
});
it("connection loss never retries POST; checking status only performs GET",async()=>{
 api.sendReminderPreview.mockRejectedValue(failure("Connection interrupted",true,0));
 api.getReminder.mockResolvedValue(row({status:"sent",attempted_at:new Date().toISOString()}));
 await open(); await generate(); await approveSend();
 await screen.findByText("Connection interrupted");
 expect(screen.getByRole("button",{name:"Create a new preview"})).toBeDisabled();
 fireEvent.click(screen.getByRole("button",{name:"Check delivery status"}));
 await screen.findByText(/Gmail accepted this email/);
 expect(api.getReminder).toHaveBeenCalledWith("p",expect.any(AbortSignal));
 expect(api.sendReminderPreview).toHaveBeenCalledTimes(1);
});
it("a still-preview GET cannot resolve an interrupted send into permission to retry",async()=>{
 api.sendReminderPreview.mockRejectedValue(failure("Connection interrupted",true,0));
 api.getReminder.mockResolvedValue(row());
 await open(); await generate(); await approveSend();
 await screen.findByText("Connection interrupted");
 fireEvent.click(screen.getByRole("button",{name:"Check delivery status"}));
 await screen.findByText(/do not assume.*safe to resend/);
 expect(screen.getByRole("button",{name:"Create a new preview"})).toBeDisabled();
 expect(api.sendReminderPreview).toHaveBeenCalledTimes(1);
});
it.each([
 ["reserved",null,/An attempt is in progress/],
 ["sending",null,/An attempt is in progress/],
 ["uncertain","delivery_uncertain",/Gmail may have accepted/],
 ["failed","authorization_failed",/authorization failed before submission/],
 ["failed","provider_rejected",/explicitly rejected/],
 ["cancelled","eligibility_changed",/Submission was cancelled/],
])("shows %s accurately without automatic retry",async(status,error_code,message)=>{
 api.sendReminderPreview.mockImplementation(async preview=>({...preview,status,error_code,attempted_at:status==="reserved"?null:new Date().toISOString()}));
 await open(); await generate(); await approveSend();
 await screen.findByText(message);
 expect(api.sendReminderPreview).toHaveBeenCalledTimes(1);
});
it("surfaces backend allowlist/stale/quiet-hour failures rather than bypassing them",async()=>{
 api.sendReminderPreview.mockRejectedValue(failure("Recipient is outside the configured demo allowlist.",false,403));
 await open(); await generate(); await approveSend();
 await screen.findByText("Recipient is outside the configured demo allowlist.");
 expect(api.sendReminderPreview).toHaveBeenCalledTimes(1);
 expect(screen.queryByRole("button",{name:"Send this email"})).not.toBeInTheDocument();
});
it("retains the permission and preview keys across explicit retries of pre-send operations",async()=>{
 api.saveReminderPermission.mockRejectedValueOnce(failure("Permission request interrupted",true,0)).mockResolvedValue({...prefs,permission_confirmed:true});
 await open();
 fireEvent.click(screen.getByLabelText(consentLabel));
 fireEvent.click(screen.getByRole("button",{name:"Generate email preview"}));
 await screen.findByText("Permission request interrupted");
 fireEvent.click(screen.getByRole("button",{name:"Generate email preview"}));
 await screen.findByLabelText("Email body");
 expect(api.saveReminderPermission.mock.calls[1][3]).toBe(api.saveReminderPermission.mock.calls[0][3]);
 expect(api.sendReminderPreview).not.toHaveBeenCalled();
});
it("retries preview creation with the same key after an interrupted response",async()=>{
 api.getReminderPreferences.mockResolvedValue({...prefs,permission_confirmed:true});
 api.createReminderPreview.mockRejectedValueOnce(failure("Preview interrupted",true,0)).mockResolvedValue(row());
 await open();
 fireEvent.click(screen.getByRole("button",{name:"Generate email preview"}));
 await screen.findByText("Preview interrupted");
 fireEvent.click(screen.getByRole("button",{name:"Generate email preview"}));
 await screen.findByLabelText("Email body");
 expect(api.createReminderPreview.mock.calls[1][2]).toBe(api.createReminderPreview.mock.calls[0][2]);
 expect(api.sendReminderPreview).not.toHaveBeenCalled();
});
it("does not silently restore permission revoked since the dialog was opened",async()=>{
 api.getReminderPreferences.mockResolvedValueOnce({...prefs,permission_confirmed:true}).mockResolvedValue(prefs);
 await open();
 fireEvent.click(screen.getByRole("button",{name:"Generate email preview"}));
 await screen.findByText(/Permission confirmation changed/);
 expect(screen.getByLabelText(consentLabel)).not.toBeChecked();
 expect(api.saveReminderPermission).not.toHaveBeenCalled();
 expect(api.createReminderPreview).not.toHaveBeenCalled();
});
it("detects a changed email before confirming consent for an outdated address",async()=>{
 api.getReminderPreferences.mockResolvedValueOnce(prefs).mockResolvedValue({...prefs,recipient_email:"new@example.com"});
 await open();
 fireEvent.click(screen.getByLabelText(consentLabel));
 fireEvent.click(screen.getByRole("button",{name:"Generate email preview"}));
 await screen.findByText(/contact’s email changed/);
 expect(screen.getByLabelText(consentLabel)).not.toBeChecked();
 expect(api.saveReminderPermission).not.toHaveBeenCalled();
 expect(api.createReminderPreview).not.toHaveBeenCalled();
});
it("revokes an existing confirmation without sending an email",async()=>{
 api.getReminderPreferences.mockResolvedValue({...prefs,permission_confirmed:true});
 await open();
 fireEvent.click(screen.getByRole("button",{name:"Revoke my permission confirmation"}));
 await screen.findByText(/confirmation was revoked/);
 expect(api.saveReminderPermission).toHaveBeenCalledWith("f",friend.email,false,expect.any(String),expect.any(AbortSignal));
 expect(screen.getByLabelText(consentLabel)).not.toBeChecked();
 expect(api.sendReminderPreview).not.toHaveBeenCalled();
});
it("ignores a late response for a previous contact",async()=>{
 let release;
 api.getReminderPreferences.mockImplementationOnce(()=>new Promise(resolve=>{release=resolve;})).mockResolvedValue({...prefs,friend_id:"other",recipient_email:"other@example.com"});
 const view=render(<EmailReminder friend={friend} eligible/>);
 view.rerender(<EmailReminder friend={{id:"other",display_name:"Other",email:"other@example.com"}} eligible/>);
 await screen.findByLabelText(consentLabel);
 await act(async()=>release(prefs));
 expect(screen.getByText("other@example.com")).toBeInTheDocument();
 expect(screen.queryByText("alex@example.com")).not.toBeInTheDocument();
});
