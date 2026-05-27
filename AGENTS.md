# Agent Conventions — Backend Project

## Mandatory Rules

### 1. Clean Git Status Before Shift End
No agent finishes a shift without a clean `git status`. Before completing any task:
- Run `git status --short`
- If there are uncommitted changes, commit them with a descriptive message
- Verify the working tree is clean before marking the task as done

### 2. .venv Directories Never Tracked
- `.venv/` and `venv/` are in `.gitignore` — never `git add` them
- If accidentally staged, immediately `git rm -r --cached .venv` and commit

### 3. Descriptive Commits
- Use conventional commit format: `type(scope): description`
- Types: feat, fix, chore, docs, refactor, test, ci
- Example: `feat(auth): add OTP validation endpoint`

### 4. No Secrets in Code
- Never commit `.env` files (only `.env.example`)
- Use environment variables for all secrets and config

### 5. Working Directory
- Default project root: `/home/maestri33/coders/backend`
- All git operations should be run from this directory
