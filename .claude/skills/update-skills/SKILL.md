---
name: update-skills
description: Refresh the five core skill documents from upstream/main (Python-first sync model).
---

# Update Core Skills (Python)

This repository keeps exactly five core skills:
- `setup`
- `debug`
- `customize`
- `update-nanoclaw`
- `update-skills`

This skill syncs those files from `upstream/main`.

## 1) Preflight

```bash
git status --porcelain
git remote -v
```

If `upstream` is missing:

```bash
git remote add upstream https://github.com/qwibitai/nanoclaw.git
```

Fetch latest upstream:

```bash
git fetch upstream --prune
```

## 2) Preview core-skill drift

```bash
git diff --name-status HEAD..upstream/main -- .claude/skills
git diff --name-only HEAD..upstream/main -- \
  .claude/skills/setup/SKILL.md \
  .claude/skills/debug/SKILL.md \
  .claude/skills/customize/SKILL.md \
  .claude/skills/update-nanoclaw/SKILL.md \
  .claude/skills/update-skills/SKILL.md
```

If no differences, stop with "core skills already up to date".

## 3) Apply selected sync

### Full sync (default)

```bash
git checkout upstream/main -- \
  .claude/skills/setup/SKILL.md \
  .claude/skills/debug/SKILL.md \
  .claude/skills/customize/SKILL.md \
  .claude/skills/update-nanoclaw/SKILL.md \
  .claude/skills/update-skills/SKILL.md
```

### Selective sync

Use the same command but include only chosen files.

## 4) Validate and summarize

```bash
git diff -- .claude/skills
```

Report:
- synced files
- skipped files
- any local edits that were intentionally retained
