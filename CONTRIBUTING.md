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
| Review | Scores the skill 0-100 | Score is under `TESSL_REVIEW_THRESHOLD` (default 80) |
| Evals | Runs an agent on `skills/actions-to-issues/evals/` with and without the skill | The run itself fails. Scores are in the job summary and are **informational** |

- No `TESSL_TOKEN` secret or `TESSL_WORKSPACE` variable (and fork or Dependabot PRs, which get no secrets): the job passes
  with a notice and runs nothing. Don't make `tessl` a required check until it is configured.
- Optional variables: `TESSL_REVIEW_THRESHOLD`, `TESSL_EVAL_AGENT`, `TESSL_EVAL_MODEL`.
- API keys expire (30 days unless `--ttl` or `--expiry-date` is passed); renew before then or the job fails.

Maintainer setup, once:

```bash
tessl login
tessl api-key create --workspace <workspace> --name ci --ttl 1y
gh secret set TESSL_TOKEN -R storra-eng/skills
gh variable set TESSL_WORKSPACE -R storra-eng/skills --body <workspace>
```

Then set `name` in `skills/actions-to-issues/.tessl-plugin/plugin.json` to `<workspace>/actions-to-issues`, and check the
first run: the plugin name and `--workspace` must agree.

Run it locally:

```bash
tessl review run skills/actions-to-issues --workspace <workspace>
tessl eval run skills/actions-to-issues
```

Evals cost model runs. Add a scenario as `evals/scenario-N-<name>/` with `task.md` and `criteria.json`
([format](https://docs.tessl.io/improving-your-skills/evaluate-skill-quality-using-scenarios.md)). Use synthetic data only.
Tools are simulated in the task text: the agent writes `CALL <tool> <args>` lines, so the criteria can check them.
