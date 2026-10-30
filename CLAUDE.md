# skills

Storra's open-source agent skills. The first, `ActionsToIssues`, is a standalone skill that turns new Granola meeting
notes into Linear issues, one human approval per issue. It ships policy (the skill), a zero-token pre-check script and
tests. It does **not** ship an approval mechanism, a scheduler or a chat bridge - those belong to the host platform, and
the README is explicit about what that means for security.

## Agent instructions

`CLAUDE.md` is this repository's canonical agent-instructions file. `AGENTS.md` is a symlink to it, never a second
copy.

## Rules for this repo

- **Public-ready from day one.** Never commit real meeting content, names, emails, Granola ids, tokens, workspace ids
  or anything from a private tracker. Tests use synthetic data only.
- **Never write the specifics of an unpatched vulnerability** in any file here. The threat model describes classes of
  risk and mitigations, not exploits.
- **Claims about third-party platforms must be sourced** (link the official docs) and dated. If a behaviour could not
  be confirmed in the docs, say so rather than implying it works.
- The skill folder `skills/ActionsToIssues/` must stay self-contained so it can be published as-is
  (`clawhub skill publish`) or copied into `.claude/skills/`.
- British English in docs, written for an international audience. Files end with a newline.
- When a repository's documentation and its existing code disagree, follow the conventions in the existing code for the task in hand, then sort each inconsistency out rather than only reporting it (Ed, 30 Oct 2026). For each one, ask Ed how to proceed - one AskUserQuestion question per inconsistency, naming the doc and the code that disagree, with the options (fix the doc to match the code, change the code to match the doc, or leave it) and your recommendation first - then carry out the answer in the same session. Fix one yourself without asking only when the doc is plainly stale (it names a file, flag or value the code has since replaced) and the fix is to the doc alone. In your final reply, list each inconsistency and what was done about it.

## Checks

```bash
python3 -m unittest discover -s tests -v
```

Standard library only; no install step.
