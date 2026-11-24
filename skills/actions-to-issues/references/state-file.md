# State file

`$MN2L_STATE` is a small JSON document, rewritten whole by the run that changes it. **Runs must not overlap**: the
host should serialise PROPOSE and FILE (a lock, or one queue), because each reads the file, works for minutes and
writes it back, and a stale copy written last silently undoes the other's changes. As a second line of defence, re-read
the file immediately before writing and change only your own entries. It is the only memory the skill
has, and `scripts/precheck.py` (or the Granola-only `granola_precheck.py`) reads its `handled` list to decide whether to wake a model at all.

```json
{
  "handled": [
    {
      "ids": ["<processed meeting id>", "<sibling meeting id>"],
      "title": "<meeting title>",
      "start": "2030-01-15T09:00",
      "date": "2030-01-15",
      "outcome": "proposed | skipped: <reason> | nothing-to-file | existing: <ISSUE-KEY>",
      "cards": [
        {"id": "<meeting id>-1", "outcome": "proposed | filed: <ISSUE-KEY> | existing: <ISSUE-KEY> | rejected"},
        {"id": "<meeting id>-2", "outcome": "proposed"}
      ]
    }
  ],
  "open": [
    {"card": "<card id>", "meeting": "<processed meeting id>", "title": "<proposed title>"}
  ]
}
```

- The meeting-level `outcome` says how the meeting was judged; each card carries its own outcome, because the cards
  from one meeting are approved, rejected and filed independently. A meeting with no cards omits `cards`.
- `handled` is newest first and is what the pre-check reads. A bare string is also accepted as an entry (an id).
- Ids are always JSON strings, even when the source's id is a number (Fathom `recording_id`).
- Every id of a meeting that arrived as several notes goes in `ids`, the processed one first.
- `open` is the cards awaiting a decision. Add a card the moment you post it. Remove it the moment it is resolved
  (filed, or rejected). **Never remove one because it has gone quiet**: age is not a decision, and a queue nobody is
  answering is not consent. Report a card pending for more than two working days (`stale=<card id>`) and leave it.
- **Bound it.** Keep the most recent 100 `handled` entries. The file must be the same size in a year as today. Never
  read anything whose size grows with your own history.
- `title` and `start` exist only to match a sibling note that arrives later. They are meeting content: keep the file
  private, and keep a `skipped: personal` meeting's title out of it (store `"title": null`). Known limit: a later sibling note of such
  a meeting cannot be matched, so it is judged and skipped again - a wasted run, but no personal content is stored.
- A `skipped` outcome carries a short reason and no meeting content.
- Write the file inside your working directory or the configured path, never under a world-readable temp directory:
  it is a record of someone's calendar.
- Do not put the file's contents in a chat message, a comment or a log.
- The pre-check treats an unreadable or malformed state file as a failure and wakes the agent. Do not paper over a
  malformed file by writing an empty one.
