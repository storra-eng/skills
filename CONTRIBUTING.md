# Contributing

Issues and pull requests are welcome.

- **Keep it generic.** No real meeting content, names, emails, ids, tokens or tracker data, in code, tests, docs or
  commit messages. Tests use synthetic data only. Nothing Storra-specific belongs in `skills/ActionsToIssues/`.
- **Standard library only** for the scripts, Python 3.9+. Run the tests with
  `python3 -m unittest discover -s tests -v` before opening a pull request.
- **The pre-check fails open.** Any path that is not a positive, parsed, internally consistent answer must wake the
  agent, never report an idle day. A change that weakens that needs a test that fails without it.
- **Say what you could not confirm.** Claims about a third-party platform need a link to its public documentation and a
  date; if the docs do not say, say so.
- **Install the git hook** (`pre-commit install`); it keeps every file under 5,000 tokens. See the README.
- **Security issues:** please report privately through GitHub's "Report a vulnerability" rather than a public issue.
