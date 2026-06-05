# Releasing Seatbelt

How `seatbelt-harness` is published to PyPI. The package is distributed as **`seatbelt-harness`**
(see [ADR-0006](decisions/ADR-0006-naming-and-distribution.md) for the naming rationale).

Publishing uses **PyPI Trusted Publishing (OIDC)** via GitHub Actions — there is **no API token**
stored anywhere. A push of a `v*` tag triggers `.github/workflows/release.yml`, which builds the
distributions and uploads them from the `publish` job using a short-lived OIDC token.

## One-time setup (maintainer, before the first release)

1. **Register a pending publisher on PyPI.** Go to
   <https://pypi.org/manage/account/publishing/> and add a *pending* publisher with:
   - **PyPI project name:** `seatbelt-harness`
   - **Owner:** `ayuan153`  ·  **Repository:** `seatbelt`
   - **Workflow filename:** `release.yml`
   - **Environment name:** `pypi`

   "Pending" means the project does not exist on PyPI yet; the first successful run creates it. No
   token is generated or stored.

2. **Create the GitHub Environment.** In the repo: *Settings → Environments → New environment* →
   name it **`pypi`**. Add **required reviewers** (yourself) so every upload is gated by a manual
   approval click — a deliberate safety stop before anything is pushed to PyPI.

3. *(Optional)* Repeat steps 1–2 against <https://test.pypi.org> with an environment `testpypi` if
   you want a staging dry-run target.

## Cutting a release

1. **Bump the version** in `pyproject.toml` (`project.version`). Seatbelt follows semantic
   versioning; pre-1.0 the project is `Development Status :: 3 - Alpha`, so minor bumps may carry
   breaking changes — call them out in the release notes.
2. **Land the changes** on `main` (PR + green CI). The release builds whatever the tag points at.
3. **Dry-run locally** (see below) to catch metadata errors before tagging.
4. **Tag and push:**
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
5. **Approve the deployment.** The `release` workflow runs `build`, then pauses at the `publish`
   job waiting for the `pypi` environment reviewer. Approve it in the GitHub Actions UI.
6. **Verify** the release appears at <https://pypi.org/project/seatbelt-harness/> and installs
   cleanly: `pipx install seatbelt-harness` (or `pip install` in a fresh venv) then `seatbelt --help`.
7. **Write GitHub release notes** for the tag.

> Tags are immutable on PyPI: **a version can never be re-uploaded or overwritten.** If a release is
> broken, yank it on PyPI and ship a new patch version (e.g. `v0.1.1`).

## Local dry-run (no upload)

Always run this before tagging — it is exactly what CI checks:

```bash
.venv/bin/pip install build twine
rm -rf dist build
.venv/bin/python -m build          # builds sdist + wheel into dist/
.venv/bin/twine check dist/*       # validates long-description rendering + metadata
```

Optionally upload to TestPyPI first (requires a TestPyPI trusted publisher or token):

```bash
.venv/bin/twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ seatbelt-harness
```

## What is NOT automated (by design)

- **The actual PyPI upload requires a human approval** on the `pypi` environment — there is no
  unattended publish.
- **Version bumps are manual** — no auto-increment, so the released version is always a deliberate
  choice.

## TypeScript client (`clients/typescript`)

Per ADR-0006, the npm `@seatbelt/client` name is **unavailable** (the `@seatbelt` scope is owned by
another user). The client's npm publish is **deferred / unresolved** — interop with the proxy works
today via a `base_url` swap without any client package. Resolve the package name (e.g.
`seatbelt-harness-client`) before attempting an npm publish; this Python release does not depend on it.
