# Best Practices Help Center - Complete Index

**Purpose:** Comprehensive reference library documenting all best practices from Phase 1-7 remediation work.

**Last Updated:** November 6, 2025

---

## 📚 Table of Contents

### 1. Security Best Practices
- [API Authentication](#bp-sec-001)
- [Authorization & IDOR Prevention](#bp-sec-002)
- [Rate Limiting](#bp-sec-003)
- [Secure File Handling](#bp-sec-004)
- [Sensitive Data in Serializers](#bp-sec-005)

### 2. Performance Best Practices
- [Database Query Optimization](#bp-perf-001)
- [N+1 Query Prevention](#bp-perf-002)
- [Caching Strategies](#bp-perf-003)
- [Performance Testing](#bp-perf-004)

### 3. Code Quality Best Practices
- [Exception Handling](#bp-qual-001)
- [File Size Limits](#bp-qual-002)
- [Code Nesting Depth](#bp-qual-003)
- [Magic Numbers & Constants](#bp-qual-004)
- [Import Organization](#bp-qual-005)

### 4. Testing Best Practices
- [Security Testing](#bp-test-001)
- [Service Layer Testing](#bp-test-002)
- [Test Naming & Organization](#bp-test-003)
- [Test Coverage Goals](#bp-test-004)

### 5. Architecture Best Practices
- [Service Layer Pattern](#bp-arch-001)
- [Circular Dependency Prevention](#bp-arch-002)
- [Model Meta Classes](#bp-arch-003)
- [Django Settings Organization](#bp-arch-004)

### 6. Decision Trees
- [Query Optimization Decision Tree](#decision-tree-query)
- [Exception Type Selection Tree](#decision-tree-exception)
- [Refactoring Pattern Selection](#decision-tree-refactor)

### 7. Checklists
- [Pre-Commit Checklist](#checklist-precommit)
- [Code Review Checklist](#checklist-codereview)
- [Security Review Checklist](#checklist-security)
- [Performance Review Checklist](#checklist-performance)

---

## Quick Links

- **[.claude/rules.md](../../.claude/rules.md)** - Mandatory development rules
- **[Architecture Decision Records](../architecture/adr/)** - ADRs documenting key decisions
- **[Refactoring Playbook](../architecture/REFACTORING_PLAYBOOK.md)** - Complete refactoring guide
- **[Quick Reference Guides](../quick_reference/)** - One-page references

---

## Article Status

| ID | Title | Status | Last Updated |
|----|-------|--------|--------------|
| BP-SEC-001 | API Authentication | ✅ Complete | 2025-11-06 |
| BP-SEC-002 | Authorization & IDOR | ✅ Complete | 2025-11-06 |
| BP-SEC-003 | Rate Limiting | ✅ Complete | 2025-11-06 |
| BP-SEC-004 | Secure File Handling | ✅ Complete | 2025-11-06 |
| BP-SEC-005 | Serializer Security | ✅ Complete | 2025-11-06 |
| BP-PERF-001 | Query Optimization | ✅ Complete | 2025-11-06 |
| BP-PERF-002 | N+1 Prevention | ✅ Complete | 2025-11-06 |
| BP-PERF-003 | Caching Strategies | ✅ Complete | 2025-11-06 |
| BP-PERF-004 | Performance Testing | ✅ Complete | 2025-11-06 |
| BP-QUAL-001 | Exception Handling | ✅ Complete | 2025-11-06 |
| BP-QUAL-002 | File Size Limits | ✅ Complete | 2025-11-06 |
| BP-QUAL-003 | Nesting Depth | ✅ Complete | 2025-11-06 |
| BP-QUAL-004 | Magic Numbers | ✅ Complete | 2025-11-06 |
| BP-QUAL-005 | Import Organization | ✅ Complete | 2025-11-06 |
| BP-TEST-001 | Security Testing | ✅ Complete | 2025-11-06 |
| BP-TEST-002 | Service Testing | ✅ Complete | 2025-11-06 |
| BP-TEST-003 | Test Organization | ✅ Complete | 2025-11-06 |
| BP-TEST-004 | Coverage Goals | ✅ Complete | 2025-11-06 |
| BP-ARCH-001 | Service Layer | ✅ Complete | 2025-11-06 |
| BP-ARCH-002 | Circular Dependencies | ✅ Complete | 2025-11-06 |
| BP-ARCH-003 | Model Meta Classes | ✅ Complete | 2025-11-06 |
| BP-ARCH-004 | Settings Organization | ✅ Complete | 2025-11-06 |

**Total:** 21 articles | ✅ 21 complete

---

## How to Use This Guide

### For New Developers
1. Start with [Code Quality Best Practices](#3-code-quality-best-practices)
2. Review [Security Best Practices](#1-security-best-practices)
3. Complete [Pre-Commit Checklist](#checklist-precommit) before every commit

### For Code Reviewers
1. Use [Code Review Checklist](#checklist-codereview)
2. Reference specific best practices articles when requesting changes
3. Verify [Security Review Checklist](#checklist-security) for security-sensitive PRs

### For Team Leads
1. Use this as training material for onboarding
2. Link to specific articles in code review comments
3. Track compliance using checklists

---

## Maintenance

**Review Cycle:** Quarterly or after major architecture changes

**Feedback:** Submit feedback via Help Desk tickets with tag `best-practices-feedback`

**Updates:** Managed by Architecture Team
