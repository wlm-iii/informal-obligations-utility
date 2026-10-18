# Continuing the handoff

The imported handoff is on `codex/handoff-import` in
https://github.com/wlm-iii/informal-obligations-utility.
It retains the history of `feat/return-tracker-work`. The previous local
`codex/mint-login-theme` branch is also preserved.

From this project folder, save and upload future changes with:

```powershell
git status
git diff
git add <files-you-changed>
git commit -m "feat: describe your change"
git push
```

Replace `<files-you-changed>` with the actual paths. Review staged files with
`git diff --cached` before committing. Use a pull request into `main` when ready
to integrate the work. Commit and push do not deploy the app themselves.

Git uses Windows Credential Manager for authentication. The branch has an
upstream after its initial push, so subsequent pushes need only `git push`.
Never commit credentials, `.env` files, databases, or dependency folders;
the repository ignores those files and includes safe `.env.example` templates.

For local development, follow `docs/DEVELOPMENT.md`. A normal terminal needs
Python 3.12, Node.js 22.12+ with npm, uv, and PostgreSQL 17 as described there.
The Codex bundled Node/Python runtimes were used to validate this import;
`npm`, `py`, and `uv` were not available on this terminal's PATH at import time.

Validation at import: 46 frontend tests, 117 backend tests, 11 tooling tests,
frontend lint, production build, and dashboard preview build passed.
The 13 PostgreSQL integration tests were not run. Live Google sign-in and
hosted services require your own environment configuration.

`docs/HANDOFF.md` preserves the supplied handoff notes. The archive's `source/`
was imported; its prebuilt `preview/` is reproducible with `npm run build:preview`
inside `frontend/` and is intentionally not committed.
