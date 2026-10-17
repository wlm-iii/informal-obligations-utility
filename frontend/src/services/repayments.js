import { supabase } from "./supabase";

export function amountToCents(value) {
	if (!/^\d+(\.\d{1,2})?$/.test(value))
		throw new Error("Enter a positive amount with up to two decimal places.");
	const [whole, fraction = ""] = value.split(".");
	const cents = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
	if (!Number.isSafeInteger(cents) || cents <= 0)
		throw new Error("Enter a valid positive amount.");
	return cents;
}

export async function recordRepayment(loanId, body, key) {
	const { data, error } = await supabase.auth.getSession();
	if (error || !data.session) throw new Error("Please sign in again.");
	const response = await fetch(`/api/loans/${encodeURIComponent(loanId)}/repayments`, {
		method: "POST",
		cache: "no-store",
		headers: {
			Authorization: `Bearer ${data.session.access_token}`,
			"Content-Type": "application/json",
			"Idempotency-Key": key,
		},
		body: JSON.stringify(body),
	});
	if (!response.ok)
		throw new Error(
			response.status === 409
				? "This repayment conflicts with the current balance. Close this form and refresh statistics before trying again."
				: "Could not record repayment. Retry the same payment safely, or check your session.",
		);
	return response.json();
}
