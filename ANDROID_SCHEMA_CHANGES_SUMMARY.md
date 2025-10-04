# 📱 Android-Kotlin Schema Changes - Executive Summary

**Date:** 2025-10-03
**Priority:** 🔴 **CRITICAL REVIEW REQUIRED**
**Impact:** 🟡 Backward compatible for 2 releases, then BREAKING

---

## 🎯 TL;DR - What Android Team MUST Know

**Total Schema Changes:** **17 changes** across 4 models + GraphQL responses

**Breaking Changes:** **NONE** for 2 releases (8-12 weeks), then **6 breaking changes**

**Effort Required:** **8-11 developer-days** spread over 3 releases

**Immediate Action:** **NONE** - existing app works unchanged ✅

**Action Required By Release N+1:** Add 17 new fields (all nullable)

**Action Required By Release N+2:** Complete migration to new fields

**Breaking Changes in Release N+3:** Old fields removed - app MUST be migrated

---

## 📊 17 SCHEMA CHANGES - COMPLETE LIST

### 🔵 Category 1: NEW FIELDS (6 changes)

**All are nullable - won't crash if null**

| # | Model | Field Name | Type | Nullable | Release | Priority |
|---|-------|------------|------|----------|---------|----------|
| 1 | Question | `options_json` | List<String> | ✅ Yes | N | 🔴 Critical |
| 2 | Question | `alert_config` | AlertConfig | ✅ Yes | N | 🔴 Critical |
| 3 | QuestionSetBelonging | `options_json` | List<String> | ✅ Yes | N | 🔴 Critical |
| 4 | QuestionSetBelonging | `alert_config` | AlertConfig | ✅ Yes | N | 🔴 Critical |
| 5 | DisplayConditions | `cascade_hide` | Boolean | ✅ Yes (default false) | N | 🟡 High |
| 6 | DisplayConditions | `group` | String | ✅ Yes | N | 🟢 Medium |

**Android Action:** Add these 6 fields to Kotlin models in Release N+1

---

### 🟠 Category 2: STRUCTURE CHANGES (4 changes)

**Backward compatible - both old and new keys present**

| # | Location | Old Key | New Key | Both Present? | Release | Priority |
|---|----------|---------|---------|---------------|---------|----------|
| 7 | Dependency | `question_id` | `qsb_id` | ✅ Yes (N, N+1, N+2) | N | 🔴 Critical |
| 8 | DependencyInfo | N/A | `cascade_hide` | N/A | N | 🟡 High |
| 9 | DependencyInfo | N/A | `group` | N/A | N | 🟢 Medium |
| 10 | GraphQL Response | N/A | `validation_warnings` | N/A | N | 🟡 High |

**Android Action:** Update parsing to support both formats

---

### ⚠️ Category 3: DEPRECATED FIELDS (4 changes)

**Still present but will be removed in Release N+3**

| # | Model | Field Name | Removal Release | Must Migrate By | Priority |
|---|-------|------------|-----------------|-----------------|----------|
| 11 | Question | `options` (text) | N+3 | N+2 | 🔴 Critical |
| 12 | Question | `alerton` (text) | N+3 | N+2 | 🔴 Critical |
| 13 | QuestionSetBelonging | `options` (text) | N+3 | N+2 | 🔴 Critical |
| 14 | QuestionSetBelonging | `alerton` (text) | N+3 | N+2 | 🔴 Critical |

**Android Action:** Stop using these by Release N+2 (8-12 weeks)

---

### 🆕 Category 4: ENUM ADDITIONS (3 changes)

**New enum values - backward compatible**

| # | Enum | New Values | Count | Optional? | Release | Priority |
|---|------|------------|-------|-----------|---------|----------|
| 15 | ConditionalOperator | NOT_CONTAINS, NOT_IN, GTE, LTE, IS_EMPTY, IS_NOT_EMPTY | +6 | ✅ Yes | N | 🟢 Medium |
| 16 | AnswerType | (None - all existed) | 0 | - | N | ✅ No change |
| 17 | AvptType | (None) | 0 | - | N | ✅ No change |

**Android Action:** Add new operator support (optional but recommended)

---

## 🎯 ANDROID DEVELOPER ACTION PLAN

### ✅ **Release N (Current) - TEST ONLY**

**Time Required:** 4-6 hours

**Checklist:**
- [ ] Pull latest staging backend
- [ ] Run all existing Android tests → Should pass ✅
- [ ] Manual testing on staging:
  - [ ] View all question types (numeric, dropdown, checkbox, etc.)
  - [ ] Submit answers for all question types
  - [ ] Test conditional logic (show/hide questions)
  - [ ] Test question sets with 50+ questions
  - [ ] Test offline sync
- [ ] Check for null pointer exceptions on new fields
- [ ] Verify GraphQL queries still work
- [ ] **No code changes required** ✅

**Deliverable:** Test report confirming compatibility

---

### 🔴 **Release N+1 (Next 4-6 Weeks) - ADD NEW FIELDS**

**Time Required:** 5-8 developer-days

#### Phase 1: Update Models (Day 1-2)

**File:** `app/src/main/java/com/yourapp/models/Question.kt`

```kotlin
@Serializable
data class Question(
    val id: Int,
    val quesname: String,
    val answertype: AnswerType,

    // ⚠️ KEEP OLD FIELDS (deprecated)
    @SerializedName("options")
    val optionsLegacy: String? = null,

    @SerializedName("alerton")
    val alertonLegacy: String? = null,

    // 🆕 ADD NEW FIELDS
    @SerializedName("options_json")
    val optionsJson: List<String>? = null,

    @SerializedName("alert_config")
    val alertConfig: AlertConfig? = null,

    // ... rest of fields unchanged
    val min: Double?,
    val max: Double?,
    val isavpt: Boolean,
    val avpttype: AvptType?,
    val client_id: Int,
    val created_at: String,
    val updated_at: String
)
```

**Checklist:**
- [ ] Add `optionsJson` to Question.kt
- [ ] Add `alertConfig` to Question.kt
- [ ] Add `optionsJson` to QuestionSetBelonging.kt
- [ ] Add `alertConfig` to QuestionSetBelonging.kt
- [ ] Create `AlertConfig.kt` data class
- [ ] Create `NumericAlert.kt` data class

**Files to Modify:** 3 files
**Lines Changed:** ~50 lines

---

#### Phase 2: Create AlertConfig Classes (Day 1)

**File:** `app/src/main/java/com/yourapp/models/AlertConfig.kt` (**NEW**)

```kotlin
package com.yourapp.models

import kotlinx.serialization.SerializedName
import kotlinx.serialization.Serializable

@Serializable
data class AlertConfig(
    val numeric: NumericAlert? = null,
    val choice: List<String>? = null,
    val enabled: Boolean = false
)

@Serializable
data class NumericAlert(
    val below: Double? = null,
    val above: Double? = null
)
```

**Checklist:**
- [ ] Create AlertConfig.kt file
- [ ] Add serialization annotations
- [ ] Write unit tests for deserialization

**Files to Create:** 1 file
**Lines Added:** ~20 lines

---

#### Phase 3: Update DisplayConditions (Day 2)

**File:** `app/src/main/java/com/yourapp/models/DisplayConditions.kt`

```kotlin
@Serializable
data class DisplayConditions(
    @SerializedName("depends_on")
    val dependsOn: Dependency? = null,

    @SerializedName("show_if")
    val showIf: Boolean = true,

    // 🆕 ADD NEW FIELDS
    @SerializedName("cascade_hide")
    val cascadeHide: Boolean = false,

    val group: String? = null
)

@Serializable
data class Dependency(
    // 🆕 NEW (preferred)
    @SerializedName("qsb_id")
    val qsbId: Int? = null,

    // ⚠️ OLD (backward compat)
    @SerializedName("question_id")
    val questionId: Int? = null,

    val operator: ConditionalOperator,
    val values: List<String>
) {
    // Helper: Support both keys
    fun getId(): Int = qsbId ?: questionId ?: 0
}
```

**Checklist:**
- [ ] Add `qsbId` to Dependency
- [ ] Keep `questionId` for backward compat
- [ ] Add `getId()` helper method
- [ ] Add `cascadeHide` to DisplayConditions
- [ ] Add `group` to DisplayConditions
- [ ] Test with both qsbId and questionId present

**Files to Modify:** 1 file
**Lines Changed:** ~15 lines

---

#### Phase 4: Add ConditionalOperator Values (Day 2)

**File:** `app/src/main/java/com/yourapp/enums/ConditionalOperator.kt`

```kotlin
enum class ConditionalOperator {
    // EXISTING (no changes)
    EQUALS,
    NOT_EQUALS,
    CONTAINS,
    IN,
    GT,
    LT,

    // 🆕 ADD THESE (Release N+1)
    NOT_CONTAINS,
    NOT_IN,
    GTE,
    LTE,
    IS_EMPTY,
    IS_NOT_EMPTY;

    // Update evaluation logic to handle new operators
    fun evaluate(value: Any, comparisonValues: List<String>): Boolean {
        return when (this) {
            // ... existing logic ...
            NOT_CONTAINS -> !(value.toString().contains(comparisonValues.firstOrNull() ?: ""))
            NOT_IN -> value.toString() !in comparisonValues
            GTE -> (value as? Number)?.toDouble()?.let { it >= comparisonValues.firstOrNull()?.toDoubleOrNull() ?: 0.0 } ?: false
            LTE -> (value as? Number)?.toDouble()?.let { it <= comparisonValues.firstOrNull()?.toDoubleOrNull() ?: 0.0 } ?: false
            IS_EMPTY -> value.toString().isEmpty()
            IS_NOT_EMPTY -> value.toString().isNotEmpty()
        }
    }
}
```

**Checklist:**
- [ ] Add 6 new enum values
- [ ] Implement evaluation logic for each
- [ ] Test each operator with sample data
- [ ] Handle unknown operators gracefully

**Files to Modify:** 1 file
**Lines Changed:** ~30 lines

---

#### Phase 5: Add ValidationWarning Support (Day 3)

**File:** `app/src/main/java/com/yourapp/models/ValidationWarning.kt` (**NEW**)

```kotlin
@Serializable
data class ValidationWarning(
    @SerializedName("question_id")
    val questionId: Int,

    val warning: String,
    val severity: String  // "error", "warning", "critical"
)

// Update response model
@Serializable
data class ConditionalLogicResponse(
    val questions: List<QuestionSetBelonging>,

    @SerializedName("dependency_map")
    val dependencyMap: Map<String, List<DependencyInfo>>,  // Note: Key is String (ID as string)

    @SerializedName("has_conditional_logic")
    val hasConditionalLogic: Boolean,

    // 🆕 ADD THIS
    @SerializedName("validation_warnings")
    val validationWarnings: List<ValidationWarning>? = null
)
```

**Checklist:**
- [ ] Create ValidationWarning.kt
- [ ] Add to ConditionalLogicResponse
- [ ] Add UI to display warnings (dialog or toast)
- [ ] Log warnings for debugging
- [ ] Test with responses containing warnings

**Files to Create:** 1 file
**Files to Modify:** 1 file
**Lines Added:** ~40 lines

---

#### Phase 6: Create Compatibility Layer (Day 3-4)

**File:** `app/src/main/java/com/yourapp/extensions/QuestionExtensions.kt` (**NEW**)

```kotlin
package com.yourapp.extensions

import com.yourapp.models.Question
import com.yourapp.models.QuestionSetBelonging

/**
 * Get options list - prefers JSON, falls back to text parsing.
 * Use this method everywhere instead of direct field access.
 */
fun Question.getOptions(): List<String> {
    return optionsJson ?: optionsLegacy?.split(",")?.map { it.trim() } ?: emptyList()
}

fun QuestionSetBelonging.getOptions(): List<String> {
    return optionsJson ?: optionsLegacy?.split(",")?.map { it.trim() } ?: emptyList()
}

/**
 * Get numeric alert below threshold - prefers structured config.
 */
fun Question.getAlertBelow(): Double? {
    return alertConfig?.numeric?.below ?: parseAlertBelow(alertonLegacy)
}

fun QuestionSetBelonging.getAlertBelow(): Double? {
    return alertConfig?.numeric?.below ?: parseAlertBelow(alertonLegacy)
}

/**
 * Get numeric alert above threshold - prefers structured config.
 */
fun Question.getAlertAbove(): Double? {
    return alertConfig?.numeric?.above ?: parseAlertAbove(alertonLegacy)
}

fun QuestionSetBelonging.getAlertAbove(): Double? {
    return alertConfig?.numeric?.above ?: parseAlertAbove(alertonLegacy)
}

/**
 * Get choice alert values (for dropdown/checkbox).
 */
fun Question.getAlertChoices(): List<String> {
    return alertConfig?.choice ?: alertonLegacy?.split(",")?.map { it.trim() } ?: emptyList()
}

fun QuestionSetBelonging.getAlertChoices(): List<String> {
    return alertConfig?.choice ?: alertonLegacy?.split(",")?.map { it.trim() } ?: emptyList()
}

// Legacy parsers (REMOVE in Release N+3)
private fun parseAlertBelow(alerton: String?): Double? {
    val match = Regex("<\\s*([0-9.]+)").find(alerton ?: "")
    return match?.groupValues?.getOrNull(1)?.toDoubleOrNull()
}

private fun parseAlertAbove(alerton: String?): Double? {
    val match = Regex(">\\s*([0-9.]+)").find(alerton ?: "")
    return match?.groupValues?.getOrNull(1)?.toDoubleOrNull()
}
```

**Checklist:**
- [ ] Create QuestionExtensions.kt file
- [ ] Implement all 6 helper methods
- [ ] Write unit tests for each method
- [ ] Test with null values
- [ ] Test with both old and new data formats

**Files to Create:** 1 file
**Lines Added:** ~80 lines

---

#### Phase 7: Update All Code References (Day 4-6)

**Search and Replace:**

```kotlin
// ❌ FIND all instances of:
question.options?.split(",")
question.alerton
belonging.options?.split(",")
dependency.questionId

// ✅ REPLACE with:
question.getOptions()
question.getAlertBelow() / question.getAlertAbove()
belonging.getOptions()
dependency.getId()
```

**Checklist:**
- [ ] Search codebase for `.options?.split` → Replace with `.getOptions()`
- [ ] Search for `.alerton` → Replace with `.getAlertBelow()` or `.getAlertChoices()`
- [ ] Search for `.questionId` in Dependency → Replace with `.getId()`
- [ ] Update all UI components rendering questions
- [ ] Update all form submission code
- [ ] Update all validation code

**Files to Modify:** 15-25 files (estimate)
**Lines Changed:** 100-200 lines (estimate)

---

#### Phase 8: Testing (Day 7-8)

**Checklist:**
- [ ] Write 35 unit tests (compatibility layer)
- [ ] Write 20 integration tests (rendering + logic)
- [ ] Run all existing tests → Should pass
- [ ] Test with staging data (mixed old/new)
- [ ] Test with production-like data
- [ ] Performance testing
- [ ] Memory leak testing
- [ ] UI testing on various devices

**Test Scenarios:**
- [ ] Question with only optionsJson (new data)
- [ ] Question with only options text (old data)
- [ ] Question with both (transition state)
- [ ] Question with neither (edge case)
- [ ] Numeric with alertConfig
- [ ] Numeric with alerton text
- [ ] Conditional logic with qsbId
- [ ] Conditional logic with questionId
- [ ] Validation warnings present
- [ ] Validation warnings absent

---

### 🔴 **Release N+2 (8-12 Weeks) - COMPLETE MIGRATION**

**Time Required:** 3-5 developer-days

**Checklist:**
- [ ] Remove all compatibility layer methods
- [ ] Use `optionsJson` directly (not helper)
- [ ] Use `alertConfig` directly (not helper)
- [ ] Use `qsbId` directly (not helper)
- [ ] Remove deprecated field references
- [ ] Full regression testing
- [ ] Update minimum API version requirements

---

## 🔢 SCHEMA CHANGE QUICK REFERENCE

### Count by Model:

| Model | New Fields | Deprecated Fields | Structure Changes | Total |
|-------|-----------|-------------------|-------------------|-------|
| Question | 2 | 2 | 0 | 4 |
| QuestionSetBelonging | 2 | 2 | 0 | 4 |
| DisplayConditions | 2 | 0 | 1 (qsbId) | 3 |
| Dependency | 1 (qsbId) | 1 (questionId) | 0 | 2 |
| GraphQL Response | 1 (validation_warnings) | 0 | 0 | 1 |
| Enums | 6 (operators) | 0 | 0 | 6 |
| **TOTAL** | **14** | **5** | **1** | **20** |

### Count by Priority:

| Priority | Count | Description |
|----------|-------|-------------|
| 🔴 Critical | 8 | Must handle in Release N+1 |
| 🟡 High | 6 | Should handle in Release N+1 |
| 🟢 Medium | 6 | Nice to have |
| **TOTAL** | **20** | - |

---

## ⚠️ BREAKING CHANGES SCHEDULE

### Release N+3 (6+ Months)

**These fields WILL BE REMOVED:**

1. ❌ `Question.options` (text field)
2. ❌ `Question.alerton` (text field)
3. ❌ `QuestionSetBelonging.options` (text field)
4. ❌ `QuestionSetBelonging.alerton` (text field)
5. ❌ `display_conditions.depends_on.question_id` (only qsb_id remains)

**Android app MUST be updated by then or it WILL CRASH!**

**Mitigation:**
- Minimum app version enforcement
- Force update for old app versions
- Deprecation warnings in Release N+2

---

## 📋 MANDATORY REVIEW CHECKLIST

**Before starting Android work:**

- [ ] Read this document completely
- [ ] Read `docs/mobile-api/QUESTION_SCHEMA_MIGRATION.md` (detailed guide)
- [ ] Review `ANDROID_SCHEMA_CHANGES_CHECKLIST.md` (task breakdown)
- [ ] Schedule migration planning meeting with backend team
- [ ] Estimate effort for your team (5-8 days suggested)
- [ ] Plan timeline (spread over 3 releases)
- [ ] Allocate resources

**Before Release N+1 deployment:**

- [ ] All models updated with new fields
- [ ] Compatibility layer implemented
- [ ] 55+ tests written and passing
- [ ] Manual testing complete
- [ ] Code review complete
- [ ] QA sign-off received

**Before Release N+2 deployment:**

- [ ] Migration to new fields 100% complete
- [ ] No references to deprecated fields
- [ ] Compatibility layer removed
- [ ] Full regression testing complete

---

## 📞 CRITICAL CONTACTS

**Questions about schema changes:**
- Backend lead: backend-team@company.com
- Slack: #mobile-backend-migration
- Documentation: `docs/mobile-api/QUESTION_SCHEMA_MIGRATION.md`

**Report issues:**
- JIRA: MOBILE-BACKEND project
- Critical bugs: PagerDuty on-call

**Testing support:**
- Staging GraphQL: `https://staging.yourapp.com/api/graphql/`
- GraphiQL explorer: Available in browser
- Test data: Contact backend team

---

## ✅ FINAL SUMMARY FOR ANDROID TEAM

**TOTAL SCHEMA CHANGES: 17** (20 if counting deprecated separately)

**IMMEDIATE IMPACT: ZERO** ✅
- Existing app works unchanged
- Test on staging recommended

**RELEASE N+1 WORK: 5-8 DAYS**
- Add 14 new fields (all nullable)
- Create 3 new data classes
- Build compatibility layer
- Write 55 tests

**RELEASE N+2 WORK: 3-5 DAYS**
- Complete migration
- Remove compatibility layer
- Full testing

**BREAKING CHANGES: Release N+3 (6+ months)**
- Must be fully migrated by then

**RISK LEVEL: 🟡 MEDIUM**
- Backward compatible for 2 releases
- Clear migration path
- Comprehensive documentation

---

**Review this document with your team and schedule migration work!** 🚀
