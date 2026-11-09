# Releasing

Releases are automatic. To publish a new version:

1. Bump `version` in `pyproject.toml` and `__version__` in `pynadtcp/__init__.py` to the same value.
2. Merge to `main`.

The Release workflow sees that this version isn't on PyPI yet, runs the tests, builds the package, publishes it to PyPI through Trusted Publishing, and creates a `v<version>` tag and GitHub Release. Pushes that don't change the version publish nothing.

The PyPI trusted publisher is configured for workflow `release.yml` and environment `pypi`. Renaming either breaks publishing until the PyPI settings are updated to match.
