# CLAUDE.md

Full AI-agent guidance for this repo lives in `AGENTS.md` — read it first.

@AGENTS.md

## Claude-specific notes

- Before proposing changes to `five9/`, run the fast unit tests
  (`make unit`, or `python -m unittest discover -s five9/tests -p 'test_utils_*.py' -v`)
  — check the `Makefile` for the exact target if it's changed since this was written.
- Activate the project virtual environment (`source venvs/five9/bin/activate` on
  Mac/Linux, `.\venvs\five9\Scripts\activate` on Windows) before running any
  script or test, or commands will fail or use the wrong Python/deps.
- Never run integration tests (`F9_INTEGRATION=1 ...`) or any example script
  against a real `--account_alias`/`--username` without first getting explicit
  confirmation from the user — these hit a live Five9 domain.
- Before executing anything that writes/modifies/deletes domain configuration
  (bulk user scripts, `domain_config/` mutations, `delete*`/`modify*` API
  calls), stop and confirm with the user per the "Safety guardrails for AI
  agents" section in `AGENTS.md`.
