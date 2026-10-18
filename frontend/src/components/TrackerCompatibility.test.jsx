// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import Dashboard from "./Dashboard";
vi.mock("../services/dashboard", async original => ({...await original(),ledgerRequest:vi.fn(),loadFriends:vi.fn()}));
vi.mock("../services/loans", async original => ({...await original(),loadLoans:vi.fn()}));
import { ledgerRequest, loadFriends } from "../services/dashboard";
import { loadLoans } from "../services/loans";
const friend={id:"f",display_name:"Alex",email:"alex@example.com"};
const money={id:"m",friend_id:"f",kind:"money",description:"Lunch",status:"open",due_date:"2099-01-01",lent_at:"2026-01-01",principal_cents:10000,outstanding_cents:10000,interest_cents:500,fees_cents:200,total_outstanding_cents:10700,interest_rate_bps:125,interest_period:"weekly"};
beforeEach(()=>{vi.resetAllMocks();loadFriends.mockResolvedValue([friend]);HTMLDialogElement.prototype.showModal=function(){this.setAttribute("open","");};});
afterEach(cleanup);
it("pays the server total including charges, not principal-only outstanding",async()=>{
 loadLoans.mockResolvedValue([money]);
 ledgerRequest.mockResolvedValue({loan:{...money,status:"completed",outstanding_cents:0,interest_cents:0,fees_cents:0,total_outstanding_cents:0}});
 render(<Dashboard/>);
 expect(await screen.findByText("$107.00")).toBeInTheDocument();
 expect(screen.getByText("1.25% / weekly")).toBeInTheDocument();
 fireEvent.click(screen.getByRole("button",{name:"Settle",exact:true}));
 await screen.findByRole("heading",{name:"Past payments"});
 expect(ledgerRequest.mock.calls[0][0]).toBe("/loans/m/repayments");
 expect(ledgerRequest.mock.calls[0][1].body).toEqual({amount_cents:10700});
});
it("pays fees on an already returned item instead of issuing a duplicate return",async()=>{
 const item={...money,id:"i",kind:"item",description:"Hoodie",principal_cents:null,outstanding_cents:null,interest_cents:0,total_outstanding_cents:200,returned_at:"2026-01-02",borrowing_status:"returned"};
 loadLoans.mockResolvedValue([item]);
 ledgerRequest.mockResolvedValue({loan:{...item,status:"completed",fees_cents:0,total_outstanding_cents:0}});
 render(<Dashboard/>);
 await screen.findByText("Returned · $2.00 fees");
 fireEvent.click(screen.getByRole("button",{name:"Settle",exact:true}));
 await screen.findByRole("heading",{name:"Past payments"});
 expect(ledgerRequest.mock.calls[0][0]).toBe("/loans/i/fee-payments");
 expect(ledgerRequest.mock.calls[0][1].body).toEqual({amount_cents:200});
});
it("filters voids and offers only the existing three polite clipboard tones",async()=>{
 loadLoans.mockResolvedValue([money,{...money,id:"v",status:"voided",description:"Voided debt"}]);
 render(<Dashboard/>);
 fireEvent.click(await screen.findByRole("button",{name:"Nudge ↗"}));
 const dialog=screen.getByRole("dialog");
 expect(within(dialog).getAllByRole("option").map(option=>option.textContent)).toEqual(["Friendly","Direct","Playful"]);
 expect(screen.queryByText("Voided debt")).not.toBeInTheDocument();
 expect(ledgerRequest).not.toHaveBeenCalled();
});
