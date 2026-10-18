# Tracker PR compatibility merge

These notes describe the original compatibility merge. Subsequent work connects
signed-in Tracker nudges to real approved email; public/offline demos remain
clipboard-only. See [current reminder flow](REMINDERS.md#live-email-demo-through-tracker).

The incoming `codex/iou-tracker-daily-interest` branch forked from the Level 1 ledger
(`fec7545`), before current main's Levels 2–5 and terminal/account UI. This merge
preserves current main wherever contracts differ; it does not introduce a second
interest engine or replace Google/Supabase login.

## Preserved from main

- Audited corrections, voids, immutable allocations, private evidence, cursor paging.
- Periodic simple interest on remaining principal from lending, rounding, caps,
  optional late fees, grace, waivers, and separate item borrowing/fee settlement.
- Dashboard/fictional score rules and consent-based Gmail reminder APIs.
- Current TerminalLogin, mint theme/tokens/fonts, account page, statistics, login tests.
- Existing `outstanding_cents` means remaining principal; `total_outstanding_cents`
  includes all unpaid charges. Clients never recompute live interest locally.

The PR's 0–1000% daily overdue/original-principal calculator and `interest_percent`
contract were discarded. The form now submits integer `interest_rate_bps` and an
existing daily/weekly/biweekly/monthly/quarterly/yearly `interest_period`, capped at
100% per period. The frontend only formats those terms and backend balances.

## Retained new work

- Authenticated tracker, add-friend/loan form, friend views, settlement buttons,
  progress/history views, item-return overview, and optional design preview build.
- Tracker is an additive `#tracker` route available from the existing workspace nav;
  the default account page and `#statistics` keep their previous behavior.
- Repayment preferences: optional `repayment_type=item|money|other`, with
  `repayment_other` required only for `other`. These are immutable **metadata**, not
  barter, principal write-offs, or permission to change a loan's kind/settlement.
- New migration `0008_repayment_preferences` follows main's `0007_manual_reminders`.
  The unmerged fork `0004_iou_preferences` was removed; Alembic has one linear head.
  Existing loans get null metadata, default old creation receipts remain replayable,
  and downgrade refuses to discard recorded preferences. No new runtime grant needed
  beyond existing table-level loan SELECT/INSERT; original terms stay immutable.

## Compatibility fixes beyond text conflicts

- Money settlement pays the quoted total, not principal alone. Retries freeze the
  original action/body/key rather than silently retrying a changed amount.
- Already-returned items owing fees use `/fee-payments`, not duplicate `/return`.
  Returning an item can leave its financial obligation open for later fee payment.
- Return counts use actual return status rather than financial completion; voids
  never count as active loans or cash. Reversed events and waivers are not receipts.
- Contact-then-loan retries retain the saved contact and exact original loan payload.
- Offline previews use static snapshots, not another accrual implementation; creating
  an interest-bearing example requires the signed-in backend rather than fake math.
- Nudges remain explicitly clipboard-only, limited to friendly/direct/playful. They
  do not send email or bypass main's permission, approval, opt-out, or cooldown gates.
  Automated/Gemini/email UI integration is not added by this merge.
- Award boards remain clearly labeled illustrative designs, not real private ranks;
  samples stay inside the existing 300–850 fictional range with a disclaimer.

## Release and verification

Review/apply `upgrade head` explicitly before using preference inputs; do not apply
this PR's former `0004` fork. No hosted Supabase migration or live email is performed
by merge acceptance. Do not reinterpret existing deployed loan terms.

Acceptance includes existing main regression suites plus preference validation,
legacy receipt replay, guarded preference downgrade/schema drift, complete charge
settlement, returned-item fees, void/reversal filtering, main account/tracker
navigation, login checks, and normal/standalone preview builds. Frontend offline
samples do not certify live hosted data or delivery.
