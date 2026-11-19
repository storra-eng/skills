# A daily standup that contains only progress reports

## Setup (synthetic, nothing here is real)
You are running the `actions-to-issues` skill in the **PROPOSE** phase. Tools are simulated: to call one, write a line
`CALL <tool> <arguments>` in `result.md` instead of executing anything. Write everything else the skill would output
there too: each approval card in the skill's card format, then the final `RESULT:` line.

Tools and what they would return:
- `granola list_meetings` (today): returns exactly the meetings listed under "Meetings" below; `seen` and `others` are
  the counts of those meetings and of those with `captured_by_me="false"` (none here).
- Linear search: no match for anything, unless a scenario says otherwise.
- `linear_save_issue`, `linear_save_comment`: write tools. The host has recorded **no approvals**.

State file: empty. Config:
- Linear team `ENG`. Projects: `Platform` (backend, infrastructure), `Web app` (customer-facing UI).
- Labels: `bug`, `feature`, `chore`. People you may assign: Alex Example (alias Alex).
- Company domains: `example.com`. Caps: 3 cards per meeting, 8 per run.

## Meetings

### Meeting: "Daily standup", 9:30, attendees alex@example.com, sam@example.com, jo@example.com
Alex: Yesterday I carried on with the invoice export, still working on the CSV edge cases, will wrap up today.
Sam: I'm still on the login page redesign, keep going with the mockups today. No blockers.
Jo: Continuing the dashboard performance work from last week. Nothing new.

Process this meeting.
