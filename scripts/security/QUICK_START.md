# Secret Scanning - Quick Start Guide

**Time to secure:** 10 minutes

---

## Step 1: Install Tools (5 minutes)

```bash
cd /Users/amar/Desktop/MyCode/DJANGO5-master
./scripts/security/install_secret_scanners.sh
```

**What happens:**
- ✅ Installs gitleaks, detect-secrets, git-filter-repo, pre-commit
- ✅ Creates configuration files
- ✅ Installs git hooks
- ✅ Runs initial validation

**Expected output:**
```
[SUCCESS] gitleaks installed successfully: v8.18.1
[SUCCESS] detect-secrets installed successfully: 1.4.0
[SUCCESS] git-filter-repo installed successfully
[SUCCESS] All tools installed and configured successfully! ✓
```

---

## Step 2: Verify Installation (1 minute)

```bash
./scripts/security/test_secret_detection.sh
```

**Expected output:**
```
Tests Passed: 10
Tests Failed: 0

[PASS] All tests passed! Secret detection is working correctly.
```

---

## Step 3: Scan Repository (2 minutes)

```bash
./scripts/security/scan_for_secrets.sh
```

**If secrets found:**
```
[ERROR] ✗ Security issues found!
  ✗ Environment files committed
  ✗ GCP service account keys found

IMMEDIATE ACTIONS REQUIRED:
  1. Rotate all exposed secrets
  2. Remove secrets from git history
  3. Update .gitignore
```

**Action:** Follow `docs/security/SECRET_ROTATION_INCIDENT_RESPONSE.md`

**If clean:**
```
[SUCCESS] ✓ Repository is clean - No secrets detected!
```

---

## Step 4: Test Pre-commit Hook (1 minute)

```bash
# Create test file with secret
echo "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE" > test_secret.txt

# Try to commit (should be blocked)
git add test_secret.txt
git commit -m "test"

# Expected: "Gitleaks Secret Scanner detected secrets"
# Commit blocked! ✓

# Cleanup
rm test_secret.txt
git reset HEAD
```

---

## Step 5: Daily Usage (Automatic)

From now on, every commit is automatically scanned:

```bash
git add .
git commit -m "feat: add new feature"
# → Pre-commit hook runs automatically
# → If secrets found: Commit blocked
# → If clean: Commit succeeds
```

**No manual intervention required!**

---

## 🚨 If Secrets Are Found

### URGENT: 3-Step Response

**1. Don't panic** - Follow the runbook:
```bash
cat docs/security/SECRET_ROTATION_INCIDENT_RESPONSE.md
```

**2. Rotate secrets immediately:**
- Database passwords
- AWS/GCP credentials
- API keys
- Admin passwords

**3. Clean git history:**
```bash
# Install git-filter-repo (if not already)
brew install git-filter-repo

# Remove secret files from ALL history
git filter-repo --invert-paths \
  --path intelliwiz_config/envs/.env.prod.secure \
  --path intelliwiz_config/envs/.env.dev.secure \
  --path sukhi-group-e35476d5ef6e.json \
  --force

# Force push (coordinate with team first!)
git push origin --force --all
```

---

## 📋 Quick Reference

| Command | Purpose | When |
|---------|---------|------|
| `./scripts/security/install_secret_scanners.sh` | Install all tools | One-time setup |
| `./scripts/security/test_secret_detection.sh` | Verify installation | After install |
| `./scripts/security/scan_for_secrets.sh` | Scan for secrets | Daily/weekly |
| `./scripts/security/scan_for_secrets.sh --all` | Scan git history | Before deployment |
| `pre-commit run --all-files` | Test all hooks | After config changes |

---

## ✅ Success Checklist

After completing setup:

- [ ] All tools installed (no errors)
- [ ] Test suite passes (10/10 tests)
- [ ] Pre-commit hooks work (blocks test secrets)
- [ ] Initial scan complete
- [ ] If secrets found: Remediation plan started
- [ ] Team notified of new workflow

---

## 🆘 Common Issues

**"gitleaks: command not found"**
```bash
# macOS
brew install gitleaks

# Linux
wget https://github.com/gitleaks/gitleaks/releases/download/v8.18.1/gitleaks_8.18.1_linux_amd64.tar.gz
tar -xzf gitleaks*.tar.gz
sudo mv gitleaks /usr/local/bin/
```

**"detect-secrets: command not found"**
```bash
pip install detect-secrets
```

**Pre-commit not running**
```bash
pre-commit install
```

---

## 📞 Need Help?

1. **Review README:** `scripts/security/README.md`
2. **Check runbook:** `docs/security/SECRET_ROTATION_INCIDENT_RESPONSE.md`
3. **Security team:** [Contact Info]

---

**Total setup time:** 10 minutes
**Ongoing effort:** Zero (automatic)
**Protection:** Comprehensive (multiple scanners)

**You're all set!** 🎉
