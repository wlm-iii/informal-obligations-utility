// @vitest-environment jsdom
import { afterEach, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import History from "./History";
import Dashboard from "./Dashboard";
import {demoFriends,referenceLoans,referencePayments} from "../services/dashboardDemo";
const demo={friends:demoFriends,loans:referenceLoans,payments:referencePayments};
afterEach(cleanup);
it("shows borrowing first with two statuses, explicit types and item or money values",()=>{
 render(<History friends={demoFriends} loans={referenceLoans} demo={demo}/>);
 const tables=screen.getAllByRole("table");
 expect(tables[0]).toHaveAccessibleName("Borrowing history");
 expect(tables[1]).toHaveAccessibleName("Payment history");
 expect(within(tables[0]).getByRole("columnheader",{name:"Type"})).toBeInTheDocument();
 expect(within(tables[0]).getByRole("columnheader",{name:"Item/amount"})).toBeInTheDocument();
 expect(within(tables[0]).getByText("Travel mug")).toBeInTheDocument();
 expect(within(tables[0]).getByText("$385.00")).toBeInTheDocument();
 const statuses=screen.getAllByText(/^(unpaid\/missing|paid\/returned)$/);
 expect(statuses).toHaveLength(referenceLoans.length+referencePayments.length);
 expect(screen.queryByLabelText("Payment details")).not.toBeInTheDocument();
 expect(screen.queryByText("02 / PAYMENT RECORDS")).not.toBeInTheDocument();
});
it("matches the reference's eight payment rows, dates, amounts, and recorded status",()=>{
 render(<History friends={demoFriends} loans={referenceLoans} demo={demo}/>);
 expect(screen.getByRole("heading",{name:"Past payments"})).toBeInTheDocument();
 expect(screen.getByText("8 RECORDS")).toBeInTheDocument();
 const rows=within(screen.getByRole("table",{name:"Payment history"})).getAllByRole("row");
 expect(rows).toHaveLength(9);
 expect(within(rows[1]).getByText("Oct 14, 2026")).toBeInTheDocument();
 expect(within(rows[1]).getByText("$30.00")).toBeInTheDocument();
 expect(within(rows[8]).getByText("Jul 1, 2026")).toBeInTheDocument();
 expect(within(screen.getByRole("table",{name:"Payment history"})).getAllByText("paid/returned")).toHaveLength(8);
});
it("records a preview payment and updates Progress and History together",async()=>{
 HTMLDialogElement.prototype.showModal=function(){this.setAttribute("open","");};
 render(<Dashboard demo={{...demo,loans:referenceLoans.map(loan=>({...loan,interest_rate_bps:0}))}}/>);
 fireEvent.click(screen.getByRole("button",{name:"Progress",exact:true}));
 expect(screen.getByText("68% of recorded balance repaid")).toBeInTheDocument();
 fireEvent.click(screen.getByRole("button",{name:"Record repayment"}));
 fireEvent.change(screen.getByLabelText("Amount (USD)"),{target:{value:"25.00"}});
 fireEvent.click(screen.getByRole("button",{name:"Record payment"}));
 expect(await screen.findByText("74% of recorded balance repaid")).toBeInTheDocument();
 expect(screen.getByRole("img",{name:"$285.00 repaid across 9 payments"})).toBeInTheDocument();
 fireEvent.click(screen.getByRole("button",{name:"History",exact:true}));
 expect(screen.getByText("9 RECORDS")).toBeInTheDocument();
});
