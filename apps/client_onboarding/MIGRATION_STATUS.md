# Client Onboarding Migration Status

**Last Updated**: November 11, 2025
**Module**: `apps.client_onboarding`
**Migration Goal**: Refactor monolithic models.py into focused submodules

---

## Migration Overview

**Original State**: Single models.py file with 15 models
**Target State**: Modular structure with domain-driven organization
**Current Status**: **Phase 1 Complete** (5 of 14 modules implemented)

---

## Phase 1: Core Models (✅ COMPLETE)

### Implemented Modules (5)

| Module | Models | Status | Notes |
|--------|--------|--------|-------|
| **business_unit** | BusinessType, BusinessUnit | ✅ Complete | Core organizational structure |
| **scheduling** | Shift, GeofenceDefinition | ✅ Complete | Shift and geofence management |
| **classification** | SiteClassificationIntent, SiteClassificationResult | ✅ Complete | Site classification with LLM |
| **infrastructure** | ClientSite, MeterReading | ✅ Complete | Client infrastructure tracking |
| **conversational_ai** | ConversationSession, ConversationMessage, UserFeedbackLearning, AuthoritativeKnowledgeChunk | ✅ Complete | Voice/text onboarding conversations |

**Total**: 15 models migrated and working in production

---

## Phase 2+: Advanced Features (📋 PLANNED - Not Implemented)

### Knowledge Base Models (3 modules)

**Status**: ❌ **NOT IMPLEMENTED** - Placeholder only
**Planned Modules**:

1. **knowledge_sources** (Planned)
   - `KnowledgeSource` - Track knowledge ingestion sources
   - `KnowledgeIngestionJob` - Background job tracking

2. **knowledge_content** (Planned)
   - `AuthoritativeKnowledgeEnhanced` - Enhanced knowledge with versioning

3. **knowledge_review** (Planned)
   - `KnowledgeReview` - Human-in-loop review workflow

**Business Case**: Not prioritized - current AuthoritativeKnowledgeChunk sufficient for MVP

---

### Change Tracking Models (3 modules)

**Status**: ❌ **NOT IMPLEMENTED** - Placeholder only
**Planned Modules**:

1. **changesets** (Planned)
   - `AIChangeSet` - Track AI-proposed configuration changes

2. **approvals** (Planned)
   - `ChangeSetApproval` - Multi-level approval workflow

3. **change_records** (Planned)
   - `AIChangeRecord` - Audit trail for AI changes

**Business Case**: Not prioritized - manual review process working well

---

### Personalization Models (3 modules)

**Status**: ❌ **NOT IMPLEMENTED** - Placeholder only
**Planned Modules**:

1. **preferences** (Planned)
   - `PreferenceProfile` - User preference learning

2. **interactions** (Planned)
   - `RecommendationInteraction` - Track recommendation effectiveness

3. **experiments** (Planned)
   - `Experiment` - A/B testing framework
   - `ExperimentAssignment` - User experiment assignments

**Business Case**: Not prioritized - personalization not yet required

---

## Decision: Phase 2+ Work Status

### Current Assessment (Nov 2025)

**Recommendation**: **REMOVE PHASE 2+ PLACEHOLDERS**

**Rationale**:
1. **No Active Development** - Phase 2+ features have not been started since initial migration (6+ months ago)
2. **Working MVP** - Current implementation fully supports business needs
3. **YAGNI Principle** - Building features before they're needed violates best practices
4. **Code Hygiene** - Placeholder TODOs create confusion about system capabilities
5. **Maintenance Cost** - Tracking functions add complexity without value

### What Should Be Done

**Option A: Remove Placeholders (Recommended)**
- Delete commented imports in `models.py:69-85`
- Remove tracking functions (`get_original_model_count`, `get_refactored_modules`, `validate_refactoring`)
- Keep this status document for historical reference
- Re-add modules when business need is confirmed

**Option B: Keep Placeholders (If Phase 2 is Planned)**
- Confirm Phase 2 is actively planned with timeline
- Create project management tickets for each module
- Add estimated delivery dates to this document
- Review quarterly to prevent stale TODOs

**Option C: Archive in Separate Design Doc**
- Move Phase 2+ plans to `docs/plans/client-onboarding-phase2-design.md`
- Clean up production code (remove placeholders)
- Revisit when feature priority changes

---

## Migration Tracking Code

### Current Helper Functions (models.py:87-120)

```python
def get_original_model_count():
    """Return count of models in original monolithic file."""
    return 15  # Total models that were in the original file

def get_refactored_modules():
    """Return list of new model modules created."""
    return [
        'business_unit',
        'scheduling',
        'classification',
        'infrastructure',
        'conversational_ai',
        # 9 commented TODO modules for Phase 2+
    ]

def validate_refactoring():
    """Validate that refactoring maintains data integrity."""
    # Runs django management checks
```

**Purpose**: These functions were scaffolding for the refactoring process.

**Status**: ⚠️ **Can be removed** - Migration is complete, tracking no longer needed

---

## Recommendations

### Immediate Actions (Nov 2025)

1. **Decision Point**: Determine if Phase 2+ work will happen in next 6 months
   - **If YES**: Create proper project plan with timelines
   - **If NO**: Remove placeholders per Option A

2. **Clean Production Code**:
   - Remove commented imports if Phase 2+ not planned
   - Remove tracking functions (migration complete)
   - Keep this status document for reference

3. **Update Documentation**:
   - Mark Phase 1 as "Complete and Production-Ready"
   - Archive Phase 2+ designs if not pursuing
   - Update CLAUDE.md if client_onboarding structure changes

### Future Considerations

**When to Implement Phase 2+**:
- **Knowledge Base**: When knowledge volume exceeds 1000+ chunks and requires versioning
- **Change Tracking**: When AI-proposed changes need formal approval workflow (compliance requirement)
- **Personalization**: When user base exceeds 100+ and A/B testing becomes valuable

**Do NOT implement until**:
- Clear business need identified
- Product team confirms priority
- Resources allocated for implementation and testing

---

## Technical Debt Assessment

**Current State**: ✅ **HEALTHY**

- Phase 1 models are production-ready
- Code is maintainable and well-organized
- No blocking issues or technical debt
- Placeholder TODOs are only cosmetic issue

**Action Required**: Low priority - cleanup recommended but not urgent

---

## References

- **Original Refactoring**: Completed in Phase 1 god file refactoring (2025-Q2)
- **Current Models**: `apps/client_onboarding/models/` (5 modules)
- **Related Systems**: Voice onboarding, site classification, shift management
- **Migration History**: See git log for `apps/client_onboarding/models/`

---

## Version History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-11-11 | 1.0 | Initial migration status document | Ultrathink Code Quality Remediation |

---

**Next Review**: When Phase 2+ work is considered (or Q1 2026 for cleanup decision)
