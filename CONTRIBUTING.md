# Contributing to Loam

Thank you for your interest in contributing to Loam Core.

Loam is early and intentionally minimal. Contributions should preserve that minimalism
and conceptual clarity.

## How to Contribute

### Issues

Use GitHub issues for:

- bugs
- documentation gaps
- substrate inconsistencies
- proposals

### Pull Requests

PRs should:

- be small and focused
- include tests if appropriate (not required for early contributions)
- update docs if behavior changes

Open a draft PR early if you want feedback.

## Development Setup

```bash
git clone https://github.com/loam-core/loam
cd loam
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Philosophy

Loam defines:

- identity
- continuity
- policy
- secrets
- substrate tools
- execution membranes

It does not define:

- frameworks
- orchestration
- workflows

Contributions should reinforce this boundary.

## Contact

For questions or discussion, please open an issue on the GitHub repository.
