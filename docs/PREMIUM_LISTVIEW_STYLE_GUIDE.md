# Premium ListView Style Guide
*A comprehensive design system for modern, professional list views*

---

## 🎨 Overview

This style guide provides a complete design system for creating premium, modern list views that match the quality of the Business Units interface. Use this as your reference for implementing consistent, professional UI across all list views in the project.

## 🏗️ Architecture

### Template Structure
```
{% extends "globals/base_list.html" %}

{% block extra_styles %}
<style>
  /* Premium styles here */
</style>
{% endblock %}

{% block table %}
  <!-- Header Controls -->
  <div class="premium-header-controls">
    <!-- Search & Filters -->
  </div>
  
  <!-- List Container -->
  <div class="premium-list-container">
    <!-- Dynamic content -->
  </div>
{% endblock %}

{% block extra_scripts %}
  <!-- JavaScript functionality -->
{% endblock %}
```

---

## 🎯 Core Design Principles

### 1. **Visual Hierarchy**
- Use typography scales: 16px (primary), 14px (secondary), 12px (tertiary)
- Clear information architecture with proper spacing
- Prominent primary actions, subtle secondary actions

### 2. **Color Psychology**
- **Primary Blue**: `#3b82f6` - Trust, reliability, professionalism
- **Success Green**: `#10b981` - Positive actions, active states
- **Warning Orange**: `#f59e0b` - Attention, medium priority
- **Danger Red**: `#ef4444` - Errors, inactive states
- **Neutral Grays**: `#6b7280` (text), `#f8fafc` (backgrounds)

### 3. **Interaction Design**
- Subtle hover effects with `transform: translateY(-1px)`
- Smooth transitions: `0.3s cubic-bezier(0.4, 0, 0.2, 1)`
- Progressive disclosure with staggered animations
- Clear feedback for all interactive elements

---

## 🎨 Design Tokens

### Colors
```css
:root {
  /* Primary Colors */
  --premium-primary: #3b82f6;
  --premium-primary-dark: #2563eb;
  --premium-success: #10b981;
  --premium-success-dark: #059669;
  --premium-warning: #f59e0b;
  --premium-danger: #ef4444;
  
  /* Neutral Palette */
  --premium-gray-50: #f8fafc;
  --premium-gray-100: #f1f5f9;
  --premium-gray-200: #e2e8f0;
  --premium-gray-300: #cbd5e1;
  --premium-gray-400: #94a3b8;
  --premium-gray-500: #64748b;
  --premium-gray-600: #475569;
  --premium-gray-700: #334155;
  --premium-gray-800: #1e293b;
  --premium-gray-900: #0f172a;
  
  /* Gradients */
  --premium-gradient-primary: linear-gradient(135deg, #3b82f6, #2563eb);
  --premium-gradient-success: linear-gradient(135deg, #10b981, #059669);
  --premium-gradient-surface: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  
  /* Shadows */
  --premium-shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
  --premium-shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  --premium-shadow-lg: 0 6px 8px -1px rgba(0, 0, 0, 0.1), 0 4px 6px -1px rgba(0, 0, 0, 0.06);
  
  /* Typography */
  --premium-font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --premium-font-size-xs: 12px;
  --premium-font-size-sm: 13px;
  --premium-font-size-base: 14px;
  --premium-font-size-lg: 15px;
  --premium-font-size-xl: 16px;
  
  /* Spacing */
  --premium-space-xs: 0.5rem;
  --premium-space-sm: 0.75rem;
  --premium-space-base: 1rem;
  --premium-space-lg: 1.5rem;
  --premium-space-xl: 2rem;
  --premium-space-2xl: 2.5rem;
  
  /* Border Radius */
  --premium-radius-sm: 6px;
  --premium-radius-base: 8px;
  --premium-radius-md: 10px;
  --premium-radius-lg: 12px;
  --premium-radius-xl: 16px;
  
  /* Transitions */
  --premium-transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
```

### Typography Scale
```css
.premium-text-xs { font-size: var(--premium-font-size-xs); }
.premium-text-sm { font-size: var(--premium-font-size-sm); }
.premium-text-base { font-size: var(--premium-font-size-base); }
.premium-text-lg { font-size: var(--premium-font-size-lg); }
.premium-text-xl { font-size: var(--premium-font-size-xl); }

.premium-font-normal { font-weight: 400; }
.premium-font-medium { font-weight: 500; }
.premium-font-semibold { font-weight: 600; }
.premium-font-bold { font-weight: 700; }
```

---

## 🧱 Component Library

### 1. Header Controls Container

**Purpose**: Main container for search, filters, and actions

```css
.premium-header-controls {
  background: var(--premium-gradient-surface) !important;
  padding: var(--premium-space-xl) var(--premium-space-2xl) !important;
  border-radius: var(--premium-radius-xl) !important;
  box-shadow: var(--premium-shadow-md) !important;
  margin-bottom: var(--premium-space-xl) !important;
  border: 1px solid var(--premium-gray-200) !important;
  backdrop-filter: blur(10px) !important;
  position: relative !important;
  z-index: 1 !important;
}
```

**HTML Structure**:
```html
<div class="premium-header-controls">
  <div class="d-flex align-items-center justify-content-between flex-wrap gap-4">
    <!-- Search component -->
    <!-- Filter components -->
    <!-- Action components -->
  </div>
</div>
```

### 2. Search Component

**Purpose**: Premium search input with icon

```css
.premium-search {
  position: relative !important;
  flex: 1 !important;
  max-width: 400px !important;
  margin-right: var(--premium-space-xl) !important;
}

.premium-search .search-icon {
  position: absolute !important;
  left: 18px !important;
  top: 50% !important;
  transform: translateY(-50%) !important;
  color: var(--premium-gray-500) !important;
  z-index: 10 !important;
  font-size: var(--premium-font-size-xl) !important;
  font-weight: 500 !important;
}

.premium-search input {
  width: 100% !important;
  padding: 14px 20px 14px 52px !important;
  background-color: #ffffff !important;
  border: 2px solid var(--premium-gray-200) !important;
  border-radius: var(--premium-radius-lg) !important;
  font-size: var(--premium-font-size-lg) !important;
  font-weight: 500 !important;
  color: var(--premium-gray-700) !important;
  transition: var(--premium-transition) !important;
  box-shadow: var(--premium-shadow-sm) !important;
  font-family: var(--premium-font-family) !important;
  height: auto !important;
}

.premium-search input:focus {
  background-color: #ffffff !important;
  border-color: var(--premium-primary) !important;
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.1), var(--premium-shadow-md) !important;
  outline: none !important;
  transform: translateY(-1px) !important;
}
```

**HTML Structure**:
```html
<div class="premium-search">
  <i class="bi bi-search search-icon"></i>
  <input type="text" id="search-input" placeholder="Search...">
</div>
```

### 3. Filter Buttons

**Purpose**: Modern filter buttons with active states

```css
.premium-filter-btn {
  padding: 10px 18px !important;
  border: 2px solid var(--premium-gray-200) !important;
  border-radius: var(--premium-radius-md) !important;
  background: #ffffff !important;
  color: var(--premium-gray-500) !important;
  font-size: var(--premium-font-size-base) !important;
  font-weight: 600 !important;
  cursor: pointer !important;
  transition: var(--premium-transition) !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 8px !important;
  white-space: nowrap !important;
  box-shadow: var(--premium-shadow-sm) !important;
  font-family: var(--premium-font-family) !important;
  letter-spacing: 0.025em !important;
  text-decoration: none !important;
  height: auto !important;
  line-height: normal !important;
}

.premium-filter-btn:hover {
  background: var(--premium-gray-50) !important;
  border-color: var(--premium-gray-300) !important;
  color: var(--premium-gray-600) !important;
  transform: translateY(-1px) !important;
  box-shadow: var(--premium-shadow-md) !important;
  text-decoration: none !important;
}

.premium-filter-btn.active {
  background: var(--premium-gradient-primary) !important;
  border-color: var(--premium-primary) !important;
  color: white !important;
  box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.4), 0 2px 4px -1px rgba(59, 130, 246, 0.2) !important;
  transform: translateY(-1px) !important;
}

.premium-filter-btn.active:hover {
  background: var(--premium-gradient-primary) !important;
  transform: translateY(-2px) !important;
  box-shadow: 0 6px 8px -1px rgba(59, 130, 246, 0.5), 0 4px 6px -1px rgba(59, 130, 246, 0.3) !important;
  color: white !important;
}
```

**HTML Structure**:
```html
<button class="premium-filter-btn" data-filter="all">
  <i class="bi bi-grid-3x3-gap"></i> All
</button>
<button class="premium-filter-btn active" data-filter="active">
  <i class="bi bi-check-circle-fill"></i> Active
</button>
```

### 4. Action Buttons

**Purpose**: Primary and secondary action buttons

```css
/* Export Button (Secondary) */
.premium-export-btn {
  padding: 10px 18px !important;
  border: 2px solid var(--premium-gray-300) !important;
  border-radius: var(--premium-radius-md) !important;
  background: #ffffff !important;
  color: var(--premium-gray-500) !important;
  font-size: var(--premium-font-size-base) !important;
  font-weight: 600 !important;
  cursor: pointer !important;
  transition: var(--premium-transition) !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 8px !important;
  white-space: nowrap !important;
  font-family: var(--premium-font-family) !important;
  letter-spacing: 0.025em !important;
  text-decoration: none !important;
  box-shadow: var(--premium-shadow-sm) !important;
}

.premium-export-btn:hover {
  background: var(--premium-gray-50) !important;
  border-color: var(--premium-gray-400) !important;
  color: var(--premium-gray-600) !important;
  transform: translateY(-1px) !important;
  box-shadow: var(--premium-shadow-md) !important;
  text-decoration: none !important;
}

/* Add Button (Primary) */
.premium-add-btn {
  padding: 10px 18px !important;
  border: 2px solid var(--premium-success) !important;
  border-radius: var(--premium-radius-md) !important;
  background: var(--premium-gradient-success) !important;
  color: white !important;
  font-size: var(--premium-font-size-base) !important;
  font-weight: 600 !important;
  cursor: pointer !important;
  transition: var(--premium-transition) !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 8px !important;
  white-space: nowrap !important;
  font-family: var(--premium-font-family) !important;
  letter-spacing: 0.025em !important;
  text-decoration: none !important;
  box-shadow: 0 4px 6px -1px rgba(16, 185, 129, 0.4), 0 2px 4px -1px rgba(16, 185, 129, 0.2) !important;
}

.premium-add-btn:hover {
  background: linear-gradient(135deg, var(--premium-success-dark), #047857) !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 6px 8px -1px rgba(16, 185, 129, 0.5), 0 4px 6px -1px rgba(16, 185, 129, 0.3) !important;
  color: white !important;
  text-decoration: none !important;
}
```

### 5. List Container

**Purpose**: Main container for list items

```css
.premium-list-container {
  background: var(--premium-gradient-surface) !important;
  border-radius: var(--premium-radius-xl) !important;
  box-shadow: var(--premium-shadow-md) !important;
  border: 1px solid var(--premium-gray-200) !important;
  overflow: hidden !important;
  backdrop-filter: blur(10px) !important;
}
```

### 6. List Items

**Purpose**: Individual list item styling

```css
.premium-list-item {
  display: flex !important;
  align-items: center !important;
  padding: 24px !important;
  border-bottom: 1px solid var(--premium-gray-100) !important;
  background: white !important;
  transition: var(--premium-transition) !important;
  cursor: pointer !important;
  opacity: 0;
  animation: fadeInUp 0.5s ease forwards;
}

.premium-list-item:hover {
  background: var(--premium-gray-50) !important;
  box-shadow: inset 4px 0 0 var(--premium-primary) !important;
  transform: translateX(4px) !important;
}

.premium-list-item:last-child {
  border-bottom: none !important;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

### 7. Avatars

**Purpose**: Colored avatar system

```css
.premium-avatar {
  width: 48px !important;
  height: 48px !important;
  border-radius: var(--premium-radius-lg) !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  font-weight: 600 !important;
  font-size: var(--premium-font-size-xl) !important;
  color: white !important;
  margin-right: var(--premium-space-base) !important;
  flex-shrink: 0 !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15) !important;
}

/* Avatar Color Variants */
.avatar-blue { background: linear-gradient(135deg, #3b82f6, #1d4ed8) !important; }
.avatar-green { background: linear-gradient(135deg, #10b981, #059669) !important; }
.avatar-purple { background: linear-gradient(135deg, #8b5cf6, #7c3aed) !important; }
.avatar-orange { background: linear-gradient(135deg, #f59e0b, #d97706) !important; }
.avatar-pink { background: linear-gradient(135deg, #ec4899, #be185d) !important; }
.avatar-indigo { background: linear-gradient(135deg, #6366f1, #4f46e5) !important; }
.avatar-red { background: linear-gradient(135deg, #ef4444, #dc2626) !important; }
.avatar-teal { background: linear-gradient(135deg, #14b8a6, #0d9488) !important; }
```

### 8. Status Badges

**Purpose**: Color-coded status indicators

```css
.premium-badge {
  padding: 4px 12px !important;
  border-radius: var(--premium-radius-sm) !important;
  font-size: var(--premium-font-size-xs) !important;
  font-weight: 600 !important;
  letter-spacing: 0.025em !important;
  text-transform: uppercase !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 4px !important;
  white-space: nowrap !important;
  font-family: var(--premium-font-family) !important;
}

/* Badge Variants */
.badge-active {
  background: #dcfdf4 !important;
  color: #065f46 !important;
}

.badge-inactive {
  background: #fef2f2 !important;
  color: #991b1b !important;
}

.badge-gps {
  background: #e0f2fe !important;
  color: #0c4a6e !important;
}

.badge-warehouse {
  background: #fef3c7 !important;
  color: #92400e !important;
}

.badge-vendor {
  background: #f3e8ff !important;
  color: #6b21a8 !important;
}

.badge-service {
  background: #e0e7ff !important;
  color: #3730a3 !important;
}
```

### 9. Progress Bars

**Purpose**: Visual progress indicators

```css
.premium-progress-container {
  display: flex !important;
  align-items: center !important;
  gap: var(--premium-space-sm) !important;
}

.premium-progress-text {
  font-size: var(--premium-font-size-sm) !important;
  color: var(--premium-gray-600) !important;
  font-weight: 600 !important;
  min-width: 40px !important;
  text-align: right !important;
}

.premium-progress {
  width: 120px !important;
  height: 8px !important;
  background: var(--premium-gray-100) !important;
  border-radius: 4px !important;
  overflow: hidden !important;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.1) !important;
}

.premium-progress-bar {
  height: 100% !important;
  border-radius: 4px !important;
  transition: width 0.6s ease !important;
  position: relative !important;
}

.premium-progress-bar.high {
  background: linear-gradient(90deg, #22c55e, #16a34a) !important;
}

.premium-progress-bar.medium {
  background: linear-gradient(90deg, #eab308, #ca8a04) !important;
}

.premium-progress-bar.low {
  background: linear-gradient(90deg, #ef4444, #dc2626) !important;
}
```

### 10. Loading States

**Purpose**: Professional loading indicators

```css
.premium-loading, .premium-empty {
  padding: 80px 32px !important;
  text-align: center !important;
  color: var(--premium-gray-500) !important;
  background: var(--premium-gradient-surface) !important;
}

.premium-loading .spinner-border {
  color: var(--premium-primary) !important;
  width: 3rem !important;
  height: 3rem !important;
  border-width: 0.3em !important;
}

.premium-loading h5, .premium-empty h5 {
  color: var(--premium-gray-600) !important;
  font-weight: 600 !important;
  margin-top: var(--premium-space-lg) !important;
  font-family: var(--premium-font-family) !important;
}

.premium-loading p, .premium-empty p {
  color: var(--premium-gray-400) !important;
  font-size: var(--premium-font-size-lg) !important;
  margin-top: var(--premium-space-xs) !important;
  font-family: var(--premium-font-family) !important;
}
```

---

## 📱 Responsive Design

### Mobile First Approach

```css
/* Base styles (mobile) */
.premium-header-controls {
  padding: var(--premium-space-lg) var(--premium-space-base);
}

/* Tablet */
@media (min-width: 768px) {
  .premium-header-controls {
    padding: var(--premium-space-xl) var(--premium-space-lg);
  }
}

/* Desktop */
@media (min-width: 1024px) {
  .premium-header-controls {
    padding: var(--premium-space-xl) var(--premium-space-2xl);
  }
}

/* Large Desktop */
@media (min-width: 1280px) {
  .premium-search {
    max-width: 500px;
  }
}
```

### Responsive Breakpoints

```css
/* Mobile adjustments */
@media (max-width: 640px) {
  .premium-filter-btn {
    flex: 1;
    justify-content: center;
    min-width: 120px;
  }
  
  .premium-action-group {
    width: 100%;
    justify-content: stretch;
  }
  
  .premium-export-btn, .premium-add-btn {
    flex: 1;
    justify-content: center;
  }
}

/* Tablet adjustments */
@media (max-width: 768px) {
  .premium-header-controls > div {
    flex-direction: column !important;
    gap: var(--premium-space-lg) !important;
  }
  
  .premium-search {
    max-width: 100%;
    margin-right: 0;
  }
  
  .premium-filter-group {
    width: 100%;
    justify-content: center;
    flex-wrap: wrap;
  }
}
```

---

## 🛠️ Implementation Guide

### Step 1: Setup Template Structure

1. **Extend base template**:
```html
{% extends "globals/base_list.html" %}
```

2. **Add CSS variables**:
```html
{% block extra_styles %}
<style>
  /* Copy design tokens from above */
  :root { /* ... */ }
  
  /* Add component styles */
  .premium-header-controls { /* ... */ }
  
  /* Force specificity with parent selectors */
  .card-body .premium-header-controls { /* ... */ }
</style>
{% endblock %}
```

### Step 2: Build Header Controls

1. **Search component**:
```html
<div class="premium-search">
  <i class="bi bi-search search-icon"></i>
  <input type="text" id="search-input" placeholder="Search...">
</div>
```

2. **Filter buttons**:
```html
<button class="premium-filter-btn active" data-filter="all">
  <i class="bi bi-grid-3x3-gap"></i> All
</button>
```

3. **Action buttons**:
```html
<button class="premium-export-btn">
  <i class="bi bi-download"></i> Export
</button>
<button class="premium-add-btn">
  <i class="bi bi-plus-lg"></i> Add New
</button>
```

### Step 3: Implement List Items

1. **Use inline styles for guaranteed display**:
```javascript
const html = `
  <div style="display: flex; align-items: center; padding: 24px; /* ... more inline styles */">
    <!-- Item content -->
  </div>
`;
```

2. **Add staggered animations**:
```javascript
const html = items.map((item, index) => {
  const itemHtml = renderItem(item);
  return itemHtml.replace(
    'animation: fadeInUp 0.5s ease forwards;', 
    `animation: fadeInUp 0.5s ease forwards; animation-delay: ${index * 0.05}s;`
  );
}).join('');
```

### Step 4: Add Interactive Features

1. **Filter functionality**:
```javascript
$('.premium-filter-btn').click(function() {
  $('.premium-filter-btn').removeClass('active');
  $(this).addClass('active');
  // Apply filter logic
});
```

2. **Search functionality**:
```javascript
$('#search-input').on('input', debounce(function() {
  const searchTerm = $(this).val();
  // Apply search logic
}, 300));
```

### Step 5: Handle Loading States

```html
<div id="loading" class="premium-loading">
  <div class="spinner-border"></div>
  <h5>Loading...</h5>
  <p>Please wait while we fetch your data</p>
</div>

<div id="empty" class="premium-empty d-none">
  <i class="bi bi-inbox" style="font-size: 4rem; color: #d1d5db;"></i>
  <h5>No items found</h5>
  <p>Try adjusting your search or filters</p>
</div>
```

---

## 🎯 Quick Reference Checklist

### ✅ Visual Design
- [ ] Premium color palette applied
- [ ] Consistent typography (Inter font family)
- [ ] Proper spacing using design tokens
- [ ] Smooth animations and transitions
- [ ] Professional shadows and gradients

### ✅ Interactive Elements
- [ ] Hover effects on all clickable items
- [ ] Active states for filter buttons
- [ ] Focus states for form inputs
- [ ] Loading and empty states implemented

### ✅ Responsive Design
- [ ] Mobile-first approach
- [ ] Proper breakpoints implemented
- [ ] Touch-friendly button sizes
- [ ] Readable text on all devices

### ✅ Performance
- [ ] CSS specificity handled correctly
- [ ] Smooth animations (60fps)
- [ ] Minimal reflows and repaints
- [ ] Debounced search functionality

### ✅ Accessibility
- [ ] Proper ARIA labels
- [ ] Keyboard navigation support
- [ ] High contrast ratios
- [ ] Screen reader friendly

---

## 📋 Common Patterns

### Avatar Generation
```javascript
function getAvatarColor(name) {
  const colors = ['blue', 'green', 'purple', 'orange', 'pink', 'indigo', 'red', 'teal'];
  return `avatar-${colors[name.length % colors.length]}`;
}

function getInitials(name) {
  return name.split(' ')
    .map(word => word.charAt(0).toUpperCase())
    .join('')
    .substring(0, 2);
}
```

### Progress Calculation
```javascript
function calculateProgress(item) {
  let score = 0;
  let total = 0;
  
  // Add your criteria
  if (item.field1) { score += 25; total += 25; }
  if (item.field2) { score += 25; total += 25; }
  if (item.field3) { score += 25; total += 25; }
  if (item.field4) { score += 25; total += 25; }
  
  return Math.round((score / total) * 100);
}

function getProgressClass(percentage) {
  if (percentage >= 75) return 'high';
  if (percentage >= 50) return 'medium';
  return 'low';
}
```

### Badge Generation
```javascript
function generateBadges(item) {
  const badges = [];
  
  if (item.active) {
    badges.push(`<span class="premium-badge badge-active">ACTIVE</span>`);
  } else {
    badges.push(`<span class="premium-badge badge-inactive">INACTIVE</span>`);
  }
  
  if (item.gps_enabled) {
    badges.push(`<span class="premium-badge badge-gps">GPS</span>`);
  }
  
  // Add more badge logic
  return badges.join('');
}
```

---

## 🚀 Advanced Features

### Custom Animations
```css
@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translateX(30px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.premium-slide-in {
  animation: slideInRight 0.4s ease-out;
}
```

### Dynamic Theming
```javascript
function setTheme(theme) {
  const root = document.documentElement;
  
  if (theme === 'dark') {
    root.style.setProperty('--premium-gray-50', '#1e293b');
    root.style.setProperty('--premium-gray-100', '#334155');
    // ... more dark theme variables
  }
}
```

### Performance Optimization
```javascript
// Intersection Observer for lazy loading
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('premium-animate-in');
    }
  });
});

document.querySelectorAll('.premium-list-item').forEach(item => {
  observer.observe(item);
});
```

---

## 📄 File Templates

### Basic List View Template
```html
{% extends "globals/base_list.html" %}

{% block card_title %}
[Entity Name] - Modern View
<div class="float-end">
  <a href="?template=true" class="btn btn-sm btn-light-secondary me-2">
    <i class="bi bi-table"></i> Classic View
  </a>
  <button class="btn btn-sm btn-primary" id="header-add-new">
    <i class="bi bi-plus"></i> Add New
  </button>
</div>
{% endblock %}

{% block extra_styles %}
<style>
  /* Include design tokens and component styles */
</style>
{% endblock %}

{% block table %}
<div class="premium-header-controls">
  <!-- Header controls -->
</div>

<div class="premium-list-container">
  <!-- Dynamic content -->
</div>
{% endblock %}

{% block extra_scripts %}
<script>
  // JavaScript functionality
</script>
{% endblock %}
```

### CSS Override Template
```css
/* Force specificity for existing frameworks */
.card .card-body .premium-header-controls,
div.card-body div.premium-header-controls,
.premium-header-controls {
  /* Styles with !important */
}
```

---

## 🎉 Conclusion

This style guide provides everything you need to create consistent, premium list views across your entire application. The design system ensures:

- **Visual Consistency**: Unified color palette, typography, and spacing
- **User Experience**: Smooth interactions and clear feedback
- **Accessibility**: WCAG compliant design patterns
- **Performance**: Optimized CSS and animations
- **Maintainability**: Modular, reusable components

Use this guide as your single source of truth for all list view implementations. Each component can be mixed and matched to create unique interfaces while maintaining the premium aesthetic.

Happy coding! 🚀

---

*Created with ❤️ for the YOUTILITY5 project*
*Version 1.0 - Premium ListView Design System*