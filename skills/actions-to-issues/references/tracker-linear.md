# Tracker adapter: Linear

Used when the config says `tracker: linear`, or has no `tracker` key (the default, so configs written before
adapters existed keep working unchanged).

## Server

| Item | Value | Source |
|---|---|---|
| MCP server | Linear's official remote server, `https://mcp.linear.app/mcp` (Streamable HTTP) | [Linear MCP docs](https://linear.app/docs/mcp), read 24 Nov 2026 |
| Read-only endpoint | `https://mcp.linear.app/mcp/readonly` - a good fit for every PROPOSE run | same |
| Auth | OAuth 2.1, or `Authorization: Bearer <API key>`; a read-only key or the `read` scope also limits it | same |
| Tool names | Not listed in Linear's docs. The names below were confirmed against the live server's tool list on 24 Nov 2026; the write path was not exercised | live `tools/list` |

## Read tools (PROPOSE and FILE)

`list_issues`, `get_issue`, `list_projects`, `list_issue_labels`, `list_users`, `list_teams`

## Write tools (FILE only, one approval per call)

`save_issue`, `save_comment`

- `save_issue` **creates** when no `id` is passed and **updates** when one is (per the server's own tool
  descriptions). A host splitting by tool name cannot tell the two apart: use a prompt that shows the arguments, or a
  hook that refuses a call carrying `id`. Treat `save_comment` the same way: a new comment never carries a comment
  `id`.
- The server has many more write tools (projects, labels, documents, attachments, releases). Allow the two above by
  name; never allow `mcp__<server>__*`.

## Config block

```yaml
linear:
  team: "ENG"
  projects: [{name, id, use_for}]   # the only projects a card may name
  labels: [{name, id}]              # the only labels a card may use
  people: [{name, id, aliases}]     # assignees, by id
  default_assignee: null
```

## Card categorisation lines

```text
*Project:* <project name from config> - <why>
*Labels:* <from config>
*Priority:* <Urgent / High / Medium / Low with the words that set it, or "none">
*Assignee:* <only someone the meeting named, else none>
```

## Calls

| Step | Call |
|---|---|
| Search (both phases) | `list_issues` with `query` = the topic and `team` = `linear.team`. Bounded: one team, a topic query, one page |
| Create | `save_issue` with `team`, `title`, `description`, `project` (**by config id**), `labels` (by id), `priority` (only if the card has one), `assignee` (by config id, only if the card has one) |
| Comment on a duplicate | `save_comment` with the existing issue's id and the comment body |
| Issue key in state | the identifier, e.g. `ENG-123` |

## Read the response

The create response must carry a project id, and its labels and assignee must match the card. A value that did not
match can be dropped with a success response. **Do not call `save_issue` again to fix it** - that is an unapproved
write. Record it in the state file and report `detail=fields-dropped`.
