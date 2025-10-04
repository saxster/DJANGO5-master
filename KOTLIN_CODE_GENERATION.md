# Kotlin/Android Design Token Code Generation

**Industrial Minimal Design System - Mobile Integration Guide**

This document explains how to generate Kotlin code from `design-tokens.json` to ensure visual consistency between Django web and Android mobile apps.

---

## 📋 Overview

The `design-tokens.json` file contains all design tokens (colors, spacing, typography, etc.) in a platform-agnostic format. This guide shows how to:

1. Generate Kotlin code from the JSON
2. Use design tokens in Jetpack Compose
3. Implement dark mode theming
4. Maintain synchronization with web platform

---

## 🎯 Goal: Unified Design Language

**Before**: Web uses `#155EEF`, Android uses `#377DFF` → Inconsistent branding
**After**: Both platforms use `YOUTILITYTheme.Color.Primary600` → Consistent branding

---

## 🛠️ Method 1: Manual Code Generation (Quick Start)

### **Step 1: Generate Kotlin Theme Object**

Create `app/src/main/java/work/youtility/design/YOUTILITYTheme.kt`:

```kotlin
package work.youtility.design

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * YOUTILITY Industrial Minimal Design System
 * Auto-generated from design-tokens.json
 *
 * DO NOT EDIT MANUALLY - regenerate when design tokens change
 */
object YOUTILITYTheme {

    /* ========================================
       COLORS
       ======================================== */

    object Color {
        // Primary - Cobalt Blue
        val Primary50 = Color(0xFFEFF6FF)
        val Primary100 = Color(0xFFDBEAFE)
        val Primary200 = Color(0xFFBFDBFE)
        val Primary300 = Color(0xFF93C5FD)
        val Primary400 = Color(0xFF60A5FA)
        val Primary500 = Color(0xFF3B82F6)
        val Primary600 = Color(0xFF155EEF)  // Main brand color
        val Primary700 = Color(0xFF0E4AC2)  // Hover/pressed
        val Primary800 = Color(0xFF1E40AF)
        val Primary900 = Color(0xFF1E3A8A)

        // Accent - Cyan
        val Accent400 = Color(0xFF22D3EE)
        val Accent500 = Color(0xFF06B6D4)  // Main accent
        val Accent600 = Color(0xFF0891B2)

        // Neutral - Cool Gray
        val Neutral50 = Color(0xFFF8FAFC)   // App background (light)
        val Neutral100 = Color(0xFFF1F5F9)  // Muted backgrounds
        val Neutral200 = Color(0xFFE2E8F0)  // Default borders
        val Neutral300 = Color(0xFFCBD5E1)
        val Neutral400 = Color(0xFF94A3B8)  // Disabled text
        val Neutral500 = Color(0xFF64748B)  // Muted text
        val Neutral600 = Color(0xFF475569)
        val Neutral700 = Color(0xFF334155)  // Secondary text
        val Neutral800 = Color(0xFF1E293B)
        val Neutral900 = Color(0xFF0F172A)  // Main text (light)

        // Success - Green
        val Success50 = Color(0xFFECFDF5)
        val Success100 = Color(0xFFD1FAE5)
        val Success500 = Color(0xFF10B981)
        val Success600 = Color(0xFF16A34A)  // Main success
        val Success700 = Color(0xFF047857)

        // Warning - Amber
        val Warning50 = Color(0xFFFFFBEB)
        val Warning100 = Color(0xFFFEF3C7)
        val Warning500 = Color(0xFFF59E0B)
        val Warning600 = Color(0xFFD97706)  // Main warning
        val Warning700 = Color(0xFFB45309)

        // Danger - Red
        val Danger50 = Color(0xFFFEF2F2)
        val Danger100 = Color(0xFFFEE2E2)
        val Danger500 = Color(0xFFEF4444)
        val Danger600 = Color(0xFFDC2626)  // Main danger
        val Danger700 = Color(0xFFB91C1C)

        // Info - Blue
        val Info50 = Color(0xFFEFF6FF)
        val Info100 = Color(0xFFDBEAFE)
        val Info500 = Color(0xFF3B82F6)
        val Info600 = Color(0xFF0EA5E9)  // Main info
        val Info700 = Color(0xFF0284C7)

        // Dark Mode - Backgrounds
        val DarkAppBackground = Color(0xFF0B1220)
        val DarkSurface = Color(0xFF0F172A)
        val DarkMuted = Color(0xFF111827)
        val DarkElevated = Color(0xFF1E293B)

        // Dark Mode - Text
        val DarkTextPrimary = Color(0xFFE5E7EB)
        val DarkTextSecondary = Color(0xFFCBD5E1)
        val DarkTextMuted = Color(0xFF94A3B8)
        val DarkTextDisabled = Color(0xFF64748B)

        // Dark Mode - Borders
        val DarkBorderDefault = Color(0xFF1F2937)
        val DarkBorderMuted = Color(0xFF111827)
        val DarkBorderStrong = Color(0xFF374151)
    }

    /* ========================================
       SPACING (8pt grid)
       ======================================== */

    object Spacing {
        val Space0: Dp = 0.dp
        val Space1: Dp = 4.dp
        val Space2: Dp = 8.dp
        val Space3: Dp = 12.dp
        val Space4: Dp = 16.dp   // Base unit
        val Space5: Dp = 20.dp
        val Space6: Dp = 24.dp
        val Space8: Dp = 32.dp
        val Space10: Dp = 40.dp
        val Space12: Dp = 48.dp
        val Space16: Dp = 64.dp
        val Space20: Dp = 80.dp
        val Space24: Dp = 96.dp
    }

    /* ========================================
       TYPOGRAPHY
       ======================================== */

    object Typography {
        // Font sizes
        val FontSizeXS: TextUnit = 12.sp
        val FontSizeSM: TextUnit = 14.sp   // Body text
        val FontSizeBase: TextUnit = 16.sp
        val FontSizeLG: TextUnit = 18.sp
        val FontSizeXL: TextUnit = 20.sp   // H3
        val FontSize2XL: TextUnit = 24.sp  // H2
        val FontSize3XL: TextUnit = 28.sp  // H1
        val FontSize4XL: TextUnit = 36.sp

        // Line heights (multipliers)
        const val LineHeightNone = 1.0f
        const val LineHeightTight = 1.25f   // Headings
        const val LineHeightNormal = 1.5f   // Body
        const val LineHeightRelaxed = 1.625f
        const val LineHeightLoose = 2.0f

        // Letter spacing
        val LetterSpacingTight = (-0.02).sp  // Headings
        val LetterSpacingNormal = 0.sp
        val LetterSpacingWide = 0.025.sp     // Uppercase labels
    }

    /* ========================================
       BORDER RADIUS
       ======================================== */

    object BorderRadius {
        val None: Dp = 0.dp
        val SM: Dp = 2.dp
        val Base: Dp = 4.dp    // Controls
        val MD: Dp = 6.dp      // Surfaces
        val LG: Dp = 8.dp
        val XL: Dp = 12.dp
        val XXL: Dp = 16.dp
        val Full: Dp = 9999.dp  // Pills, circles
    }

    /* ========================================
       BORDER WIDTH
       ======================================== */

    object BorderWidth {
        val None: Dp = 0.dp
        val Thin: Dp = 1.dp    // Default
        val Medium: Dp = 2.dp  // Emphasis
        val Thick: Dp = 4.dp   // Strong emphasis
    }

    /* ========================================
       OPACITY
       ======================================== */

    object Opacity {
        const val Transparent = 0f
        const val Low = 0.1f
        const val Medium = 0.5f
        const val Disabled = 0.6f
        const val High = 0.8f
        const val Opaque = 1f
    }
}
```

### **Step 2: Create Compose Theme**

Create `app/src/main/java/work/youtility/design/Theme.kt`:

```kotlin
package work.youtility.design

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/**
 * Light color scheme (industrial minimal)
 */
private val LightColorScheme = lightColorScheme(
    primary = YOUTILITYTheme.Color.Primary600,
    onPrimary = Color.White,
    primaryContainer = YOUTILITYTheme.Color.Primary100,
    onPrimaryContainer = YOUTILITYTheme.Color.Primary900,

    secondary = YOUTILITYTheme.Color.Accent500,
    onSecondary = Color.White,
    secondaryContainer = YOUTILITYTheme.Color.Accent400,
    onSecondaryContainer = YOUTILITYTheme.Color.Neutral900,

    tertiary = YOUTILITYTheme.Color.Info600,
    onTertiary = Color.White,

    error = YOUTILITYTheme.Color.Danger600,
    onError = Color.White,
    errorContainer = YOUTILITYTheme.Color.Danger50,
    onErrorContainer = YOUTILITYTheme.Color.Danger700,

    background = YOUTILITYTheme.Color.Neutral50,
    onBackground = YOUTILITYTheme.Color.Neutral900,

    surface = Color.White,
    onSurface = YOUTILITYTheme.Color.Neutral900,
    surfaceVariant = YOUTILITYTheme.Color.Neutral100,
    onSurfaceVariant = YOUTILITYTheme.Color.Neutral700,

    outline = YOUTILITYTheme.Color.Neutral200,
    outlineVariant = YOUTILITYTheme.Color.Neutral100
)

/**
 * Dark color scheme (industrial night)
 */
private val DarkColorScheme = darkColorScheme(
    primary = YOUTILITYTheme.Color.Primary500,  // Brighter in dark mode
    onPrimary = YOUTILITYTheme.Color.Neutral900,
    primaryContainer = YOUTILITYTheme.Color.Primary700,
    onPrimaryContainer = YOUTILITYTheme.Color.Primary100,

    secondary = YOUTILITYTheme.Color.Accent400,
    onSecondary = YOUTILITYTheme.Color.Neutral900,
    secondaryContainer = YOUTILITYTheme.Color.Accent600,
    onSecondaryContainer = YOUTILITYTheme.Color.Accent100,

    tertiary = YOUTILITYTheme.Color.Info500,
    onTertiary = YOUTILITYTheme.Color.Neutral900,

    error = YOUTILITYTheme.Color.Danger500,
    onError = Color.White,
    errorContainer = YOUTILITYTheme.Color.Danger700,
    onErrorContainer = YOUTILITYTheme.Color.Danger100,

    background = YOUTILITYTheme.Color.DarkAppBackground,
    onBackground = YOUTILITYTheme.Color.DarkTextPrimary,

    surface = YOUTILITYTheme.Color.DarkSurface,
    onSurface = YOUTILITYTheme.Color.DarkTextPrimary,
    surfaceVariant = YOUTILITYTheme.Color.DarkMuted,
    onSurfaceVariant = YOUTILITYTheme.Color.DarkTextSecondary,

    outline = YOUTILITYTheme.Color.DarkBorderDefault,
    outlineVariant = YOUTILITYTheme.Color.DarkBorderMuted
)

/**
 * YOUTILITY Industrial Minimal Theme
 *
 * Usage:
 * ```kotlin
 * YOUTILITYTheme {
 *     // Your composables here
 * }
 * ```
 */
@Composable
fun YOUTILITYComposeTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) {
        DarkColorScheme
    } else {
        LightColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = createYOUTILITYTypography(),
        shapes = createYOUTILITYShapes(),
        content = content
    )
}

/**
 * Typography definitions using Inter font
 */
private fun createYOUTILITYTypography() = androidx.compose.material3.Typography(
    displayLarge = androidx.compose.ui.text.TextStyle(
        fontSize = YOUTILITYTheme.Typography.FontSize4XL,
        lineHeight = (36.sp.value * YOUTILITYTheme.Typography.LineHeightTight).sp,
        letterSpacing = YOUTILITYTheme.Typography.LetterSpacingTight
    ),
    displayMedium = androidx.compose.ui.text.TextStyle(
        fontSize = YOUTILITYTheme.Typography.FontSize3XL,  // H1
        lineHeight = (28.sp.value * YOUTILITYTheme.Typography.LineHeightTight).sp,
        letterSpacing = YOUTILITYTheme.Typography.LetterSpacingTight
    ),
    headlineLarge = androidx.compose.ui.text.TextStyle(
        fontSize = YOUTILITYTheme.Typography.FontSize2XL,  // H2
        lineHeight = (24.sp.value * YOUTILITYTheme.Typography.LineHeightTight).sp,
        letterSpacing = YOUTILITYTheme.Typography.LetterSpacingTight
    ),
    headlineMedium = androidx.compose.ui.text.TextStyle(
        fontSize = YOUTILITYTheme.Typography.FontSizeXL,   // H3
        lineHeight = (20.sp.value * YOUTILITYTheme.Typography.LineHeightTight).sp,
        letterSpacing = YOUTILITYTheme.Typography.LetterSpacingTight
    ),
    bodyLarge = androidx.compose.ui.text.TextStyle(
        fontSize = YOUTILITYTheme.Typography.FontSizeBase,
        lineHeight = (16.sp.value * YOUTILITYTheme.Typography.LineHeightNormal).sp,
        letterSpacing = YOUTILITYTheme.Typography.LetterSpacingNormal
    ),
    bodyMedium = androidx.compose.ui.text.TextStyle(
        fontSize = YOUTILITYTheme.Typography.FontSizeSM,  // Body text
        lineHeight = (14.sp.value * YOUTILITYTheme.Typography.LineHeightNormal).sp,
        letterSpacing = YOUTILITYTheme.Typography.LetterSpacingNormal
    ),
    labelMedium = androidx.compose.ui.text.TextStyle(
        fontSize = YOUTILITYTheme.Typography.FontSizeXS,
        lineHeight = (12.sp.value * YOUTILITYTheme.Typography.LineHeightNormal).sp,
        letterSpacing = YOUTILITYTheme.Typography.LetterSpacingWide
    )
)

/**
 * Shape definitions using border radius tokens
 */
private fun createYOUTILITYShapes() = androidx.compose.material3.Shapes(
    extraSmall = androidx.compose.foundation.shape.RoundedCornerShape(YOUTILITYTheme.BorderRadius.SM),
    small = androidx.compose.foundation.shape.RoundedCornerShape(YOUTILITYTheme.BorderRadius.Base),  // Controls
    medium = androidx.compose.foundation.shape.RoundedCornerShape(YOUTILITYTheme.BorderRadius.MD),   // Surfaces
    large = androidx.compose.foundation.shape.RoundedCornerShape(YOUTILITYTheme.BorderRadius.LG),
    extraLarge = androidx.compose.foundation.shape.RoundedCornerShape(YOUTILITYTheme.BorderRadius.XL)
)
```

### **Step 3: Use in Your App**

```kotlin
// MainActivity.kt
import work.youtility.design.YOUTILITYComposeTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            YOUTILITYComposeTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    // Your app content
                    AttendanceScreen()
                }
            }
        }
    }
}

// Example composable using design tokens
@Composable
fun AttendanceCard(name: String, status: String) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(YOUTILITYTheme.Spacing.Space4),
        shape = RoundedCornerShape(YOUTILITYTheme.BorderRadius.MD),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        )
    ) {
        Row(
            modifier = Modifier.padding(YOUTILITYTheme.Spacing.Space4),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = name,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface
            )

            Spacer(modifier = Modifier.weight(1f))

            Badge(
                containerColor = when (status) {
                    "PRESENT" -> YOUTILITYTheme.Color.Success600
                    "ABSENT" -> YOUTILITYTheme.Color.Danger600
                    else -> YOUTILITYTheme.Color.Warning600
                }
            ) {
                Text(
                    text = status,
                    fontSize = YOUTILITYTheme.Typography.FontSizeXS,
                    color = Color.White
                )
            }
        }
    }
}
```

---

## 🤖 Method 2: Automated Code Generation (Recommended for Production)

Use **Style Dictionary** to automatically generate Kotlin code from `design-tokens.json`.

### **Step 1: Install Style Dictionary**

```bash
# In your Android project root
npm install -D style-dictionary
```

### **Step 2: Create Config File**

Create `style-dictionary.config.js`:

```javascript
module.exports = {
  source: ["../design-tokens.json"],  // Path to web design tokens
  platforms: {
    android: {
      transformGroup: "android",
      buildPath: "app/src/main/java/work/youtility/design/",
      files: [
        {
          destination: "YOUTILITYTheme.kt",
          format: "custom/kotlin",
          className: "YOUTILITYTheme"
        }
      ]
    }
  }
};
```

### **Step 3: Add Custom Format**

Create `custom-format.js`:

```javascript
module.exports = function(dictionary, config) {
  return `package ${config.packageName}

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Auto-generated design tokens
 * DO NOT EDIT MANUALLY
 */
object ${config.className} {
    ${dictionary.allProperties.map(prop => {
      // Generate Kotlin code for each token
      const name = prop.name.replace(/-/g, '_').toUpperCase();
      const value = formatValue(prop.value, prop.type);
      return `val ${name} = ${value}`;
    }).join('\n    ')}
}`;
};
```

### **Step 4: Run Code Generation**

```bash
npx style-dictionary build
```

This generates `YOUTILITYTheme.kt` automatically!

---

## 📱 Example: Building Industrial Minimal Button

```kotlin
@Composable
fun YOUTILITYButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    variant: ButtonVariant = ButtonVariant.Primary,
    enabled: Boolean = true
) {
    val backgroundColor = when (variant) {
        ButtonVariant.Primary -> if (enabled)
            YOUTILITYTheme.Color.Primary600
        else
            YOUTILITYTheme.Color.Neutral300

        ButtonVariant.Secondary -> Color.Transparent
        ButtonVariant.Danger -> YOUTILITYTheme.Color.Danger600
    }

    val contentColor = when (variant) {
        ButtonVariant.Primary -> Color.White
        ButtonVariant.Secondary -> YOUTILITYTheme.Color.Neutral900
        ButtonVariant.Danger -> Color.White
    }

    Button(
        onClick = onClick,
        modifier = modifier.height(40.dp),  // Hit target minimum
        enabled = enabled,
        shape = RoundedCornerShape(YOUTILITYTheme.BorderRadius.Base),
        colors = ButtonDefaults.buttonColors(
            containerColor = backgroundColor,
            contentColor = contentColor,
            disabledContainerColor = backgroundColor.copy(alpha = YOUTILITYTheme.Opacity.Disabled),
            disabledContentColor = contentColor.copy(alpha = YOUTILITYTheme.Opacity.Disabled)
        ),
        contentPadding = PaddingValues(
            horizontal = YOUTILITYTheme.Spacing.Space4,
            vertical = YOUTILITYTheme.Spacing.Space2
        )
    ) {
        Text(
            text = text,
            fontSize = YOUTILITYTheme.Typography.FontSizeSM,
            fontWeight = FontWeight.SemiBold
        )
    }
}

enum class ButtonVariant {
    Primary,
    Secondary,
    Danger
}
```

---

## ✅ Validation & Testing

### **Color Contrast Check**

```kotlin
// Test function to validate WCAG AA compliance
fun validateColorContrast() {
    val combinations = listOf(
        Pair(YOUTILITYTheme.Color.Primary600, Color.White),
        Pair(YOUTILITYTheme.Color.Neutral900, YOUTILITYTheme.Color.Neutral50),
        Pair(YOUTILITYTheme.Color.Success600, Color.White)
    )

    combinations.forEach { (foreground, background) ->
        val ratio = calculateContrastRatio(foreground, background)
        assert(ratio >= 4.5f) { "WCAG AA failed: $ratio" }
        Log.d("Contrast", "✓ WCAG AA passed: $ratio:1")
    }
}
```

---

## 🔄 Keeping Tokens Synchronized

### **Weekly Sync Process**

1. **Web team updates `design-tokens.json`**
2. **Commit to Git**
3. **Android team runs**:
   ```bash
   git pull origin main
   npx style-dictionary build
   ```
4. **Rebuild Android app**

### **CI/CD Integration**

Add to GitHub Actions:

```yaml
- name: Generate Kotlin Design Tokens
  run: |
    cd android/
    npm install
    npx style-dictionary build

- name: Commit generated files
  run: |
    git config user.name "Design Token Bot"
    git add app/src/main/java/work/youtility/design/YOUTILITYTheme.kt
    git commit -m "Update design tokens from web" || true
```

---

## 📚 Resources

- **Style Dictionary**: https://amzn.github.io/style-dictionary/
- **Material 3 Theming**: https://m3.material.io/develop/android/jetpack-compose
- **Compose Color Scheme**: https://developer.android.com/reference/kotlin/androidx/compose/material3/ColorScheme

---

**Status**: Ready for Android integration
**Next**: Run manual code generation or set up automated pipeline
