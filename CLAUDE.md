# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository

GitHub: https://github.com/ahmedsweis9/claude-projects  
Branch: `main`

## Git workflow

After every `git commit`, a PostToolUse hook in `.claude/settings.json` automatically runs `git push` to keep GitHub in sync. Always commit with clean, descriptive messages. No manual push needed.

Permissions for git and gh commands are pre-approved in `.claude/settings.local.json`.
