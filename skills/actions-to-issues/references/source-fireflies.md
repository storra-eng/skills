# Note source: Fireflies.ai

`source: fireflies` in the config.

Sources, read **24 November 2026**: [MCP configuration](https://docs.fireflies.ai/getting-started/mcp-configuration),
[MCP tools](https://docs.fireflies.ai/mcp-tools/overview),
[`transcripts` query](https://docs.fireflies.ai/graphql-api/query/transcripts),
[Transcript schema](https://docs.fireflies.ai/schema/transcript),
[quickstart](https://docs.fireflies.ai/getting-started/quickstart). **Not tested against a live account.**

| | |
|---|---|
| MCP server | `https://api.fireflies.ai/mcp`, streamable HTTP only |
| Auth | OAuth (default), or an API key as `Authorization: Bearer <key>` |
| Meeting id | the transcript `id` (format not documented). This is the id in the state file and in card ids |
| Meeting link | the transcript's `transcript_url` field; or set `issue.link_template` if you know your link format |
| Start time | `date`, epoch milliseconds (UTC); `duration` is in minutes |

## Tools

| Use | Tool | Kind |
|---|---|---|
| Step 0 list | `fireflies_get_transcripts` (`fromDate`, `toDate` as `YYYY-MM-DD`; `limit` max 50; `skip`) | read |
| Read the note | `fireflies_get_summary` (`transcriptId`) | read |
| Transcript, only if the summary is too thin | `fireflies_get_transcript` (`transcriptId`) | read |
| **Never** | `fireflies_share_meeting`, `fireflies_revoke_meeting_access`, `fireflies_update_meeting_title`, `fireflies_move_meeting`, `fireflies_create_soundbite`, `fireflies_create_upload_url`, `fireflies_confirm_upload`, `fireflies_create_meeting_from_transcript`, `fireflies_add_transcript_part` | write |

- The docs do not label tools read or write; the split above is from each tool's description. Allow the three read
  tools by name; deny or omit the rest in **both** phases. `fireflies_share_meeting` sends access to email addresses.
- `fireflies_fetch` and `fireflies_search` are marked experimental; not used.
- Page with `skip` while a page comes back full (50). Stop at 10 pages and report `status=error detail=too-many-meetings`.

## Step 0 counts

- `seen`: every transcript returned.
- `others`: Fireflies has no "captured by me" flag. Report `others=unknown`. Do not use the `mine` filter: it would
  hide meetings someone else organised.

## Fireflies specifics

- **One meeting, one transcript:** the notetaker joins the call once, so duplicate captures are rarer than with
  Granola, but two users' bots can join the same call. Collapse by title and start time as usual.
- **Readiness:** a transcript is listed once processed; the docs give no processing time. `meeting_info.summary_status`
  exists but its values are not documented. If the summary is empty, treat the meeting as deferred.
- **Workspace visibility:** `scope.skip_workspace_hidden` does not apply. Apply the scope filter from content as usual.

## Pre-check

```bash
FIREFLIES_API_KEY=... python3 scripts/precheck.py --source fireflies
```

One GraphQL `transcripts(fromDate, toDate, limit, skip) { id date }` call per page, with a long-lived API key
(not the agent's OAuth session). Keep that key out of the agent's environment. Details in
`scripts/source_fireflies.py`. API rate limits depend on plan ([limits](https://docs.fireflies.ai/fundamentals/limits)):
Free is 500 calls a day, so a 5-minute schedule is about 290 calls.
