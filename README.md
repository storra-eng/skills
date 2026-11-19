# skills

Agent skills from Storra. Currently one: **ActionsToIssues**, which turns new **Granola** meeting notes into **Linear**
issues, with **a human approval for every issue**.

It is a skill (instructions plus one script), not a service. It runs in [OpenClaw](https://docs.openclaw.ai) and Claude
Code, and follows the [Agent Skills](https://agentskills.io) layout.

> **Read before installing.** It reads text other people wrote (transcripts) and can write to a shared tracker, so
> prompt injection is the main risk. The skill states an approval rule; **it cannot enforce it.** Whether a human
> approval really gates Linear writes depends on your host. See [Is the approval enforced?](#is-the-approval-enforced).

## What it does

- Finds meetings not yet handled, with a zero-token pre-check so an idle day costs almost nothing.
- Filters to company business, then applies a **New-work test** (new, decided, durable): a standup usually yields no
  issues.
- Proposes each item as its own **approval card**: title, source, verbatim quote, tracker search result, and the
  project, labels, priority and assignee it would use.
- After a human approves, re-searches Linear, then files the issue or comments on an existing one.
- Records what it handled in a state file, so nothing is proposed twice.

```text
 scheduler -> granola_precheck.py -> idle? --yes--> stop (zero tokens)
                    | no, or cannot tell
                    v
        PROPOSE run (read-only tools)
   Granola > scope filter > New-work test > Linear search > card per item
                    |
                    v  posted to chat (e.g. Slack)
        a human approves or rejects each card      <-- enforced by the HOST
                    | approved
                    v
        FILE run (write tools, approved items only)
   re-search Linear > create issue / comment on duplicate > update state
```

Two phases with two tool sets is the core design: PROPOSE needs read-only access, and only FILE needs Linear write
tools, started only after the host has recorded an approval.

## Requirements

| Need | Detail |
|---|---|
| Granola | Account with its MCP server connected to your agent host (`https://mcp.granola.ai/mcp`) |
| Linear | Workspace with its MCP server connected (`https://mcp.linear.app/mcp`) |
| Approvals | A chat surface for cards (built around Slack) and a way for a human to approve |
| Python | 3.9+ for the pre-check, standard library only |

## Install

| Host | How |
|---|---|
| Claude Code | Copy `skills/ActionsToIssues` into `.claude/skills/` or `~/.claude/skills/`; keep Linear write tools on **ask** or **deny**. See [`docs/claude-code.md`](docs/claude-code.md) |
| OpenClaw | `openclaw skills install @<publisher>/actions-to-issues` once published, or copy the folder into `<workspace>/skills/`. See [`docs/openclaw.md`](docs/openclaw.md) |

Installing does **not** configure approvals.

## Configure

1. Copy [`config.example.yaml`](skills/ActionsToIssues/config.example.yaml) somewhere private and fill it in: team,
   allowed projects, labels and people (with ids), company email domains, caps. The skill invents none of these.
2. Set the environment:

   | Variable | Required | Meaning |
   |---|---|---|
   | `MN2L_CONFIG` | yes | Path to your config |
   | `MN2L_STATE` | yes | Path of the state file (created on first run) |
   | `GRANOLA_ACCESS_TOKEN` or `MCP_AUTH_FILE` | for the pre-check | Bearer token, or a JSON auth file. No default path |

3. Run the [pre-check](docs/precheck.md) from your scheduler and start the agent unless it exits `0`.

## Is the approval enforced?

| Setup | Enforced? |
|---|---|
| **Reference pattern**: a dispatcher outside the model starts it without Linear write tools, starts a separate run with them only after an approval store records a decision, then audits | **Yes.** The model never holds the tool |
| OpenClaw, skill installed, nothing else | **No.** A prompt rule |
| OpenClaw with the tool split and authorised-approver setup in [`docs/openclaw.md`](docs/openclaw.md) | **Partly.** Not verified on a live install |
| OpenClaw plus a `before_tool_call` plugin using `requireApproval` | **Yes, per call**, if it can match the Linear tools (docs do not confirm) |
| Claude Code, Linear write tools on `ask` ([permissions](https://code.claude.com/docs/en/permissions)) | **Yes, interactively.** Headless, an unanswered `ask` is not an approval |
| Anything else | Assume a prompt rule until tested |

**Test it:** in the PROPOSE setup, ask the agent to create a Linear issue. If it can, you have no gate.

## Threat model

- **Untrusted input.** Anyone quoted in a transcribed meeting can try to instruct the model. The skill treats meeting
  text as data; that is a mitigation, not a defence. Design so the worst case is a rejected card.
- **The gate is the host's job.** See the table above.
- **The approver is attack surface.** Cards quote meeting text verbatim.
- **Data exposure.** The Granola account may see a whole calendar; the scope filter is also a prompt rule.

Full version and hardening steps: [`docs/threat-model.md`](docs/threat-model.md).

## Layout

| Path | What |
|---|---|
| `skills/ActionsToIssues/` | The skill; copy this folder as-is |
| `skills/ActionsToIssues/SKILL.md`, `config.example.yaml`, `reference/` | Instructions, config template, policy and formats |
| `skills/ActionsToIssues/scripts/` | Zero-token pre-check and its reply parser |
| `docs/` | Threat model, pre-check, OpenClaw and Claude Code notes |
| `tests/` | Unit and loopback tests, synthetic data only |

## Related projects

Licences and activity as seen on GitHub on 18 November 2026; check before relying on them.

| Project | What it is | Difference |
|---|---|---|
| [OneWave-AI/claude-skills](https://github.com/OneWave-AI/claude-skills) `meeting-to-tasks` (MIT) | Claude Code skill: transcript to action items and Linear / GitHub task files | Captures more and flags low confidence; this skill files less, reads Granola directly, and gates every issue on an approval |
| [franzvill/action-sync](https://github.com/franzvill/action-sync) (MIT) | App: transcript to Jira tickets, with repo context | Jira, pasted transcripts; last pushed March 2026 |
| [Granola MCP](https://docs.granola.ai/help-center/sharing/integrations/mcp) | The server this skill reads from | Not replaced by this skill |

## Acknowledgements

- The [Agent Skills](https://agentskills.io) format ([spec](https://github.com/agentskills/agentskills), Apache-2.0).
- [OpenClaw](https://docs.openclaw.ai) and ClawHub.
- [Granola](https://www.granola.ai) and [Linear](https://linear.app). Not affiliated with or endorsed by either.

## Contributing and licence

See [`CONTRIBUTING.md`](CONTRIBUTING.md). MIT, see [`LICENSE`](LICENSE). Derived from an internal meeting-triage
assistant; only the generic policy and pre-check were carried over, with no deployment machinery, tracker data or real
meeting content. OpenClaw statements come from its public docs as read on 9 October 2026 (linked in
[`docs/openclaw.md`](docs/openclaw.md)); verify them against your install.
