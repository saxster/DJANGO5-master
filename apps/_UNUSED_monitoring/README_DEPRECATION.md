# ⚠️ DEPRECATED: Monitoring App

## Status: **UNUSED / NOT REGISTERED**

This directory contains an **unused monitoring application** that was never integrated into the project.

### Why Deprecated?

1. **Not Registered**: Never added to `INSTALLED_APPS`
2. **No Migrations**: No database migrations exist (never used in production)
3. **Zero External References**: All imports are self-referencing (22 files, all within this directory)
4. **Superseded**: Functionality replaced by `apps/noc/` (Network Operations Center)

### Namespace Collision Issue

This app caused a **critical namespace collision**:
- Top-level `monitoring/` app registered as `'monitoring'` in INSTALLED_APPS
- This app tried to register as `'apps.monitoring'` but was never added
- Created import confusion and potential runtime errors

### Functionality Overview

Intended to provide:
- Device health monitoring (engines/: activity, battery, network, performance, security)
- Alert management (models/alert_models.py)
- Ticket integration (models/ticket_models.py)
- Real-time monitoring via WebSockets (consumers/)
- Background tasks (tasks/monitoring_tasks.py)

### Current Solution

**Active Monitoring Systems:**
- `apps/noc/` - Network Operations Center (registered, 1,616 lines, production-ready)
- Top-level `monitoring/` - Production performance monitoring (registered, 2,540 lines)

### Disposition

**Directory renamed from `apps/monitoring/` → `apps/_UNUSED_monitoring/`** on 2025-09-30

**Options:**
1. **Delete entirely** after 1 sprint cycle if no issues arise
2. **Merge useful patterns** into `apps/noc/` if features are needed
3. **Keep as reference** for future monitoring enhancements

### Related Documentation

- NOC Implementation: `NOC_PHASE6_IMPLEMENTATION_COMPLETE.md`
- Code Quality Fixes: See remediation plan for namespace collision resolution

---

**Last Review:** 2025-09-30
**Decision:** Preserve temporarily, delete after verification period
**Contact:** Architecture team for questions