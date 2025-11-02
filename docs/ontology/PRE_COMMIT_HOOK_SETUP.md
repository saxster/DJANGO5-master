# Pre-Commit Hook Setup - Ontology Validation
**Purpose**: Enforce 100% validation pass rate before commits

**Last Updated**: 2025-11-01
**Maintainer**: Ontology Expansion Team

---

## OVERVIEW

The pre-commit hook automatically validates all ontology decorators in staged files before allowing commits. This ensures:

✅ **100% validation pass rate** - No commits with validation errors
✅ **Immediate feedback** - Developers know about issues before code review
✅ **Consistent quality** - Enforces gold-standard requirements
✅ **Fast iteration** - Fix issues locally instead of in PR

---

## INSTALLATION (ONE-TIME SETUP)

### Step 1: Make Hook Executable

```bash
cd /Users/amar/Desktop/MyCode/DJANGO5-master

# Make the hook script executable
chmod +x .githooks/pre-commit-ontology-validation
```

### Step 2: Install Hook in Git

**Option A: Symlink (Recommended)**
```bash
# Create symlink from .git/hooks to .githooks
ln -sf ../../.githooks/pre-commit-ontology-validation .git/hooks/pre-commit

# Verify installation
ls -la .git/hooks/pre-commit
# Should show: .git/hooks/pre-commit -> ../../.githooks/pre-commit-ontology-validation
```

**Option B: Copy Hook**
```bash
# Copy hook to .git/hooks
cp .githooks/pre-commit-ontology-validation .git/hooks/pre-commit

# Make executable
chmod +x .git/hooks/pre-commit
```

**Why symlink is better**: Updates to `.githooks/pre-commit-ontology-validation` automatically apply to all developers.

### Step 3: Test Installation

```bash
# Test with a dummy commit
git add some_file.py
git commit -m "Test pre-commit hook"

# You should see:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#   Ontology Decorator Validation (Pre-Commit Hook)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## HOW IT WORKS

### 1. Detects Staged Python Files
```bash
git diff --cached --name-only --diff-filter=ACM | grep '\.py$'
```
Only Python files are checked.

### 2. Identifies Files with @ontology Decorators
```bash
grep -q "@ontology" $file
```
Only files with decorators are validated.

### 3. Runs Validation Script
```bash
python scripts/validate_ontology_decorators.py --file $file
```
Each decorated file is validated individually.

### 4. Blocks Commit on Errors
- **Errors**: Commit blocked, must fix before committing
- **Warnings**: Commit allowed, but quality suggestions shown
- **Pass**: Commit allowed

---

## VALIDATION RULES

### ERRORS (Commit Blocked) ❌

These issues **block commits**:

1. **Missing required fields** - All 14 fields must be filled
   ```
   ✗ Error: Missing required field 'security_notes'
   ```

2. **PII not marked sensitive** - All PII fields must have `sensitive: True`
   ```
   ✗ Error: Field 'email' appears to be PII but 'sensitive' is not set to True
   ```

3. **Empty required fields** - No "TODO" or "TBD" placeholders
   ```
   ✗ Error: Field 'purpose' is empty or contains placeholder text
   ```

4. **Invalid decorator syntax** - AST parsing fails
   ```
   ✗ Error: Failed to parse decorator (syntax error)
   ```

### WARNINGS (Commit Allowed) ⚠️

These issues **allow commits** but show suggestions:

1. **Tag count < 5** - Recommend 7-10 tags
   ```
   ⚠ Warning: Only 3 tags. Recommend at least 5 tags.
   ```

2. **Example count < 2** - Recommend 3-5 examples
   ```
   ⚠ Warning: Only 1 example. Recommend at least 2 examples.
   ```

3. **Security notes < 3 sections** - Recommend 5+ sections
   ```
   ⚠ Warning: Security notes have only 2 sections. Recommend at least 3.
   ```

---

## EXAMPLE OUTPUTS

### ✅ PASS (All Validations Passed)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Ontology Decorator Validation (Pre-Commit Hook)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 Found 1 staged Python file(s)

🔍 Found 1 file(s) with @ontology decorators

Validating: apps/core/services/encryption_key_manager.py
  ✓ Validation passed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Validation Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Files validated: 1
  Errors:          0
  Warnings:        0

✅ VALIDATION PASSED - Commit allowed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[main abc1234] feat(ontology): Add encryption_key_manager decorator
 1 file changed, 250 insertions(+)
```

---

### ⚠️ WARNING (Quality Suggestions)

```
Validating: apps/core/services/example_service.py
  ⚠ Warnings found (commit allowed, but please review)
  ⚠ Warning: Only 4 tags. Recommend at least 5 tags.
  ⚠ Warning: Only 2 examples. Recommend at least 3 examples.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Validation Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Files validated: 1
  Errors:          0
  Warnings:        2

⚠️  WARNINGS FOUND - Commit allowed, but please review warnings

Common warnings:
  - Tag count < 5 (recommend 7-10 tags)
  - Example count < 2 (recommend 3-5 examples)
  - Security notes < 3 sections (recommend 5+)

These are quality suggestions, not blockers.
Consider improving before final PR submission.

✅ VALIDATION PASSED - Commit allowed
```

---

### ❌ FAIL (Validation Errors)

```
Validating: apps/core/services/bad_example.py
  ✗ Validation failed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Validating: apps/core/services/bad_example.py
✗ Errors:
  • ExampleService: Missing required field 'security_notes'
  • ExampleService: Field 'email' appears to be PII but 'sensitive' is not set to True
  • ExampleService: Field 'purpose' is empty or contains placeholder text

⚠ Warnings:
  • ExampleService: Only 2 tags. Recommend at least 5 tags.

✗ Validation failed - fix errors before committing
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Validation Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Files validated: 1
  Errors:          1
  Warnings:        1

❌ COMMIT BLOCKED - Fix validation errors before committing

How to fix:
  1. Review error messages above
  2. Fix missing required fields or PII marking issues
  3. Run validation manually:
     python scripts/validate_ontology_decorators.py --file <file>
  4. Try committing again

Need help?
  - See: docs/ontology/GOLD_STANDARD_EXAMPLES.md
  - See: apps/ontology/templates/DECORATOR_TEMPLATES.md
  - Ask in #ontology-expansion Slack channel
```

---

## BYPASSING THE HOOK (NOT RECOMMENDED)

### When to Bypass

Only bypass in these scenarios:
- ⚠️ Emergency hotfix (production down)
- ⚠️ Work-in-progress commit (planning to fix before PR)
- ⚠️ Non-decorator Python changes triggering false positives

### How to Bypass

```bash
# Skip all git hooks (including pre-commit)
git commit --no-verify -m "WIP: encryption service (decorator incomplete)"
```

**⚠️ WARNING**: Bypassed commits will fail in code review. Use sparingly!

---

## TROUBLESHOOTING

### Hook Not Running

**Symptom**: Commit succeeds without validation output

**Solutions**:
1. Check hook is executable:
   ```bash
   ls -l .git/hooks/pre-commit
   # Should show: -rwxr-xr-x (executable)
   ```

2. Verify symlink is correct:
   ```bash
   ls -la .git/hooks/pre-commit
   # Should show: pre-commit -> ../../.githooks/pre-commit-ontology-validation
   ```

3. Re-install hook:
   ```bash
   rm .git/hooks/pre-commit
   ln -sf ../../.githooks/pre-commit-ontology-validation .git/hooks/pre-commit
   chmod +x .git/hooks/pre-commit
   ```

---

### Validation Script Not Found

**Symptom**:
```
✗ Error: Validation script not found at scripts/validate_ontology_decorators.py
```

**Solution**: Run from repository root:
```bash
cd /Users/amar/Desktop/MyCode/DJANGO5-master
git commit -m "..."
```

---

### False Positives (Non-PII Marked as PII)

**Symptom**:
```
⚠ Warning: Field 'api_key' appears to be PII but 'sensitive' is not set to True
```

**Solution 1**: Mark as sensitive if it IS PII:
```python
{
    "name": "api_key",
    "sensitive": True,  # API keys are sensitive data
}
```

**Solution 2**: Document why it's NOT PII (if false positive):
```python
{
    "name": "public_api_key",  # Rename to clarify it's public
    "sensitive": False,
    "description": "Public API key (not secret, safe to expose)",
}
```

---

### Hook Runs on Non-Decorated Files

**Symptom**: Hook validates files without `@ontology` decorators

**Expected Behavior**: Hook skips files without decorators:
```
✓ No files with @ontology decorators in this commit.
  Validation skipped (not required).
```

If this doesn't happen, check for accidental `@ontology` strings in comments.

---

## TEAM ROLLOUT

### Step 1: Tech Lead Installs First
```bash
# Tech lead installs and tests
chmod +x .githooks/pre-commit-ontology-validation
ln -sf ../../.githooks/pre-commit-ontology-validation .git/hooks/pre-commit

# Test with dummy commit
git add README.md
git commit -m "test hook"
```

### Step 2: Share Installation Instructions
Send this document to the team via:
- Slack/Teams: #ontology-expansion channel
- Email: Link to `docs/ontology/PRE_COMMIT_HOOK_SETUP.md`
- Kickoff meeting: Walk through installation

### Step 3: Verify Team Installation
```bash
# Each team member verifies
git commit --allow-empty -m "test pre-commit hook"
# Should see validation output
```

### Step 4: Enforce in Code Review
Add to PR checklist:
- [ ] Pre-commit hook installed
- [ ] All commits passed validation (no `--no-verify`)

---

## UPDATING THE HOOK

### Updating Validation Rules

If validation script changes (`scripts/validate_ontology_decorators.py`):
```bash
# No action needed if using symlink
# Hook automatically uses latest validation script
```

### Updating Hook Logic

If hook itself changes (`.githooks/pre-commit-ontology-validation`):

**Option 1: Symlink users (automatic)**
```bash
# Pull latest changes
git pull origin main

# Symlink users get update automatically
```

**Option 2: Copy users (manual)**
```bash
# Pull latest changes
git pull origin main

# Re-copy hook
cp .githooks/pre-commit-ontology-validation .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

---

## ALTERNATIVE: CI/CD Validation

If pre-commit hooks are not desired, enforce in CI/CD instead:

**GitHub Actions Example**:
```yaml
name: Ontology Validation

on: [pull_request]

jobs:
  validate-ontology:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - name: Validate Ontology Decorators
        run: |
          python scripts/validate_ontology_decorators.py --all
```

**Pros**: Centralized, can't be bypassed
**Cons**: Slower feedback (after push, not before commit)

---

## FAQ

**Q: Can I disable the hook temporarily?**
A: Yes, use `git commit --no-verify`, but fix issues before PR.

**Q: What if I'm not decorating any files?**
A: Hook skips validation for non-decorated files. No impact.

**Q: Can warnings be upgraded to errors?**
A: Yes, edit `.githooks/pre-commit-ontology-validation` and change warning checks to exit 1.

**Q: Does this slow down commits?**
A: Minimal. Validation takes 1-3 seconds per decorated file.

**Q: Can I test validation without committing?**
A: Yes! Run manually:
```bash
python scripts/validate_ontology_decorators.py --file your_file.py
```

---

## SUMMARY

✅ **Install once** - `chmod +x` and symlink
✅ **Automatic validation** - Runs on every commit
✅ **Immediate feedback** - Fix issues before code review
✅ **Quality enforcement** - 100% validation pass rate

**Next Steps**:
1. Install hook (5 minutes)
2. Test with dummy commit
3. Start decorating components
4. Enjoy fast, quality feedback loop!

---

**SUPPORT**: #ontology-expansion Slack channel or see tech lead
