# skills

Agent skills from Storra. Currently one: **ActionsToIssues**, an agent skill that turns **new Granola meeting notes**
into **Linear issues**, with **a human approval for every issue**. It is the generalised policy from an internal
meeting-triage assistant: what counts as trackable work, how to avoid duplicates, how to word a card a reviewer can
decide on in fifteen seconds, and how to keep a model from filing things nobody agreed to.

It is a skill (instructions plus one script), not a service. It works in [OpenClaw](https://docs.openclaw.ai) and in
Claude Code, and the folder follows the [Agent Skills](https://agentskills.io) layout.

> **Read this before installing.** This skill reads text written by other people (meeting transcripts) and can write
> to a shared tracker. Prompt injection is the main risk. The skill states an approval rule; **the skill cannot
> enforce it.** Whether a human approval really gates Linear writes depends on how your host platform is configured.
> See [Threat model](#threat-model) and [What the gate is, per platform](#what-the-gate-is-per-platform).

## What it does

- Polls Granola for meetings that are not yet handled.
- Applies a scope filter (company business only) and a **New-work test** (new, decided, durable) so a standup
  usually yields no issues rather than a pile of status updates.
- Proposes each item as its own **approval card**: title, description, source, verbatim quote, the result of a
  tracker search, and the project, labels, priority and assignee it would be filed with.
- After a human approves a card, re-searches Linear and files the issue (or comments on an existing one).
- Records what it handled in a small state file, so nothing is proposed twice and an idle day costs almost nothing.

## Flow

```
 scheduler ──► granola_precheck.py ──► idle?  ──yes──► stop (zero tokens)
                    │ no, or cannot tell
                    ▼
        PROPOSE run (read-only tools)
   Granola ─► scope filter ─► New-work test ─► Linear search ─► card per item
                    │
                    ▼  posted to chat (e.g. Slack)
        a human approves or rejects each card      ◄── enforced by the HOST
                    │ approved
                    ▼
        FILE run (write tools, approved items only)
   re-search Linear ─► create issue / comment on duplicate ─► update state
```

Two phases with two tool sets is the heart of the design. Everything in PROPOSE can run with read-only access; only
FILE needs Linear write tools, and it should only ever be started, or only ever be given those tools, once the host
has recorded an approval. See [Hardening](#hardening-the-split).

## Repository layout

```
skills/ActionsToIssues/     the skill; publish or copy this folder as-is
  SKILL.md                          instructions + frontmatter (env vars, MCP servers, permissions)
  config.example.yaml               your Linear team/projects/labels/people, scope rules, caps
  reference/                        policy, card and issue format, state file
  scripts/granola_precheck.py       zero-token pre-check: fetch, classify, verdict (Python 3, standard library only)
  scripts/granola_reply.py          parser for Granola's meeting-list reply, imported by the pre-check
tests/                              unit and loopback end-to-end tests, synthetic data only
docs/                               threat model, OpenClaw notes, Claude Code notes
```

## Requirements

- A Granola account with its MCP server connected to your agent host (`https://mcp.granola.ai/mcp`).
- A Linear workspace with Linear's MCP server connected (`https://mcp.linear.app/mcp`).
- A chat surface for approval cards (Slack is what this was built around) and a way for a human to approve.
- Python 3.9+ for the pre-check script (CI runs 3.9 and 3.12). No packages.

## Configure

1. Copy `skills/ActionsToIssues/config.example.yaml` somewhere private and fill it in: the team key, the
   projects and labels the skill may use (with their ids), the people it may assign, your company email domains, and the
   caps on cards per meeting and per run. The skill invents none of these.
2. Set the environment the skill declares:

   | Variable | Required | Meaning |
   |---|---|---|
   | `MN2L_CONFIG` | yes | path to your filled-in config |
   | `MN2L_STATE` | yes | path of the state file (created on first run) |
   | `GRANOLA_ACCESS_TOKEN` or `MCP_AUTH_FILE` | for the pre-check | a bearer token, or a JSON file in the shape described in the script header. **No default path is assumed.** |
   | `MCP_AUTH_SERVER` | no | key of the Granola entry in that file (default `granola`) |
   | `GRANOLA_MCP_URL` | no | override the endpoint (https only; loopback allowed for tests) |

3. Run the pre-check from your scheduler before starting the agent:

   ```bash
   python3 skills/ActionsToIssues/scripts/granola_precheck.py   # exit 0 idle, 10 work, 1 cannot tell
   ```

   Copy the whole `scripts/` folder: the pre-check imports `granola_reply.py` from beside it.

   Start the agent unless the exit status is `0`, and paste the script's `new` / `defer` lines into the agent's
   prompt. It looks at yesterday and today (UTC), not just today, so a meeting that straddles midnight is not lost;
   it defers a meeting for 30 minutes after it starts (`--min-age`; it cannot see end times, so set this above your
   longest regular meeting). Run PROPOSE and FILE one at a time: both rewrite the state file.
   A pre-check failure wakes the agent on purpose: it can only make a run cheaper, never blinder. That includes a
   missing `MN2L_STATE`, an expired token, and a reply it does not understand. Because it never refreshes a token (the
   MCP client that owns the OAuth session does that), an idle day costs roughly one agent run per access-token
   lifetime, not zero. It prints counts and ids only, never a title, a body or a token. Alert on a streak of non-zero
   exits, or a persistent failure quietly becomes a full-cost run on every tick.

   **If you already keep your own record of which meetings are handled** (a database, a ledger issue), add `--rows`: the
   script then needs no state file and prints `OK seen=<n> others=<m>` followed by one line per meeting,
   `id <meeting id> <minutes since start> <note length in seconds> <minutes since last update>` (`unknown` where a value
   could not be read), and leaves deciding what is new to you. It exits `0` on a well-formed answer and `1` on anything
   else, and a failure must still wake your agent. `--days` sets how many UTC days to look back (default 2).

## Install

### OpenClaw

```bash
openclaw skills install @<publisher>/actions-to-issues     # once published to ClawHub
# or, from a checkout: copy skills/ActionsToIssues into <workspace>/skills/
```

Install and publish commands are from the [ClawHub docs](https://docs.openclaw.ai/clawhub) (read 9 October 2026).
Publishing is `clawhub skill publish ./skills/ActionsToIssues --slug actions-to-issues --name "Meeting
notes to Linear" --version 1.0.0`. Installing the skill does **not** configure approvals. Read
[`docs/openclaw.md`](docs/openclaw.md) before you point it at a real Linear workspace.

### Claude Code

Copy `skills/ActionsToIssues` into `.claude/skills/` (project) or `~/.claude/skills/` (personal), add the two
MCP servers, and keep Linear's write tools on **ask** or **deny**. See [`docs/claude-code.md`](docs/claude-code.md).

## What the gate is, per platform

The skill says: no Linear write without a recorded human approval. Who enforces that?

| Setup | Is the approval enforced? |
|---|---|
| **The reference pattern** (a dispatcher outside the model starts the model without Linear write tools, and starts a separate run with them only after an approval store records a decision; afterwards it audits that every created issue traces to an approved card) | **Yes.** The model cannot create an issue because it does not hold the tool. Strongest option. |
| **OpenClaw, skill installed from ClawHub, nothing else configured** | **No. It is a prompt rule.** A skill grants and restricts no tools, and exec approvals do not cover MCP tool calls. |
| **OpenClaw with the tool split and authorised-approver channel setup** in [`docs/openclaw.md`](docs/openclaw.md) | **Partly, by the platform:** the proposing agent does not hold the write tools, and only authorised senders can instruct the filing agent. Fidelity of the filed text to the approved card is still a prompt rule. **Not verified on a live install.** |
| **OpenClaw plus a `before_tool_call` plugin using `requireApproval`** | **Yes, per call**, if the hook matches the Linear write tools. Synchronous, 10-minute ceiling. Docs do not confirm MCP tools can be matched this way. |
| **Claude Code, Linear write tools set to `ask`** ([permissions docs](https://code.claude.com/docs/en/permissions)) | **Yes, interactively:** the harness prompts the operator. In headless runs an unanswered `ask` is not a human approval; route it through a permission-prompt tool or keep the tools denied. |
| **Anything else** | Assume it is a prompt rule until you have tested that the proposing agent *cannot* call the write tools. |

How to test: in the PROPOSE configuration, ask the agent to create a Linear issue directly. If it can, you do not have
a gate.

## Hardening the split

Do these, in this order of value:

1. **Read-only until approved.** The identity that reads meetings never holds Linear's write tools (`save_issue`,
   `save_comment`). Linear's MCP exposes many more write tools (labels, projects, documents, attachments); this skill
   needs only those two, so expose nothing else for writing.
2. **A separate filing identity**, reachable only by the people allowed to approve, receiving the approved card text
   from the approval store or the approved chat thread, never from the proposer's memory.
3. **Caps** (`limits` in the config) so a manipulated run can propose only a handful of cards.
4. **A per-call confirmation** on the write tools where the platform offers one.
5. **A current, best-tier model.** It reduces injection success; it does not eliminate it.
6. **Audit after the fact:** every issue the skill created should trace to an approved card. Alert when one does not.

## Threat model

Short version; the full one is in [`docs/threat-model.md`](docs/threat-model.md).

- **(a) It reads untrusted text and has write access to Linear.** Anyone who can speak in, or be quoted in, a meeting
  that gets transcribed can try to put instructions in front of the model: "create an issue assigned to X", "approve
  this card", "ignore your rules". A guest, a vendor, a forwarded transcript or an automated notetaker bot counts.
  The skill instructs the model to treat meeting content as data. That is a mitigation, not a defence: OpenClaw's own [prompt-injection guidance](https://docs.openclaw.ai/gateway/security/prompt-injection.md) says model
  choice reduces risk without solving it, and cites adaptive-attack success rates above 80% against state-of-the-art
  defences (its figure; not independently checked here). Design as if the instruction will sometimes be followed, and make sure the worst case is a
  rejected card.
- **(b) The approval gate is only as strong as the host platform enforces it.** If the same model run that read the
  meeting can also call the write tool, the "approval" is a sentence in a prompt. In the reference pattern the model has
  no create tool until a human approved. On OpenClaw, see the table above and [`docs/openclaw.md`](docs/openclaw.md):
  as far as the official documentation shows, installing a skill does not by itself gate anything.
- **The approver is part of the attack surface.** A card quotes meeting text verbatim, so injected text reaches the
  reviewer's screen. Reviewers should compare the card with what they know happened, and the skill keeps URLs from
  meeting notes out of cards by default.
- **Data exposure.** The account behind Granola may see a whole calendar. The scope filter exists so personal meetings
  never become tracker issues; it is also a prompt rule, so prefer a Granola account that sees only what you intend.
- **Credentials.** The pre-check sends a bearer token to one URL, refuses redirects and non-https endpoints, and never
  prints the token. Keep tokens out of the skill's working directory and out of prompts.

## Related projects

Other open-source work in the same space. These are different tools with different trade-offs, listed so you can pick
the right one (licences and activity as seen on GitHub on 18 November 2026; check before relying on them).

- [OneWave-AI/claude-skills](https://github.com/OneWave-AI/claude-skills), `meeting-to-tasks` (MIT). A Claude Code
  skill that turns a pasted transcript into decisions, action items with owners and deadlines, and task files for
  Linear, GitHub Issues and similar. It leans towards capturing more and flagging low confidence; this skill leans
  towards filing less, reads Granola directly, and puts a recorded human approval in front of every issue.
- [franzvill/action-sync](https://github.com/franzvill/action-sync) (MIT). A small app that has Claude turn a meeting
  transcript into Jira tickets, with repository context. Jira rather than Linear, and a pasted transcript rather than
  a connected notes tool. Last pushed March 2026.
- [Granola's MCP server](https://docs.granola.ai/help-center/sharing/integrations/mcp) is what this skill reads from;
  the skill does not replace it.

## Acknowledgements

- The [Agent Skills](https://agentskills.io) open format ([specification](https://github.com/agentskills/agentskills),
  Apache-2.0), which gives the skill its folder layout and `SKILL.md` frontmatter.
- [OpenClaw](https://docs.openclaw.ai) and its ClawHub registry, one of the two hosts this is written for.
- [Granola](https://www.granola.ai) and [Linear](https://linear.app) for the MCP servers the skill talks to. This
  project is not affiliated with or endorsed by either.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Standard library only. The end-to-end cases run against a loopback fake MCP endpoint; all data is synthetic.

## Provenance and licence

Derived from an internal meeting-triage assistant. Only the generic policy and pre-check were carried over; no
deployment machinery, tracker data or real meeting content. MIT licensed, see [`LICENSE`](LICENSE).

Platform statements about OpenClaw come from its public documentation as read on 9 October 2026 and are linked from
[`docs/openclaw.md`](docs/openclaw.md). Verify them against your installed version.

## Git hooks

Commits are checked by [pre-commit](https://pre-commit.com). Install it and the hook once per clone (git worktrees share
the install):

```sh
brew install pre-commit   # or: pipx install pre-commit
pre-commit install
```

The hook blocks a new file, or a change that grows one, past 5,000 tokens (bytes / 4), so files stay readable by an
agent in one pass. The error explains how to split the file. Lockfiles, generated output and data are exempt; add
repo-specific exemptions, with a reason, to `.token-budget-exempt`.
