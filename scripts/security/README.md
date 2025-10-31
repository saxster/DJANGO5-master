# Security Scripts - Secret Scanning & Remediation

Automated tools for secret detection, installation, and verification.

---

## 📋 Available Scripts

### 1. `install_secret_scanners.sh`

**Purpose**: One-command installation of all secret scanning tools

**What it installs:**
- ✅ **gitleaks** (industry-standard secret scanner)
- ✅ **detect-secrets** (Yelp's secret detection tool)
- ✅ **git-filter-repo** (git history cleanup)
- ✅ **pre-commit** (framework for git hooks)

**Usage:**
```bash
./scripts/security/install_secret_scanners.sh
```

**What it does:**
1. Detects your OS (macOS/Linux) and installs appropriately
2. Creates `.gitleaks.toml` configuration
3. Generates `.secrets.baseline` for detect-secrets
4. Installs pre-commit git hooks
5. Runs verification tests on all files

**Time:** ~5-10 minutes (depending on internet speed)

**Requirements:**
- macOS: Homebrew
- Linux: wget/curl and Python 3
- Both: pip (for Python packages)

---

### 2. `scan_for_secrets.sh`

**Purpose**: Comprehensive secret scanning with multiple detection engines

**Usage:**
```bash
# Scan current working directory
./scripts/security/scan_for_secrets.sh

# Scan entire git history (slower but thorough)
./scripts/security/scan_for_secrets.sh --all

# Scan only staged files (pre-commit mode)
./scripts/security/scan_for_secrets.sh --staged

# Generate detailed report
./scripts/security/scan_for_secrets.sh --report
```

**What it scans:**
1. **Gitleaks**: Pattern-based secret detection
2. **detect-secrets**: Entropy-based secret detection
3. **Sensitive files**: Checks for .env, .pem, .key files
4. **Environment files**: Verifies no .env files committed
5. **GCP keys**: Detects service account JSON keys

**Output:**
- Detailed findings with file paths and line numbers
- Color-coded severity (red = critical, yellow = warning)
- Actionable remediation steps

**Exit codes:**
- `0`: No secrets found (clean)
- `1`: Secrets detected (requires action)

---

### 3. `test_secret_detection.sh`

**Purpose**: Verify that secret scanners are working correctly

**Usage:**
```bash
./scripts/security/test_secret_detection.sh
```

**What it tests:**
1. ✅ AWS access key detection
2. ✅ AWS secret key detection
3. ✅ Google API key detection
4. ✅ Django SECRET_KEY detection
5. ✅ Database password detection
6. ✅ GCP service account key detection
7. ✅ SSH private key detection
8. ✅ Generic password detection
9. ✅ False positive handling (documentation)
10. ✅ False positive handling (test code)

**Test methodology:**
- Creates temporary git repository
- Adds files with known secrets
- Verifies scanners detect them
- Cleans up automatically

**Pass criteria:** 10/10 tests pass

---

## 🚀 Quick Start Guide

### First-time Setup

```bash
# 1. Install all tools (one-time setup)
./scripts/security/install_secret_scanners.sh

# 2. Verify installation works
./scripts/security/test_secret_detection.sh

# 3. Scan your repository
./scripts/security/scan_for_secrets.sh

# 4. If secrets found:
#    - Rotate all exposed credentials
#    - See: docs/security/SECRET_ROTATION_INCIDENT_RESPONSE.md
```

---

## 📊 Typical Workflow

### Daily Development

Pre-commit hooks run automatically:
```bash
git add .
git commit -m "feature: add new endpoint"
# Pre-commit hook scans automatically
# If secrets found → commit blocked
# If clean → commit succeeds
```

### Weekly Security Scan

```bash
# Run comprehensive scan
./scripts/security/scan_for_secrets.sh --all --report

# Review report
less gitleaks-report.json

# If secrets found, follow remediation procedures
```

### Before Deployment

```bash
# Full history scan
./scripts/security/scan_for_secrets.sh --all

# Must exit with code 0 (no secrets)
if [ $? -eq 0 ]; then
    echo "✓ Safe to deploy"
else
    echo "✗ Fix secrets before deploying!"
fi
```

---

## 🔧 Configuration Files

### `.gitleaks.toml`

Custom rules for Django-specific secrets:
- Django SECRET_KEY
- Database passwords (DBPASS)
- Encryption keys (ENCRYPT_KEY)
- MQTT passwords
- Redis passwords
- Superadmin passwords

**Location:** Project root
**Auto-created by:** `install_secret_scanners.sh`

### `.secrets.baseline`

Baseline of known secrets (for whitelisting false positives):
- Documentation examples
- Test fixtures
- Placeholder values

**Location:** Project root
**Auto-created by:** `install_secret_scanners.sh`
**Manage with:** `detect-secrets audit .secrets.baseline`

### `.pre-commit-config.yaml`

Pre-commit hook configuration (already in repo):
- Gitleaks protect mode
- detect-secrets scanner
- Plus existing hooks (flake8, black, bandit, etc.)

**Location:** Project root
**Already configured:** ✅

---

## 🐛 Troubleshooting

### "gitleaks: command not found"

**Solution:**
```bash
# macOS
brew install gitleaks

# Linux
./scripts/security/install_secret_scanners.sh
```

### "detect-secrets: command not found"

**Solution:**
```bash
pip install detect-secrets
# or
./scripts/security/install_secret_scanners.sh
```

### Pre-commit hooks not running

**Solution:**
```bash
# Reinstall hooks
pre-commit install

# Test manually
pre-commit run --all-files
```

### False positives in detect-secrets

**Solution:**
```bash
# Audit baseline and mark false positives
detect-secrets audit .secrets.baseline

# For each finding:
# - Press 'n' for false positive
# - Press 'y' for real secret
```

### Gitleaks reports known secrets

**Solution:**
Update `.gitleaks.toml` allowlist:
```toml
[[allowlist.regexes]]
description = "My specific false positive"
regex = '''pattern-to-ignore'''
```

---

## 📚 Reference Documentation

| Document | Purpose |
|----------|---------|
| `docs/security/SECRET_ROTATION_INCIDENT_RESPONSE.md` | Comprehensive incident response runbook |
| `SECURITY_REMEDIATION_SUMMARY.md` | Current security status and fixes |
| `.claude/rules.md` | Security compliance rules |

---

## 🎯 Success Criteria

### Installation Complete

- [ ] All tools installed (`gitleaks --version`, `detect-secrets --version`)
- [ ] Configuration files created (`.gitleaks.toml`, `.secrets.baseline`)
- [ ] Pre-commit hooks installed (`pre-commit run --all-files`)
- [ ] Test suite passes (`./scripts/security/test_secret_detection.sh`)

### Repository Secure

- [ ] Scan returns 0 findings (`./scripts/security/scan_for_secrets.sh`)
- [ ] No sensitive files tracked (`git ls-files | grep -E '\.env|\.pem|\.key'`)
- [ ] Pre-commit blocks test secrets (`echo "AWS_KEY=test" > test && git add test && git commit`)
- [ ] Team trained on secret management

---

## 🔄 Maintenance

### Weekly Tasks

```bash
# Update tools
brew upgrade gitleaks  # macOS
pip install --upgrade detect-secrets

# Update pre-commit hooks
pre-commit autoupdate

# Full repository scan
./scripts/security/scan_for_secrets.sh --all
```

### Monthly Tasks

```bash
# Review and update baseline
detect-secrets audit .secrets.baseline

# Review gitleaks configuration
vi .gitleaks.toml

# Rotate long-lived secrets (if any)
# See: docs/security/SECRET_ROTATION_INCIDENT_RESPONSE.md
```

---

## ⚡ Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Install tools | 5-10 min | One-time setup |
| Scan working directory | 5-30 sec | Fast, for daily use |
| Scan entire git history | 2-10 min | Thorough, for weekly scans |
| Pre-commit hook | 2-5 sec | Blocks commit if secrets found |
| Test suite | 10-15 sec | Validates scanner functionality |

---

## 🆘 Support

**Issues with scripts:**
1. Check script permissions: `chmod +x scripts/security/*.sh`
2. Verify tool installation: `gitleaks version`, `detect-secrets --version`
3. Review error messages (color-coded)
4. See troubleshooting section above

**Security incident:**
1. Don't panic - follow the runbook
2. See: `docs/security/SECRET_ROTATION_INCIDENT_RESPONSE.md`
3. Contact security team immediately

---

**Last Updated:** 2025-10-11
**Maintainer:** Security Team
**Review Cycle:** Quarterly
