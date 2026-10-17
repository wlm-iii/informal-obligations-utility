import { useState, useEffect } from "react";

/** Retained starter connectivity check; replace with domain API hooks in feature PRs. */
function useRandomItem(maximum) {
	const [randomItem, setRandomItem] = useState(null);

	useEffect(() => {
		const controller = new AbortController();
		getRandomItem(maximum, controller.signal)
			.then((value) => {
				if (!controller.signal.aborted) setRandomItem(value);
			})
			.catch((error) => {
				if (!controller.signal.aborted) console.error("Starter API check failed:", error);
			});
		return () => controller.abort();
	}, [maximum]);

	return randomItem;
}

async function getRandomItem(maximum, signal) {
	const params = new URLSearchParams({ maximum });
	const res = await fetch(`/api/random?${params}`, { signal });
	if (!res.ok) throw new Error(`API responded with HTTP ${res.status}`);
	const data = await res.json();
	return data.itemId;
}

export default useRandomItem;
