// Decorative seeded samples, never user balances or live stock-market data.
export const SAMPLE_COUNT = 60;
export const SAMPLE_STEP = 720 / (SAMPLE_COUNT - 1);
const labels = ["CHARGER", "$20.00", "HOODIE", "$60.00", "BOOK", "$12.50"];
function next(state) {
	const seed = (state.seed * 1664525 + 1013904223) >>> 0;
	const value = Math.max(55, Math.min(148, state.value + (seed / 4294967296 - .5) * 17 + (103 - state.value) * .065));
	return { seed, value };
}
export function createSeries() {
	let state = { seed: 803, value: 103 };
	const values = Array.from({ length: SAMPLE_COUNT + 2 }, () => { state = next(state); return state.value; });
	return { ...state, values, tick: 0, tags: [{ index: 18, value: values[18], label: "CHARGER" }, { index: 45, value: values[45], label: "$20.00" }] };
}
export function advanceSeries(state) {
	const generated = next(state), values = [...state.values.slice(1), generated.value], tick = state.tick + 1;
	const tags = state.tags.map(tag => ({ ...tag, index: tag.index - 1 })).filter(tag => tag.index >= 0);
	if (tick % 12 === 0) tags.push({ index: SAMPLE_COUNT - 3, value: values[SAMPLE_COUNT - 3], label: labels[(tick / 12 - 1) % labels.length] });
	return { ...generated, tick, values, tags };
}
export const marketY = value => 210 - (value - 100) * 3.25;
export function seriesPaths(values) {
	const line = values.map((v, i) => `${i ? "L" : "M"}${((i - 1) * SAMPLE_STEP).toFixed(2)} ${marketY(v).toFixed(2)}`).join(" ");
	return { line, area: `${line} L${(values.length - 2) * SAMPLE_STEP} 400 L${-SAMPLE_STEP} 400 Z` };
}
