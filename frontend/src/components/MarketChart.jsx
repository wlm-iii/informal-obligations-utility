import { useEffect, useId, useState } from "react";
import { advanceSeries, createSeries, marketY, SAMPLE_COUNT, SAMPLE_STEP, seriesPaths } from "./marketSeries";

export default function MarketChart({ paused = false, enabled = true }) {
	const [series, setSeries] = useState(createSeries);
	const [reduced, setReduced] = useState(() => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);
	const [hidden, setHidden] = useState(() => document.hidden);
	const gradient = useId().replaceAll(":", "");
	const active = enabled && !paused && !reduced && !hidden;
	useEffect(() => {
		const media = window.matchMedia?.("(prefers-reduced-motion: reduce)");
		const motion = event => setReduced(event.matches), visibility = () => setHidden(document.hidden);
		media?.addEventListener("change", motion);
		document.addEventListener("visibilitychange", visibility);
		return () => { media?.removeEventListener("change", motion); document.removeEventListener("visibilitychange", visibility); };
	}, []);
	useEffect(() => {
		if (!active) return;
		const timer = window.setInterval(() => setSeries(advanceSeries), 1000);
		return () => window.clearInterval(timer);
	}, [active]);
	const paths = seriesPaths(series.values);
	return (
		<div className="headline-chart" hidden={!enabled} aria-hidden="true">
			<svg viewBox="0 0 720 400" preserveAspectRatio="none" data-testid="market-chart" data-tick={series.tick} style={{ color: series.values[SAMPLE_COUNT - 1] >= 100 ? "var(--green)" : "var(--red)" }}>
				<defs><linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="currentColor" stopOpacity=".17" /><stop offset="1" stopColor="currentColor" stopOpacity=".015" /></linearGradient></defs>
				<g className="ticker-grid"><path d="M0 80H720 M0 160H720 M0 240H720 M0 320H720 M90 0V400 M210 0V400 M330 0V400 M450 0V400 M570 0V400 M690 0V400" /></g>
				<path className="ticker-baseline" d="M0 210H720" />
				<g key={series.tick} className="ticker-scroll" style={{ "--ticker-step": `${-SAMPLE_STEP}px`, animationPlayState: active ? "running" : "paused" }}>
					<path className="ticker-area" d={paths.area} fill={`url(#${gradient})`} /><path className="ticker-line" d={paths.line} />
					{series.tags.map(tag => <g className="ticker-tag" key={`${tag.label}-${tag.index}`} transform={`translate(${(tag.index - 1) * SAMPLE_STEP} ${marketY(tag.value)})`} opacity={Math.min(1, tag.index / 8)}><circle r="2.5" /><text x="7" y="-11">{tag.label}</text></g>)}
				</g>
			</svg>
		</div>
	);
}
