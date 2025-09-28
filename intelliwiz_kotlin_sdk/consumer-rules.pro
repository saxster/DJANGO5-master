# Keep all telemetry SDK public APIs
-keep class com.intelliwiz.mobile.telemetry.** { *; }

# Keep kotlinx.serialization classes
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt

# Keep Ktor client classes for WebSocket/HTTP transport
-keep class io.ktor.** { *; }
-dontwarn io.ktor.**

# Keep OkHttp for network interception
-keep class okhttp3.** { *; }
-dontwarn okhttp3.**