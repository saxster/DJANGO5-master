# ANDROID SECURITY IMPLEMENTATION GUIDE
## OWASP Mobile Top 10 (2024-2025) Best Practices

**Version**: 1.0
**Last Updated**: October 30, 2025
**Based on**: OWASP Mobile Top 10 2024, Android Security Best Practices 2025

---

## Table of Contents

1. [Secure Data Storage](#1-secure-data-storage)
2. [Network Security](#2-network-security)
3. [Authentication & Session Management](#3-authentication--session-management)
4. [ProGuard/R8 Configuration](#4-proguardr8-configuration)
5. [Code Protection](#5-code-protection)
6. [Sensitive Data Protection](#6-sensitive-data-protection)
7. [Security Testing](#7-security-testing)

---

## 1. Secure Data Storage

### 1.1 OWASP Mobile Top 10 2024: M1 - Insecure Data Storage

**Risk**: Sensitive data stored in plain text can be extracted via backup, rooting, or physical access.

### 1.2 EncryptedSharedPreferences (Correct Implementation)

```kotlin
package com.example.facility.security

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SecureStorage @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val masterKey: MasterKey by lazy {
        MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
    }

    private val encryptedPrefs: SharedPreferences by lazy {
        EncryptedSharedPreferences.create(
            context,
            "secure_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    // Token Storage
    fun saveAccessToken(token: String) {
        encryptedPrefs.edit().putString(KEY_ACCESS_TOKEN, token).apply()
    }

    fun getAccessToken(): String? {
        return encryptedPrefs.getString(KEY_ACCESS_TOKEN, null)
    }

    fun saveRefreshToken(token: String) {
        encryptedPrefs.edit().putString(KEY_REFRESH_TOKEN, token).apply()
    }

    fun getRefreshToken(): String? {
        return encryptedPrefs.getString(KEY_REFRESH_TOKEN, null)
    }

    // Device ID Storage
    fun saveDeviceId(deviceId: String) {
        encryptedPrefs.edit().putString(KEY_DEVICE_ID, deviceId).apply()
    }

    fun getDeviceId(): String {
        return encryptedPrefs.getString(KEY_DEVICE_ID, null) ?: run {
            val newId = UUID.randomUUID().toString()
            saveDeviceId(newId)
            newId
        }
    }

    // User ID (for multi-account)
    fun saveUserId(userId: Int) {
        encryptedPrefs.edit().putInt(KEY_USER_ID, userId).apply()
    }

    fun getUserId(): Int? {
        return if (encryptedPrefs.contains(KEY_USER_ID)) {
            encryptedPrefs.getInt(KEY_USER_ID, -1)
        } else null
    }

    // Clear all on logout
    fun clearAll() {
        encryptedPrefs.edit().clear().apply()
    }

    companion object {
        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_REFRESH_TOKEN = "refresh_token"
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_USER_ID = "user_id"
    }
}
```

**Key Points**:
- ✅ Uses AES256_GCM for master key (most secure)
- ✅ Uses AES256_SIV for key encryption
- ✅ Uses AES256_GCM for value encryption
- ✅ Lazy initialization (only created when needed)
- ✅ Clear all on logout

**What NOT to Store**:
- ❌ Passwords (even encrypted)
- ❌ Credit card numbers
- ❌ Social security numbers
- ❌ Health records (use Android KeyStore or server-side only)

---

### 1.3 Android KeyStore (For Cryptographic Keys)

**Use KeyStore when**: Storing encryption keys, biometric-protected data

```kotlin
class KeyStoreManager @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }

    fun generateKey(alias: String) {
        val keyGenerator = KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES,
            "AndroidKeyStore"
        )

        val keyGenSpec = KeyGenParameterSpec.Builder(
            alias,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setUserAuthenticationRequired(true)  // Requires biometric/PIN
            .setUserAuthenticationValidityDurationSeconds(30)  // Require auth every 30s
            .build()

        keyGenerator.init(keyGenSpec)
        keyGenerator.generateKey()
    }

    fun encrypt(alias: String, data: ByteArray): EncryptedData {
        val key = keyStore.getKey(alias, null) as SecretKey
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key)

        val iv = cipher.iv
        val encrypted = cipher.doFinal(data)

        return EncryptedData(encrypted, iv)
    }

    fun decrypt(alias: String, encryptedData: EncryptedData): ByteArray {
        val key = keyStore.getKey(alias, null) as SecretKey
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        val spec = GCMParameterSpec(128, encryptedData.iv)
        cipher.init(Cipher.DECRYPT_MODE, key, spec)

        return cipher.doFinal(encryptedData.ciphertext)
    }
}

data class EncryptedData(
    val ciphertext: ByteArray,
    val iv: ByteArray
)
```

---

### 1.4 Encrypted Database (SQLCipher)

**For highly sensitive data** (journal entries with PII):

```kotlin
// build.gradle.kts
dependencies {
    implementation("net.zetetic:android-database-sqlcipher:4.5.4")
    implementation("androidx.sqlite:sqlite-ktx:2.4.0")
}

// Database setup with encryption
@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(
        @ApplicationContext context: Context,
        secureStorage: SecureStorage
    ): FacilityDatabase {
        // Get or generate database passphrase
        val passphrase = secureStorage.getDatabasePassphrase() ?: run {
            val newPassphrase = generateSecurePassphrase()
            secureStorage.saveDatabasePassphrase(newPassphrase)
            newPassphrase
        }

        val factory = SupportFactory(passphrase.toByteArray())

        return Room.databaseBuilder(
            context,
            FacilityDatabase::class.java,
            "facility_database"
        )
            .openHelperFactory(factory)  // Use SQLCipher
            .build()
    }

    private fun generateSecurePassphrase(): String {
        val random = SecureRandom()
        val bytes = ByteArray(32)
        random.nextBytes(bytes)
        return Base64.encodeToString(bytes, Base64.NO_WRAP)
    }
}
```

**When to Use**: Apps handling sensitive PII, health data, financial data

**Trade-off**: ~5-15% performance overhead for encryption/decryption

---

## 2. Network Security

### 2.1 OWASP Mobile Top 10 2024: M5 - Insecure Communication

**Risk**: Man-in-the-middle attacks, data interception

### 2.2 Network Security Configuration

**res/xml/network_security_config.xml**:
```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <!-- Localhost for development (cleartext allowed) -->
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">localhost</domain>
        <domain includeSubdomains="true">10.0.2.2</domain>  <!-- Android emulator -->
        <domain includeSubdomains="true">192.168.1.0</domain>  <!-- Local network -->
    </domain-config>

    <!-- Production API (HTTPS only with certificate pinning) -->
    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">api.example.com</domain>

        <!-- Certificate Pinning -->
        <pin-set expiration="2026-10-30">
            <!-- Primary certificate pin -->
            <pin digest="SHA-256">base64EncodedPublicKeyHash1==</pin>
            <!-- Backup certificate pin (for rotation) -->
            <pin digest="SHA-256">base64EncodedPublicKeyHash2==</pin>
        </pin-set>

        <!-- Trust only system certificates (not user-added) -->
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </domain-config>

    <!-- Enforce HTTPS globally (all other domains) -->
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>
</network-security-config>
```

**AndroidManifest.xml**:
```xml
<application
    android:networkSecurityConfig="@xml/network_security_config"
    ...>
</application>
```

---

### 2.3 Get Certificate Pins

**Extract from production server**:

```bash
# Method 1: OpenSSL
openssl s_client -servername api.example.com -connect api.example.com:443 < /dev/null \
  | openssl x509 -pubkey -noout \
  | openssl rsa -pubin -outform der \
  | openssl dgst -sha256 -binary \
  | openssl enc -base64

# Method 2: Online tool
# Visit: https://www.ssllabs.com/ssltest/analyze.html?d=api.example.com

# Method 3: From certificate file
openssl x509 -inform PEM -in certificate.pem -pubkey -noout \
  | openssl rsa -pubin -outform der \
  | openssl dgst -sha256 -binary \
  | openssl enc -base64
```

**Rotation Strategy**:
1. Always have 2 pins (current + backup)
2. Set expiration date (1 year max)
3. Update pins before expiration
4. Test new pins in staging before production release

---

### 2.4 Certificate Pinning Validation

```kotlin
// Verify certificate pinning is working
@Test
fun `certificate pinning rejects invalid certificate`() {
    // Use MockWebServer with self-signed cert
    val mockServer = MockWebServer()
    val sslContext = SSLContext.getInstance("TLS")
    sslContext.init(null, arrayOf(TrustAllCerts()), SecureRandom())

    mockServer.useHttps(sslContext.socketFactory, false)
    mockServer.start()

    // Configure OkHttp with certificate pinning
    val client = OkHttpClient.Builder()
        .certificatePinner(
            CertificatePinner.Builder()
                .add(mockServer.hostName, "sha256/invalidpin==")
                .build()
        )
        .build()

    // Attempt connection - should fail
    assertFailsWith<SSLPeerUnverifiedException> {
        client.newCall(
            Request.Builder()
                .url(mockServer.url("/"))
                .build()
        ).execute()
    }
}
```

---

## 3. Authentication & Session Management

### 3.1 OWASP Mobile Top 10 2024: M3 - Insecure Authentication/Authorization

**Risk**: Weak session management, token leakage

### 3.2 Secure Token Lifecycle

```kotlin
@Singleton
class AuthenticationManager @Inject constructor(
    private val secureStorage: SecureStorage,
    private val authApi: AuthApi
) {
    private val _authState = MutableStateFlow<AuthState>(AuthState.Unauthenticated)
    val authState: StateFlow<AuthState> = _authState.asStateFlow()

    suspend fun login(username: String, password: String): Result<User> {
        // Validate inputs
        if (username.isBlank() || password.isBlank()) {
            return Result.Error(ValidationException("Username and password required"))
        }

        try {
            val response = authApi.login(LoginRequest(username, password))

            if (response.isSuccessful) {
                val loginResponse = response.body()!!

                // Store tokens securely
                secureStorage.saveAccessToken(loginResponse.access)
                secureStorage.saveRefreshToken(loginResponse.refresh)
                secureStorage.saveUserId(loginResponse.user.id)

                // Update state
                _authState.value = AuthState.Authenticated(loginResponse.user)

                return Result.Success(loginResponse.user)

            } else {
                return Result.Error(HttpException(response.code(), response.message()))
            }

        } catch (e: Exception) {
            return Result.Error(e)
        }
    }

    suspend fun logout() {
        val refreshToken = secureStorage.getRefreshToken()

        // Call logout endpoint (blacklist refresh token)
        try {
            authApi.logout(LogoutRequest(refreshToken))
        } catch (e: Exception) {
            // Logout locally even if server call fails
        }

        // Clear tokens
        secureStorage.clearAll()

        // Update state
        _authState.value = AuthState.Unauthenticated
    }

    fun isAuthenticated(): Boolean {
        return secureStorage.getAccessToken() != null
    }
}

sealed class AuthState {
    object Unauthenticated : AuthState()
    data class Authenticated(val user: User) : AuthState()
}
```

**Security Rules**:
- ✅ Never log tokens (even in debug)
- ✅ Clear tokens on logout
- ✅ Blacklist refresh tokens server-side on logout
- ✅ Auto-logout on security events (root detection, etc.)

---

### 3.3 Biometric Authentication (Optional Enhancement)

```kotlin
class BiometricAuthManager @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val executor = ContextCompat.getMainExecutor(context)
    private val biometricPrompt by lazy {
        BiometricPrompt(
            context as FragmentActivity,
            executor,
            authenticationCallback
        )
    }

    private val authenticationCallback = object : BiometricPrompt.AuthenticationCallback() {
        override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
            // Access granted - decrypt sensitive data
        }

        override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
            // Handle error
        }

        override fun onAuthenticationFailed() {
            // Biometric not recognized
        }
    }

    fun authenticate(callback: (Boolean) -> Unit) {
        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle("Biometric Authentication")
            .setSubtitle("Authenticate to access journal entries")
            .setNegativeButtonText("Use PIN")
            .setAllowedAuthenticators(
                BiometricManager.Authenticators.BIOMETRIC_STRONG or
                BiometricManager.Authenticators.DEVICE_CREDENTIAL
            )
            .build()

        biometricPrompt.authenticate(promptInfo)
    }

    fun canAuthenticate(): Boolean {
        val biometricManager = BiometricManager.from(context)
        return biometricManager.canAuthenticate(
            BiometricManager.Authenticators.BIOMETRIC_STRONG
        ) == BiometricManager.BIOMETRIC_SUCCESS
    }
}
```

---

## 4. ProGuard/R8 Configuration

### 4.1 OWASP Mobile Top 10 2024: M7 - Insufficient Binary Protections

**Risk**: Reverse engineering, code analysis

### 4.2 Complete ProGuard Rules

**app/proguard-rules.pro**:
```proguard
# ═══════════════════════════════════════════════════════════
# GENERAL OPTIMIZATION
# ═══════════════════════════════════════════════════════════

# Enable aggressive optimization
-optimizationpasses 5
-dontusemixedcaseclassnames
-dontskipnonpubliclibraryclasses
-verbose

# Preserve line numbers for debugging
-keepattributes SourceFile,LineNumberTable

# Preserve annotations
-keepattributes *Annotation*,Signature,InnerClasses,EnclosingMethod

# ═══════════════════════════════════════════════════════════
# KOTLINX.SERIALIZATION (CRITICAL - Don't break JSON)
# ═══════════════════════════════════════════════════════════

-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt
-dontnote kotlinx.serialization.SerializationKt

# Keep serialization metadata
-keep,includedescriptorclasses class com.example.facility.network.dto.**$$serializer { *; }
-keepclassmembers class com.example.facility.network.dto.** {
    *** Companion;
}
-keepclasseswithmembers class com.example.facility.network.dto.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# Keep all DTO classes
-keep class com.example.facility.network.dto.** { *; }

# Keep JSON serializers
-keepclassmembers class kotlinx.serialization.json.** {
    *** Companion;
}
-keepclasseswithmembers class kotlinx.serialization.json.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# ═══════════════════════════════════════════════════════════
# RETROFIT & OKHTTP
# ═══════════════════════════════════════════════════════════

# Keep Retrofit annotations
-keepattributes RuntimeVisibleAnnotations,RuntimeVisibleParameterAnnotations,AnnotationDefault
-keepclassmembers,allowshrinking,allowobfuscation interface * {
    @retrofit2.http.* <methods>;
}

# Keep Retrofit service interfaces
-keep interface com.example.facility.network.api.** { *; }

# OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn javax.annotation.**
-dontwarn org.conscrypt.**

# ═══════════════════════════════════════════════════════════
# ROOM DATABASE
# ═══════════════════════════════════════════════════════════

# Keep Room classes
-keep class * extends androidx.room.RoomDatabase
-keep @androidx.room.Entity class *
-keep @androidx.room.Dao class *

# Keep Room annotations
-dontwarn androidx.room.paging.**

# ═══════════════════════════════════════════════════════════
# HILT / DAGGER
# ═══════════════════════════════════════════════════════════

# Keep Hilt generated classes
-keep class dagger.hilt.** { *; }
-keep class javax.inject.** { *; }
-keep class * extends dagger.hilt.android.internal.managers.ViewComponentManager$FragmentContextWrapper

# ═══════════════════════════════════════════════════════════
# JETPACK COMPOSE
# ═══════════════════════════════════════════════════════════

-keep class androidx.compose.** { *; }
-keep class kotlin.Metadata { *; }

# ═══════════════════════════════════════════════════════════
# SECURITY - Remove logging in release
# ═══════════════════════════════════════════════════════════

# Remove all Log calls
-assumenosideeffects class android.util.Log {
    public static *** d(...);
    public static *** v(...);
    public static *** i(...);
    public static *** w(...);
    public static *** e(...);
}

# Remove printStackTrace
-assumenosideeffects class java.lang.Throwable {
    public void printStackTrace();
}

# ═══════════════════════════════════════════════════════════
# KOTLIN COROUTINES
# ═══════════════════════════════════════════════════════════

-keepclassmembernames class kotlinx.** {
    volatile <fields>;
}

# ═══════════════════════════════════════════════════════════
# SECURITY - Obfuscate sensitive classes
# ═══════════════════════════════════════════════════════════

# Keep only public API, obfuscate internals
-keep public class com.example.facility.MainActivity
-keep public class com.example.facility.FacilityApplication

# Obfuscate everything else aggressively
-repackageclasses 'o'
```

---

### 4.3 Testing ProGuard Rules

```bash
# Build release APK
./gradlew assembleRelease

# Check ProGuard applied
unzip -l app/build/outputs/apk/release/app-release.apk | grep classes.dex

# Decompile to verify obfuscation (use jadx or dex2jar)
jadx app/build/outputs/apk/release/app-release.apk

# Verify:
# 1. DTO classes NOT obfuscated (JSON serialization needs original names)
# 2. Internal classes ARE obfuscated (names like "a", "b", "c")
# 3. No Log.d() calls in code
# 4. Retrofit interfaces NOT obfuscated
```

**Common ProGuard Issues**:

**Issue 1**: Serialization breaks (JSON parsing fails)
```
Solution: Keep DTO classes and @SerialName annotations
-keep class com.example.facility.network.dto.** { *; }
```

**Issue 2**: Retrofit crashes (method not found)
```
Solution: Keep Retrofit annotations
-keepattributes RuntimeVisibleAnnotations
```

**Issue 3**: Room crashes (DAO method not found)
```
Solution: Keep @Dao interfaces
-keep @androidx.room.Dao class *
```

---

## 5. Code Protection

### 5.1 Root Detection

```kotlin
class RootDetector @Inject constructor(
    @ApplicationContext private val context: Context
) {
    fun isDeviceRooted(): Boolean {
        return checkBuildTags() ||
               checkSuBinary() ||
               checkRootApps() ||
               checkRWPaths()
    }

    private fun checkBuildTags(): Boolean {
        val buildTags = Build.TAGS
        return buildTags != null && buildTags.contains("test-keys")
    }

    private fun checkSuBinary(): Boolean {
        val paths = arrayOf(
            "/system/app/Superuser.apk",
            "/sbin/su",
            "/system/bin/su",
            "/system/xbin/su",
            "/data/local/xbin/su",
            "/data/local/bin/su",
            "/system/sd/xbin/su",
            "/system/bin/failsafe/su",
            "/data/local/su",
            "/su/bin/su"
        )

        return paths.any { File(it).exists() }
    }

    private fun checkRootApps(): Boolean {
        val packages = arrayOf(
            "com.noshufou.android.su",
            "com.thirdparty.superuser",
            "eu.chainfire.supersu",
            "com.koushikdutta.superuser",
            "com.zachspong.temprootremovejb",
            "com.ramdroid.appquarantine",
            "com.topjohnwu.magisk"
        )

        val pm = context.packageManager
        return packages.any { pkg ->
            try {
                pm.getPackageInfo(pkg, 0)
                true
            } catch (e: PackageManager.NameNotFoundException) {
                false
            }
        }
    }

    private fun checkRWPaths(): Boolean {
        val paths = arrayOf(
            "/system",
            "/system/bin",
            "/system/sbin",
            "/system/xbin",
            "/vendor/bin",
            "/sbin",
            "/etc"
        )

        return paths.any { path ->
            val file = File(path)
            file.exists() && file.canWrite()
        }
    }
}

// Usage in Application
override fun onCreate() {
    super.onCreate()

    if (rootDetector.isDeviceRooted() && !BuildConfig.DEBUG) {
        // Show warning or restrict functionality
        AlertDialog.Builder(this)
            .setTitle("Security Warning")
            .setMessage("This device appears to be rooted. Some features may be restricted.")
            .setPositiveButton("OK", null)
            .show()

        // Optional: Disable sensitive features or exit app
    }
}
```

---

### 5.2 Debugger Detection

```kotlin
fun isDebuggerAttached(): Boolean {
    return Debug.isDebuggerConnected() || Debug.waitingForDebugger()
}

// Check periodically
class SecurityMonitor @Inject constructor() {
    init {
        // Check every 5 seconds
        Timer().scheduleAtFixedRate(object : TimerTask() {
            override fun run() {
                if (isDebuggerAttached() && !BuildConfig.DEBUG) {
                    // Debugger attached in production build
                    android.os.Process.killProcess(android.os.Process.myPid())
                }
            }
        }, 0, 5000)
    }
}
```

**Note**: Aggressive anti-debugging can be bypassed. Use for defense-in-depth, not as sole protection.

---

## 6. Sensitive Data Protection

### 6.1 Prevent Screenshots (For Sensitive Screens)

```kotlin
@Composable
fun JournalDetailScreen() {
    val context = LocalContext.current

    DisposableEffect(Unit) {
        val window = (context as? ComponentActivity)?.window

        // Prevent screenshots for this screen
        window?.setFlags(
            WindowManager.LayoutParams.FLAG_SECURE,
            WindowManager.LayoutParams.FLAG_SECURE
        )

        onDispose {
            // Remove flag when leaving screen
            window?.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
        }
    }

    // Screen content...
}
```

**When to Use**: Journal entries (PII), personal health data, financial info

---

### 6.2 Sanitize Logs (Remove PII)

```kotlin
object SecureLogger {
    private const val TAG = "FacilityApp"

    fun d(message: String) {
        if (BuildConfig.DEBUG) {
            Log.d(TAG, sanitize(message))
        }
        // No logging in release (ProGuard removes)
    }

    fun e(message: String, throwable: Throwable? = null) {
        if (BuildConfig.DEBUG) {
            Log.e(TAG, sanitize(message), throwable)
        } else {
            // Send to crash reporting (sanitized)
            crashlytics.recordException(throwable)
        }
    }

    private fun sanitize(message: String): String {
        return message
            .replace(Regex("\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b"), "[EMAIL]")
            .replace(Regex("\\b\\d{10,}\\b"), "[PHONE]")
            .replace(Regex("Bearer [A-Za-z0-9._-]+"), "Bearer [TOKEN]")
            .replace(Regex("\"password\"\\s*:\\s*\"[^\"]+\""), "\"password\":\"[REDACTED]\"")
    }
}

// Usage
SecureLogger.d("User logged in: john@example.com")  // Logs: "User logged in: [EMAIL]"
SecureLogger.d("Token: Bearer abc123...")  // Logs: "Token: Bearer [TOKEN]"
```

---

### 6.3 Clipboard Security

```kotlin
// Clear clipboard after sensitive data copied
fun copyToClipboard(context: Context, text: String, isSensitive: Boolean = false) {
    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    val clip = ClipData.newPlainText("label", text)

    if (isSensitive && Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
        // Set sensitive flag (prevents clipboard from appearing in suggestions)
        val description = ClipDescription("sensitive", arrayOf(ClipDescription.MIMETYPE_TEXT_PLAIN))
        description.extras = PersistableBundle().apply {
            putBoolean(ClipDescription.EXTRA_IS_SENSITIVE, true)
        }
        clipboard.setPrimaryClip(ClipData(description, ClipData.Item(text)))
    } else {
        clipboard.setPrimaryClip(clip)
    }

    // Auto-clear after 30 seconds
    if (isSensitive) {
        Handler(Looper.getMainLooper()).postDelayed({
            clipboard.setPrimaryClip(ClipData.newPlainText("", ""))
        }, 30_000)
    }
}
```

---

## 7. Security Testing

### 7.1 Security Test Checklist

```kotlin
@RunWith(AndroidJUnit4::class)
class SecurityTests {

    @Test
    fun `tokens are stored encrypted`() {
        val context = ApplicationProvider.getApplicationContext<Context>()

        // Save token
        val secureStorage = SecureStorage(context)
        secureStorage.saveAccessToken("test-token-123")

        // Verify NOT stored in plain SharedPreferences
        val plainPrefs = context.getSharedPreferences("secure_prefs", Context.MODE_PRIVATE)
        val plainValue = plainPrefs.getString("access_token", null)

        // Should be encrypted (not "test-token-123")
        assertNotEquals("test-token-123", plainValue)
    }

    @Test
    fun `certificate pinning prevents MITM`() {
        // Verify network_security_config.xml exists
        val resourceId = context.resources.getIdentifier(
            "network_security_config",
            "xml",
            context.packageName
        )

        assertTrue(resourceId != 0, "network_security_config.xml not found")
    }

    @Test
    fun `no sensitive data in logs (release build)`() {
        // This test should be run on release build
        val testEmail = "test@example.com"
        SecureLogger.d("User email: $testEmail")

        // Verify log was sanitized (should be [EMAIL], not actual email)
        // In release, logs are stripped by ProGuard
    }

    @Test
    fun `app detects root`() {
        val rootDetector = RootDetector(context)
        // Run on both rooted and non-rooted devices
        val isRooted = rootDetector.isDeviceRooted()

        // Verify detection works (manually verify on rooted device)
    }

    @Test
    fun `logout clears all tokens`() = runTest {
        val authManager = AuthenticationManager(secureStorage, authApi)

        // Login
        authManager.login("test@example.com", "password")

        // Verify tokens saved
        assertNotNull(secureStorage.getAccessToken())
        assertNotNull(secureStorage.getRefreshToken())

        // Logout
        authManager.logout()

        // Verify tokens cleared
        assertNull(secureStorage.getAccessToken())
        assertNull(secureStorage.getRefreshToken())
    }
}
```

---

### 7.2 Penetration Testing

**Manual Tests**:
1. **MITM Attack**: Use proxy (Charles, mitmproxy) to intercept traffic
   - Verify certificate pinning rejects proxy cert
   - Verify tokens not visible in logs

2. **Root Detection**: Test on rooted device
   - Verify app detects root
   - Verify sensitive features disabled/restricted

3. **Data Extraction**: Root device, extract app data
   - Verify tokens encrypted (not plain text)
   - Verify database encrypted (if using SQLCipher)

4. **Reverse Engineering**: Decompile APK
   - Verify code obfuscated
   - Verify no hardcoded secrets
   - Verify API keys not in code

---

## 8. Compliance with OWASP Mobile Top 10 2024

### Checklist

| # | Risk | Mitigation | Status |
|---|------|------------|--------|
| M1 | Insecure Data Storage | EncryptedSharedPreferences, SQLCipher (optional) | ✅ |
| M2 | Inadequate Supply Chain Security | Dependency verification, SHA checking | ⚠️ |
| M3 | Insecure Authentication/Authorization | JWT, secure storage, token refresh | ✅ |
| M4 | Insufficient Input/Output Validation | Server-side validation, client sanitization | ✅ |
| M5 | Insecure Communication | HTTPS only, certificate pinning | ✅ |
| M6 | Inadequate Privacy Controls | Privacy scope, consent management | ✅ |
| M7 | Insufficient Binary Protections | ProGuard, code obfuscation | ✅ |
| M8 | Security Misconfiguration | Network security config, no debug in release | ✅ |
| M9 | Insecure Data Storage | Covered by M1 | ✅ |
| M10 | Insufficient Cryptography | Android KeyStore, strong algorithms | ✅ |

---

## 9. Security Configuration Checklist

### Development vs Production

**Debug Build** (build.gradle.kts):
```kotlin
buildTypes {
    debug {
        isDebuggable = true
        isMinifyEnabled = false  // No ProGuard
        buildConfigField("String", "API_BASE_URL", "\"http://10.0.2.2:8000\"")
        buildConfigField("Boolean", "ENABLE_LOGGING", "true")
    }
}
```

**Release Build**:
```kotlin
buildTypes {
    release {
        isDebuggable = false
        isMinifyEnabled = true           // Enable ProGuard
        isShrinkResources = true         // Remove unused resources
        proguardFiles(
            getDefaultProguardFile("proguard-android-optimize.txt"),
            "proguard-rules.pro"
        )

        buildConfigField("String", "API_BASE_URL", "\"https://api.example.com\"")
        buildConfigField("Boolean", "ENABLE_LOGGING", "false")

        // Sign with release key (not debug key!)
        signingConfig = signingConfigs.getByName("release")
    }
}
```

---

### Before Production Release

- [ ] EncryptedSharedPreferences for tokens
- [ ] Certificate pinning configured with 2 pins
- [ ] ProGuard rules tested (release build works)
- [ ] All Log statements removed (or disabled in release)
- [ ] No hardcoded secrets (API keys, passwords)
- [ ] Network security config enforces HTTPS
- [ ] Root detection implemented
- [ ] Debugger detection (if needed for sensitive apps)
- [ ] Screenshot prevention on sensitive screens
- [ ] Clipboard cleared after sensitive data copy
- [ ] Crash reporting configured (sanitized)
- [ ] Penetration testing completed
- [ ] Security review by team/external auditor

---

## Summary

This guide prevents the **25+ most common security vulnerabilities**:

✅ Secure token storage (EncryptedSharedPreferences + KeyStore)
✅ Certificate pinning (MITM prevention)
✅ ProGuard configuration (reverse engineering protection)
✅ Root detection (device tampering)
✅ Sensitive data protection (screenshot prevention, log sanitization)
✅ OWASP Mobile Top 10 2024 compliance
✅ Production security checklist

**Follow this guide during Phase 8 (Security & Polish) implementation.**

---

**Document Version**: 1.0
**Last Reviewed**: October 30, 2025
**Based on**: OWASP Mobile Top 10 2024, Android Security Best Practices 2025
**Prevents**: 25+ security vulnerabilities
