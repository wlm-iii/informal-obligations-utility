import { supabase } from "./supabase";

// Read every page: the ledger endpoint defaults to just 25 records.
export async function loadLoans(signal) {
 const { data, error } = await supabase.auth.getSession();
 if (error || !data.session) throw new Error("Please sign in again to view lending data.");
 const loans = [];
 for (let offset = 0; offset <= 100000; offset += 100) {
  const response = await fetch(`/api/loans?limit=100&offset=${offset}`, {
   signal, cache: "no-store", headers: { Authorization: `Bearer ${data.session.access_token}` },
  });
  if (response.status === 401) throw new Error("Your session expired. Please sign in again.");
  if (!response.ok) throw new Error("Lending data is unavailable. Please retry.");
  const page = await response.json();
  if (!Array.isArray(page.items)) throw new Error("Lending data is unavailable. Please retry.");
  loans.push(...page.items);
  if (!page.has_more) return loans;
 }
 throw new Error("Your ledger is too large to display completely.");
}

export function summarizeLoans(loans) {
 const items = loans.filter(loan => loan.kind === "item");
 const returned = items.filter(loan => loan.status === "completed").length;
 return {
  outstanding: items.length - returned, returned,
  unpaid: loans.filter(loan => loan.status === "open").length,
  repaid: loans.filter(loan => loan.status === "completed").length,
 };
}
