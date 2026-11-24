# Tracker adapter: Jira

Used when the config says `tracker: jira`. **Docs-only**: nothing here has been run against a live Jira site.

## Server

| Item | Value | Source |
|---|---|---|
| MCP server | Atlassian Rovo MCP Server (Atlassian's official remote server), `https://mcp.atlassian.com/v2/mcp`; "New setups should use" v2 | [atlassian/atlassian-mcp-server](https://github.com/atlassian/atlassian-mcp-server), read 24 Nov 2026 |
| Auth | OAuth 2.1 or API tokens; API-token auth is a separate setting an organisation admin controls | same; [MCP server settings](https://support.atlassian.com/security-and-access-policies/docs/control-atlassian-mcp-server-settings/) |
| Tool groups | Tools sit in permission groups (`read_jira`, `search_jira`, `write_jira`; `delete_jira` and `manage_jira` are off by default). Some tools are *deferred*: found with `discover` and run through `executeRead`, `executeWrite` or `executeDestructive` | [Supported tools](https://support.atlassian.com/atlassian-rovo-mcp-server/docs/supported-tools/), [developer guide](https://developer.atlassian.com/cloud/rovo-mcp/guides/supported-tools/) |
| v1 names | v1 tool names (e.g. `addCommentToJiraIssue`, `getVisibleJiraProjects`) are not on the current page; use the v2 names below | same |

## Read tools (PROPOSE and FILE)

`searchJiraIssuesUsingJql`, `getJiraIssue`, `getAccessibleAtlassianResources`

All three are *primary* tools, so the run needs neither `discover` nor `executeRead`. Other read tools
(`listJiraProjects`, `listJiraProjectComponents`, `getJiraIssueTypeMetaWithFields`) are deferred and a run does not
need them: the config holds the projects, components and issue types.

## Write tools (FILE only, one approval per call)

`createJiraIssue`, `addOrEditJiraIssueComment`

- `addOrEditJiraIssueComment` can also **edit** an existing comment. Show the arguments in the approval prompt.
- **Deny `executeWrite` and `executeDestructive` in both phases.** They run deferred write tools by name, so an
  allow- or deny-list of named tools does not cover what they can reach. Whether denying them closes every route is
  not stated in the docs.
- Never allow `editJiraIssue` or `transitionJiraIssue`: the skill only creates and comments.
- The server spans Confluence, Jira Service Management and other products. Give this skill's identity Jira only, and
  ask the admin to leave `delete_jira` and `manage_jira` off.

## Config block

```yaml
jira:
  cloud_id: "00000000-0000-4000-8000-0000000000d1"   # from getAccessibleAtlassianResources, once, at setup
  projects: [{key: "ENG", name: "Engineering", use_for: "backend and infrastructure"}]
  issue_types: ["Task", "Bug"]          # names as the project uses them
  components: [{name: "Billing", id: "10001", project: "ENG"}]   # optional
  labels: ["meeting-action"]            # Jira creates any label it is given; only these
  priorities: ["Highest", "High", "Medium", "Low"]   # the site's priority names
  people: [{name: "Alex Example", account_id: "000000:00000000-0000-4000-8000-0000000000c1", aliases: ["Alex"]}]
  default_assignee: null
```

## Card categorisation lines

```text
*Project:* <project key from config> - <why>
*Issue type:* <from config>
*Components:* <from config, or none>
*Labels:* <from config, or none>
*Priority:* <a config priority with the words that set it, or "none">
*Assignee:* <only someone the meeting named, else none>
```

## Calls

| Step | Call |
|---|---|
| Search (both phases) | `searchJiraIssuesUsingJql` with JQL pinned to the project, e.g. `project = ENG AND text ~ "<topic>" ORDER BY created DESC`, one page. Quote the topic as JQL text; never paste meeting text into JQL unescaped |
| Create | `createJiraIssue` with the config's cloud id, project key, issue type, summary, description, and assignee account id, priority, labels and components only if on the card |
| Comment on a duplicate | `addOrEditJiraIssueComment` on the existing key, new comment only |
| Issue key in state | the key, e.g. `ENG-123` |

**`createJiraIssue`'s parameters are not documented** (unconfirmed, 24 Nov 2026). Read the tool's input schema
before the first create. If an approved field (priority, labels, components) has no place in it, file without it,
record that in the state file and report `detail=fields-dropped`. Never follow up with `editJiraIssue`.

## Read the response

The create response must carry the new key. Then read it back once with `getJiraIssue` and compare the approved
fields. A mismatch is recorded and reported, never fixed with a second write.

## Fallback without MCP

Jira Cloud REST v3, per the [API reference](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/)
(read 24 Nov 2026): `POST /rest/api/3/search/jql` (read; the older `/search` is being removed),
`POST /rest/api/3/issue` (write; `description` is Atlassian Document Format), and
`POST /rest/api/3/issue/{key}/comment` (write; body in ADF). A shell route cannot be split by tool name, so PROPOSE
must run with a token that cannot create issues or comments.
