export function rankEntries(entries, shame) {
 return [...entries].sort((a, b) => {
  if (shame) {
   const pinned = Number(b.title === "Public Enemy #1") - Number(a.title === "Public Enemy #1");
   if (pinned) return pinned;
  }
  return (shame ? 1 : -1) * (a.score - b.score) || a.name.localeCompare(b.name);
 });
}
