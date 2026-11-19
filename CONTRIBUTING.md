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
