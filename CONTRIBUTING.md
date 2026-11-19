# Contributing

Issues and pull requests are welcome.

## Rules

| Rule | Why |
|---|---|
| **Keep it generic.** No real meeting content, names, emails, ids, tokens or tracker data, in code, tests, docs or commits. Synthetic test data only | The repo is public-ready |
| **Standard library only**, Python 3.9+ | No install step for users |
| **The pre-check fails open.** Any answer that is not positive, parsed and consistent must wake the agent. A change that weakens this needs a test that fails without it | An idle day must never hide a failure |
| **Cite platform claims.** Link the public docs and date it; if the docs do not say, say so | Avoid implying behaviour nobody confirmed |
| **Private security reports** via GitHub's "Report a vulnerability" | Not in public issues |

## Set up

```bash
python3 -m unittest discover -s tests -v   # tests (loopback fake MCP endpoint, synthetic data)
brew install pre-commit                    # or: pipx install pre-commit
pre-commit install                         # once per clone; worktrees share it
```

## Git hook

- Blocks a new file, or a change that grows one, past 5,000 tokens (bytes / 4), so an agent can read each file in one pass.
- The error explains how to split the file.
- Lockfiles, generated output and data are exempt; add other exemptions, with a reason, to `.token-budget-exempt`.

## Skill quality (Tessl)

The `tessl` workflow runs on pull requests that touch `skills/actions-to-issues/`.

| Step | What it does | Fails the PR when |
|---|---|---|
| Lint | Validates the plugin and `SKILL.md` | The skill is invalid |
| Review | Scores the skill 0-100 (validation, description, content) | Score is under `TESSL_REVIEW_THRESHOLD` (default 80) |
| Evals | Runs an agent on the scenarios in `skills/actions-to-issues/evals/`, with and without the skill, and scores each against its checklist | The run fails; the with/without scores are in the job summary |

Without the secret and variable below (and on fork PRs, which get no secrets) the job passes with a notice.

Maintainer setup, once:

```bash
tessl login
```

```bash
tessl api-key create --workspace <workspace> --name ci --ttl 1y
```

```bash
gh secret set TESSL_TOKEN -R storra-eng/skills
```

```bash
gh variable set TESSL_WORKSPACE -R storra-eng/skills --body <workspace>
```

Then set the workspace in `skills/actions-to-issues/.tessl-plugin/plugin.json` (`name` is `<workspace>/actions-to-issues`).
API keys expire (30 days unless you pass `--ttl` or `--expiry-date`); renew before then or the check fails.

Run locally:

```bash
tessl review run skills/actions-to-issues --workspace <workspace>
tessl eval run skills/actions-to-issues
```

Evals cost model runs. Add a scenario as `evals/scenario-N-<name>/` with `task.md` and `criteria.json`
([format](https://docs.tessl.io/improving-your-skills/evaluate-skill-quality-using-scenarios.md)); use synthetic data only.
