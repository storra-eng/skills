# Tracker adapter: GitHub Issues

Used when the config says `tracker: github`.

## Server

| Item | Value | Source |
|---|---|---|
| MCP server | GitHub's official server, remote at `https://api.githubcopilot.com/mcp/` (or run locally) | [github/github-mcp-server README](https://github.com/github/github-mcp-server), read 24 Nov 2026 |
| Issues only | `https://api.githubcopilot.com/mcp/x/issues` exposes just the `issues` toolset | [Remote server docs](https://github.com/github/github-mcp-server/blob/main/docs/remote-server.md) |
| Read-only | `https://api.githubcopilot.com/mcp/x/issues/readonly`, or the `X-MCP-Readonly` header; locally `--read-only`, which "takes priority" over `--tools` | same |
| One tool at a time | `X-MCP-Tools` header (locally `--tools` / `GITHUB_TOOLS`) enables only the named tools | same |
| Auth | OAuth, or `Authorization: Bearer <token>`. Use a fine-grained token limited to the target repositories with Issues read (PROPOSE) or Issues read and write (FILE) | README; token scoping per [GitHub docs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) |
| Verified | Tool names below confirmed by a read-only `tools/list` against both `/x/issues` URLs on 24 Nov 2026. No write was made | live |

## Read tools (PROPOSE and FILE)

`search_issues`, `issue_read`, `get_label`, `list_issue_types`

Leave `list_issues` out: it lists a whole repository, and the skill only runs topic-scoped searches.

## Write tools (FILE only, one approval per call)

`issue_write`, `add_issue_comment`

- `issue_write` does **create and update** (`method: "create" | "update"`, including closing an issue). A host cannot
  split them by tool name: show the arguments in the approval prompt, or use a hook that refuses anything but
  `method: "create"` with no `issue_number`.
- `add_issue_comment` also adds reactions, and works on pull requests. Refuse a call without `body`.
- The `/x/issues` toolset also holds `sub_issue_write` and `update_issue_comment`; never allow them. Do not enable
  other toolsets (repos, pull requests, actions): this skill needs none of them.

## Config block

```yaml
github:
  repos:                       # the only repositories a card may name; replaces "project"
    - {owner: "example-org", name: "web", use_for: "customer-facing web UI"}
  labels: ["bug", "feature", "chore"]   # a card's labels must exist in its repo; checked before filing
  milestones: [{title: "Launch", number: 3, repo: "example-org/web"}]   # optional
  people: [{name: "Alex Example", login: "alex-example", aliases: ["Alex"]}]
  default_assignee: null
```

## Card categorisation lines

GitHub issues have **no priority field**. Do not invent one with a label; if the meeting gave urgency, say so in the
description.

```text
*Repository:* <owner/name from config> - <why>
*Labels:* <from config>
*Milestone:* <only a config milestone whose repo is the card's repository, and only if the meeting tied it, else none>
*Assignees:* <only people the meeting named, by login from config, else none>
```

## Calls

| Step | Call |
|---|---|
| Search (both phases) | One `search_issues` per configured repo, with `owner` and `repo` **always set** (unpinned, it searches all of GitHub) and `query` = the topic with any `word:` qualifier (`repo:`, `org:`, `is:`) removed. Ignore pull requests in the results |
| Check labels | `get_label` for each card label in the card's repo: in PROPOSE before posting the card (a missing label is left off the card), and again in FILE before creating. A label that is missing is left off (record and report `detail=fields-dropped`), so the create call can never add a label to the repo. Whether GitHub would create or reject an unknown label is not stated in the docs read |
| Create | `issue_write` with `method: "create"`, `owner`, `repo`, `title`, `body`, `labels` (names), `assignees` (logins), `milestone` (number) - each only if on the card |
| Comment on a duplicate | `add_issue_comment` with `owner`, `repo`, `issue_number`, `body` |
| Issue key in state | `owner/repo#number` |

## Read the response

Per the [REST create-issue docs](https://docs.github.com/en/rest/issues/issues#create-an-issue) (read 24 Nov 2026),
labels and assignees from a user without push access "are silently dropped". Compare the response's labels,
assignees and milestone with the card. **Do not call `issue_write` again to fix a mismatch**; record it and report
`detail=fields-dropped`. Give the filing identity the Write role (push access) on the target repositories so this does not happen.

## Public repositories

An issue in a public repository is **world-readable** and indexed. The scope filter, the "quote only the justifying
line" rule and the meeting link all matter more: meeting-note share links are often viewable by anyone with the link.
Prefer a private repository for meeting-derived issues; for a public one, consider an empty
`issue.link_template` and keep quotes to the minimum.

## Fallback without MCP

`gh issue list -R owner/repo --search "<topic>"` (read), `gh issue create` / `gh issue comment` (write), per the
[gh manual](https://cli.github.com/manual/gh_issue). A host using it must give PROPOSE a token without Issues write,
since a shell command cannot be split by tool name.
