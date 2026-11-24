# The pre-check

`skills/actions-to-issues/scripts/precheck.py` asks the note source for the meetings in a short window, with no model,
and says whether to start the agent. Python 3.9+, standard library only. Copy the whole `scripts/` folder: the harness
imports `precheck_lib.py` and the `source_<name>.py` modules from beside it.

## Run it

```bash
python3 skills/actions-to-issues/scripts/precheck.py --source granola   # granola | fireflies | fathom
```

`--source` (or `MN2L_SOURCE`) must match `source:` in the skill's config; the script reads no YAML. With neither it is
`granola`. `scripts/granola_precheck.py` still works unchanged and always means Granola.

| Source | One call per tick | Credential | `others` |
|---|---|---|---|
| `granola` | MCP `list_meetings` (+ `get_meetings` for timing in `--rows`) | the agent's OAuth token: `GRANOLA_ACCESS_TOKEN` or `--auth-file` | counted |
| `fireflies` | GraphQL `transcripts(fromDate, toDate)`, 50 a page | `FIREFLIES_API_KEY` | `unknown` |
| `fathom` | REST `GET /meetings?created_after=...`, by cursor | `FATHOM_API_KEY` | `unknown` |

Each `scripts/source_<name>.py` header has the endpoint, the variables and the docs it follows. Fireflies and Fathom
use a long-lived API key rather than an OAuth session: give it to the scheduler only, never to the agent. More than 10
pages in the window is a `FAIL`, never an idle day.

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
| `--source` / `MN2L_SOURCE` | `granola` | Note source; must match the config's `source:` |
| `--auth-file` / `MCP_AUTH_FILE` | none | Granola: JSON with the tokens (shape in `source_granola.py`); no default path is assumed |
| `GRANOLA_ACCESS_TOKEN` | none | Granola: a bearer token instead of a file |
| `--auth-key` / `MCP_AUTH_SERVER` | the source name | Key of the source's entry in that file |
| `GRANOLA_MCP_URL` | Granola's | Endpoint for `GRANOLA_ACCESS_TOKEN` only (https; loopback for tests) |
| `FIREFLIES_API_KEY`, `FIREFLIES_GRAPHQL_URL` | none, Fireflies' | Fireflies key and endpoint override (https; loopback for tests) |
| `FATHOM_API_KEY`, `FATHOM_API_URL` | none, Fathom's | Fathom key and base URL override (https; loopback for tests) |
| `--state` / `MN2L_STATE` | none | State file of handled meetings; required unless `--rows` |
| `--min-age` / `PRECHECK_MIN_AGE_MIN` | 30 | Minutes after a meeting starts before it counts as new; set above your longest meeting |
| `--no-defer` | off | Judge every meeting regardless of age (last run of the day) |
| `--days` / `PRECHECK_DAYS` | 2 | UTC days to look back, today included |
| `--rows` | off | Print every meeting and let the caller classify (below) |

## Your own record of handled meetings: `--rows`

Use it when the handled set lives in a database or ledger. No state file is read. Output:

```text
OK seen=<n> others=<m|unknown>
id <meeting id> <minutes since start> <note length s> <minutes since last update>
```

`unknown` marks a value it could not read. Exit `0` on a well-formed answer, `1` on anything else, and a failure must
still wake your agent.

## Things to know

- **It never refreshes a token.** For Granola the MCP client that owns the OAuth session does. An idle day costs about
  one agent run per access-token lifetime, not zero. API-key sources have no such cost.
- **`others=unknown`** means the source has no "captured by someone else" notion; it is not zero.
- **Alert on a streak of non-zero exits.** A persistent failure otherwise becomes a full-cost run on every tick.
- **Run PROPOSE and FILE one at a time.** Both rewrite the state file.
