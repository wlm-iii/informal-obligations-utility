// @vitest-environment jsdom
import { afterEach, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import Leaderboards from "./Leaderboards";
import { rankEntries } from "../services/leaderboards";

afterEach(cleanup);

it("renders Fame in descending score order with each matching award and illustration", () => {
 render(<Leaderboards />);
 const rows = within(screen.getByRole("region", { name: "Hall of Fame" })).getAllByRole("listitem");
 expect(rows.map(row => within(row).getByText(/^(980|965|940|910)$/).textContent)).toEqual(["980", "965", "940", "910"]);
 for (const [index, title] of ["Credit Royalty", "Certified Green Flag", "Walking ATM", "Speedrun Champion"].entries()) {
  expect(within(rows[index]).getByRole("heading", { name: title })).toBeInTheDocument();
  expect(within(rows[index]).getByRole("img", { name: `${title} illustration` })).toBeInTheDocument();
 }
});

it("pins Public Enemy #1 first and ranks the remaining Shame entries by ascending score", () => {
 render(<Leaderboards />);
 const rows = within(screen.getByRole("region", { name: "Hall of Shame" })).getAllByRole("listitem");
 expect(rows.map(row => within(row).getByRole("heading").textContent)).toEqual(["Public Enemy #1", "Professional Ghoster", "Debt Criminal", "Brokie Alert"]);
 expect(within(rows[0]).getByText("Alex")).toBeInTheDocument();
 expect(within(rows[0]).getByText("420")).toBeInTheDocument();
 expect(screen.getByText(/Illustrative sample names and scores/)).toBeInTheDocument();
});

it("breaks tied scores alphabetically without changing the input records", () => {
 const entries = [{ name: "Zoe", score: 900, title: "A" }, { name: "Alex", score: 900, title: "B" }];
 expect(rankEntries(entries, false).map(entry => entry.name)).toEqual(["Alex", "Zoe"]);
 expect(entries.map(entry => entry.name)).toEqual(["Zoe", "Alex"]);
 expect(rankEntries([], true)).toEqual([]);
});
