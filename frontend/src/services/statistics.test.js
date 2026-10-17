import { describe, expect, it } from 'vitest';
import { summarizePayments } from './statistics';
const loan = {id:'a',friend_id:'friend',kind:'money',status:'open',principal_cents:20000,outstanding_cents:12500};
const event = {id:'one', action:'repayment', amount_cents:7500,effective_at:'2026-10-01T12:00:00Z',loan};
describe('repayment statistics',()=>{
 it('totals recorded repayments in integer cents',()=>{expect(summarizePayments([loan],[event],0,new Date('2026-10-17'))).toMatchObject({repaid:7500,outstanding:12500,lent:20000,open:1});});
 it('excludes reversed payments, voided loans, item returns and other contacts',()=>{expect(summarizePayments([loan],[{...event,reversed_at:'2026-10-02'}, {...event,loan:{...loan,id:'other'}}, {...event,action:'return'}],0,new Date('2026-10-17')).repaid).toBe(0);expect(summarizePayments([{...loan,status:'voided'}],[event],0,new Date('2026-10-17')).lent).toBe(0);});
 it('filters the payment period without changing current outstanding balance',()=>{expect(summarizePayments([loan],[{...event,effective_at:'2026-01-01'}],30,new Date('2026-10-17'))).toMatchObject({repaid:0,outstanding:12500});});
});
