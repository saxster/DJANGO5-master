# IntelliWiz Test Suite

This package groups all cross-cutting test suites and shared fixtures.  App-specific
tests continue to live alongside their code (for example `apps/core/tests/`), while
this directory provides a home for scenarios that span multiple applications or the
entire platform.

```
tests/
├── api/            # End-to-end API contracts (REST v1/v2)
├── factories/      # Shared factory classes and pytest fixtures
├── integration/    # Multi-app flows (database, Celery, external adapters)
├── performance/    # Load/perf smoke suites executed on-demand
├── security/       # Security and permission regression tests
├── unit/           # Domain-level units that span multiple apps
└── conftest.py     # Global fixtures (Django settings, API client, etc.)
```

### Running the suite

```bash
pytest                      # Full run (apps + top-level suites)
pytest tests/unit           # Fast unit tests
pytest -m integration       # Marker-based selection
```

### Adding new tests

1. Choose the directory that best matches the test category.
2. Import shared fixtures from `tests/conftest.py` and app-specific fixtures as
   needed.
3. Use pytest markers (`unit`, `integration`, `performance`, `security`) so the
   tests can participate in targeted CI jobs.

Refer to `docs/testing/TESTING_AND_QUALITY_GUIDE.md` for the full testing
standards and validation workflow.

