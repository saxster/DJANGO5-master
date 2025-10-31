# DATA MAPPING GUIDE
## DTO ↔ Entity ↔ Cache Transformations

**Version**: 1.0
**Last Updated**: October 30, 2025
**Purpose**: Define exact data transformations between Django backend and Kotlin frontend

---

## Overview: One System, Two Databases

### Core Principle

**PostgreSQL (Django) and SQLite (Kotlin) serve DIFFERENT purposes** - they are NOT mirrors of each other.

```
┌──────────────────────────────────────────────────────────┐
│  DJANGO BACKEND - PostgreSQL                             │
│  Purpose: Source of Truth, Relational Integrity         │
│  Structure: Normalized (3NF), Foreign Keys, Constraints │
│                                                           │
│  Example: People table (20+ columns)                     │
│           + PeopleProfile (JOIN required)                │
│           + PeopleOrganizational (JOIN required)         │
└──────────────────────────────────────────────────────────┘
                           │
                           │ REST API (JSON)
                           ▼
┌──────────────────────────────────────────────────────────┐
│  KOTLIN FRONTEND - SQLite                                │
│  Purpose: Offline Cache, Fast Queries, Pending Queue    │
│  Structure: Denormalized (for reads), JSON blobs        │
│                                                           │
│  Example: people_cache (single table with all data)     │
│           + Denormalized name/email/site                 │
│           + JSON blob for capabilities                   │
│           + Cache metadata (TTL, staleness)              │
└──────────────────────────────────────────────────────────┘
```

---

## Complete Transformation Chains

### Read Flow (Django → Kotlin)

```
[1] PostgreSQL Model (Django ORM)
    ↓ (DRF Serializer)
[2] JSON over HTTP
    ↓ (Retrofit + kotlinx.serialization)
[3] DTO (Data Transfer Object - Kotlin data class)
    ↓ (Mapper.toDomain)
[4] Entity (Business Object - Domain layer)
    ↓ (Mapper.toCache)
[5] Cache Entity (Room database)
    ↓ (Room DAO query)
[6] Entity (Domain layer)
    ↓ (ViewModel)
[7] UI State (Compose)
```

### Write Flow (Kotlin → Django)

```
[1] UI Input (Compose)
    ↓ (ViewModel)
[2] Entity (Business Object - validated)
    ↓ (Mapper.toDto)
[3] DTO (Data Transfer Object)
    ↓ (Retrofit + kotlinx.serialization)
[4] JSON over HTTP
    ↓ (DRF Serializer)
[5] Django Model
    ↓ (ORM)
[6] PostgreSQL Database
```

---

## Type Conversions

### DateTime: ISO 8601 String ↔ Instant ↔ Long (Epoch)

**Django → JSON**:
```python
# Django Model
created_at = models.DateTimeField(auto_now_add=True)

# DRF Serializer Output
"created_at": "2025-10-30T09:00:00.123456Z"
```

**JSON → Kotlin DTO**:
```kotlin
@Serializable
data class JournalEntryDTO(
    @SerialName("created_at")
    val createdAt: Instant  // kotlinx-datetime
)

// Deserialization handled by kotlinx.serialization
val dto = Json.decodeFromString<JournalEntryDTO>(jsonString)
// dto.createdAt = Instant("2025-10-30T09:00:00.123456Z")
```

**DTO → Domain Entity**:
```kotlin
// No transformation needed - same type
data class JournalEntity(
    val createdAt: Instant  // Domain uses Instant directly
)

fun JournalEntryDTO.toDomain(): JournalEntity {
    return JournalEntity(
        createdAt = this.createdAt  // Direct assignment
    )
}
```

**Entity → Room Cache**:
```kotlin
@Entity(tableName = "journal_entry_local")
data class JournalCacheEntity(
    @PrimaryKey
    val id: String,

    @ColumnInfo(name = "created_at")
    val createdAtEpoch: Long  // Stored as Unix timestamp for SQLite
)

fun JournalEntity.toCache(): JournalCacheEntity {
    return JournalCacheEntity(
        createdAtEpoch = this.createdAt.toEpochMilliseconds()
    )
}

fun JournalCacheEntity.toDomain(): JournalEntity {
    return JournalEntity(
        createdAt = Instant.fromEpochMilliseconds(this.createdAtEpoch)
    )
}
```

---

### Enums: Django String Choices ↔ Kotlin Sealed Class

**Django Model**:
```python
class JournalEntry(models.Model):
    ENTRY_TYPE_CHOICES = [
        ('mood_check_in', 'Mood Check-In'),
        ('gratitude', 'Gratitude'),
        ('daily_reflection', 'Daily Reflection'),
    ]
    entry_type = models.CharField(max_length=50, choices=ENTRY_TYPE_CHOICES)
```

**JSON**:
```json
{
  "entry_type": "mood_check_in"
}
```

**Kotlin DTO** (generated):
```kotlin
@Serializable
enum class EntryTypeEnum {
    @SerialName("mood_check_in") MOOD_CHECK_IN,
    @SerialName("gratitude") GRATITUDE,
    @SerialName("daily_reflection") DAILY_REFLECTION
}

@Serializable
data class JournalEntryDTO(
    @SerialName("entry_type")
    val entryType: EntryTypeEnum
)
```

**Domain Entity** (sealed class for flexibility):
```kotlin
sealed class EntryType {
    abstract val key: String

    object MoodCheckIn : EntryType() {
        override val key = "mood_check_in"
    }

    object Gratitude : EntryType() {
        override val key = "gratitude"
    }

    object DailyReflection : EntryType() {
        override val key = "daily_reflection"
    }

    companion object {
        fun fromKey(key: String): EntryType = when (key) {
            "mood_check_in" -> MoodCheckIn
            "gratitude" -> Gratitude
            "daily_reflection" -> DailyReflection
            else -> throw IllegalArgumentException("Unknown entry type: $key")
        }
    }
}

// Mapper
fun EntryTypeEnum.toDomain(): EntryType = when (this) {
    EntryTypeEnum.MOOD_CHECK_IN -> EntryType.MoodCheckIn
    EntryTypeEnum.GRATITUDE -> EntryType.Gratitude
    EntryTypeEnum.DAILY_REFLECTION -> EntryType.DailyReflection
}

fun EntryType.toDto(): EntryTypeEnum = when (this) {
    EntryType.MoodCheckIn -> EntryTypeEnum.MOOD_CHECK_IN
    EntryType.Gratitude -> EntryTypeEnum.GRATITUDE
    EntryType.DailyReflection -> EntryTypeEnum.DAILY_REFLECTION
}
```

**Room Cache** (string for simplicity):
```kotlin
@Entity
data class JournalCacheEntity(
    @ColumnInfo(name = "entry_type")
    val entryType: String  // Store as string key
)

fun EntryType.toCache(): String = this.key

fun String.toEntryType(): EntryType = EntryType.fromKey(this)
```

---

### JSONField: Django JSON ↔ Kotlin Data Class ↔ Room String

**Django Model**:
```python
gratitude_items = models.JSONField(default=list)  # Array of strings

# Database: ["Great weather", "Good health", "Family time"]
```

**JSON**:
```json
{
  "gratitude_items": ["Great weather", "Good health", "Family time"]
}
```

**Kotlin DTO**:
```kotlin
@Serializable
data class JournalEntryDTO(
    @SerialName("gratitude_items")
    val gratitudeItems: List<String>? = null
)
```

**Domain Entity**:
```kotlin
data class JournalEntity(
    val gratitudeItems: List<String>  // Kotlin list
)

fun JournalEntryDTO.toDomain(): JournalEntity {
    return JournalEntity(
        gratitudeItems = this.gratitudeItems ?: emptyList()
    )
}
```

**Room Cache** (serialize as JSON string):
```kotlin
@Entity
data class JournalCacheEntity(
    @ColumnInfo(name = "gratitude_items_json")
    val gratitudeItemsJson: String  // Serialized JSON string
)

private val json = Json { encodeDefaults = false }

fun JournalEntity.toCache(): JournalCacheEntity {
    return JournalCacheEntity(
        gratitudeItemsJson = json.encodeToString(this.gratitudeItems)
    )
}

fun JournalCacheEntity.toDomain(): JournalEntity {
    return JournalEntity(
        gratitudeItems = json.decodeFromString<List<String>>(this.gratitudeItemsJson)
    )
}
```

---

### Spatial: PostGIS Point ↔ {lat, lng} JSON ↔ Room Separate Columns

**Django Model**:
```python
from django.contrib.gis.db import models

class PeopleEventlog(models.Model):
    location = models.PointField(geography=True, srid=4326)  # PostGIS

# Database: POINT(77.2090 28.6139)  -- lng, lat order (GeoJSON)
```

**DRF Serializer**:
```python
class AttendanceSerializer(serializers.ModelSerializer):
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()

    def get_lat(self, obj):
        return obj.location.y if obj.location else None

    def get_lng(self, obj):
        return obj.location.x if obj.location else None

    class Meta:
        model = PeopleEventlog
        fields = ['id', 'lat', 'lng', ...]
```

**JSON**:
```json
{
  "id": "uuid-abc-123",
  "lat": 28.6139,
  "lng": 77.2090
}
```

**Kotlin DTO**:
```kotlin
@Serializable
data class AttendanceDTO(
    val id: String,
    val lat: Double,
    val lng: Double
)
```

**Domain Entity** (value object):
```kotlin
@Serializable
data class Coordinates(
    val lat: Double,  // -90 to 90
    val lng: Double   // -180 to 180
) {
    init {
        require(lat in -90.0..90.0) { "Invalid latitude: $lat" }
        require(lng in -180.0..180.0) { "Invalid longitude: $lng" }
    }
}

data class AttendanceEntity(
    val id: String,
    val location: Coordinates
)

fun AttendanceDTO.toDomain(): AttendanceEntity {
    return AttendanceEntity(
        location = Coordinates(lat = this.lat, lng = this.lng)
    )
}
```

**Room Cache** (separate columns):
```kotlin
@Entity(tableName = "attendance_local")
data class AttendanceCacheEntity(
    @PrimaryKey
    val id: String,

    @ColumnInfo(name = "lat")
    val latitude: Double,

    @ColumnInfo(name = "lng")
    val longitude: Double
)

fun AttendanceEntity.toCache(): AttendanceCacheEntity {
    return AttendanceCacheEntity(
        latitude = this.location.lat,
        longitude = this.location.lng
    )
}

fun AttendanceCacheEntity.toDomain(): AttendanceEntity {
    return AttendanceEntity(
        location = Coordinates(lat = this.latitude, lng = this.longitude)
    )
}
```

---

## Complete Transformation Examples by Domain

### 1. Wellness: Journal Entry (Complex Nested Structure)

**Django Model** (25+ fields):
```python
class JournalEntry(models.Model):
    id = models.UUIDField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    entry_type = models.CharField(max_length=50, choices=ENTRY_TYPE_CHOICES)
    mood_rating = models.IntegerField(null=True, validators=[MinValueValidator(1), MaxValueValidator(10)])
    stress_level = models.IntegerField(null=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    gratitude_items = models.JSONField(default=list)
    location_coordinates = models.JSONField(null=True)  # {lat, lng}
    privacy_scope = models.CharField(max_length=20, choices=PRIVACY_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    # ... 15 more fields
```

**JSON Response**:
```json
{
  "id": "abc-123-def-456",
  "title": "Morning reflection",
  "entry_type": "mood_check_in",
  "mood_rating": 8,
  "stress_level": 2,
  "energy_level": 7,
  "gratitude_items": ["Great weather", "Productive morning"],
  "daily_goals": ["Complete inspection", "Review reports"],
  "location_coordinates": {"lat": 28.6139, "lng": 77.2090},
  "privacy_scope": "private",
  "created_at": "2025-10-30T09:00:00Z",
  "updated_at": "2025-10-30T09:00:00Z"
}
```

**Kotlin DTO** (generated):
```kotlin
@Serializable
data class JournalEntryDTO(
    val id: String,
    val title: String,
    @SerialName("entry_type") val entryType: EntryTypeEnum,
    @SerialName("mood_rating") val moodRating: Int? = null,
    @SerialName("stress_level") val stressLevel: Int? = null,
    @SerialName("energy_level") val energyLevel: Int? = null,
    @SerialName("gratitude_items") val gratitudeItems: List<String>? = null,
    @SerialName("daily_goals") val dailyGoals: List<String>? = null,
    @SerialName("location_coordinates") val locationCoordinates: CoordinatesDTO? = null,
    @SerialName("privacy_scope") val privacyScope: PrivacyScopeEnum,
    @SerialName("created_at") val createdAt: Instant,
    @SerialName("updated_at") val updatedAt: Instant
)

@Serializable
data class CoordinatesDTO(
    val lat: Double,
    val lng: Double
)
```

**Domain Entity**:
```kotlin
data class JournalEntry(
    val id: JournalId,
    val title: Title,
    val entryType: EntryType,
    val wellbeingMetrics: WellbeingMetrics?,
    val positiveReflections: PositiveReflections?,
    val locationContext: LocationContext?,
    val privacyScope: PrivacyScope,
    val audit: AuditInfo
)

@JvmInline
value class JournalId(val value: String)

@JvmInline
value class Title(val value: String) {
    init {
        require(value.length in 1..200) { "Title must be 1-200 chars" }
    }
}

data class WellbeingMetrics(
    val moodRating: MoodRating?,
    val stressLevel: StressLevel?,
    val energyLevel: EnergyLevel?
)

@JvmInline
value class MoodRating(val value: Int) {
    init {
        require(value in 1..10) { "Mood rating must be 1-10" }
    }
}

data class PositiveReflections(
    val gratitudeItems: List<String>,
    val dailyGoals: List<String>
)

data class LocationContext(
    val coordinates: Coordinates?
)

data class Coordinates(
    val lat: Double,
    val lng: Double
)

sealed class PrivacyScope {
    object Private : PrivacyScope()
    object Manager : PrivacyScope()
    object Team : PrivacyScope()
    object Aggregate : PrivacyScope()
    object Shared : PrivacyScope()

    companion object {
        fun fromString(value: String): PrivacyScope = when (value) {
            "private" -> Private
            "manager" -> Manager
            "team" -> Team
            "aggregate" -> Aggregate
            "shared" -> Shared
            else -> throw IllegalArgumentException("Unknown privacy scope: $value")
        }
    }
}
```

**Mapper (DTO → Domain)**:
```kotlin
class JournalMapper @Inject constructor(
    private val json: Json
) {
    fun toDomain(dto: JournalEntryDTO): JournalEntry {
        return JournalEntry(
            id = JournalId(dto.id),
            title = Title(dto.title),
            entryType = dto.entryType.toDomain(),
            wellbeingMetrics = WellbeingMetrics(
                moodRating = dto.moodRating?.let { MoodRating(it) },
                stressLevel = dto.stressLevel?.let { StressLevel(it) },
                energyLevel = dto.energyLevel?.let { EnergyLevel(it) }
            ),
            positiveReflections = PositiveReflections(
                gratitudeItems = dto.gratitudeItems ?: emptyList(),
                dailyGoals = dto.dailyGoals ?: emptyList()
            ),
            locationContext = LocationContext(
                coordinates = dto.locationCoordinates?.let {
                    Coordinates(lat = it.lat, lng = it.lng)
                }
            ),
            privacyScope = PrivacyScope.fromString(dto.privacyScope.name.lowercase()),
            audit = AuditInfo(
                createdAt = dto.createdAt,
                updatedAt = dto.updatedAt
            )
        )
    }
}
```

**Room Cache Entity** (denormalized):
```kotlin
@Entity(tableName = "journal_entry_local")
data class JournalCacheEntity(
    @PrimaryKey
    val id: String,

    val title: String,

    @ColumnInfo(name = "entry_type")
    val entryType: String,

    // Wellbeing metrics (separate columns for queries)
    @ColumnInfo(name = "mood_rating")
    val moodRating: Int?,

    @ColumnInfo(name = "stress_level")
    val stressLevel: Int?,

    @ColumnInfo(name = "energy_level")
    val energyLevel: Int?,

    // Complex fields as JSON
    @ColumnInfo(name = "gratitude_items_json")
    val gratitudeItemsJson: String,  // JSON array

    @ColumnInfo(name = "daily_goals_json")
    val dailyGoalsJson: String,  // JSON array

    // Location (separate columns)
    @ColumnInfo(name = "location_lat")
    val locationLat: Double?,

    @ColumnInfo(name = "location_lng")
    val locationLng: Double?,

    // Privacy
    @ColumnInfo(name = "privacy_scope")
    val privacyScope: String,

    // Sync metadata
    @ColumnInfo(name = "mobile_id")
    val mobileId: String,

    @ColumnInfo(name = "version")
    val version: Int,

    @ColumnInfo(name = "sync_status")
    val syncStatus: String,

    // Audit
    @ColumnInfo(name = "created_at")
    val createdAtEpoch: Long,

    @ColumnInfo(name = "updated_at")
    val updatedAtEpoch: Long
)
```

**Mapper (Entity → Cache)**:
```kotlin
fun JournalEntry.toCache(): JournalCacheEntity {
    return JournalCacheEntity(
        id = this.id.value,
        title = this.title.value,
        entryType = this.entryType.key,
        moodRating = this.wellbeingMetrics?.moodRating?.value,
        stressLevel = this.wellbeingMetrics?.stressLevel?.value,
        energyLevel = this.wellbeingMetrics?.energyLevel?.value,
        gratitudeItemsJson = json.encodeToString(this.positiveReflections?.gratitudeItems ?: emptyList()),
        dailyGoalsJson = json.encodeToString(this.positiveReflections?.dailyGoals ?: emptyList()),
        locationLat = this.locationContext?.coordinates?.lat,
        locationLng = this.locationContext?.coordinates?.lng,
        privacyScope = this.privacyScope::class.simpleName!!.lowercase(),
        mobileId = this.syncMetadata.mobileId,
        version = this.syncMetadata.version,
        syncStatus = this.syncMetadata.syncStatus.name,
        createdAtEpoch = this.audit.createdAt.toEpochMilliseconds(),
        updatedAtEpoch = this.audit.updatedAt.toEpochMilliseconds()
    )
}
```

**Why This Design?**:
- **Separate mood/stress columns**: Enable SQL queries like `WHERE mood_rating < 5`
- **JSON for arrays**: Gratitude items/goals don't need individual queries
- **Separate lat/lng**: Enable spatial queries (within radius)
- **Denormalized**: No joins needed for UI display

---

### 2. People: Multi-Model Denormalization

**Django Models** (3 separate tables):
```python
class People(AbstractBaseUser):  # Main table
    username = models.CharField(unique=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField()
    last_name = models.CharField()
    client_id = models.ForeignKey(Client)
    bu_id = models.ForeignKey(BusinessUnit, null=True)

class PeopleProfile(models.Model):  # Profile info (1-to-1)
    people = models.OneToOneField(People)
    phone = models.CharField()
    profile_image = models.ImageField()
    department = models.CharField()
    role = models.CharField()

class PeopleOrganizational(models.Model):  # Organizational (1-to-1)
    people = models.OneToOneField(People)
    site_ids = models.JSONField(default=list)  # Assigned sites
    manager_id = models.ForeignKey(People, null=True)
```

**DRF Serializer** (denormalized):
```python
class PeopleSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    phone = serializers.CharField(source='profile.phone', read_only=True)
    department = serializers.CharField(source='profile.department', read_only=True)
    role = serializers.CharField(source='profile.role', read_only=True)
    site_ids = serializers.ListField(source='organizational.site_ids', read_only=True)

    class Meta:
        model = People
        fields = ['id', 'username', 'email', 'full_name', 'phone', 'department', 'role', 'site_ids', ...]
```

**JSON Response**:
```json
{
  "id": 456,
  "username": "jdoe",
  "email": "jdoe@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "full_name": "John Doe",
  "phone": "+1234567890",
  "department": "Operations",
  "role": "Field Technician",
  "client_id": 10,
  "bu_id": 2,
  "site_ids": [5, 12, 18],
  "capabilities": {
    "view_reports": true,
    "create_reports": false
  }
}
```

**Kotlin DTO**:
```kotlin
@Serializable
data class PeopleDTO(
    val id: Int,
    val username: String,
    val email: String,
    @SerialName("first_name") val firstName: String,
    @SerialName("last_name") val lastName: String,
    @SerialName("full_name") val fullName: String,
    val phone: String? = null,
    val department: String? = null,
    val role: String? = null,
    @SerialName("client_id") val clientId: Int,
    @SerialName("bu_id") val buId: Int? = null,
    @SerialName("site_ids") val siteIds: List<Int>,
    val capabilities: Map<String, Boolean>
)
```

**Domain Entity**:
```kotlin
data class Person(
    val id: PersonId,
    val username: Username,
    val email: Email,
    val personalInfo: PersonalInfo,
    val organizationalInfo: OrganizationalInfo,
    val capabilities: Capabilities
)

@JvmInline
value class PersonId(val value: Int)

data class PersonalInfo(
    val firstName: String,
    val lastName: String,
    val fullName: String,
    val phone: PhoneNumber?
)

data class OrganizationalInfo(
    val department: String?,
    val role: String?,
    val clientId: Int,
    val buId: Int?,
    val assignedSiteIds: List<Int>
)

data class Capabilities(
    val permissions: Map<String, Boolean>
) {
    fun hasPermission(key: String): Boolean = permissions[key] == true
}
```

**Room Cache** (single denormalized table):
```kotlin
@Entity(tableName = "people_cache")
data class PersonCacheEntity(
    @PrimaryKey
    val id: Int,

    val username: String,
    val email: String,

    // Personal info (denormalized)
    @ColumnInfo(name = "first_name")
    val firstName: String,

    @ColumnInfo(name = "last_name")
    val lastName: String,

    @ColumnInfo(name = "full_name")
    val fullName: String,

    val phone: String?,

    // Organizational info (denormalized)
    val department: String?,
    val role: String?,

    @ColumnInfo(name = "client_id")
    val clientId: Int,

    @ColumnInfo(name = "bu_id")
    val buId: Int?,

    // JSON for arrays
    @ColumnInfo(name = "site_ids_json")
    val siteIdsJson: String,  // "[5, 12, 18]"

    @ColumnInfo(name = "capabilities_json")
    val capabilitiesJson: String,  // '{"view_reports": true, ...}'

    // Cache metadata
    @ColumnInfo(name = "fetched_at")
    val fetchedAt: Long,

    @ColumnInfo(name = "expires_at")
    val expiresAt: Long
)
```

**Why This Design?**:
- **Single table**: No joins needed (Django has 3 tables)
- **Denormalized**: Full name, phone, department all in one row
- **JSON for arrays/maps**: site_ids and capabilities as JSON strings
- **Fast queries**: Can query by department, role without joins

---

## Conflict Resolution Mapping

### Scenario: Concurrent Edits

**User edits journal entry offline while server version also changes.**

**Client State**:
```kotlin
JournalEntry(
    id = "abc-123",
    title = "Updated title (client)",
    moodRating = 9,
    mobileId = "mobile-uuid-abc",
    version = 2,  // Incremented locally
    syncStatus = PENDING_SYNC,
    updatedAt = Instant("2025-10-30T10:05:00Z")
)
```

**Server State**:
```json
{
  "id": "abc-123",
  "title": "Updated title (server)",
  "mood_rating": 7,
  "version": 2,
  "updated_at": "2025-10-30T10:03:00Z"
}
```

**Conflict Detection**:
```kotlin
if (clientVersion == serverVersion && clientUpdatedAt != serverUpdatedAt) {
    // Conflict detected
    handleConflict()
}
```

**Resolution Strategy: Last-Write-Wins**:
```kotlin
fun resolveConflict(client: JournalEntry, server: JournalEntryDTO): JournalEntry {
    return if (client.audit.updatedAt > Instant.parse(server.updatedAt)) {
        // Client wins
        client.copy(version = server.version + 1)  // Increment version
    } else {
        // Server wins
        server.toDomain()  // Accept server version
    }
}
```

**Alternative: Merge Strategy** (for non-conflicting fields):
```kotlin
fun mergeConflict(client: JournalEntry, server: JournalEntryDTO): JournalEntry {
    return client.copy(
        title = if (client.audit.updatedAt > server.updatedAt) client.title else Title(server.title),
        moodRating = MoodRating(maxOf(client.wellbeingMetrics?.moodRating?.value ?: 0, server.moodRating ?: 0)),  // Take higher rating
        gratitudeItems = (client.positiveReflections?.gratitudeItems.orEmpty() + server.gratitudeItems.orEmpty()).distinct(),  // Merge arrays
        version = server.version + 1
    )
}
```

---

## Summary

This guide defines **exact transformations** between Django and Kotlin:

✅ **DateTime**: ISO 8601 String ↔ Instant ↔ Long (epoch)
✅ **Enums**: String choices ↔ Sealed classes ↔ String keys
✅ **JSONField**: JSON ↔ Data classes ↔ Serialized strings
✅ **Spatial**: PostGIS Point ↔ {lat, lng} ↔ Separate columns
✅ **Multi-model**: 3 Django tables ↔ 1 denormalized SQLite table
✅ **Conflict Resolution**: Version tracking + timestamp comparison

**Key Principle**: SQLite is optimized for **client needs** (fast reads, offline queue), NOT a mirror of PostgreSQL.

---

**Document Version**: 1.0
**Last Reviewed**: October 30, 2025
**Reference**: [API_CONTRACT_FOUNDATION.md](./API_CONTRACT_FOUNDATION.md), [KOTLIN_PRD.md](./KOTLIN_PRD_SUMMARY.md)
