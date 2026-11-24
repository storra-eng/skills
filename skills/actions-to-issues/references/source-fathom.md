# Note source: Fathom

`source: fathom` in the config.

Sources, read **24 November 2026**: [List meetings](https://developers.fathom.ai/api-reference/meetings/list-meetings),
[OpenAPI spec](https://developers.fathom.ai/api-reference/openapi.yaml), [FAQ](https://developers.fathom.ai/faq),
[MCP in Claude](https://developers.fathom.ai/mcp-docs/claude.md), [API overview](https://developers.fathom.ai/api-overview.md).
**Not tested against a live account.**

| | |
|---|---|
| MCP server | `https://api.fathom.ai/mcp` (Claude Code: `claude mcp add fathom -- npx mcp-remote@latest https://api.fathom.ai/mcp`) |
| Auth | Sign-in through the client; the method is not named in the docs. The REST API takes `X-Api-Key` or an OAuth bearer |
| Plan | API access on all plans. A key sees meetings its user recorded or that were shared with them |
| Meeting id | `recording_id`, an integer: write it **as a string** (`"123456"`) in the state file, or the pre-check fails on every tick. Also the card-id prefix |
| Meeting link | the meeting's `share_url` (or `url`): put it on the card's *Source:* line, where FILE reads it (FILE has no Fathom tools; the link cannot be built from the id) |
| Start time | `recording_start_time`, else `scheduled_start_time` |

## Tools

**The Fathom docs do not list the MCP server's tool names or say which ones write** (checked 24 November 2026).
Before enabling it, list the tools your client sees (in Claude Code, `/mcp`) and allow by name only those that list
meetings, read a summary and read a transcript. Deny everything else in **both** phases. Expected reads, matching the
REST API:

| Use | REST equivalent | Kind |
|---|---|---|
| Step 0 list | `GET /meetings?created_after=...&created_before=...` (page with `cursor` / `next_cursor`) | read |
| Read the note | `GET /recordings/{recording_id}/summary` | read |
| Transcript, only if the summary is too thin | `GET /recordings/{recording_id}/transcript` | read |

Never pass `destination_url` to those endpoints: it makes Fathom POST the content to that URL.

## Step 0 counts

- `seen`: every meeting returned across all pages. Stop at 20 pages and report `status=error detail=too-many-meetings`.
- `others`: report `others=unknown`. `recorded_by` names the recorder, but nothing says who the key belongs to.

## Fathom specifics

- **One meeting, one recording per recorder:** if two people record the same call, collapse by title and start time.
- **Readiness:** transcripts exist only after post-call processing, with no published delay. The docs do not say
  whether an unprocessed meeting is listed. An empty summary means deferred.
- **Workspace visibility:** `scope.skip_workspace_hidden` does not apply. `calendar_invitees_domains_type`
  (`only_internal` / `one_or_more_external`) can inform the scope filter.

## Pre-check

```bash
FATHOM_API_KEY=... python3 scripts/precheck.py --source fathom
```

One `GET /meetings` per page (page size is not documented; more than 20 pages is a `FAIL`) with a long-lived API key,
not the agent's session. Keep that key out of the agent's environment. Details in `scripts/source_fathom.py`. Fathom allows 60 calls per 60 seconds per key.
