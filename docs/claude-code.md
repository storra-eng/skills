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

Sources, read on **9 October 2026**: [Permissions](https://code.claude.com/docs/en/permissions) and
[CLI reference](https://code.claude.com/docs/en/cli-reference). Flag availability varies by version; check yours.

What the docs say, and what this setup relies on:

- "Permission rules are enforced by Claude Code, not by the model." That is what makes them a gate where a prompt
  rule is not.
- Rules are evaluated **deny, then ask, then allow**; an allow rule cannot carve an exception out of a deny rule.
- MCP tools are `mcp__<server>__<tool>`; `mcp__<server>__*` matches every tool of a server.
- `--settings <file or JSON>` layers extra settings over the normal files for one run.
- `--permission-prompt-tool <mcp tool>` answers permission prompts in non-interactive mode, and
  `--permission-prompts none` makes unanswerable prompts deny instead.
- `PreToolUse` hooks can inspect a call before it runs, but they do not override deny or ask rules.

So keep **two settings files** and pass the right one to each kind of run with `--settings`, rather than one shared
`.claude/settings.json` (a `deny` there would also block the FILE phase). Replace the paths and server names with
yours. Note the **double** leading slash in file rules: per the permissions docs a single leading slash is relative to the
settings source, and `//path` is how an absolute path is written.

**`proposer.settings.json`** - every scheduled or headless PROPOSE run. Allow the read tools and the state file by
name, deny the Linear write surface:

```json
{
  "permissions": {
    "allow": [
      "mcp__granola__list_meetings", "mcp__granola__get_meetings", "mcp__granola__get_meeting_transcript",
      "mcp__linear__list_issues", "mcp__linear__get_issue", "mcp__linear__list_projects",
      "mcp__linear__list_issue_labels", "mcp__linear__list_users", "mcp__linear__list_teams",
      "Read(//path/to/config.yaml)", "Read(//path/to/state.json)", "Edit(//path/to/state.json)"
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

Also allow whichever tool posts the cards (for example a Slack send-message tool), and nothing broader. Run it with
`--permission-prompts none` so any prompt is a denial. The deny list is a snapshot, since Linear adds tools over time:
in an unattended run the allow list is what protects you, because anything not allowed is refused.

**`filer.settings.json`** - the FILE phase only. The same read and state-file allows, plus the two write tools on `ask`:

```json
{
  "permissions": {
    "allow": [
      "mcp__linear__list_issues", "mcp__linear__get_issue", "mcp__linear__list_projects",
      "mcp__linear__list_issue_labels", "mcp__linear__list_users", "mcp__linear__list_teams",
      "Read(//path/to/config.yaml)", "Read(//path/to/state.json)", "Edit(//path/to/state.json)"
    ],
    "ask": ["mcp__linear__save_issue", "mcp__linear__save_comment"]
  }
}
```

- **Run FILE interactively** (an approver at the keyboard, approved cards in the prompt). Each write prompts with its
  arguments, which is a per-issue human approval enforced by the harness. Read the arguments, not the model's summary.
- **Headless FILE** needs something that answers the prompt with a real decision: `--permission-prompt-tool` pointing at
  an MCP tool that asks an approver in chat and returns their answer. An auto-answered prompt is not a human approval.
  Test that a denied prompt files nothing.
- **A per-call equivalent to the plugin approach on OpenClaw:** a `PreToolUse` hook on the two write tools that exits
  non-zero unless the card id in the call appears in an approved-ids file written by something other than the model
  (for example a chat handler run by a person). This repository does not ship one.
- Do not list the write tools in the skill's `allowed-tools`, and do not add an "always allow" rule for them:
  pre-approving removes the prompt.

## Scheduling

Run `scripts/granola_precheck.py` from cron or launchd first.

1. **Exit 0**: stop. **Anything else**: start the agent. The pre-check fails open by design.
2. **Pass its output into the prompt.** The `new <id>` and `defer <id>` lines are how the agent learns which meetings
   to leave alone for now; without them it re-lists Granola and may judge a half-finished meeting.
   ```bash
   out=$(python3 skills/meeting-notes-to-linear/scripts/granola_precheck.py); rc=$?
   [ "$rc" -eq 0 ] && exit 0
   claude -p --settings proposer.settings.json --permission-prompts none \
     "Run the meeting-notes-to-linear PROPOSE phase. Pre-check output:
   $out"
   ```
3. **Serialise runs** with a lock (`flock` or equivalent): PROPOSE and FILE both read and rewrite the state file.
4. **Alert on a streak** of consecutive non-zero pre-check exits. A persistent failure (an expired token nothing
   refreshes, a changed reply shape) otherwise silently becomes a full-cost run every tick.
5. Launch the FILE phase as a separate invocation with `filer.settings.json`, after an approval, passing the approved
   card text and approval id in the prompt.
