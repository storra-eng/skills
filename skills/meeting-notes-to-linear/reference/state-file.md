# State file

`$MN2L_STATE` is a small JSON document, rewritten whole by the run that changes it. It is the only memory the skill
has, and `scripts/granola_precheck.py` reads its `handled` list to decide whether to wake a model at all.

```json
{
  "handled": [
    {
      "ids": ["<processed meeting id>", "<sibling meeting id>"],
      "date": "2030-01-15",
      "outcome": "proposed | skipped: <reason> | existing: <ISSUE-KEY> | filed: <ISSUE-KEY>",
      "cards": ["<card id>"]
    }
  ],
  "open": [
    {"card": "<card id>", "meeting": "<processed meeting id>", "title": "<proposed title>"}
  ]
}
```

- `handled` is newest first and is what the pre-check reads. A bare string is also accepted as an entry (an id).
- Every id of a meeting that arrived as several notes goes in `ids`, the processed one first.
- `open` is the cards awaiting a decision. Add a card the moment you post it. Remove it the moment it is resolved
  (filed, or rejected). **Never remove one because it has gone quiet**: age is not a decision, and a queue nobody is
  answering is not consent. Report a card pending for more than two working days (`stale=<card id>`) and leave it.
- **Bound it.** Keep the most recent 100 `handled` entries. The file must be the same size in a year as today. Never
  read anything whose size grows with your own history.
- A `skipped` outcome carries a short reason and no meeting content.
- Write the file inside your working directory or the configured path, never under a world-readable temp directory:
  it is a record of someone's calendar.
- Do not put the file's contents in a chat message, a comment or a log.
- The pre-check treats an unreadable or malformed state file as a failure and wakes the agent. Do not paper over a
  malformed file by writing an empty one.
