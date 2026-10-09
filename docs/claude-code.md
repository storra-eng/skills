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

Claude Code's permission system is enforced by the harness, not by the model, which makes it a real gate. Rules are
`mcp__<server>__<tool>` (with the server names above). Two facts shape the setup: **`deny` always beats `allow`**, and a
tool that needs a prompt in a non-interactive run is refused because nobody can answer it. So keep **two settings
files** and pass the right one to each kind of run with `--settings` (check the flag on your version), rather than one
shared `.claude/settings.json`.

**`proposer.settings.json`** - for every scheduled or headless PROPOSE run. Allow the read tools by name and deny the
Linear write surface, so the run cannot write whatever the model is told:

```json
{
  "permissions": {
    "allow": [
      "mcp__granola__list_meetings", "mcp__granola__get_meetings", "mcp__granola__get_meeting_transcript",
      "mcp__linear__list_issues", "mcp__linear__get_issue", "mcp__linear__list_projects",
      "mcp__linear__list_issue_labels", "mcp__linear__list_users", "mcp__linear__list_teams"
    ],
    "deny": [
      "mcp__linear__save_issue", "mcp__linear__save_comment", "mcp__linear__save_project",
      "mcp__linear__save_milestone", "mcp__linear__save_document", "mcp__linear__save_release",
      "mcp__linear__save_status_update", "mcp__linear__save_issue_label", "mcp__linear__create_issue_label",
      "mcp__linear__create_attachment", "mcp__linear__delete_comment", "mcp__linear__share_issue"
    ]
  }
}
```

Also allow whichever chat tool posts the cards (for example a Slack send-message tool), and nothing broader.

The deny list is a snapshot: Linear adds tools over time. In a headless run the allow list is what protects you,
because anything not allowed is refused. In an interactive session, unlisted tools prompt; read every prompt.

**`filer.settings.json`** - for the FILE phase only. Allow the same read tools; put the two write tools on `ask`:

```json
{ "permissions": { "ask": ["mcp__linear__save_issue", "mcp__linear__save_comment"] } }
```

- **Run FILE interactively** (an approver at the keyboard, passing the approved cards in the prompt). Each write prompts
  with its arguments, which is a per-issue human approval enforced by the harness. Read the arguments, not the model's
  summary of them.
- **Headless FILE** needs something that answers the prompt with a real decision, such as a permission-prompt tool that
  asks an approver in chat and returns their answer. An auto-answered or unanswered prompt is not a human approval.
  Check that your version supports this before relying on it, and test that a denied prompt files nothing.
- **A per-call equivalent to the plugin approach on OpenClaw:** a `PreToolUse` hook on the two write tools that exits
  non-zero unless the card id in the call appears in an approved-ids file written by something other than the model
  (for example a chat handler run by a person). This repository does not ship one.
- Do not list the write tools in the skill's `allowed-tools`, and do not add an "always allow" rule for them:
  pre-approving removes the prompt.

## Scheduling

Run `scripts/granola_precheck.py` from cron or launchd first; start `claude -p --settings proposer.settings.json` only
when it exits with anything other than `0`. Count consecutive non-zero exits and alert on a streak: the pre-check fails
open by design, so a persistent failure silently becomes a full-cost run every tick. Launch the FILE phase as a separate
invocation with `filer.settings.json`, after an approval, passing the approved card text in the prompt.
