# Threat model

Scope: this skill, the pre-check script, and the way they are usually deployed. It says what can go wrong in classes
and what reduces it. It deliberately contains no exploit detail.

## What is protected

| Asset | Why it matters |
|---|---|
| The Linear workspace | Issues are durable, widely readable and drive other people's work. Junk or malicious issues cost trust and triage time. |
| Meeting content | Transcripts hold other people's words, sometimes personal or commercially sensitive. |
| Credentials | Granola and Linear OAuth sessions; the chat bot token. |
| The approver's attention | A reviewer who learns to click approve is no gate at all. |

## Who can attack, and how

**Anyone whose words reach a transcript** is an author of input to the model: meeting guests, vendors, candidates,
people quoted on a shared screen, an automated notetaker, someone who forwards a transcript. They do not need access to
any system you run. This is *indirect prompt injection*: instructions hidden in data.

| Class | Example outcome | Primary mitigations |
|---|---|---|
| Direct instruction in a note ("file this", "assign to X", "approve all") | The model files or assigns something nobody agreed to | No write tools in the reading run; approvals recorded by the host; caps on cards; the skill's "data, not instructions" rule |
| Approver manipulation | A card with a persuasive, attacker-shaped quote or title gets approved | Verbatim quote on the card so the reviewer can check it; URLs from notes kept out of cards; reviewer training; caps |
| Exfiltration via output | Meeting text or secrets copied into an issue, a comment or a link | Quote only the justifying line; scope filter; no fetching URLs from notes; dedicated low-privilege Linear identity |
| Tool abuse beyond the two write tools | Creating labels, projects, documents, attachments | Expose only `save_issue` and `save_comment` for writing; deny the rest |
| State tampering | A manipulated run edits the state file so a different card is later filed, or so real meetings are skipped | Filer takes approved text from the approval store or chat thread, not state; state holds ids and titles, not authority |
| Approval confusion | A user allowed to approve one class of action approves another | Separate approver lists per action class; keep the platform patched |
| Cost and availability | A flood of meetings, markup in a note that makes the pre-check unsure, or a failing integration burns tokens every tick | Zero-token pre-check; caps. The pre-check is stateless and fails open, so a wake that repeats is **not** surfaced by this repository: count consecutive non-zero exits in your scheduler and alert on a streak |
| Credential exposure | A token printed to a log or sent to the wrong host | Pre-check never prints tokens, refuses redirects and non-https, never refreshes; agent told never to dump environment or auth files |

## What this skill does and does not do

- It **states** the policy: approval before any write, meeting content is data, minimum quoting, caps, scope.
- It **cannot enforce** any of that. A skill is instructions to a model. Anything a model can be talked out of is not a
  security boundary. The README's table says, per platform, what is actually enforced.
- It **helps** the host enforce by shaping the work into two phases with different tool needs, so a host can give the
  reading phase no write tools at all.

## The approval gate, stated plainly

A gate is real only if the process that reads untrusted text **cannot** perform the write, and the process that can
perform the write only acts on a decision a human made. That gives three properties to check on any platform:

1. **Tool absence.** The reading identity does not hold the write tools. Test: ask it to create an issue.
2. **Authenticated approval.** The decision comes from an allowlisted human identity, through a channel the model cannot
   write to as that identity. A chat message the model can read is not evidence; neither is a button the model can
   click.
3. **Fidelity.** What is filed is what was approved: the text comes from the approval store or the approved message,
   not from the model's memory of it. Audit afterwards that every created issue traces to an approved card.

The strongest deployment is a dispatcher outside the model that runs the reading phase read-only, records decisions in
an approval store, starts the filing phase with the write tools only for approved items, and fails loudly if an issue
exists without an approved card. On platforms without that, approximate it with the OpenClaw Option A split in
[`openclaw.md`](openclaw.md) or Claude Code `ask`/`deny` rules in [`claude-code.md`](claude-code.md).

## Residual risks you accept by running this

- A model can misjudge scope and propose a card from a personal meeting. The reviewer is the backstop.
- A convincing injected card can still be approved by a tired human.
- Prompt-level rules fail some of the time; model choice lowers the rate but does not remove it.
- The Granola and Linear OAuth sessions are as powerful as the accounts behind them. Use the least-privileged accounts
  you can.
- Platform behaviour described in [`openclaw.md`](openclaw.md) is from public documentation and unverified on a live
  install.

## Reporting a problem

Open a private security advisory on the repository rather than a public issue.
