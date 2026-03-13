# Changelog

All notable changes to NanoClaw will be documented in this file.

## [Unreleased]

- **breaking:** Runtime and setup are Python-only; Node/TypeScript execution paths were removed.
- **breaking:** Repository structure was pruned to core Python runtime, core skills, and single CI workflow.
- **docs:** Core skills were rewritten to Python-first workflows.
- **ops:** CI upgraded with lint/test matrix/package checks; added Dependabot and Python launchd template.
- **ops:** Repository layout standardized (`tests/`, `scripts/`, `deploy/launchd`) and runtime home anchored to `NANOCLAW_HOME`.

## [1.2.0](https://github.com/qwibitai/nanoclaw/compare/v1.1.6...v1.2.0)

[BREAKING] WhatsApp removed from core, now a skill. Run `/add-whatsapp` to re-add (existing auth/groups preserved).
- **fix:** Prevent scheduled tasks from executing twice when container runtime exceeds poll interval (#138, #669)
