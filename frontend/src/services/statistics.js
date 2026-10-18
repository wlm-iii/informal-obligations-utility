import { supabase } from "./supabase";

export async function statisticsRequest(path, signal) {
	const { data, error } = await supabase.auth.getSession();
	if (error || !data.session) throw new Error("Please sign in again.");
	const items = [];
	let cursor = null;
	do {
		const url = new URL(`/api/${path}`, window.location.origin);
		url.searchParams.set("pagination", "cursor");
		url.searchParams.set("limit", "100");
		if (cursor) url.searchParams.set("cursor", cursor);
		const response = await fetch(url.pathname + url.search, {
			signal,
			cache: "no-store",
			headers: { Authorization: `Bearer ${data.session.access_token}` },
		});
		if (!response.ok)
			throw new Error(
				response.status === 401
					? "Your session expired. Please sign in again."
					: "Statistics are unavailable. Please retry.",
			);
		const page = await response.json();
		items.push(...page.items);
		cursor = page.has_more ? page.next_cursor : null;
		if (page.has_more && !cursor)
			throw new Error("Could not load the complete history. Please retry.");
	} while (cursor);
	return items;
}

export function summarizePayments(loans, history, days = 0, now = new Date()) {
	const validLoans = loans.filter(
		(loan) => loan.kind === "money" && loan.status !== "voided",
	);
	const ids = new Set(validLoans.map((loan) => loan.id));
	const cutoff = days ? now.getTime() - days * 86400000 : -Infinity;
	const payments = history
		.filter(
			(event) =>
				event.action === "repayment" &&
				!event.reversed_at &&
				ids.has(event.loan.id) &&
				new Date(event.effective_at).getTime() >= cutoff &&
				new Date(event.effective_at) <= now,
		)
		.sort((a, b) => new Date(a.effective_at) - new Date(b.effective_at));
	return {
		payments,
		repaid: payments.reduce((sum, payment) => sum + payment.amount_cents, 0),
		outstanding: validLoans.reduce((sum, loan) => sum + loan.outstanding_cents, 0),
		lent: validLoans.reduce((sum, loan) => sum + loan.principal_cents, 0),
		open: validLoans.filter((loan) => loan.status === "open").length,
	};
}
