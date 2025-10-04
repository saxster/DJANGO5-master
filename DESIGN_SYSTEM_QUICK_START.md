# 🚀 Industrial Minimal Design System - 5-Minute Quick Start

**Get your design system running in 5 minutes!**

---

## ⚡ Super Quick Start (Copy-Paste Ready)

### **1. Download Fonts** (2 minutes)

```bash
# Create fonts directory
mkdir -p frontend/static/fonts

# Visit these URLs and download WOFF2 files:
# Inter: https://gwfh.mranftl.com/fonts/inter (select: latin, weights 400+600)
# JetBrains Mono: https://gwfh.mranftl.com/fonts/jetbrains-mono (select: latin, weights 400+600)

# Rename and place in frontend/static/fonts/:
# - inter-v12-latin-regular.woff2
# - inter-v12-latin-600.woff2
# - jetbrains-mono-v13-latin-regular.woff2
# - jetbrains-mono-v13-latin-600.woff2
```

**Detailed instructions**: See `FONT_DOWNLOAD_GUIDE.md`

---

### **2. Update Base Template** (1 minute)

**Add to `frontend/templates/globals/base.html` `<head>` section**:

```html
<!-- Industrial Minimal Design System -->
<link rel="preload" href="{% static 'fonts/inter-v12-latin-regular.woff2' %}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{% static 'theme/fonts.css' %}">
<link rel="stylesheet" href="{% static 'theme/tokens.css' %}">
<link rel="stylesheet" href="{% static 'theme/components/toast.css' %}">
<link rel="stylesheet" href="{% static 'theme/print.css' %}" media="print">
```

**Add before `</body>` tag**:

```html
<!-- Design System JavaScript -->
<script src="{% static 'theme/theme-toggle.js' %}"></script>
<script src="{% static 'theme/components/toast.js' %}"></script>
```

---

### **3. Add Dark Mode Toggle** (1 minute)

**Add to your header/navbar**:

```html
<button data-theme-toggle aria-label="Toggle dark mode" style="
  background: transparent;
  border: 1px solid var(--border-default);
  border-radius: 999px;
  width: 36px;
  height: 36px;
  cursor: pointer;
  color: var(--text-primary);
">
  🌙
</button>
```

**Or use Material Icons**:

```html
<button data-theme-toggle class="theme-toggle" aria-label="Toggle dark mode">
  <svg class="theme-icon-light" width="20" height="20" viewBox="0 0 20 20">
    <path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" fill="currentColor"/>
  </svg>
  <svg class="theme-icon-dark" width="20" height="20" viewBox="0 0 20 20">
    <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" fill="currentColor"/>
  </svg>
</button>
```

---

### **4. Deploy** (1 minute)

```bash
# Collect static files
python manage.py collectstatic --no-input

# Start server
python manage.py runserver
```

---

### **5. Test** (5 minutes)

**Visit these URLs**:

1. **Admin**: http://localhost:8000/admin/
   - ✅ See custom branding
   - ✅ Click dark mode toggle
   - ✅ Forms use new styling

2. **API Docs**: http://localhost:8000/api/docs/
   - ✅ See Swagger UI themed
   - ✅ Dark mode toggle works

3. **Style Guide**: http://localhost:8000/styleguide/
   - ✅ See all components
   - ✅ Test toast buttons

**Test Toast System**:

Open browser console and run:

```javascript
window.toast.success('Design system is working!');
window.toast.error('Test error notification');
window.toast.warning('Test warning');
window.toast.info('Test info');
```

---

## 🎨 Using Components (Copy-Paste Examples)

### **Button**

```django
{% include 'components/button.html' with
  text='Save Site'
  type='primary'
  icon='save'
  button_type='submit'
%}
```

### **Form Field**

```django
{% include 'components/form-field.html' with
  label='Site Name'
  name='site_name'
  required=True
  placeholder='Enter site name'
%}
```

### **Card**

```django
{% include 'components/card.html' with
  title='Active Guards'
  icon='people'
  elevated=True
%}
  <p>Card content here</p>
</div>
```

### **Toast (JavaScript)**

```javascript
// Show success message
window.toast.success('Data saved!');

// Show error with longer duration
window.toast.error('Failed to save', { duration: 8000 });

// With action button
window.toast.info('Report ready', {
  action: {
    text: 'Download',
    onClick: () => window.location.href = '/download/'
  }
});
```

---

## 🎯 Configuration (URLs)

**Add to `urls.py`**:

```python
from django.urls import path
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # API Schema & Docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(
        template_name='drf_spectacular/swagger_ui.html',
        url_name='schema'
    ), name='swagger-ui'),

    # Style Guide
    path('styleguide/', TemplateView.as_view(
        template_name='styleguide/index.html'
    ), name='styleguide'),
]
```

---

## 🧪 Run Tests

```bash
# Run all frontend tests
python -m pytest tests/frontend/ -v

# Expected output:
# tests/frontend/test_design_system.py .................... [20 PASSED]
# tests/frontend/test_accessibility.py .................... [25 PASSED]
```

---

## 📱 Kotlin Mobile Integration (Optional)

**Export design tokens to Android**:

1. Copy `design-tokens.json` to your Android project
2. Generate Kotlin code (see `KOTLIN_CODE_GENERATION.md`)
3. Use in Jetpack Compose:

```kotlin
YOUTILITYComposeTheme {
    Button(
        onClick = { },
        colors = ButtonDefaults.buttonColors(
            containerColor = YOUTILITYTheme.Color.Primary600
        )
    ) {
        Text("Save")
    }
}
```

---

## ✅ Success Checklist

After completing the above steps, verify:

- [ ] Fonts load (check DevTools Network tab)
- [ ] Admin has custom branding
- [ ] Dark mode toggle works
- [ ] Toast notifications appear
- [ ] Print preview looks professional
- [ ] Style guide loads at /styleguide/
- [ ] All tests pass
- [ ] Colors are cobalt blue (#155EEF), not old blue (#377dff)

---

## 🆘 Need Help?

- **Can't download fonts?** → See `FONT_DOWNLOAD_GUIDE.md`
- **Dark mode not working?** → Check browser console for errors
- **Components not styled?** → Ensure `collectstatic` ran successfully
- **Tests failing?** → Check file paths match directory structure
- **Want examples?** → Visit `/styleguide/` for live demos

---

## 📚 Full Documentation

For complete details, see:
- `DESIGN_SYSTEM_COMPLETE_GUIDE.md` - **This is the master guide**
- `FONT_DOWNLOAD_GUIDE.md` - Font installation
- `KOTLIN_CODE_GENERATION.md` - Android integration

---

**Total Time**: 5 minutes to deploy, 100% production-ready design system!

🎉 **Welcome to the YOUTILITY Industrial Minimal Design System!** 🎉
