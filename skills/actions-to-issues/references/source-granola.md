# Note source: Granola

`source: granola` in the config (also the default when `source` is absent).

Source: [Granola MCP docs](https://docs.granola.ai/help-center/sharing/integrations/mcp), read **24 November 2026**.

| | |
|---|---|
| MCP server | `https://mcp.granola.ai/mcp`, streamable HTTP |
| Auth | OAuth 2.0 per user (dynamic client registration). No API keys or service accounts over MCP |
| Plan | Basic (free) sees the last 30 days and has no transcript tools; transcripts and edit tools need a paid plan |
| Meeting id | the `id` attribute of each `<meeting>` (a UUID). This is the id in the state file and in card ids |
| Meeting link | `issue.link_template: "https://notes.granola.ai/d/{meeting_id}"` |

## Tools

| Use | Tool | Kind |
|---|---|---|
| Step 0 list | `list_meetings` (`time_range: "custom"`, `custom_start`, `custom_end`) | read |
| Step 0 list, where `list_meetings` is hidden | `search_meetings` (`from_date`, `to_date`, no `query`, no `keywords`) | read |
| Read the note | `get_meetings` (up to 10 ids) | read |
| Transcript, only if the note is too thin | `get_meeting_transcript` | read |
| **Never** | `create_folder`, `update_folder`, `add_note_to_folder`, `remove_note_from_folder`, `update_meeting_title`, `update_private_notes`, `update_summary`, `generate_summary`, `switch_workspace`, `sign_out`, `create_meeting_note_from_transcript` | write |

- Hosts: allow the read tools by name and deny or omit the write tools in **both** phases. The skill never edits notes.
- The docs say `list_meetings` is not shown in Claude, Claude Code, ChatGPT or Cursor, which use `search_meetings` and
  `get_meetings` instead. Use whichever is present. With `search_meetings`, page through `next_cursor`; it groups
  the captures of one event under one id, so count every `other_ids` entry of `duplicate_recordings` in `seen` too,
  and record those ids in the meeting's `ids` in the state file. Otherwise the pre-check, which lists every capture,
  finds the sibling and wakes the agent on every tick.
- The docs list no parameters for any tool. The `list_meetings` arguments above are what the pre-check sends and the
  server accepted when last run; they are not in the docs.

## Step 0 counts

- `seen`: every meeting returned, before filtering.
- `others`: meetings with `captured_by_me="false"` (someone else's note). A high `others` with a low `seen` means an
  account that cannot see its own meetings.

## Granola specifics

- **Several captures of one meeting:** each attendee's capture is its own note with its own id. Collapse them by title
  and start time (`references/policy.md`).
- **Workspace visibility:** `scope.skip_workspace_hidden` skips notes with `is_workspace_visible="false"`.
- **Readiness:** a note is written while the meeting runs. Treat a young meeting as deferred (the pre-check's `defer`
  lines, or 30 minutes since it started).

## Pre-check

```bash
python3 scripts/precheck.py --source granola     # or the older scripts/granola_precheck.py, unchanged
```

`GRANOLA_ACCESS_TOKEN` or `--auth-file` / `MCP_AUTH_FILE`; details in `scripts/source_granola.py`. It never
refreshes the OAuth token, so an idle day costs about one agent run per token lifetime. Granola also has a separate
REST API with API keys ([docs](https://docs.granola.ai)); the pre-check does not use it yet.
