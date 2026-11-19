# The pre-check

`skills/ActionsToIssues/scripts/granola_precheck.py` makes one Granola `list_meetings` call and says whether to start
the agent. Python 3.9+, standard library only. Copy the whole `scripts/` folder: it imports `granola_reply.py` from
beside it.

## Run it

```bash
python3 skills/ActionsToIssues/scripts/granola_precheck.py
```

| Exit | Meaning | Do |
|---|---|---|
| `0` | Idle: nothing new | Skip the agent |
| `10` | Work: a new, old-enough meeting | Start the agent; paste the `new` / `defer` lines into its prompt |
| `1` | Cannot tell (`FAIL <reason>`) | Start the agent |
| `2` | Usage error | Fix the call |

It fails open on purpose: it can make a run cheaper, never blinder. A missing `MN2L_STATE`, an expired token, a
non-2xx, a redirect and a reply it does not parse all wake the agent. It prints counts and ids only, never a title,
body or token.

## Options

| Flag / variable | Default | Meaning |
|---|---|---|
| `--auth-file` / `MCP_AUTH_FILE` | none | JSON with the Granola tokens (shape in the script header); no default path is assumed |
| `GRANOLA_ACCESS_TOKEN` | none | A bearer token instead of a file |
| `--auth-key` / `MCP_AUTH_SERVER` | `granola` | Key of the Granola entry in that file |
| `GRANOLA_MCP_URL` | Granola's | Endpoint for `GRANOLA_ACCESS_TOKEN` only (https; loopback for tests) |
| `--state` / `MN2L_STATE` | none | State file of handled meetings; required unless `--rows` |
| `--min-age` / `PRECHECK_MIN_AGE_MIN` | 30 | Minutes after a meeting starts before it counts as new; set above your longest meeting |
| `--no-defer` | off | Judge every meeting regardless of age (last run of the day) |
| `--days` / `PRECHECK_DAYS` | 2 | UTC days to look back, today included |
| `--rows` | off | Print every meeting and let the caller classify (below) |

## Your own record of handled meetings: `--rows`

Use it when the handled set lives in a database or ledger. No state file is read. Output:

```text
OK seen=<n> others=<m>
id <meeting id> <minutes since start> <note length s> <minutes since last update>
```

`unknown` marks a value it could not read. Exit `0` on a well-formed answer, `1` on anything else, and a failure must
still wake your agent.

## Things to know

- **It never refreshes a token.** The MCP client that owns the OAuth session does. An idle day costs about one agent
  run per access-token lifetime, not zero.
- **Alert on a streak of non-zero exits.** A persistent failure otherwise becomes a full-cost run on every tick.
- **Run PROPOSE and FILE one at a time.** Both rewrite the state file.
