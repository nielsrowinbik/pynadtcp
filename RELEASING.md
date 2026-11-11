# Releasing

Releases are automatic. Merge to `main` and the Release workflow does the rest.

[semantic-release](https://semantic-release.gitbook.io/) reads the commit messages since the last tag. They must follow [Conventional Commits](https://www.conventionalcommits.org/):

| Commit | Release |
|---|---|
| `fix: ...` | patch (1.0.0 → 1.0.1) |
| `feat: ...` | minor (1.0.0 → 1.1.0) |
| `feat!: ...`, or a `BREAKING CHANGE:` footer | major (1.0.0 → 2.0.0) |
| `ci:`, `docs:`, `test:`, `chore:`, `refactor:` | no release |

With squash merging, the PR title becomes the commit message, so the PR title decides the release.

When a release is due, the workflow runs the tests, sets the version in `pyproject.toml` and `pynadtcp/__init__.py`, builds the package, updates `CHANGELOG.md`, commits with `[skip ci]`, creates the `v<version>` tag and GitHub Release, and publishes to PyPI through Trusted Publishing. Don't change the version by hand.

The PyPI trusted publisher is configured for workflow `release.yml` and environment `pypi`. Renaming either breaks publishing until the PyPI settings are updated to match.

If `main` is protected by a ruleset, the release commit is pushed with a deploy key that may bypass it. The key's private half is the `RELEASE_DEPLOY_KEY` secret.
