# CourDL engine

Python sidecar used by the CourDL desktop app.

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/courdl-engine version
```

Subcommands: `version`, `check-cookies`, `resolve`, `download`, `beautify`.

See [docs/engine.md](../docs/engine.md) and [docs/packaging.md](../docs/packaging.md).
