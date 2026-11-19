# A meeting that settles one clear, trackable piece of work

## Setup (synthetic, nothing here is real)
You are running the `actions-to-issues` skill in the **PROPOSE** phase. The MCP servers are not connected in this
sandbox, so work from the notes below and write your result to `result.md` in the working directory: for each card, the
full approval card exactly as the skill's card format specifies; then the final `RESULT:` line. Do not create issues.

Config:
- Linear team `ENG`. Projects (use the id when filing): `Platform` (backend, infrastructure), `Web app` (customer-facing UI).
- Labels: `bug`, `feature`, `chore`. People you may assign: Alex Example (alias Alex).
- Company domains: `example.com`. Caps: 3 cards per meeting, 8 per run.
- Existing Linear search results: no match for anything unless a scenario says otherwise.

## Meeting: "Billing sync" (meeting id `m-0001`), 14:00, attendees alex@example.com, sam@example.com
Sam: The webhook retries are dropping events under load. We should fix that before the launch.
Alex: Agreed. Decision: we add a dead-letter queue for failed billing webhooks and alert on it. I'll take it, it's needed by the 12th, that's the launch date.
Sam: Fine. Search for anything already covering it first.

Process this meeting.
