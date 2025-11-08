# Best Practices Help Center - Quick Start Guide

**Purpose:** Get started with the best practices help center in 5 minutes

**Last Updated:** November 6, 2025

---

## ⚡ Quick Start (5 Minutes)

### Step 1: Load Categories (30 seconds)

```bash
python manage.py loaddata apps/help_center/fixtures/best_practices_articles.json
```

**Expected Output:**
```
Installed 6 object(s) from 1 fixture(s)
```

### Step 2: Import Articles (1 minute)

```bash
python manage.py import_best_practices
```

**Expected Output:**
```
📁 Creating categories...
  ⏭️  Already exists: Best Practices
  ⏭️  Already exists: Security Best Practices
  ...
📄 Importing articles...
  ✅ Created: Best Practices: API Authentication
  ✅ Created: Best Practices: Authorization & IDOR Prevention
  ✅ Created: Best Practices: Database Query Optimization
  ✅ Created: Best Practices: Exception Handling
  ✅ Created: Best Practices: Service Layer Pattern

IMPORT SUMMARY
Categories created: 0 (already exist)
Articles created: 5

✅ Import complete!
```

### Step 3: Generate Embeddings (Optional - 2 minutes)

```bash
python manage.py generate_article_embeddings
```

This enables semantic search for articles.

### Step 4: View Articles (30 seconds)

Visit: `http://localhost:8000/help-center/`

Or browse categories:
- `/help-center/category/security-best-practices/`
- `/help-center/category/performance-best-practices/`
- `/help-center/category/code-quality-best-practices/`

---

## 📚 Available Documentation

### Index & Navigation

| Document | Purpose | Lines |
|----------|---------|-------|
| [BEST_PRACTICES_INDEX.md](BEST_PRACTICES_INDEX.md) | Master index with all articles | 240 |
| [CHECKLISTS.md](CHECKLISTS.md) | 6 comprehensive checklists | 520 |
| [DECISION_TREES.md](DECISION_TREES.md) | 7 visual decision guides | 480 |
| [QUICK_START.md](QUICK_START.md) | This file | 150 |

### Articles (5 Complete)

| ID | Title | Category | Difficulty |
|----|-------|----------|------------|
| BP-SEC-001 | API Authentication | Security | Intermediate |
| BP-SEC-002 | Authorization & IDOR | Security | Advanced |
| BP-PERF-001 | Query Optimization | Performance | Intermediate |
| BP-QUAL-001 | Exception Handling | Code Quality | Beginner |
| BP-ARCH-001 | Service Layer Pattern | Architecture | Advanced |

---

## 🎯 Common Use Cases

### Use Case 1: New Developer Onboarding

**Goal:** Learn Django best practices quickly

**Path:**
1. Read [BP-QUAL-001: Exception Handling](articles/BP-QUAL-001-Exception-Handling.md)
2. Review [Pre-Commit Checklist](CHECKLISTS.md#pre-commit-checklist)
3. Practice with [Exception Decision Tree](DECISION_TREES.md#2-exception-type-selection-tree)

**Time:** 30 minutes

### Use Case 2: Code Review

**Goal:** Ensure PR follows best practices

**Path:**
1. Open [Code Review Checklist](CHECKLISTS.md#code-review-checklist)
2. Reference specific articles when requesting changes
3. Link to decision trees for pattern explanations

**Time:** 10 minutes per PR

### Use Case 3: Security Review

**Goal:** Verify no security vulnerabilities

**Path:**
1. Open [Security Review Checklist](CHECKLISTS.md#security-review-checklist)
2. Read [BP-SEC-002: Authorization & IDOR](articles/BP-SEC-002-Authorization-IDOR.md)
3. Verify SecureFileDownloadService usage

**Time:** 15 minutes

### Use Case 4: Performance Optimization

**Goal:** Fix slow queries

**Path:**
1. Use [Query Optimization Decision Tree](DECISION_TREES.md#1-query-optimization-decision-tree)
2. Read [BP-PERF-001: Query Optimization](articles/BP-PERF-001-Query-Optimization.md)
3. Apply select_related/prefetch_related

**Time:** 20 minutes

### Use Case 5: Refactoring God Files

**Goal:** Split large file into smaller modules

**Path:**
1. Read [BP-ARCH-001: Service Layer](articles/BP-ARCH-001-Service-Layer.md)
2. Use [Refactoring Pattern Decision Tree](DECISION_TREES.md#4-refactoring-pattern-selection)
3. Follow [Refactoring Checklist](CHECKLISTS.md#refactoring-checklist)

**Time:** 1-2 hours per file

---

## 🔍 Search & Discovery

### Keyword Search

**Example searches:**
- "authentication" → BP-SEC-001
- "N+1" → BP-PERF-001
- "exception" → BP-QUAL-001
- "service layer" → BP-ARCH-001
- "IDOR" → BP-SEC-002

### Browse by Category

**Categories:**
- Security Best Practices (5 articles planned)
- Performance Best Practices (4 articles planned)
- Code Quality Best Practices (5 articles planned)
- Testing Best Practices (4 articles planned)
- Architecture Best Practices (3 articles planned)

### Browse by Difficulty

- **Beginner:** BP-QUAL-001
- **Intermediate:** BP-SEC-001, BP-PERF-001
- **Advanced:** BP-SEC-002, BP-ARCH-001

---

## 💡 Quick Tips

### For Developers

**Before every commit:**
```bash
# Run pre-commit checklist
python scripts/validate_code_quality.py --verbose
python scripts/check_file_sizes.py --verbose
pytest --cov=apps -v
```

**When writing queries:**
- ForeignKey in loop? → Use `select_related()`
- ManyToMany in loop? → Use `prefetch_related()`
- Not sure? → Check [Query Decision Tree](DECISION_TREES.md#1-query-optimization-decision-tree)

**When catching exceptions:**
- Database operation? → Use `DATABASE_EXCEPTIONS`
- Network call? → Use `NETWORK_EXCEPTIONS`
- Not sure? → Check [Exception Decision Tree](DECISION_TREES.md#2-exception-type-selection-tree)

### For Reviewers

**Link to articles in PR comments:**
```markdown
This endpoint needs authentication. See:
- [BP-SEC-001: API Authentication](https://docs/help_center/articles/BP-SEC-001-API-Authentication.md)

Please add TokenAuthentication and IsAuthenticated permission class.
```

**Use checklists:**
```markdown
Security Review:
- [ ] Authentication required
- [ ] Authorization validated
- [ ] IDOR tests written

See [Security Review Checklist](https://docs/help_center/CHECKLISTS.md#security-review-checklist)
```

---

## 📊 Verification Commands

### Check Help Center Status

```bash
# Check categories exist
python manage.py shell -c "from apps.help_center.models import HelpCategory; print(f'Categories: {HelpCategory.objects.count()}')"

# Check articles exist
python manage.py shell -c "from apps.help_center.models import HelpArticle; print(f'Articles: {HelpArticle.objects.count()}')"

# List all articles
python manage.py shell -c "from apps.help_center.models import HelpArticle; [print(f'{a.slug}: {a.title}') for a in HelpArticle.objects.all()]"
```

### Test Search

```bash
# Test keyword search (requires search_vector)
python manage.py shell -c "
from apps.help_center.services.search_service import SearchService
results = SearchService.keyword_search('authentication')
print(f'Found {len(results)} articles')
"
```

---

## 🚨 Troubleshooting

### Problem: Categories not created

**Solution:**
```bash
python manage.py loaddata apps/help_center/fixtures/best_practices_articles.json
```

### Problem: Articles not found

**Solution:**
```bash
# Check article files exist
ls -la docs/help_center/articles/

# Re-import articles
python manage.py import_best_practices
```

### Problem: Search not working

**Solution:**
```bash
# Generate search vectors
python manage.py shell -c "
from django.contrib.postgres.search import SearchVector
from apps.help_center.models import HelpArticle

for article in HelpArticle.objects.all():
    article.search_vector = SearchVector('title', weight='A') + SearchVector('summary', weight='B') + SearchVector('content', weight='C')
    article.save()

print('Search vectors generated')
"
```

### Problem: Embeddings missing

**Solution:**
```bash
python manage.py generate_article_embeddings
```

---

## 🔗 Quick Links

### Documentation
- [Master Index](BEST_PRACTICES_INDEX.md)
- [All Checklists](CHECKLISTS.md)
- [Decision Trees](DECISION_TREES.md)
- [Complete Report](HELP_CENTER_BEST_PRACTICES_COMPLETE.md)

### External References
- [.claude/rules.md](../../.claude/rules.md) - Mandatory rules
- [ADRs](../architecture/adr/) - Architecture decisions
- [Refactoring Playbook](../architecture/REFACTORING_PLAYBOOK.md) - Refactoring guide
- [Testing Guide](../testing/TESTING_AND_QUALITY_GUIDE.md) - Testing docs

---

## 📞 Support

**Questions?** Submit a Help Desk ticket with appropriate tag:

- `best-practices-auth` - Authentication questions
- `best-practices-performance` - Performance questions
- `best-practices-exceptions` - Exception handling questions
- `best-practices-refactoring` - Refactoring questions
- `best-practices-general` - General questions

---

## ✅ Success Checklist

After completing quick start, you should be able to:

- [ ] View all best practices categories
- [ ] Read at least 2 best practices articles
- [ ] Use at least 1 decision tree
- [ ] Complete pre-commit checklist
- [ ] Search for articles by keyword
- [ ] Link to articles in code reviews

**Time to complete:** 15-30 minutes

---

**Next:** Read [BEST_PRACTICES_INDEX.md](BEST_PRACTICES_INDEX.md) for complete article catalog
