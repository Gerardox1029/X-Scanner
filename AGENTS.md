# Project instructions

- `PLAN.md` is the approved scope; keep `plan.md` as the execution ledger and `memory.md` as the architecture and command map.
- The browser is an untrusted client. The Python service must bind to `127.0.0.1`, require an exact allowed Origin and in-memory session, and accept only typed operations. Never accept shell commands from the page.
- Privileged actions belong in the installed, root-owned helper with a fixed allowlist. Scripts written in technician mode always run as the logged-in user.
- Diagnostics should state what was measured, what was inaccessible, and what remains uncertain. Reports must match results.
- Labs own all altered resources and must be restorable independently of the browser.
- Keep UI copy in Spanish, accessible, and explicit about the effects of each action.
- Avoid retaining personal file contents in logs or repository fixtures. Run meaningful tests and update `plan.md` with results.

Responsibilities: architecture maintains contracts and permissions; interface maintains navigation and accessible results; Linux service maintains measurements, actions and packaging; verification checks security, results and cleanup.
