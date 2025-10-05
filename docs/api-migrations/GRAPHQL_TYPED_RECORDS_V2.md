# GraphQL Typed Records Migration Guide

**For**: Android/Kotlin Apollo Client Teams
**Effective Date**: October 5, 2025
**Migration Timeline**: 6 weeks (until November 16, 2025)
**Removal Date**: June 30, 2026 (v2.0 release)

---

## Overview

The GraphQL API has been enhanced with **type-safe record fields** to enable Apollo Kotlin to generate proper sealed classes instead of `Any` types.

### What Changed

**BEFORE** (Apollo Kotlin gets `Any`):
```graphql
query {
    getQuestionsmodifiedafter(mdtz: "2025-01-01", clientid: 1) {
        nrows
        records  # ❌ Returns JSONString → Apollo sees: records: Any
    }
}
```

**AFTER** (Apollo Kotlin gets sealed class):
```graphql
query {
    getQuestionsmodifiedafter(mdtz: "2025-01-01", clientid: 1) {
        nrows
        recordsTyped {  # ✅ Returns Union → Apollo sees: records: List<SelectRecord>
            ... on QuestionRecordType {
                id
                quesname
                answertype
                options
                min
                max
            }
        }
        recordType  # ✅ Discriminator: "question", "location", etc.
    }
}
```

---

## Breaking Changes: NONE (Dual-Field Period)

**Good News**: This is a **non-breaking enhancement**.

- ✅ Old `records` field still works (returns JSON string)
- ✅ New `records_typed` field available (returns typed list)
- ✅ New `record_type` field indicates record type
- ✅ You control migration pace (no immediate action required)

**Timeline**:
- **Weeks 1-6**: Both fields available (dual-field period)
- **After 6 weeks**: Deprecation warning added
- **June 30, 2026**: Old `records` field removed in v2.0

---

## Migration Steps

### Week 1: Update GraphQL Queries

#### Old Query (current)

```graphql
query GetQuestions($mdtz: String!, $clientid: Int!) {
    getQuestionsmodifiedafter(mdtz: $mdtz, clientid: $clientid) {
        nrows
        records  # ❌ JSONString
        msg
    }
}
```

#### New Query (type-safe)

```graphql
query GetQuestions($mdtz: String!, $clientid: Int!) {
    getQuestionsmodifiedafter(mdtz: $mdtz, clientid: $clientid) {
        nrows
        recordType  # ✅ NEW: Discriminator
        recordsTyped {  # ✅ NEW: Typed records
            ... on QuestionRecordType {
                id
                quesname
                answertype
                options
                min
                max
                isworkflow
                enable
                categoryId
                clientId
                mdtz
            }
        }
        msg
    }
}
```

### Week 2: Regenerate Apollo Kotlin Code

```bash
./gradlew downloadApolloSchema \
  --endpoint="http://staging-api.youtility.in/api/graphql/" \
  --schema="app/src/main/graphql/schema.graphqls"

./gradlew generateApolloSources
```

**Generated Output**:

```kotlin
// OLD (before migration)
data class GetQuestionsData(
    val getQuestionsmodifiedafter: GetQuestionsmodifiedafter?
) {
    data class GetQuestionsmodifiedafter(
        val nrows: Int?,
        val records: Any?,  // ❌ Untyped blob
        val msg: String?
    )
}

// NEW (after migration)
data class GetQuestionsData(
    val getQuestionsmodifiedafter: GetQuestionsmodifiedafter?
) {
    data class GetQuestionsmodifiedafter(
        val nrows: Int?,
        val recordType: String?,  // ✅ "question"
        val recordsTyped: List<RecordsTyped>?,  // ✅ Typed list
        val msg: String?
    ) {
        sealed class RecordsTyped {
            data class QuestionRecordType(
                val id: Int?,
                val quesname: String?,
                val answertype: String?,
                val options: List<String?>?,
                val min: Double?,
                val max: Double?,
                val isworkflow: Boolean?,
                val enable: Boolean?,
                val categoryId: Int?,
                val clientId: Int?,
                val mdtz: String?
            ) : RecordsTyped()
            // ... other record types
        }
    }
}
```

### Week 3-4: Update Kotlin Code

#### OLD: Manual JSON Parsing (error-prone)

```kotlin
val response = apolloClient.query(GetQuestions(mdtz, clientid)).execute()
val recordsJson = response.data?.getQuestionsmodifiedafter?.records  // ❌ Any type

// Manual parsing required
val jsonArray = JSONArray(recordsJson.toString())
for (i in 0 until jsonArray.length()) {
    val obj = jsonArray.getJSONObject(i)
    val id = obj.optInt("id")  // ❌ Could be wrong type, null, etc.
    val name = obj.optString("quesname")  // ❌ No autocomplete
    // ... error-prone parsing
}
```

#### NEW: Type-Safe Sealed Classes (compile-time safe)

```kotlin
val response = apolloClient.query(GetQuestions(mdtz, clientid)).execute()
val questions = response.data?.getQuestionsmodifiedafter?.recordsTyped  // ✅ List<RecordsTyped>

questions?.forEach { record ->
    when (record) {
        is GetQuestionsData.GetQuestionsmodifiedafter.RecordsTyped.QuestionRecordType -> {
            // ✅ Type-safe access, IDE autocomplete works
            val id = record.id ?: return@forEach
            val name = record.quesname ?: "Unnamed"
            val answerType = record.answertype  // ✅ Compile error if wrong type

            when (answerType) {
                "NUMERIC" -> handleNumericQuestion(record.min, record.max)
                "DROPDOWN" -> handleDropdownQuestion(record.options)
                "TEXT" -> handleTextQuestion()
            }
        }
        // Other record types (if query returns mixed types)
    }
}
```

### Week 5-6: Remove Old Code

```kotlin
// Delete old manual JSON parsing functions
// Remove JSONObject dependencies
// Use only type-safe sealed class approach
```

---

## Supported Record Types

| Record Type | GraphQL Type | Use Case | Queries |
|------------|--------------|----------|---------|
| `question` | `QuestionRecordType` | Question definitions | `getQuestionsmodifiedafter` |
| `questionset` | `QuestionSetRecordType` | Question set/checklist definitions | `getQsetmodifiedafter`, `getQsetbelongingmodifiedafter` |
| `location` | `LocationRecordType` | Site/location data | `getLocations`, `getGfsForSiteids` |
| `asset` | `AssetRecordType` | Asset/equipment data | Asset-related queries |
| `pgroup` | `PgroupRecordType` | People group data | `getGroupsmodifiedafter` |
| `typeassist` | `TypeAssistRecordType` | Type assist/metadata | `getTypeassistmodifiedafter`, `getShifts` |

---

## Query Examples

### Example 1: Get Questions

```graphql
query GetQuestions($mdtz: String!, $clientid: Int!) {
    getQuestionsmodifiedafter(mdtz: $mdtz, clientid: $clientid) {
        nrows
        recordType
        recordsTyped {
            ... on QuestionRecordType {
                id
                quesname
                answertype
                options  # ✅ List<String> not Any
                min
                max
                isworkflow
                enable
                mdtz
            }
        }
        msg
    }
}
```

### Example 2: Get Locations

```graphql
query GetLocations($mdtz: String!, $ctzoffset: Int!, $buid: Int!) {
    getLocations(mdtz: $mdtz, ctzoffset: $ctzoffset, buid: $buid) {
        nrows
        recordType
        recordsTyped {
            ... on LocationRecordType {
                id
                loccode
                locname
                gpslocation  # ✅ GeoJSON string
                iscritical
                enable
                parentId
            }
        }
    }
}
```

### Example 3: Get Question Sets

```graphql
query GetQuestionSets($mdtz: String!, $buid: Int!, $clientid: Int!, $peopleid: Int!) {
    getQsetmodifiedafter(
        mdtz: $mdtz,
        buid: $buid,
        clientid: $clientid,
        peopleid: $peopleid
    ) {
        nrows
        recordType
        recordsTyped {
            ... on QuestionSetRecordType {
                id
                qsetname
                type
                enable
                assetincludes  # ✅ List<Int> not Any
                buincludes
                showToAllSites
            }
        }
    }
}
```

---

## Kotlin Code Patterns

### Pattern 1: Type-Safe Iteration

```kotlin
val questions = response.data?.getQuestionsmodifiedafter?.recordsTyped

questions?.filterIsInstance<QuestionRecordType>()?.forEach { question ->
    println("Question: ${question.quesname}")

    if (question.answertype == "NUMERIC") {
        val range = "${question.min} - ${question.max}"
        showNumericQuestion(question.quesname, range)
    }
}
```

### Pattern 2: Exhaustive When

```kotlin
questions?.forEach { record ->
    when (record) {
        is QuestionRecordType -> handleQuestion(record)
        is LocationRecordType -> handleLocation(record)
        is AssetRecordType -> handleAsset(record)
        // Compiler ensures all types handled
    }
}
```

### Pattern 3: Null Safety

```kotlin
val record = questions?.firstOrNull() as? QuestionRecordType
val questionText = record?.quesname ?: "Unknown"  // ✅ Safe unwrapping
val answerType = record?.answertype  // ✅ String? (nullable)
```

---

## Testing Your Migration

### 1. Verify Schema Changes

```bash
# Download updated schema
./gradlew downloadApolloSchema

# Check for new fields
grep "recordsTyped" app/src/main/graphql/schema.graphqls
grep "recordType" app/src/main/graphql/schema.graphqls
```

### 2. Test Side-by-Side

```kotlin
@Test
fun `old and new fields return same data`() = runTest {
    val response = apolloClient.query(GetQuestions("2025-01-01", 1)).execute()
    val data = response.dataOrThrow().getQuestionsmodifiedafter

    // Parse old field manually
    val oldRecords = JSONArray(data.records.toString())
    val oldCount = oldRecords.length()

    // Use new typed field
    val newRecords = data.recordsTyped?.filterIsInstance<QuestionRecordType>()
    val newCount = newRecords?.size ?: 0

    // Should match
    assertEquals(oldCount, newCount)
}
```

### 3. Monitor Validation Errors

```kotlin
try {
    val response = apolloClient.query(GetQuestions(...)).execute()
    val records = response.dataOrThrow().getQuestionsmodifiedafter.recordsTyped
    // Process records...
} catch (e: ApolloException) {
    // Log for analytics
    analytics.track("graphql_parse_error", mapOf(
        "query" to "GetQuestions",
        "error" to e.message
    ))
    // Fallback to old field if needed
}
```

---

## Common Migration Issues

### Issue 1: Missing Fields in Fragment

**Problem**: Apollo error "Unknown field 'recordsTyped'"

**Solution**: Update GraphQL schema
```bash
./gradlew downloadApolloSchema
```

### Issue 2: Type Mismatch

**Problem**: `options` is `Any` instead of `List<String>`

**Solution**: Add field to fragment
```graphql
... on QuestionRecordType {
    options  # Must explicitly request
}
```

### Issue 3: Nullable Fields

**Problem**: Unexpected nulls

**Solution**: All fields are nullable - use safe calls
```kotlin
val options = record.options?.filterNotNull() ?: emptyList()
```

---

## Rollback Plan

If issues arise, you can rollback client-side:

### Option 1: Use Old Field Temporarily

```kotlin
// Fallback to old JSONString field
val recordsJson = data.records?.toString()
val jsonArray = JSONArray(recordsJson)
// Manual parsing (old way)
```

### Option 2: Feature Flag

```kotlin
val useTypedRecords = RemoteConfig.getBoolean("use_typed_graphql", false)

val records = if (useTypedRecords) {
    parseTypedRecords(data.recordsTyped)
} else {
    parseJsonRecords(data.records)  // Legacy
}
```

---

## Deprecation Timeline

| Date | Event | Action Required |
|------|-------|-----------------|
| **Oct 5, 2025** | `records_typed` field available | None (opt-in) |
| **Nov 16, 2025** | Deprecation warning added | Start migration |
| **Dec 31, 2025** | Sunset warning added | Complete migration |
| **Jun 30, 2026** | `records` field removed (v2.0) | Must use `records_typed` |

---

## Benefits of Migration

### Before (JSONString)

❌ No type safety
❌ Manual JSON parsing
❌ No IDE autocomplete
❌ Runtime errors from typos
❌ Hard to maintain
❌ No compile-time validation

### After (Typed Records)

✅ Full type safety with sealed classes
✅ No manual parsing
✅ IDE autocomplete works perfectly
✅ Compile-time error detection
✅ Easy to maintain and refactor
✅ Apollo generates all code

---

## Support & Resources

### Documentation

- **Apollo Kotlin**: https://www.apollographql.com/docs/kotlin
- **GraphQL Schema**: http://localhost:8000/api/graphql/ (GraphiQL)
- **Backend Code**: `apps/service/graphql_types/record_types.py`

### Testing Environments

| Environment | GraphQL Endpoint |
|------------|------------------|
| Development | `http://localhost:8000/api/graphql/` |
| Staging | `https://staging-api.youtility.in/api/graphql/` |
| Production | `https://api.youtility.in/api/graphql/` |

### Support Channels

- **Slack**: `#mobile-backend-integration`
- **Email**: `api-support@youtility.in`
- **Issues**: Create GitHub issue with `[GraphQL Migration]` prefix

---

## FAQ

### Q: Do I need to update all queries at once?

**A**: No! Update gradually:
1. Start with one query (e.g., questions)
2. Test thoroughly in dev
3. Deploy to staging
4. Migrate remaining queries
5. Remove old code after 6 weeks

### Q: What if I need new fields in the record type?

**A**: Request them! We can add fields to record types without breaking changes.

### Q: Can I use both old and new fields during migration?

**A**: Yes! The dual-field approach is designed for gradual migration. Use old field as fallback:

```kotlin
val records = data.recordsTyped?.takeIf { it.isNotEmpty() }
    ?: parseOldJsonRecords(data.records)
```

### Q: Will this affect GraphQL mutations?

**A**: No. This change only affects **query responses**. Mutations are unaffected.

### Q: How do I know which record type I'll get?

**A**: Check the `recordType` field:

```kotlin
when (data.recordType) {
    "question" -> data.recordsTyped?.filterIsInstance<QuestionRecordType>()
    "location" -> data.recordsTyped?.filterIsInstance<LocationRecordType>()
    // ...
}
```

---

## Next Steps

1. **This Week**: Review this guide and update one query
2. **Week 2**: Regenerate Apollo code and test
3. **Week 3-4**: Migrate remaining queries
4. **Week 5-6**: Remove old JSON parsing code
5. **After 6 weeks**: Enjoy fully type-safe GraphQL! 🎉

**Questions?** Contact the backend team - we're here to help with the migration!

---

**Last Updated**: October 5, 2025
**Backend Contact**: api@youtility.in
**Slack**: #mobile-backend-integration
