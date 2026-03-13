# Contributing

## Source Code Changes

**Accepted:** Bug fixes, security fixes, simplifications, reducing code.

**Not accepted:** Features, capabilities, compatibility, enhancements. These should be skills.

## Skills

A [skill](https://code.claude.com/docs/en/skills) is a markdown file in `.claude/skills/` that teaches Claude Code how to transform a NanoClaw installation.

A PR that updates a **core skill** should not modify any source files.

Core skills in this repository are operational only: `setup`, `debug`, `customize`, `update-nanoclaw`, and `update-skills`.
Skill updates should contain the **instructions** Claude follows, not pre-built feature code.

### Why?

Every user should have clean and minimal code that does exactly what they need. The core skill set is kept intentionally small to reduce maintenance overhead.

### Testing

Test your skill by running it on a fresh clone before submitting.
