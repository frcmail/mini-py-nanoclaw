---
name: update-nanoclaw
description: Safely sync this customized Python NanoClaw fork with upstream/main while preserving local changes.
---

# Update NanoClaw (Python)

Use this skill to bring upstream updates into the current fork with minimal risk.

## Operating rules

- Never proceed with a dirty tree.
- Always create rollback points before merge/rebase/cherry-pick.
- Prefer git-native operations and resolve only true conflicts.
- Validate using Python test flow.

## 1) Preflight

```bash
git status --porcelain
git remote -v
```

If `upstream` is missing:

```bash
git remote add upstream https://github.com/qwibitai/nanoclaw.git
```

Fetch:

```bash
git fetch upstream --prune
```

## 2) Safety snapshot

```bash
HASH=$(git rev-parse --short HEAD)
TS=$(date +%Y%m%d-%H%M%S)
git branch backup/pre-update-$HASH-$TS
git tag pre-update-$HASH-$TS
```

## 3) Preview upstream drift

```bash
BASE=$(git merge-base HEAD upstream/main)
git log --oneline $BASE..upstream/main
git log --oneline $BASE..HEAD
git diff --name-only $BASE..upstream/main
```

Group likely conflict areas:
- Python runtime: `nanoclaw/`
- Tests: `tests/`
- Core skills: `.claude/skills/`
- Infra/docs: `.github/`, `README*`, `container/`, `deploy/launchd/`

## 4) Apply chosen strategy

### Default: merge

```bash
git merge upstream/main --no-edit
```

### Alternative: selective cherry-pick

```bash
git cherry-pick <commit...>
```

### Alternative: rebase

```bash
git rebase upstream/main
```

If conflicts occur, resolve only conflict markers and keep intentional local customizations.

## 5) Validate

```bash
python -m pytest tests
```

If tests fail, fix only update-related regressions.

## 6) Rollback

Use the generated tag:

```bash
git reset --hard pre-update-<hash>-<timestamp>
```
