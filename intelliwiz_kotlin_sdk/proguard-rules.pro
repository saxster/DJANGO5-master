# Add project specific ProGuard rules here.
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# Keep telemetry client initialization
-keep class com.intelliwiz.mobile.telemetry.core.StreamTelemetryClient { *; }

# Keep data models for serialization
-keep class com.intelliwiz.mobile.telemetry.models.** { *; }

# Keep transport layer
-keep class com.intelliwiz.mobile.telemetry.transport.** { *; }

# Standard Android optimizations
-dontusemixedcaseclassnames
-dontskipnonpubliclibraryclasses
-verbose