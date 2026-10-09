# Running in Claude Code

## Install

```bash
mkdir -p .claude/skills && cp -R skills/meeting-notes-to-linear .claude/skills/     # project
# or ~/.claude/skills/meeting-notes-to-linear for every project
```

Add the MCP servers (names are yours to choose; the permission rules below use them):

```bash
claude mcp add --transport http granola https://mcp.granola.ai/mcp
claude mcp add --transport http linear  https://mcp.linear.app/mcp
```

Authenticate each from inside Claude Code (`/mcp`). Set `MN2L_CONFIG` and `MN2L_STATE` in the environment of the
session.

## The gate in Claude Code

Claude Code's permission system is enforced by the harness, not by the model, which makes it a real gate for
interactive use. Leave Linear's write tools out of `allowed-tools` and any "always allow" rule, and put them on `ask`
or `deny` in `.claude/settings.json` (tool names follow `mcp__<server>__<tool>`, so with the server names above):

```json
{
  "permissions": {
    "ask":  ["mcp__linear__save_issue", "mcp__linear__save_comment"],
    "deny": ["mcp__linear__create_issue_label", "mcp__linear__save_document", "mcp__linear__save_project"]
  }
}
```

- **Interactive use:** every write prompts you, showing the arguments. That is a per-issue human approval enforced by
  the harness. Read the arguments, not the model's summary of them.
- **Proposing sessions (scheduled or headless):** use `deny` for the two write tools. A non-interactive run cannot
  answer an `ask`, and an unanswered or auto-answered prompt is not a human approval. If you want approvals from a chat
  app, route them with a permission-prompt tool that asks an approver and returns their decision, and check that your
  version behaves this way before relying on it.
- **A per-call equivalent to the plugin approach on OpenClaw:** a `PreToolUse` hook on the two write tools that exits
  non-zero unless the card id in the call appears in an approved-ids file written by something other than the model
  (for example a Slack handler run by a person). This repository does not ship one.
- Do not list the write tools in the skill's `allowed-tools`; pre-approving them removes the prompt.

## Scheduling

Run `scripts/granola_precheck.py` from cron or launchd first; start `claude -p` only when it exits with anything other
than `0`. Keep the headless run's permissions to read-only tools plus the chat tool, and start the FILE phase as a
separate invocation that you launch after an approval, passing the approved card text in the prompt.
