import { useState } from "react";

export default function AddFriendForm({ onSubmit, busy, error, friendSaved }) {
 const [type, setType] = useState("");
 const [repayment, setRepayment] = useState("");
 const [interest, setInterest] = useState(0);
 const [valid, setValid] = useState(false);
 const today = new Date();
 const minDate = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,"0")}-${String(today.getDate()).padStart(2,"0")}`;
 return <form className="add-iou-form" onSubmit={onSubmit} onChange={e => setValid(e.currentTarget.checkValidity() && !(e.target.name === "type" || (e.target.name === "repayment_type" && e.target.value === "other")))}>
  <p className="form-intro">Hold your friends accountable. Don’t let it slide. Get repaid.</p>
  <label htmlFor="friend-name">Name</label><input id="friend-name" name="name" required maxLength={100} pattern=".*\S.*" readOnly={friendSaved}/>
  <label htmlFor="friend-email">Email</label><input id="friend-email" name="email" type="email" required maxLength={320} readOnly={friendSaved}/>
  <label htmlFor="iou-type">Type</label><select id="iou-type" name="type" required value={type} onChange={e => {setType(e.target.value); setValid(false);}}><option value="" disabled>Select a type</option><option value="amount">Amount</option><option value="item">Item</option></select>
  {type === "amount" && <><label htmlFor="iou-amount">Amount (USD)</label><div className="amount-input"><span aria-hidden="true">$</span><input id="iou-amount" name="amount" type="number" min="0.01" max="10000000000" step="0.01" required placeholder="0.00"/></div></>}
  {type === "item" && <><label htmlFor="iou-item">Item</label><input id="iou-item" name="item" required maxLength={500} pattern=".*\S.*" placeholder="What did they borrow?"/></>}
  <label htmlFor="iou-due">Due date</label><input id="iou-due" name="due_date" type="date" min={minDate} max="9999-12-30" required/>
  <label htmlFor="iou-repayment">Repayment type</label><select id="iou-repayment" name="repayment_type" required value={repayment} onChange={e => {setRepayment(e.target.value); if (e.target.value === "item") setInterest(0); setValid(false);}}><option value="" disabled>How should they repay you?</option><option value="item">Item</option><option value="money">Money</option><option value="other">Other</option></select>
  {repayment === "other" && <><label htmlFor="iou-other">Repayment details</label><input id="iou-other" name="repayment_other" required maxLength={500} pattern=".*\S.*" placeholder="Describe how you want to be repaid"/></>}
  {type === "amount" && repayment && repayment !== "item" && <><label htmlFor="iou-interest">Daily interest (optional) <output htmlFor="iou-interest">{interest}%</output></label><input id="iou-interest" name="interest" type="range" min="0" max="1000" step="1" value={interest} onChange={e => setInterest(Number(e.target.value))}/><div className="range-labels"><span>0%</span><span>1000%</span></div><small className="interest-note">{interest}% of the original amount per day after the due date. No compounding.</small></>}
  {error && <p role="alert">{error}</p>}
  <button className="primary-action" disabled={busy || !valid}>{busy ? "Addingâ€¦" : "Add friend"}</button>
 </form>;
}
