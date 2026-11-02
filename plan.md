# X-Scanner implementation ledger

Scope and acceptance criteria: [PLAN.md](PLAN.md). This file records implementation state and evidence; `PLAN.md` remains the approved product specification.

| Stage | State | Evidence / remaining check |
|---|---|---|
| Documentation and versioned API contract | Complete in source | `docs/API.md`, `docs/openapi.json`, `docs/INSTALL.md`, `docs/TESTING.md`, `AGENTS.md`, `memory.md` |
| Local browser pairing and security | Implemented; external check pending | Origin/session tests pass; real HTTPS Netlify to Brave and polkit on installed package remain unverified |
| Nine diagnostics and reports | Implemented; manual matrix pending | Real system measurements, limitations and TXT reports implemented; file, photo, process and network paths covered by API tests |
| Three controlled labs and unusual case | Implemented and tested locally | 128 MiB storage, CPU process, local HTTP outage and open deleted file; independent restore commands |
| UI, full scan, history, technician tools | Built; browser review pending | `npm run build` succeeds; headless Brave screenshot did not complete in this environment |
| Debian package and Netlify bundle | Built; deployment check pending | Offline wheel install from extracted `.deb` succeeds; `web/dist`, `_headers`, `_redirects`, `netlify.toml` and deployment ZIP ready; second Linux installation pending |

## Working order

1. Establish documentation, API, origin and session controls.
2. Implement diagnostics, reports, actions and labs.
3. Build the Spanish interface and its task flows.
4. Package and verify; update this ledger with measured outcomes.

No production data, secrets, passwords or reports belong in this repository.

## Verification record, 2026-11-01

- Python: `10 passed, 1 warning` in 13.70 s after adding duplicate byte comparison. Warning is Starlette's deprecation of the current `httpx` test client.
- Web: TypeScript and Vite production build succeed.
- Additional routes (`process-frozen`, `process-heat`, `network-offline`, `network-slow`, `full-scan`) completed against an isolated test home and reported concrete limitations.
- Agent: a real loopback health request returned 200 with the exact allowed CORS origin; a second instance rejected occupied port 8765.
- Packaging: `.deb` built; its wheelhouse installed with `--no-index` in an extracted temporary environment, and the packaged FastAPI app imported with Pillow 13.
- Remaining acceptance: published HTTPS Netlify/Brave permission flow, live polkit cancellation, all nine manual UI paths on the target desktop, and a second compatible Linux installation. No published URL or second installation is available in this workspace. The app browser is disabled in current Work settings, and headless Brave did not produce a screenshot.
- 2026-11-01 update: Client/Técnico result toggle, measured yellow lab alert, action progress/confirmation, user-folder scanning, Arsenal script reader and reconnection guide implemented. Web build and Python compile pass. Final DOCX and offline HTML presentation added; external Brave/polkit/second-machine checks remain pending.
- Deployment discovery found no Netlify connector. A local package installation could not start because this execution environment sets Linux `no_new_privileges`, so `sudo` cannot gain root privileges. The package itself was inspected and its dependencies installed offline in an extracted temporary environment.
- Deliverables: `dist/xscanner-agent_0.1.0_amd64.deb` and `dist/xscanner-web-netlify.zip`; the ZIP contains `_headers`, `_redirects`, `index.html` and compiled assets.
