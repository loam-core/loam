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

### Internal / Substrate
- Introduced a real runtime trust membrane (_live gating + one‑shot runtime)
- Structural signer wrapping moved to initialize_authority(); signer invalidated after run
- Continuity now guarded via AgentRuntime overrides
- Refactored identity unlock flow; removed silent unlocks; unified signer derivation
- Stabilized continuity chain semantics (seq/hash/kind)
- Unified envelope semantics across runtime + protocol
- Python driver correctness fixes
- Added chunked‑write protocol + new state tools
- Added Discord backend tooling for ARI agents
- A truncated/hand-edited file missing its trailing newline can no longer cause the next real append to glue onto the previous line

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
