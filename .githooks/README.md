# Git Hooks for Django5 Project

This directory contains custom git hooks to enforce code quality standards defined in `.claude/rules.md`.

## Available Hooks

### `validate-model-complexity`

Enforces model and code complexity limits before commit:

- **Rule #7**: Model files < 150 lines (absolute max: 200)
- **Rule #14**: Utility functions < 50 lines
- **Rule #6**: Settings files < 200 lines

**What it checks:**
- All model files in `apps/*/models.py` and `apps/*/models/*.py`
- All mixin files in `apps/*/mixins/*.py`
- All settings files in `*/settings.py` and `*/settings/*.py`

**When it runs:**
- Automatically before every `git commit`
- Only checks files that are staged for commit

## Installation

### Automatic Setup (Recommended)

Run the setup script from the project root:

```bash
./scripts/setup-git-hooks.sh
```

This will:
1. Copy all hooks from `.githooks/` to `.git/hooks/`
2. Make them executable
3. Configure git to use the hooks

### Manual Setup

```bash
# Copy the hook
cp .githooks/validate-model-complexity .git/hooks/pre-commit

# Make it executable
chmod +x .git/hooks/pre-commit

# Test it
.git/hooks/pre-commit
```

## Usage

### Normal Workflow

Once installed, hooks run automatically:

```bash
git add apps/peoples/models/user_model.py
git commit -m "Update user model"

# Hook runs automatically...
# 🔍 Validating model complexity compliance...
# ✅ All model complexity checks passed!
```

### If Violations Found

The hook will prevent the commit and show violations:

```bash
git commit -m "Add large model"

# 🔍 Validating model complexity compliance...
# ❌ FAIL: apps/peoples/models/huge_model.py has 250 lines (absolute max: 200)
# ❌ Found 1 violations of code complexity rules
#
# Please refactor the files above to comply with .claude/rules.md
```

### Bypassing Hooks (Emergency Only)

If you absolutely must bypass the hooks (not recommended):

```bash
git commit --no-verify -m "Emergency fix"
```

**Note:** Bypassed commits will still be caught by CI/CD pipeline.

## Troubleshooting

### Hook Not Running

**Problem:** Hook doesn't execute on commit

**Solution:**
1. Verify hook is in `.git/hooks/` (not `.githooks/`)
2. Check hook is executable: `ls -la .git/hooks/pre-commit`
3. If not executable: `chmod +x .git/hooks/pre-commit`

### Permission Denied

**Problem:** `permission denied: .git/hooks/pre-commit`

**Solution:**
```bash
chmod +x .git/hooks/pre-commit
```

### Hook Fails on Valid Code

**Problem:** Hook incorrectly reports violations

**Solution:**
1. Manually count lines: `wc -l apps/peoples/models/user_model.py`
2. Check if file truly violates limits
3. If false positive, report issue to team

### Updating Hooks

When hooks are updated in `.githooks/`, reinstall them:

```bash
./scripts/setup-git-hooks.sh
```

Or manually:

```bash
cp .githooks/validate-model-complexity .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## CI/CD Integration

These same rules are enforced in the CI/CD pipeline via:
- `.github/workflows/code-quality.yml`
- `scripts/validate-code-quality.sh`

Even if hooks are bypassed locally, CI/CD will catch violations before merge.

## Customization

To adjust limits, edit the hook file:

```bash
# In .githooks/validate-model-complexity
MODEL_LINE_LIMIT=150      # Target limit
MODEL_MAX_LIMIT=200       # Absolute maximum
UTILITY_LINE_LIMIT=50     # Utility function limit
SETTINGS_LINE_LIMIT=200   # Settings file limit
```

After editing, reinstall the hook.

## Related Documentation

- `.claude/rules.md` - Complete code quality rules
- `docs/people-model-migration-guide.md` - Model refactoring guide
- `TEAM_SETUP.md` - Team onboarding and tool setup

---

**Maintainer:** Development Team
**Last Updated:** September 27, 2025