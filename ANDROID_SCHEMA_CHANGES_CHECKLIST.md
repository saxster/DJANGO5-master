# 🚨 ANDROID-KOTLIN SCHEMA CHANGES CHECKLIST

**Critical:** This document lists EVERY schema change that requires Android code updates.
**Date:** 2025-10-03
**Impact Level:** 🟡 **MEDIUM** - No immediate breaking changes, migration required by Release N+2

---

## ⚠️ CRITICAL: Timeline Summary

| Release | Android Changes Required | Risk Level | Deadline |
|---------|-------------------------|------------|----------|
| **Release N** (Current) | ✅ NONE - Test only | 🟢 Low | Now |
| **Release N+1** (Next) | 🟡 Add nullable fields to models | 🟡 Medium | 4-6 weeks |
| **Release N+2** (Future) | 🔴 Complete migration to new fields | 🔴 High | 8-12 weeks |
| **Release N+3** (Future) | ⛔ Old fields removed - MUST be migrated | ⛔ Critical | 6+ months |

---

## 📊 Schema Change Categories

### 🔵 Category A: NEW FIELDS (Nullable, Non-Breaking)
**Impact:** Add to models, handle null gracefully
**Timeline:** Release N+1
**Risk:** 🟢 Low (nullable, backward compatible)

### 🟠 Category B: FIELD STRUCTURE CHANGES (Backward Compatible)
**Impact:** Update parsing logic, support both formats
**Timeline:** Release N+1
**Risk:** 🟡 Medium (requires careful migration)

### 🟡 Category C: DEPRECATED FIELDS (Still Present)
**Impact:** Plan migration away from these fields
**Timeline:** Release N+2
**Risk:** 🟡 Medium (will be removed in N+3)

### 🔴 Category D: ENUM/VALIDATION CHANGES
**Impact:** Update validation logic, handle new error responses
**Timeline:** Release N+1
**Risk:** 🟢 Low (additions only, no removals)

---

## 📋 COMPREHENSIVE SCHEMA CHANGE LIST

### 1️⃣ **Question Model Schema Changes**

#### 🔵 NEW FIELDS (Add to Kotlin Model)

```kotlin
data class Question(
    // ... existing fields ...

    // 🆕 ADD THESE FIELDS (Release N+1):
    @SerializedName("options_json")
    val optionsJson: List<String>? = null,  // ⚠️ Can be null initially

    @SerializedName("alert_config")
    val alertConfig: AlertConfig? = null    // ⚠️ Can be null initially
)

// 🆕 NEW DATA CLASS (Release N+1):
@Serializable
data class AlertConfig(
    val numeric: NumericAlert? = null,
    val choice: List<String>? = null,
    val enabled: Boolean = false
)

// 🆕 NEW DATA CLASS (Release N+1):
@Serializable
data class NumericAlert(
    val below: Double? = null,
    val above: Double? = null
)
```

**Android Action Items:**
- [ ] Add `optionsJson: List<String>?` field to Question model
- [ ] Add `alertConfig: AlertConfig?` field to Question model
- [ ] Create `AlertConfig` data class
- [ ] Create `NumericAlert` data class
- [ ] Handle null values gracefully (use old fields as fallback)
- [ ] Add unit tests for null handling

#### 🟡 DEPRECATED FIELDS (Keep But Plan to Remove)

```kotlin
// ⚠️ KEEP for backward compat, but plan to remove in Release N+3:
@SerializedName("options")
val options: String? = null  // Will be removed in N+3

@SerializedName("alerton")
val alerton: String? = null  // Will be removed in N+3
```

**Android Action Items:**
- [ ] Keep existing fields in model (Release N, N+1, N+2)
- [ ] Create migration strategy to stop using these by Release N+2
- [ ] Add deprecation comments in code
- [ ] Plan removal for Release N+3

#### 📊 Field Comparison Table

| Field Name | Old Type | New Type | Nullable | Present in Release N | Present in Release N+3 |
|------------|----------|----------|----------|---------------------|----------------------|
| `options` | String | String | Yes | ✅ Yes | ❌ **Removed** |
| `alerton` | String | String | Yes | ✅ Yes | ❌ **Removed** |
| `options_json` | N/A | List<String> | Yes | ✅ **NEW** | ✅ Yes |
| `alert_config` | N/A | AlertConfig | Yes | ✅ **NEW** | ✅ Yes |
| `quesname` | String | String | No | ✅ Yes | ✅ Yes (unchanged) |
| `answertype` | String (enum) | String (enum) | No | ✅ Yes | ✅ Yes (unchanged) |
| `min` | Double | Double | Yes | ✅ Yes | ✅ Yes (unchanged) |
| `max` | Double | Double | Yes | ✅ Yes | ✅ Yes (unchanged) |
| `isavpt` | Boolean | Boolean | No | ✅ Yes | ✅ Yes (unchanged) |
| `avpttype` | String (enum) | String (enum) | Yes | ✅ Yes | ✅ Yes (unchanged) |

**Key Insight:** ✅ **NO existing fields changed type** - only additions!

---

### 2️⃣ **QuestionSetBelonging Model Schema Changes**

#### 🔵 NEW FIELDS (Add to Kotlin Model)

```kotlin
data class QuestionSetBelonging(
    // ... existing fields ...

    // 🆕 ADD THESE FIELDS (Release N+1):
    @SerializedName("options_json")
    val optionsJson: List<String>? = null,

    @SerializedName("alert_config")
    val alertConfig: AlertConfig? = null  // Same AlertConfig class as Question
)
```

**Android Action Items:**
- [ ] Add `optionsJson: List<String>?` field to QuestionSetBelonging model
- [ ] Add `alertConfig: AlertConfig?` field to QuestionSetBelonging model
- [ ] Reuse `AlertConfig` and `NumericAlert` classes from Question
- [ ] Handle null values (fallback to old fields)
- [ ] Update all references to options/alerton

#### 🟡 DEPRECATED FIELDS

```kotlin
// ⚠️ KEEP for backward compat:
@SerializedName("options")
val options: String? = null  // Will be removed in N+3

@SerializedName("alerton")
val alerton: String? = null  // Will be removed in N+3
```

#### 📊 Field Comparison Table

| Field Name | Old Type | New Type | Nullable | Present in N | Present in N+3 |
|------------|----------|----------|----------|--------------|----------------|
| `options` | String | String | Yes | ✅ Yes | ❌ **Removed** |
| `alerton` | String | String | Yes | ✅ Yes | ❌ **Removed** |
| `options_json` | N/A | List<String> | Yes | ✅ **NEW** | ✅ Yes |
| `alert_config` | N/A | AlertConfig | Yes | ✅ **NEW** | ✅ Yes |
| `qset_id` | Int | Int | No | ✅ Yes | ✅ Yes (unchanged) |
| `question_id` | Int | Int | No | ✅ Yes | ✅ Yes (unchanged) |
| `answertype` | String | String | No | ✅ Yes | ✅ Yes (unchanged) |
| `seqno` | Int | Int | No | ✅ Yes | ✅ Yes (unchanged) |
| `ismandatory` | Boolean | Boolean | No | ✅ Yes | ✅ Yes (unchanged) |
| `display_conditions` | JSON | JSON | Yes | ✅ Yes | ✅ Yes (structure changed - see below) |

---

### 3️⃣ **display_conditions Field Structure Changes**

#### 🟠 CRITICAL: Key Name Change (Backward Compatible)

**The Problem:**
```kotlin
// OLD (MISLEADING - but still present):
data class Dependency(
    @SerializedName("question_id")
    val questionId: Int  // ⚠️ Actually holds QuestionSetBelonging ID, not Question ID!
)
```

**The Fix:**
```kotlin
// NEW (CORRECT naming):
data class Dependency(
    @SerializedName("qsb_id")
    val qsbId: Int? = null,  // ✅ Correct: QuestionSetBelonging ID

    @SerializedName("question_id")
    val questionId: Int? = null  // ⚠️ Backward compat: Same value as qsbId

) {
    // Helper: Support both keys
    fun getId(): Int = qsbId ?: questionId ?: 0
}
```

#### 🔵 NEW FIELDS in display_conditions

```kotlin
data class DisplayConditions(
    val dependsOn: Dependency? = null,
    val showIf: Boolean = true,

    // 🆕 NEW FIELDS (Release N):
    @SerializedName("cascade_hide")
    val cascadeHide: Boolean = false,  // NEW: Hide dependent questions if hidden

    val group: String? = null  // NEW: Group identifier for related questions
)
```

#### 📊 display_conditions Structure Comparison

**OLD Structure (Still works):**
```json
{
  "depends_on": {
    "question_id": 123,
    "operator": "EQUALS",
    "values": ["Yes"]
  },
  "show_if": true
}
```

**NEW Structure (Preferred):**
```json
{
  "depends_on": {
    "qsb_id": 123,           // 🆕 NEW key (preferred)
    "question_id": 123,       // ⚠️ OLD key (still present, same value)
    "operator": "EQUALS",
    "values": ["Yes"]
  },
  "show_if": true,
  "cascade_hide": false,      // 🆕 NEW field
  "group": "labour_work"      // 🆕 NEW field
}
```

**Android Action Items:**
- [ ] Update `Dependency` model to include `qsbId` field
- [ ] Keep `questionId` field for backward compatibility
- [ ] Add helper method `getId()` to support both keys
- [ ] Add `cascadeHide` field to DisplayConditions
- [ ] Add `group` field to DisplayConditions
- [ ] Update conditional logic evaluation to use qsbId
- [ ] Test with both old and new response formats

---

### 4️⃣ **GraphQL Response Structure Changes**

#### 🔵 NEW FIELDS in get_questionset_with_conditional_logic Response

```kotlin
// Response structure changed:
data class ConditionalLogicResponse(
    val questions: List<QuestionSetBelonging>,
    val dependencyMap: Map<Int, List<DependencyInfo>>,
    val hasConditionalLogic: Boolean,

    // 🆕 NEW FIELD (Release N):
    @SerializedName("validation_warnings")
    val validationWarnings: List<ValidationWarning>? = null  // NEW: May be null or empty
)

// 🆕 NEW DATA CLASS (Release N):
@Serializable
data class ValidationWarning(
    @SerializedName("question_id")
    val questionId: Int,

    val warning: String,
    val severity: String  // "error", "warning", "critical"
)
```

**Android Action Items:**
- [ ] Add `validationWarnings` field to response model (nullable)
- [ ] Create `ValidationWarning` data class
- [ ] Handle validation warnings in UI (show to user or log)
- [ ] Test with responses that have warnings
- [ ] Test with responses that don't have warnings (null)

#### 🔵 NEW FIELDS in dependency_map Structure

```kotlin
// Each dependency entry now includes:
data class DependencyInfo(
    val questionId: Int,
    val questionSeqno: Int,
    val operator: String,
    val values: List<String>,
    val showIf: Boolean,

    // 🆕 NEW FIELDS (Release N):
    @SerializedName("cascade_hide")
    val cascadeHide: Boolean = false,  // NEW

    val group: String? = null  // NEW
)
```

**Android Action Items:**
- [ ] Add `cascadeHide` field to DependencyInfo
- [ ] Add `group` field to DependencyInfo
- [ ] Update conditional logic UI to respect cascade_hide
- [ ] Support grouping of related questions

---

### 5️⃣ **QuestionSet Model Schema Changes**

#### 🟢 NO SCHEMA CHANGES - Only Label Improvements

**Good News:** QuestionSet has **ZERO breaking changes**!

**Label Changes (UI display only):**
- `KPITEMPLATE` label: "Kpi" → "KPI Template" (value unchanged: still "KPITEMPLATE")

**Android Action Items:**
- [ ] ✅ **NO CODE CHANGES REQUIRED**
- [ ] Optional: Update UI labels to match backend (cosmetic)

---

### 6️⃣ **Enum Value Changes**

#### 🔵 NEW ConditionalOperator Values (Android May Want to Support)

```kotlin
enum class ConditionalOperator {
    // EXISTING (already supported):
    EQUALS,
    NOT_EQUALS,
    CONTAINS,
    IN,
    GT,
    LT,

    // 🆕 NEW (Release N - optional support):
    NOT_CONTAINS,      // NEW
    NOT_IN,            // NEW
    GTE,               // NEW (Greater Than or Equal)
    LTE,               // NEW (Less Than or Equal)
    IS_EMPTY,          // NEW
    IS_NOT_EMPTY       // NEW
}
```

**Android Action Items:**
- [ ] Add new operator values to ConditionalOperator enum
- [ ] Implement evaluation logic for new operators
- [ ] Test each new operator type
- [ ] Handle unknown operators gracefully (backward compat)

**Backward Compatibility:**
- ✅ Old operators still work (EQUALS, GT, LT, etc.)
- ✅ If backend sends unknown operator, Android can log warning and skip

#### 🟢 AnswerType Enum - NO NEW VALUES

**Good News:** AnswerType has **NO new values** for Android!

- `BACKCAMERA` and `FRONTCAMERA` already existed in QuestionSetBelonging
- No new types added
- No types removed

**Android Action Items:**
- [ ] ✅ **NO CHANGES REQUIRED**

#### 🟢 AvptType Enum - NO CHANGES

**Android Action Items:**
- [ ] ✅ **NO CHANGES REQUIRED**

---

## 🎯 MASTER ANDROID MIGRATION CHECKLIST

### ✅ Release N (Current) - NO CODE CHANGES

**Testing Only:**
- [ ] Test existing app against new backend (staging)
- [ ] Verify no crashes when new fields are null
- [ ] Verify old fields still present and working
- [ ] Verify GraphQL queries return expected data
- [ ] Check for any null pointer exceptions
- [ ] Verify conditional logic still works

**Estimated Effort:** 2-4 hours (testing only)

---

### 🟡 Release N+1 (Next 4-6 Weeks) - ADD NEW FIELDS

#### Step 1: Update Data Models

**Files to Modify:**
- `app/src/main/java/com/yourapp/models/Question.kt`
- `app/src/main/java/com/yourapp/models/QuestionSetBelonging.kt`
- `app/src/main/java/com/yourapp/models/DisplayConditions.kt`
- `app/src/main/java/com/yourapp/models/AlertConfig.kt` (NEW FILE)

**Checklist:**
- [ ] **Question.kt:**
  - [ ] Add `optionsJson: List<String>?` field (nullable)
  - [ ] Add `alertConfig: AlertConfig?` field (nullable)
  - [ ] Keep `options: String?` field (deprecated)
  - [ ] Keep `alerton: String?` field (deprecated)

- [ ] **QuestionSetBelonging.kt:**
  - [ ] Add `optionsJson: List<String>?` field (nullable)
  - [ ] Add `alertConfig: AlertConfig?` field (nullable)
  - [ ] Keep `options: String?` field (deprecated)
  - [ ] Keep `alerton: String?` field (deprecated)
  - [ ] Update `displayConditions: DisplayConditions?` to support new structure

- [ ] **DisplayConditions.kt:**
  - [ ] Update `Dependency` to include `qsbId: Int?` field
  - [ ] Keep `questionId: Int?` field for backward compat
  - [ ] Add `cascadeHide: Boolean = false` field
  - [ ] Add `group: String?` field

- [ ] **AlertConfig.kt** (NEW FILE):
  - [ ] Create `AlertConfig` data class
  - [ ] Create `NumericAlert` data class
  - [ ] Add serialization annotations

- [ ] **ConditionalOperator.kt:**
  - [ ] Add 6 new operator values (NOT_CONTAINS, NOT_IN, GTE, LTE, IS_EMPTY, IS_NOT_EMPTY)

- [ ] **ConditionalLogicResponse.kt:**
  - [ ] Add `validationWarnings: List<ValidationWarning>?` field

- [ ] **DependencyInfo.kt:**
  - [ ] Add `cascadeHide: Boolean = false` field
  - [ ] Add `group: String?` field

#### Step 2: Add Compatibility Layer

**Files to Create:**
- `app/src/main/java/com/yourapp/extensions/QuestionExtensions.kt` (NEW)
- `app/src/main/java/com/yourapp/extensions/AlertExtensions.kt` (NEW)

**Checklist:**
- [ ] **QuestionExtensions.kt:**
  - [ ] `fun Question.getOptions(): List<String>` - Prefer JSON, fallback to text
  - [ ] `fun Question.getAlertBelow(): Double?` - Prefer config, fallback to text
  - [ ] `fun Question.getAlertAbove(): Double?` - Prefer config, fallback to text
  - [ ] `fun Question.getAlertChoices(): List<String>` - For dropdown/checkbox

- [ ] **QuestionSetBelongingExtensions.kt:**
  - [ ] Same methods as Question

- [ ] **DependencyExtensions.kt:**
  - [ ] `fun Dependency.getBelongingId(): Int` - Support both qsbId and questionId

#### Step 3: Update All Usages

**Estimated Files to Update:** 15-25 files

**Checklist:**
- [ ] **Question Rendering:**
  - [ ] Replace `question.options?.split(",")` with `question.getOptions()`
  - [ ] Replace manual alert parsing with `question.getAlertBelow()`
  - [ ] Update dropdown/checkbox components
  - [ ] Update numeric input validation

- [ ] **Conditional Logic:**
  - [ ] Replace `dependency.questionId` with `dependency.getBelongingId()`
  - [ ] Add support for `cascadeHide` behavior
  - [ ] Add support for question grouping

- [ ] **Form Submission:**
  - [ ] Update answer submission to handle new alert format
  - [ ] Test with various question types

#### Step 4: Testing

**Checklist:**
- [ ] Unit tests for all extension methods
- [ ] Unit tests for null handling
- [ ] Integration tests with mixed data (old + new formats)
- [ ] UI tests for all question types:
  - [ ] NUMERIC with new alert_config
  - [ ] DROPDOWN with options_json
  - [ ] CHECKBOX with options_json
  - [ ] MULTISELECT
  - [ ] Conditional logic with qsbId
  - [ ] Cascade hide behavior
- [ ] Performance tests (100+ question sets)
- [ ] Regression tests (ensure old data still works)

**Estimated Effort:** 5-8 developer-days

---

### 🔴 Release N+2 (8-12 Weeks) - COMPLETE MIGRATION

#### Step 1: Remove Compatibility Layer

**Checklist:**
- [ ] Remove all `parseOptions()` functions
- [ ] Remove all `parseNumericAlert()` functions
- [ ] Replace `question.getOptions()` with direct `question.optionsJson!!`
- [ ] Replace `dependency.getBelongingId()` with direct `dependency.qsbId!!`
- [ ] Add null checks where JSON fields might still be null

#### Step 2: Update All Code to Use JSON Fields Exclusively

**Checklist:**
- [ ] Search codebase for `.options?.split` - replace all
- [ ] Search codebase for `.alerton` references - replace all
- [ ] Search codebase for `.questionId` in Dependency - replace all
- [ ] Update GraphQL queries to request new fields explicitly

#### Step 3: Remove Deprecated Field References

**Checklist:**
- [ ] Remove `options: String?` from Question model
- [ ] Remove `alerton: String?` from Question model
- [ ] Remove `options: String?` from QuestionSetBelonging model
- [ ] Remove `alerton: String?` from QuestionSetBelonging model
- [ ] Remove `questionId: Int?` from Dependency (keep only qsbId)

#### Step 4: Comprehensive Testing

**Checklist:**
- [ ] Full regression test suite
- [ ] Test with production-like data
- [ ] Performance testing
- [ ] Memory leak testing
- [ ] Crash reporting validation
- [ ] Beta testing with real users

**Estimated Effort:** 3-5 developer-days

---

### ⛔ Release N+3 (6+ Months) - BREAKING CHANGES

**Backend Removes Old Fields:**
- ❌ `Question.options` removed
- ❌ `Question.alerton` removed
- ❌ `QuestionSetBelonging.options` removed
- ❌ `QuestionSetBelonging.alerton` removed
- ❌ `display_conditions.depends_on.question_id` removed (only qsb_id remains)

**Android MUST BE FULLY MIGRATED by this release!**

**Pre-Flight Checklist:**
- [ ] Confirm 100% migration complete in Release N+2
- [ ] Verify minimum app version enforced
- [ ] No references to deprecated fields in codebase
- [ ] All users on compatible app version

---

## 🔍 DETAILED FIELD-BY-FIELD ANDROID UPDATES

### Question.optionsJson

**Purpose:** Replaces CSV text parsing

**Kotlin Implementation:**
```kotlin
// Release N+1: Add field
@SerializedName("options_json")
val optionsJson: List<String>? = null

// Release N+1: Add helper
fun Question.getOptions(): List<String> {
    return optionsJson ?: options?.split(",")?.map { it.trim() } ?: emptyList()
}

// Release N+2: Use directly
val options = question.optionsJson ?: emptyList()
```

**Test Cases:**
- [ ] Null optionsJson, valid options text → Returns parsed list
- [ ] Valid optionsJson, null options text → Returns JSON list
- [ ] Both null → Returns empty list
- [ ] Both present → Prefers optionsJson

---

### Question.alertConfig

**Purpose:** Replaces ad-hoc string parsing for alerts

**Kotlin Implementation:**
```kotlin
// Release N+1: Add field
@SerializedName("alert_config")
val alertConfig: AlertConfig? = null

// Release N+1: Add helpers
fun Question.getAlertBelow(): Double? {
    return alertConfig?.numeric?.below ?: parseAlertBelow(alerton)
}

fun Question.getAlertAbove(): Double? {
    return alertConfig?.numeric?.above ?: parseAlertAbove(alerton)
}

fun Question.getAlertChoices(): List<String> {
    return alertConfig?.choice ?: alerton?.split(",") ?: emptyList()
}

// Release N+2: Use directly
val alertBelow = question.alertConfig?.numeric?.below
```

**Test Cases:**
- [ ] Numeric type with alertConfig → Returns structured values
- [ ] Numeric type with alerton text → Parses correctly
- [ ] Choice type with alertConfig.choice → Returns list
- [ ] Choice type with alerton text → Parses correctly
- [ ] Both null → Returns null/empty

---

### Dependency.qsbId

**Purpose:** Clarifies that ID is for QuestionSetBelonging, not Question

**Kotlin Implementation:**
```kotlin
// Release N+1: Add new field, keep old
data class Dependency(
    @SerializedName("qsb_id")
    val qsbId: Int? = null,

    @SerializedName("question_id")
    val questionId: Int? = null  // Backward compat
) {
    fun getId(): Int = qsbId ?: questionId ?: 0
}

// Release N+2: Remove questionId
data class Dependency(
    @SerializedName("qsb_id")
    val qsbId: Int  // Required
)
```

**Test Cases:**
- [ ] Response with qsbId only → Works
- [ ] Response with questionId only → Works (legacy)
- [ ] Response with both (same value) → Works
- [ ] Response with neither → Returns 0 (safe default)

---

### DisplayConditions.cascadeHide

**Purpose:** Automatically hide dependent questions when parent is hidden

**Kotlin Implementation:**
```kotlin
@SerializedName("cascade_hide")
val cascadeHide: Boolean = false

// Usage in conditional logic engine:
fun evaluateVisibility(
    question: QuestionSetBelonging,
    answers: Map<Int, String>,
    allQuestions: List<QuestionSetBelonging>
): Boolean {
    val conditions = question.displayConditions ?: return true

    val isParentVisible = // ... evaluate parent visibility

    if (!isParentVisible && conditions.cascadeHide) {
        return false  // Hide this question too
    }

    // ... rest of logic
}
```

**Test Cases:**
- [ ] cascadeHide = true, parent hidden → Child hidden
- [ ] cascadeHide = false, parent hidden → Child shows if condition met
- [ ] cascadeHide = true, parent visible, condition not met → Child hidden
- [ ] Multi-level cascade (A→B→C all cascade)

---

### ValidationWarning Array

**Purpose:** Inform mobile app of data integrity issues

**Kotlin Implementation:**
```kotlin
fun handleQuestionSetResponse(response: ConditionalLogicResponse) {
    // Check for validation warnings
    response.validationWarnings?.let { warnings ->
        warnings.forEach { warning ->
            when (warning.severity) {
                "critical" -> {
                    // Show error to user
                    showError("Question set has critical issues: ${warning.warning}")
                }
                "error" -> {
                    // Log error, maybe show warning
                    Log.e("QuestionSet", "Validation error: ${warning.warning}")
                }
                "warning" -> {
                    // Just log
                    Log.w("QuestionSet", "Validation warning: ${warning.warning}")
                }
            }
        }
    }

    // Continue processing questions even if warnings exist
    // (warnings are informational, not blocking)
}
```

**Test Cases:**
- [ ] No warnings (null) → Processes normally
- [ ] Empty warnings array → Processes normally
- [ ] Critical warning → Shows error to user
- [ ] Multiple warnings → All displayed/logged

---

## 🧪 ANDROID TEST PLAN

### Phase 1: Unit Tests (Release N+1)

**New Tests Required: ~35 tests**

```kotlin
// QuestionExtensionsTest.kt
class QuestionExtensionsTest {
    @Test fun `getOptions prefers JSON over text`() { }
    @Test fun `getOptions handles null JSON, valid text`() { }
    @Test fun `getOptions handles both null`() { }
    @Test fun `getAlertBelow parses from config`() { }
    @Test fun `getAlertBelow parses from text fallback`() { }
    // ... 10 more
}

// AlertConfigTest.kt
class AlertConfigTest {
    @Test fun `numeric alert deserialization`() { }
    @Test fun `choice alert deserialization`() { }
    @Test fun `null alertConfig handled`() { }
    // ... 8 more
}

// DependencyTest.kt
class DependencyTest {
    @Test fun `getId prefers qsbId`() { }
    @Test fun `getId falls back to questionId`() { }
    @Test fun `both keys work`() { }
    // ... 5 more
}

// ValidationWarningTest.kt
class ValidationWarningTest {
    @Test fun `warning deserialization`() { }
    @Test fun `severity levels handled`() { }
    // ... 4 more
}
```

### Phase 2: Integration Tests (Release N+1)

**New Tests Required: ~20 tests**

```kotlin
// QuestionRenderingIntegrationTest.kt
class QuestionRenderingIntegrationTest {
    @Test fun `dropdown with optionsJson renders correctly`() { }
    @Test fun `dropdown with options text fallback works`() { }
    @Test fun `numeric with alertConfig validates correctly`() { }
    @Test fun `numeric with alerton text fallback works`() { }
    @Test fun `conditional logic with qsbId works`() { }
    @Test fun `conditional logic with questionId fallback works`() { }
    @Test fun `cascade hide behavior works`() { }
    // ... 13 more
}
```

### Phase 3: Regression Tests (Release N+1)

**Existing Tests to Run:**

```kotlin
// Verify all existing tests still pass
@Test fun `all existing question rendering tests pass`() { }
@Test fun `all existing form submission tests pass`() { }
@Test fun `all existing validation tests pass`() { }
@Test fun `all existing conditional logic tests pass`() { }
```

### Phase 4: Performance Tests (Release N+1)

```kotlin
@Test fun `parsing 100 questions with JSON is fast`() {
    // Should be faster than CSV parsing
}

@Test fun `rendering questionset with conditional logic is smooth`() {
    // Should have no UI lag
}
```

---

## 🚨 CRITICAL: Breaking Change Prevention Checklist

**Before ANY Android deployment, verify:**

- [ ] **Old fields still present in API response:**
  - [ ] `options` field exists in Question
  - [ ] `alerton` field exists in Question
  - [ ] `options` field exists in QuestionSetBelonging
  - [ ] `alerton` field exists in QuestionSetBelonging
  - [ ] `display_conditions.depends_on.question_id` exists

- [ ] **New fields are nullable:**
  - [ ] `optionsJson` can be null
  - [ ] `alertConfig` can be null
  - [ ] `validationWarnings` can be null
  - [ ] `cascadeHide` has default value
  - [ ] `group` can be null

- [ ] **Backward compatibility verified:**
  - [ ] Test with responses that have ONLY old fields → App doesn't crash
  - [ ] Test with responses that have ONLY new fields → App works
  - [ ] Test with responses that have BOTH → App prefers new fields

---

## 📊 ANDROID EFFORT ESTIMATION

| Phase | Tasks | Test Cases | Estimated Hours | Risk |
|-------|-------|------------|-----------------|------|
| **Release N** (Testing) | 5 | 15 | 4-6 hrs | 🟢 Low |
| **Release N+1** (Add Fields) | 25 | 35 | 32-40 hrs (5-8 days) | 🟡 Medium |
| **Release N+2** (Complete Migration) | 15 | 25 | 24-32 hrs (3-5 days) | 🔴 High |
| **Release N+3** (Cleanup) | 5 | 10 | 4-8 hrs | 🟢 Low |
| **TOTAL** | 50 | 85 | **64-86 hrs** | - |

**Total Effort: 8-11 developer-days** spread over 3 releases (12-16 weeks)

---

## 📋 FIELD CHANGE SUMMARY TABLE

### Question Model

| Field | Type | Change Type | Nullable | Action Required | Deadline |
|-------|------|-------------|----------|-----------------|----------|
| `options_json` | List<String> | ✅ NEW | Yes | Add to model | N+1 |
| `alert_config` | AlertConfig | ✅ NEW | Yes | Add to model + create class | N+1 |
| `options` | String | ⚠️ DEPRECATED | Yes | Keep but stop using | N+2 |
| `alerton` | String | ⚠️ DEPRECATED | Yes | Keep but stop using | N+2 |

### QuestionSetBelonging Model

| Field | Type | Change Type | Nullable | Action Required | Deadline |
|-------|------|-------------|----------|-----------------|----------|
| `options_json` | List<String> | ✅ NEW | Yes | Add to model | N+1 |
| `alert_config` | AlertConfig | ✅ NEW | Yes | Add to model + create class | N+1 |
| `options` | String | ⚠️ DEPRECATED | Yes | Keep but stop using | N+2 |
| `alerton` | String | ⚠️ DEPRECATED | Yes | Keep but stop using | N+2 |

### DisplayConditions Structure

| Field | Type | Change Type | Nullable | Action Required | Deadline |
|-------|------|-------------|----------|-----------------|----------|
| `depends_on.qsb_id` | Int | ✅ NEW | Yes | Add to Dependency model | N+1 |
| `depends_on.question_id` | Int | ⚠️ DEPRECATED | Yes | Keep but plan removal | N+3 |
| `cascade_hide` | Boolean | ✅ NEW | No (default false) | Add to DisplayConditions | N+1 |
| `group` | String | ✅ NEW | Yes | Add to DisplayConditions | N+1 |

### GraphQL Response

| Field | Type | Change Type | Nullable | Action Required | Deadline |
|-------|------|-------------|----------|-----------------|----------|
| `validation_warnings` | List<ValidationWarning> | ✅ NEW | Yes | Add to response model | N+1 |

### Enums

| Enum | Values Added | Values Removed | Action Required | Deadline |
|------|--------------|----------------|-----------------|----------|
| ConditionalOperator | +6 (NOT_CONTAINS, NOT_IN, GTE, LTE, IS_EMPTY, IS_NOT_EMPTY) | None | Add to enum | N+1 |
| AnswerType | None | None | ✅ No changes | - |
| AvptType | None | None | ✅ No changes | - |

---

## 🎯 PRIORITIZED ACTION LIST FOR ANDROID TEAM

### 🔴 **CRITICAL (Must Do for Release N+1):**

1. [ ] **Add 4 new fields to Question model** (optionsJson, alertConfig)
2. [ ] **Add 4 new fields to QuestionSetBelonging model** (optionsJson, alertConfig)
3. [ ] **Create AlertConfig data class** (with NumericAlert nested class)
4. [ ] **Update Dependency model** (add qsbId, keep questionId)
5. [ ] **Create compatibility layer** (getOptions(), getAlertBelow(), getId())
6. [ ] **Test with null values** (critical - prevents crashes)

### 🟡 **HIGH PRIORITY (Should Do for Release N+1):**

7. [ ] **Update DisplayConditions** (add cascadeHide, group)
8. [ ] **Add ConditionalOperator values** (6 new operators)
9. [ ] **Add ValidationWarning model** (for error handling)
10. [ ] **Update conditional logic** (support cascade_hide)
11. [ ] **Write 35 unit tests** (compatibility layer)
12. [ ] **Write 20 integration tests** (rendering + logic)

### 🟢 **MEDIUM PRIORITY (Nice to Have for Release N+1):**

13. [ ] **Update UI to show validation warnings**
14. [ ] **Support question grouping** (group field)
15. [ ] **Optimize rendering** (leverage structured JSON)

---

## ✅ **VALIDATION CHECKLIST**

**Before Android Release N+1 Deployment:**

- [ ] All new fields added to models
- [ ] All new data classes created
- [ ] Compatibility layer implemented
- [ ] All existing tests pass
- [ ] 35+ new unit tests pass
- [ ] 20+ integration tests pass
- [ ] No crashes with null JSON fields
- [ ] No crashes with old data format
- [ ] Performance acceptable (no regressions)
- [ ] Code review complete
- [ ] QA sign-off received

---

## 📞 **Support Resources**

**Backend Documentation:**
- API Contract: `docs/mobile-api/QUESTION_SCHEMA_MIGRATION.md`
- Implementation: `QUESTION_QUESTIONSET_REFACTORING_COMPLETE.md`
- Quick Reference: `QUESTION_REFACTORING_QUICK_REFERENCE.md`

**Testing Backend:**
- Staging GraphQL: `https://staging.yourapp.com/api/graphql/`
- GraphiQL Explorer: Access via browser for manual testing
- Test Data: Use staging environment data

**Contacts:**
- Backend Lead: backend-team@company.com
- Migration Questions: Slack #mobile-backend-migration
- Critical Issues: PagerDuty on-call

---

**TOTAL SCHEMA CHANGES REQUIRING ANDROID UPDATES: 17**

**CRITICAL CHANGES: 6** (Must handle in Release N+1)
**HIGH PRIORITY: 7** (Should handle in Release N+1)
**MEDIUM PRIORITY: 4** (Nice to have)

**All changes are BACKWARD COMPATIBLE for 2 releases!** ✅
