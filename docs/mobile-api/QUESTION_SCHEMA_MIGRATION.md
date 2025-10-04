# Question Schema Migration Guide for Android/Kotlin Frontend

**Version:** 2.0
**Date:** 2025-10-03
**Status:** ⚠️ BREAKING CHANGES IN 3 RELEASES
**Priority:** 🔴 HIGH - Mobile team action required

---

## 📋 Executive Summary

The backend Question/QuestionSet schema is being enhanced with structured JSON fields to replace brittle text parsing. This migration ensures better data integrity, easier mobile parsing, and improved performance.

**Impact Timeline:**
- **Release N (Current)**: NEW fields added, OLD fields maintained ✅ **NO BREAKING CHANGES**
- **Release N+1 (Next)**: Dual-write to both fields ✅ **NO BREAKING CHANGES**
- **Release N+2 (Future)**: OLD fields deprecated, warnings added ⚠️ **DEPRECATION WARNINGS**
- **Release N+3 (Future)**: OLD fields removed 🔴 **BREAKING CHANGES**

---

## 🔄 What's Changing

### 1. **Options Field Migration**

#### Question Model

**OLD (Deprecated):**
```kotlin
// Text field - requires parsing
data class Question(
    val options: String?  // "Option1,Option2,Option3"
)

// Parse manually in Kotlin
val optionsList = question.options?.split(",") ?: emptyList()
```

**NEW (Preferred):**
```kotlin
// Structured JSON field - direct deserialization
data class Question(
    val optionsJson: List<String>?  // ["Option1", "Option2", "Option3"]
)

// Direct use - no parsing needed
val optionsList = question.optionsJson ?: emptyList()
```

#### QuestionSetBelonging Model

**Same pattern** - `options` (text) → `optionsJson` (array)

---

### 2. **Alert Configuration Migration**

#### Numeric Alerts

**OLD (Deprecated):**
```kotlin
// Text field with custom format
data class Question(
    val alerton: String?  // "<10, >90"
)

// Complex parsing required
fun parseNumericAlert(alerton: String?): AlertConfig {
    val belowMatch = Regex("<([0-9.]+)").find(alerton ?: "")
    val aboveMatch = Regex(">([0-9.]+)").find(alerton ?: "")
    return AlertConfig(
        below = belowMatch?.groupValues?.get(1)?.toDoubleOrNull(),
        above = aboveMatch?.groupValues?.get(1)?.toDoubleOrNull()
    )
}
```

**NEW (Preferred):**
```kotlin
// Structured JSON field
data class AlertConfig(
    val numeric: NumericAlert?,
    val choice: List<String>?,
    val enabled: Boolean
)

data class NumericAlert(
    val below: Double?,
    val above: Double?
)

data class Question(
    val alertConfig: AlertConfig?
)

// Direct deserialization - no parsing
val below = question.alertConfig?.numeric?.below
val above = question.alertConfig?.numeric?.above
```

#### Choice Alerts (Dropdown/Checkbox)

**OLD:**
```kotlin
val alerton: String?  // "Critical,Urgent"
```

**NEW:**
```kotlin
val alertConfig: AlertConfig?
// alertConfig.choice = ["Critical", "Urgent"]
```

---

### 3. **Conditional Logic Naming Clarification**

#### Critical Fix: `question_id` → `qsb_id`

**OLD (Misleading):**
```kotlin
data class DisplayConditions(
    val dependsOn: Dependency?
)

data class Dependency(
    val questionId: Int  // ⚠️ MISLEADING - actually holds QuestionSetBelonging ID!
)
```

**NEW (Accurate):**
```kotlin
data class Dependency(
    val qsbId: Int,  // ✅ CORRECT - QuestionSetBelonging ID
    @SerializedName("question_id") val questionId: Int?  // Backward compat alias
)
```

**Migration Strategy:**
```kotlin
// Support both keys during transition
fun getDependencyId(dependency: Dependency): Int {
    return dependency.qsbId ?: dependency.questionId ?: 0
}
```

---

## 📅 Migration Timeline

### Release N (Current - Backend Version 2025-10-03)

**Backend Changes:**
- ✅ Added `options_json` field (nullable)
- ✅ Added `alert_config` field (nullable)
- ✅ OLD fields (`options`, `alerton`) still present
- ✅ Data migration populates JSON fields from existing data
- ✅ GraphQL returns BOTH old and new fields

**Mobile Changes Required:** **NONE** ✅
- Continue using existing fields
- Optionally start reading new fields

**API Contract:**
```graphql
type Question {
  # OLD (still works)
  options: String
  alerton: String

  # NEW (available but optional)
  optionsJson: [String]
  alertConfig: AlertConfig
}
```

---

### Release N+1 (Next - Estimated 2025-11-01)

**Backend Changes:**
- ✅ Dual-write: Updates write to BOTH old and new fields
- ✅ GraphQL continues returning both fields
- ✅ No breaking changes

**Mobile Changes Required:** **LOW PRIORITY** 🟡
- Start migrating to new fields in new code
- Keep old field support for backward compat
- Update models to include new fields

**Kotlin Model Update:**
```kotlin
data class Question(
    // OLD (maintain for backward compat)
    @SerializedName("options") val optionsLegacy: String?,
    @SerializedName("alerton") val alertonLegacy: String?,

    // NEW (start using)
    @SerializedName("options_json") val optionsJson: List<String>?,
    @SerializedName("alert_config") val alertConfig: AlertConfig?,
) {
    // Helper: prefer JSON, fallback to text
    val options: List<String>
        get() = optionsJson ?: optionsLegacy?.split(",") ?: emptyList()

    val alertBelow: Double?
        get() = alertConfig?.numeric?.below
            ?: parseNumericAlert(alertonLegacy)?.below

    val alertAbove: Double?
        get() = alertConfig?.numeric?.above
            ?: parseNumericAlert(alertonLegacy)?.above
}
```

---

### Release N+2 (Future - Estimated 2025-12-01)

**Backend Changes:**
- ⚠️ OLD fields marked as deprecated in GraphQL schema
- ⚠️ Deprecation warnings logged when old fields are used
- ✅ Both fields still returned (no breaking changes yet)

**Mobile Changes Required:** **REQUIRED** 🔴
- Complete migration to new fields
- Remove old field parsers
- Update all code to use `optionsJson` and `alertConfig`
- Test thoroughly on all question types

**Deadline:** Before Release N+3

---

### Release N+3 (Future - Estimated 2026-01-01)

**Backend Changes:**
- 🔴 **BREAKING:** OLD fields removed from database
- 🔴 **BREAKING:** GraphQL no longer returns `options` or `alerton`
- 🔴 **BREAKING:** Only JSON fields available

**Mobile Changes Required:** **MUST BE COMPLETE** ⛔
- App **MUST** use `optionsJson` and `alertConfig`
- Old field references will cause crashes
- Minimum supported app version increased

---

## 🛠️ Android Implementation Guide

### Step 1: Update Data Models (Release N+1)

**File:** `app/src/main/java/com/yourapp/models/Question.kt`

```kotlin
import com.google.gson.annotations.SerializedName

data class Question(
    val id: Int,
    val quesname: String,
    val answertype: AnswerType,

    // PHASE 1: Add new fields (nullable)
    @SerializedName("options_json")
    val optionsJson: List<String>? = null,

    @SerializedName("alert_config")
    val alertConfig: AlertConfig? = null,

    // Keep old fields for backward compat
    @SerializedName("options")
    val optionsLegacy: String? = null,

    @SerializedName("alerton")
    val alertonLegacy: String? = null,

    // Other fields...
    val min: Double?,
    val max: Double?,
    val isavpt: Boolean,
    val avpttype: AvptType?,
    val client_id: Int,
    val created_at: String,
    val updated_at: String
)

// Alert configuration
data class AlertConfig(
    val numeric: NumericAlert? = null,
    val choice: List<String>? = null,
    val enabled: Boolean = false
)

data class NumericAlert(
    val below: Double? = null,
    val above: Double? = null
)
```

---

### Step 2: Add Compatibility Layer (Release N+1)

```kotlin
// Extension functions for smooth migration
fun Question.getOptions(): List<String> {
    // Prefer JSON, fallback to text parsing
    return optionsJson ?: optionsLegacy?.split(",")?.map { it.trim() } ?: emptyList()
}

fun Question.getAlertBelow(): Double? {
    // Prefer structured config
    return alertConfig?.numeric?.below ?: run {
        // Fallback to parsing text
        alertonLegacy?.let { parseAlertBelow(it) }
    }
}

fun Question.getAlertAbove(): Double? {
    return alertConfig?.numeric?.above ?: run {
        alertonLegacy?.let { parseAlertAbove(it) }
    }
}

fun Question.getAlertChoices(): List<String> {
    return alertConfig?.choice ?: run {
        alertonLegacy?.split(",")?.map { it.trim() } ?: emptyList()
    }
}

// Legacy parsers (keep for Release N+1, remove in N+2)
private fun parseAlertBelow(alerton: String): Double? {
    val match = Regex("<\\s*([0-9.]+)").find(alerton)
    return match?.groupValues?.get(1)?.toDoubleOrNull()
}

private fun parseAlertAbove(alerton: String): Double? {
    val match = Regex(">\\s*([0-9.]+)").find(alerton)
    return match?.groupValues?.get(1)?.toDoubleOrNull()
}
```

---

### Step 3: Update All Usages (Release N+2)

**Replace direct field access with compatibility methods:**

```kotlin
// ❌ OLD (will break in Release N+3)
val options = question.options?.split(",") ?: emptyList()

// ✅ NEW (safe for all releases)
val options = question.getOptions()
```

**Refactor UI components:**

```kotlin
// Dropdown rendering
@Composable
fun QuestionDropdown(question: Question) {
    val options = question.getOptions()  // ✅ Uses compatibility method

    DropdownMenu {
        options.forEach { option ->
            DropdownMenuItem(text = { Text(option) })
        }
    }
}

// Numeric validation
fun validateNumericAnswer(question: Question, answer: Double): ValidationResult {
    val below = question.getAlertBelow()
    val above = question.getAlertAbove()

    return when {
        below != null && answer < below -> ValidationResult.BelowThreshold
        above != null && answer > above -> ValidationResult.AboveThreshold
        else -> ValidationResult.Valid
    }
}
```

---

### Step 4: Remove Legacy Support (Release N+3)

**Remove compatibility layer and old field references:**

```kotlin
// Remove legacy fields
data class Question(
    val optionsJson: List<String>?,
    val alertConfig: AlertConfig?,
    // optionsLegacy REMOVED
    // alertonLegacy REMOVED
)

// Remove compatibility methods
// fun Question.getOptions() - REMOVED
// Use question.optionsJson directly
```

---

## 🧪 Testing Checklist for Mobile Team

### Before Release N+1:

- [ ] Run existing tests - should pass (no changes)
- [ ] Test on staging with new fields present (nulls)
- [ ] Verify app doesn't crash with null JSON fields

### Before Release N+2:

- [ ] Add new data models with JSON fields
- [ ] Implement compatibility methods
- [ ] Update all question rendering code to use compatibility methods
- [ ] Test with mixed data (some records old format, some new)
- [ ] Test all question types:
  - [ ] NUMERIC with alerts
  - [ ] DROPDOWN with options
  - [ ] CHECKBOX with options and alerts
  - [ ] MULTISELECT
  - [ ] RATING
  - [ ] DATE/TIME
  - [ ] SIGNATURE
  - [ ] PEOPLELIST/SITELIST
  - [ ] GPSLOCATION
  - [ ] METERREADING
- [ ] Test conditional logic (display_conditions)
- [ ] Performance test with 100+ question sets

### Before Release N+3:

- [ ] Remove all legacy field references
- [ ] Remove compatibility methods
- [ ] Update minimum API version
- [ ] Full regression testing
- [ ] Test on production-like data

---

## 🔧 GraphQL Query Updates

### OLD Query (Still works in N, N+1, N+2):

```graphql
query GetQuestions($mdtz: String!, $clientid: Int!) {
  getQuestionsmodifiedafter(mdtz: $mdtz, ctzoffset: 0, clientid: $clientid) {
    records
  }
}

# Response includes:
# {
#   "options": "Option1,Option2,Option3",
#   "alerton": "<10, >90"
# }
```

### NEW Query (Available N, N+1, N+2, N+3):

```graphql
query GetQuestionsEnhanced($mdtz: String!, $clientid: Int!) {
  getQuestionsmodifiedafter(mdtz: $mdtz, ctzoffset: 0, clientid: $clientid) {
    records  # Now includes optionsJson and alertConfig
  }
}

# Response includes:
# {
#   "options": "Option1,Option2,Option3",     # OLD (N, N+1, N+2 only)
#   "optionsJson": ["Option1", "Option2", "Option3"],  # NEW
#   "alerton": "<10, >90",                    # OLD (N, N+1, N+2 only)
#   "alertConfig": {                          # NEW
#     "numeric": {"below": 10, "above": 90},
#     "enabled": true
#   }
# }
```

### Conditional Logic Query (Enhanced):

```graphql
query GetQuestionSetWithLogic($qsetId: Int!, $clientid: Int!, $buid: Int!) {
  getQuestionsetWithConditionalLogic(qsetId: $qsetId, clientid: $clientid, buid: $buid) {
    records
  }
}

# Response structure:
# {
#   "questions": [...],
#   "dependency_map": {
#     "123": [  # Parent question ID
#       {
#         "question_id": 456,      # Dependent question ID
#         "operator": "EQUALS",
#         "values": ["Yes"],
#         "show_if": true,
#         "cascade_hide": false
#       }
#     ]
#   },
#   "has_conditional_logic": true,
#   "validation_warnings": []  # NEW - may contain dependency issues
# }
```

---

## 🚨 Critical: `question_id` → `qsb_id` Clarification

### The Problem

The `display_conditions.depends_on.question_id` field name is **MISLEADING**.

**It actually holds a `QuestionSetBelonging` ID, NOT a `Question` ID!**

### The Fix

**Backend now supports BOTH keys:**

```json
{
  "display_conditions": {
    "depends_on": {
      "qsb_id": 123,       // NEW - correct naming
      "question_id": 123    // OLD - maintained for backward compat (same value)
    }
  }
}
```

### Android Migration

**Phase 1 (Release N+1):** Support both keys

```kotlin
data class Dependency(
    @SerializedName("qsb_id")
    val qsbId: Int? = null,

    @SerializedName("question_id")
    val questionId: Int? = null  // Backward compat
) {
    // Helper: get ID from either key
    fun getId(): Int = qsbId ?: questionId ?: 0
}
```

**Phase 2 (Release N+2):** Migrate to `qsb_id`

```kotlin
// When creating new display conditions, use qsb_id
val dependency = Dependency(
    qsbId = parentBelonging.id,  // ✅ Correct key
    operator = "EQUALS",
    values = listOf("Yes")
)
```

**Phase 3 (Release N+3):** Remove `question_id` support

```kotlin
data class Dependency(
    val qsbId: Int  // Only this key remains
)
```

---

## 📊 Field Mapping Reference

### Question Model

| Old Field | New Field | Type Change | Status | Android Action |
|-----------|-----------|-------------|--------|----------------|
| `options` (Text) | `optionsJson` (JSON) | String → List<String> | Deprecated | Migrate by N+2 |
| `alerton` (Text) | `alertConfig` (JSON) | String → AlertConfig | Deprecated | Migrate by N+2 |
| `answertype` | `answertype` | Enum (unchanged) | Active | No change |
| `min`, `max` | `min`, `max` | Decimal (unchanged) | Active | No change |

### QuestionSetBelonging Model

| Old Field | New Field | Type Change | Status | Android Action |
|-----------|-----------|-------------|--------|----------------|
| `options` (Text) | `optionsJson` (JSON) | String → List<String> | Deprecated | Migrate by N+2 |
| `alerton` (Text) | `alertConfig` (JSON) | String → AlertConfig | Deprecated | Migrate by N+2 |
| `display_conditions.depends_on.question_id` | `display_conditions.depends_on.qsb_id` | Renamed for clarity | Both supported | Migrate by N+2 |

### Display Conditions

| Old Key | New Key | Description | Status |
|---------|---------|-------------|--------|
| `question_id` | `qsb_id` | QuestionSetBelonging ID (not Question ID) | Both supported |
| - | `cascade_hide` | NEW: Hide dependent questions if hidden | New in N |
| - | `group` | NEW: Group identifier for related questions | New in N |

---

## 🔍 Example: Complete Migration

### Before (Release N):

```kotlin
// Old model
@Serializable
data class Question(
    val id: Int,
    val quesname: String,
    val answertype: String,
    val options: String?,  // "Yes,No,Maybe"
    val alerton: String?,  // "No"
    val min: Double?,
    val max: Double?
)

// Usage
fun renderQuestion(question: Question) {
    when (question.answertype) {
        "DROPDOWN" -> {
            val opts = question.options?.split(",") ?: emptyList()
            DropdownField(options = opts)
        }
        "NUMERIC" -> {
            val alert = parseAlert(question.alerton)
            NumericField(min = question.min, max = question.max, alert = alert)
        }
    }
}
```

### After (Release N+2):

```kotlin
// New model
@Serializable
data class Question(
    val id: Int,
    val quesname: String,
    val answertype: AnswerType,

    // NEW: Prefer these
    @SerializedName("options_json")
    val optionsJson: List<String>? = null,

    @SerializedName("alert_config")
    val alertConfig: AlertConfig? = null,

    val min: Double?,
    val max: Double?
)

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

// Usage (cleaner!)
fun renderQuestion(question: Question) {
    when (question.answertype) {
        AnswerType.DROPDOWN -> {
            DropdownField(options = question.optionsJson ?: emptyList())
        }
        AnswerType.NUMERIC -> {
            NumericField(
                min = question.min,
                max = question.max,
                alertBelow = question.alertConfig?.numeric?.below,
                alertAbove = question.alertConfig?.numeric?.above
            )
        }
    }
}
```

---

## ✅ Validation Checklist

Before deploying Android app with new schema:

### Development:
- [ ] Update data models with new fields (nullable)
- [ ] Add compatibility layer (getOptions(), getAlertBelow(), etc.)
- [ ] Update GraphQL queries to request new fields
- [ ] Test with mock data (both old and new formats)

### Staging:
- [ ] Test with real staging data
- [ ] Verify all question types render correctly
- [ ] Test conditional logic still works
- [ ] Performance test with large question sets (100+ questions)
- [ ] Test offline sync with new fields

### Production:
- [ ] Gradual rollout (10% → 50% → 100%)
- [ ] Monitor crash reports for null pointer exceptions
- [ ] Monitor API errors for malformed requests
- [ ] Validate data integrity (spot checks)

---

## 🆘 Troubleshooting

### Issue: Null pointer exception on `optionsJson`

**Cause:** Old data not migrated yet or migration failed

**Solution:**
```kotlin
// Always use fallback
val options = question.optionsJson ?: question.optionsLegacy?.split(",") ?: emptyList()
```

### Issue: Alert parsing fails

**Cause:** Unexpected alert format

**Solution:**
```kotlin
// Defensive parsing
fun Question.getAlertBelow(): Double? {
    return try {
        alertConfig?.numeric?.below ?: parseAlertBelow(alertonLegacy)
    } catch (e: Exception) {
        Log.w("Question", "Failed to parse alert below", e)
        null
    }
}
```

### Issue: Conditional logic not working

**Cause:** Using wrong ID (question_id vs qsb_id)

**Solution:**
```kotlin
// Use helper to get correct ID
fun Dependency.getBelongingId(): Int {
    return qsbId ?: questionId ?: throw IllegalStateException("No dependency ID found")
}
```

---

## 📞 Support Contacts

- **Backend Team:** backend-team@company.com
- **API Documentation:** https://api.yourapp.com/docs/graphql
- **Migration Issues:** Slack #mobile-backend-migration
- **Emergency:** On-call engineer via PagerDuty

---

## 📚 Additional Resources

- **GraphQL Schema:** `/api/graphql/` (GraphiQL interface)
- **Test Data:** `scripts/generate_mobile_test_data.py`
- **Backend Changes:** `apps/activity/CHANGELOG.md`
- **Performance Benchmarks:** `docs/performance/question-query-optimization.md`

---

**Last Updated:** 2025-10-03
**Document Version:** 2.0
**Next Review:** Before Release N+1 deployment
