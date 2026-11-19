# A meeting that settles one clear, trackable piece of work

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

### Meeting: "Billing sync" (meeting id `m-0001`), 14:00, attendees alex@example.com, sam@example.com
Sam: The webhook retries are dropping events under load. We should fix that before the launch.
Alex: Agreed. Decision: we add a dead-letter queue for failed billing webhooks and alert on it. I'll take it, it's needed by the 12th, that's the launch date.
Sam: Fine by me.

Process this meeting.
