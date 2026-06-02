# Changelog

This project follows semantic versioning.

### Fixed
- ARI: Fixed ARI human‑input handling -- replaced the broken async input() with a correct synchronous checkpoint/await‑input 
- CLI: Fixed path resolution for run and exec commands
- CLI: `ops init` was not wired correctly; now initializes substrate as documented.

### Changed
- Documentation: overhauled agent_dev_guide, added comprehensive_example.md
- Documentation: cleaned up agent examples using new path resolution fix
- Documentation: major rewrite and reorganization for clarity and correctness.
- Quickstart renamed to `getting_started.md` and validated on a clean VM.

## v0.1.0 — Initial Release

- Identity substrate
- Continuity
- Chronicle
- Policy enforcement
- Secrets
- Substrate tools
- ARI runtime
- SDK helpers
- CLI
- Backends
- Examples
- Documentation
