// @vitest-environment jsdom
import { StrictMode } from "react";
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import MarketChart from "./MarketChart";
import { advanceSeries, createSeries, SAMPLE_STEP, seriesPaths } from "./marketSeries";

beforeEach(() => {
	vi.useFakeTimers();
	vi.spyOn(document, "hidden", "get").mockReturnValue(false);
	vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("decorative market chart", () => {
	it("adds exactly one sample each second, including in StrictMode", () => {
		render(<StrictMode><MarketChart /></StrictMode>);
		const chart = screen.getByTestId("market-chart");
		act(() => vi.advanceTimersByTime(999)); expect(chart).toHaveAttribute("data-tick", "0");
		act(() => vi.advanceTimersByTime(1)); expect(chart).toHaveAttribute("data-tick", "1");
		act(() => vi.advanceTimersByTime(1000)); expect(chart).toHaveAttribute("data-tick", "2");
	});
	it("pauses, resumes, and cleans up its timer", () => {
		const { rerender, unmount } = render(<MarketChart />);
		act(() => vi.advanceTimersByTime(1000));
		rerender(<MarketChart paused />);
		act(() => vi.advanceTimersByTime(5000)); expect(screen.getByTestId("market-chart")).toHaveAttribute("data-tick", "1");
		rerender(<MarketChart />);
		act(() => vi.advanceTimersByTime(1000)); expect(screen.getByTestId("market-chart")).toHaveAttribute("data-tick", "2");
		unmount(); expect(vi.getTimerCount()).toBe(0);
	});
	it("stays static with reduced motion and when another pattern is selected", () => {
		window.matchMedia.mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() });
		const { rerender } = render(<MarketChart />);
		act(() => vi.advanceTimersByTime(3000)); expect(screen.getByTestId("market-chart")).toHaveAttribute("data-tick", "0");
		rerender(<MarketChart enabled={false} />); expect(screen.getByTestId("market-chart").parentElement).toHaveAttribute("hidden");
	});
	it("suspends sample updates while the document is hidden", () => {
		render(<MarketChart />);
		vi.spyOn(document, "hidden", "get").mockReturnValue(true);
		act(() => document.dispatchEvent(new Event("visibilitychange")));
		act(() => vi.advanceTimersByTime(3000)); expect(screen.getByTestId("market-chart")).toHaveAttribute("data-tick", "0");
	});
	it("drops the oldest sample and creates a finite clipped area with item labels", () => {
		const start = createSeries(), next = advanceSeries(start);
		expect(next.values.slice(0, -1)).toEqual(start.values.slice(1));
		expect(next.tags[0].index).toBe(start.tags[0].index - 1);
		expect(seriesPaths(next.values).area).not.toMatch(/NaN|undefined/);
		expect(SAMPLE_STEP).toBeGreaterThan(0);
		let later = start; for (let i = 0; i < 12; i++) later = advanceSeries(later);
		expect(later.tags.at(-1).label).toBe("CHARGER");
	});
});
