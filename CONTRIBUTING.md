# Contributing

Issues and pull requests are welcome. Agent rules are in [`CLAUDE.md`](CLAUDE.md).

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

## Landing changes

Maintainers work in a `git gtr` worktree and land straight on the default branch: rebase onto `origin/<default>`, run the
checks above and `/code-review`, then fast-forward push. No pull request. Never commit in the main checkout, never
force-push the default branch, never `--no-verify`. Dependabot and other bot PRs still arrive as PRs; outside
contributors open a PR as usual.

## Git hook

- Blocks a new file, or a change that grows one, past 5,000 tokens (bytes / 4), so an agent can read each file in one pass.
- The error explains how to split the file.
- Lockfiles, generated output and data are exempt; add other exemptions, with a reason, to `.token-budget-exempt`.

## Skill quality (Tessl)

The `tessl` workflow runs on pull requests that touch `skills/actions-to-issues/`.

| Step | What it does | Fails the PR when |
|---|---|---|
| Lint | Validates the plugin and `SKILL.md` | The skill is invalid |
| Review | Scores the skill 0-100 | Score is under `TESSL_REVIEW_THRESHOLD` (default 80) |
| Evals | Runs an agent on `skills/actions-to-issues/evals/` with and without the skill | The run itself fails. Scores are in the job summary and are **informational** |

- No `TESSL_TOKEN` secret or `TESSL_WORKSPACE` variable (and fork or Dependabot PRs, which get no secrets): the job passes
  with a notice and runs nothing. Don't make `tessl` a required check until it is configured.
- Optional variables: `TESSL_REVIEW_THRESHOLD`, `TESSL_EVAL_AGENT`, `TESSL_EVAL_MODEL`.
- A first run scored 76 on review (now 84) and lifted evals from 83% to 98% with the skill. Each eval run costs about
  110 Tessl credits per run; it runs when the skill or the workflow file changes, and on manual dispatch.

Configured for this repo: workspace `storra`, project `storra/skills` (`tessl.json`), secret `TESSL_TOKEN` (key `skills-ci`,
role publisher, expires 19 Nov 2027), variable `TESSL_WORKSPACE`. To rotate the key, from a logged-in machine:

```bash
tessl api-key create --workspace storra --name skills-ci-2 --role publisher --ttl 1y
```

Put the printed key in the `TESSL_TOKEN` secret (`gh secret set TESSL_TOKEN -R storra-eng/skills`), confirm a PR run
passes, then `tessl api-key delete --workspace storra skills-ci`.

Run it locally:

```bash
tessl review run skills/actions-to-issues --workspace storra
tessl eval run skills/actions-to-issues
```

Evals cost model runs. Add a scenario as `evals/scenario-N-<name>/` with `task.md` and `criteria.json`
([format](https://docs.tessl.io/improving-your-skills/evaluate-skill-quality-using-scenarios.md)). Use synthetic data only.
Tools are simulated in the task text: the agent writes `CALL <tool> <args>` lines, so the criteria can check them.
