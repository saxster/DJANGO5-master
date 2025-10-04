# Font Download & Installation Guide

**Industrial Minimal Design System - Self-Hosted Fonts**

## Overview

This guide explains how to download and install Inter and JetBrains Mono fonts for self-hosting (privacy, reliability, GDPR compliance).

---

## Required Fonts

### 1. **Inter** (Sans-serif - UI & Body Text)
- **Weights**: 400 (Regular), 600 (SemiBold)
- **Format**: WOFF2
- **Subset**: Latin only
- **Size**: ~30KB per weight (Latin subset)

### 2. **JetBrains Mono** (Monospace - Code & Data)
- **Weights**: 400 (Regular), 600 (SemiBold)
- **Format**: WOFF2
- **Subset**: Latin only
- **Size**: ~35KB per weight (Latin subset)

---

## Download Methods

### **Method 1: google-webfonts-helper (Recommended)**

This tool generates optimized font files and CSS automatically.

#### **Step 1: Download Inter**

1. Visit: https://gwfh.mranftl.com/fonts/inter
2. Select charset: **latin**
3. Select styles:
   - [x] regular (400)
   - [x] 600
4. Customize folder prefix: `/static/fonts/`
5. Click **Download files**
6. Extract the ZIP

#### **Step 2: Download JetBrains Mono**

1. Visit: https://gwfh.mranftl.com/fonts/jetbrains-mono
2. Select charset: **latin**
3. Select styles:
   - [x] regular (400)
   - [x] 600
4. Customize folder prefix: `/static/fonts/`
5. Click **Download files**
6. Extract the ZIP

---

### **Method 2: Official Sources**

#### **Inter**
1. Download from: https://fonts.google.com/specimen/Inter
2. Click **Download family**
3. Extract ZIP
4. Locate WOFF2 files in `/static/` folder:
   - `Inter-Regular.woff2`
   - `Inter-SemiBold.woff2`

#### **JetBrains Mono**
1. Download from: https://www.jetbrains.com/lp/mono/
2. Click **Download font**
3. Extract ZIP
4. Locate WOFF2 files in `/fonts/webfonts/` folder:
   - `JetBrainsMono-Regular.woff2`
   - `JetBrainsMono-SemiBold.woff2`

---

## Installation

### **Step 1: Create Fonts Directory**

```bash
mkdir -p frontend/static/fonts
```

### **Step 2: Copy Font Files**

Place the downloaded `.woff2` files in `frontend/static/fonts/` with these exact names:

```
frontend/static/fonts/
├── inter-v12-latin-regular.woff2       # Inter Regular (400)
├── inter-v12-latin-600.woff2           # Inter SemiBold (600)
├── jetbrains-mono-v13-latin-regular.woff2  # JetBrains Mono Regular (400)
└── jetbrains-mono-v13-latin-600.woff2      # JetBrains Mono SemiBold (600)
```

**Note**: If your downloaded files have different names, rename them to match the above.

### **Step 3: Verify File Sizes**

Optimal file sizes (Latin subset):

```bash
ls -lh frontend/static/fonts/

# Expected output (approximate):
# inter-v12-latin-regular.woff2       ~28-30KB
# inter-v12-latin-600.woff2           ~28-30KB
# jetbrains-mono-v13-latin-regular.woff2  ~33-35KB
# jetbrains-mono-v13-latin-600.woff2      ~33-35KB
```

If files are >100KB each, they likely include all character sets. Consider subsetting (see Advanced section below).

---

## Verification

### **Step 1: Collect Static Files**

```bash
python manage.py collectstatic --no-input
```

### **Step 2: Check Font Loading**

1. Start dev server: `python manage.py runserver`
2. Open browser DevTools → Network tab
3. Filter by "font"
4. Reload page
5. Verify fonts load with `200 OK` status

### **Step 3: Visual Check**

1. Visit: `http://localhost:8000/admin/`
2. Open DevTools → Inspect element
3. Check computed font-family:
   - Body text should show: `Inter, ...`
   - Code blocks should show: `JetBrains Mono, ...`

---

## Advanced: Font Subsetting

If you need to reduce file sizes further, use `pyftsubset` to create Latin-only subsets.

### Install `fonttools`

```bash
pip install fonttools brotli
```

### Subset Fonts

```bash
# Inter Regular
pyftsubset Inter-Regular.ttf \
  --output-file=inter-v12-latin-regular.woff2 \
  --flavor=woff2 \
  --layout-features='*' \
  --unicodes=U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD

# Inter SemiBold
pyftsubset Inter-SemiBold.ttf \
  --output-file=inter-v12-latin-600.woff2 \
  --flavor=woff2 \
  --layout-features='*' \
  --unicodes=U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD

# JetBrains Mono Regular
pyftsubset JetBrainsMono-Regular.ttf \
  --output-file=jetbrains-mono-v13-latin-regular.woff2 \
  --flavor=woff2 \
  --layout-features='*' \
  --unicodes=U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD

# JetBrains Mono SemiBold
pyftsubset JetBrainsMono-SemiBold.ttf \
  --output-file=jetbrains-mono-v13-latin-600.woff2 \
  --flavor=woff2 \
  --layout-features='*' \
  --unicodes=U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD
```

This reduces file sizes by ~60-70% while keeping all Latin characters.

---

## Performance Optimization

### **1. Preload Critical Fonts**

Add to base template `<head>`:

```html
<!-- frontend/templates/globals/base.html -->
<link rel="preload" href="{% static 'fonts/inter-v12-latin-regular.woff2' %}" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{% static 'fonts/inter-v12-latin-600.woff2' %}" as="font" type="font/woff2" crossorigin>
```

**Why**: Browsers discover fonts late in rendering; preload ensures early fetch.

### **2. Enable Compression**

Ensure your web server (Nginx, Apache) serves fonts with Brotli or Gzip compression.

**Nginx example**:

```nginx
# nginx.conf
location /static/fonts/ {
    expires 1y;
    add_header Cache-Control "public, immutable";

    # Brotli compression
    brotli on;
    brotli_types font/woff2;

    # Fallback to Gzip
    gzip on;
    gzip_types font/woff2;
}
```

### **3. Set Cache Headers**

Fonts rarely change - cache for 1 year:

```python
# settings.py
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# In production, WhiteNoise automatically:
# - Compresses static files (Brotli + Gzip)
# - Sets immutable cache headers
# - Serves with efficient HTTP/2 multiplexing
```

---

## Troubleshooting

### **Fonts Not Loading**

**Issue**: Fonts show as system fonts (Arial/Helvetica) instead of Inter.

**Solutions**:

1. **Check file paths**:
   ```bash
   ls frontend/static/fonts/
   # Should list all 4 .woff2 files
   ```

2. **Check browser Network tab**:
   - Open DevTools → Network → Filter: "font"
   - Reload page
   - Fonts should load with `200 OK` status
   - If `404 Not Found`: Run `python manage.py collectstatic`

3. **Check MIME types**:
   - Server must send `Content-Type: font/woff2` header
   - WhiteNoise handles this automatically

4. **Check CORS** (if fonts on different domain):
   ```html
   <link rel="preload" href="..." as="font" crossorigin>
   ```
   Add `crossorigin` attribute for cross-origin font loads.

### **Fonts Appear Blurry**

**Issue**: Fonts look fuzzy on Windows/Linux.

**Solution**: Ensure antialiasing is enabled in `tokens.css`:

```css
html {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}
```

### **Large File Sizes**

**Issue**: Font files are >100KB each.

**Solutions**:

1. **Use Latin subset only** (recommended for English-only apps)
2. **Use pyftsubset** (see Advanced section)
3. **Verify WOFF2 format** (not TTF/OTF)

### **Flash of Unstyled Text (FOUT)**

**Issue**: System font shows briefly before custom font loads.

**Expected Behavior**: This is normal and preferred over invisible text (FOIT).

**Minimize FOUT**:

```css
@font-face {
  font-display: swap;  /* Already set in fonts.css */
}
```

Preload critical fonts in `<head>` (see Performance Optimization above).

---

## CDN Alternative (Not Recommended)

If you absolutely cannot self-host fonts:

```html
<!-- Load from Google Fonts CDN -->
<link rel="preconnect" href="https://fonts.googleapis.com" crossorigin>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
```

**Downsides**:
- GDPR compliance issues (user data sent to Google)
- Single point of failure (if Google Fonts down, your fonts fail)
- Slower (extra DNS lookup + connection)
- No control over caching

**Recommendation**: Always self-host in production.

---

## Success Checklist

- [ ] All 4 font files downloaded (2x Inter, 2x JetBrains Mono)
- [ ] Files renamed to match `fonts.css` paths
- [ ] Files placed in `frontend/static/fonts/`
- [ ] `python manage.py collectstatic` run successfully
- [ ] Browser DevTools shows fonts loading with `200 OK`
- [ ] Admin pages display Inter font (not Arial/Helvetica)
- [ ] Code blocks display JetBrains Mono (not Courier)
- [ ] File sizes are optimal (<40KB per font)
- [ ] Fonts preloaded in base template `<head>`

---

## Resources

- **Inter**: https://rsms.me/inter/
- **JetBrains Mono**: https://www.jetbrains.com/lp/mono/
- **google-webfonts-helper**: https://gwfh.mranftl.com/
- **Font Subsetting Tool**: https://everythingfonts.com/subsetter
- **WOFF2 Converter**: https://cloudconvert.com/woff-to-woff2

---

**Next Step**: Once fonts are installed, load `fonts.css` in your base template:

```html
<!-- frontend/templates/globals/base.html -->
<link rel="stylesheet" href="{% static 'theme/fonts.css' %}">
<link rel="stylesheet" href="{% static 'theme/tokens.css' %}">
```
