# Contributing to pylar-admin

## Scope

This is the public source for the `pylar-admin` package — the Vue.js
SPA admin panel for `pylar-framework`. The framework lives in a
separate repository:
<https://github.com/pylar-foundation/pylar-framework>.

`pylar-admin` depends on `pylar-framework` at runtime; if a feature
touches both, land the framework change first.

## Local Setup

Use Python 3.12 and `uv`. Clone `pylar-framework` as a sibling
directory and install both in editable mode:

```bash
uv pip install -e "../pylar-framework[dev,sqlite,webauthn]"
uv pip install -e ".[dev]"
```

For the admin SPA:

```bash
cd pylar_admin/spa
npm install
```

## Required Checks

Before opening a pull request:

```bash
uv run ruff check pylar_admin tests
uv run pytest tests -q

cd pylar_admin/spa && npm run build
```

## Engineering Rules

- Prefer explicit typed APIs over magic or string-based indirection.
- Do not commit generated artifacts: `node_modules/`, `pylar_admin/spa/dist/`, `htmlcov/`, `.coverage*`, runtime `.env*`.
- Add or update tests with every behavior change.
- Keep documentation and support/versioning statements aligned with the shipped package version.

## Commit and Pull Request Policy

Use Conventional Commits, for example:

- `feat(fields): add GeoMapField polygon editing`
- `fix(api): preserve filters on pagination`
- `docs: clarify webauthn flow`

Pull requests should include:

- a short problem statement
- tests run locally
- screenshots for SPA UI changes
- linked issue when the change is architectural
