# Modern ListView Design Style Guide

## Overview
This document defines the modern ListView design style for YOUTILITY5 application. All new listviews should follow these patterns for consistency and premium user experience.

## Design Principles
- **Clean & Modern**: Minimalist design with solid colors and subtle shadows
- **Interactive**: Smooth transitions and hover effects
- **Responsive**: Mobile-first approach with adaptive layouts
- **Consistent**: Unified styling across all listviews
- **Accessible**: Clear visual hierarchy and readable typography

## Core Components

### 1. Page Structure

#### Template Inheritance
```django
{% extends "globals/base_list.html" %}
```

#### Card Title Block
```django
{% block card_title %}
[Entity] Directory - Modern View
<div class="float-end">
    <a href="{{ url('[app]:[entity]') }}?template=true" class="btn btn-sm btn-light-secondary me-2">
        <i class="bi bi-table"></i> Classic View
    </a>
    <button class="btn btn-sm btn-primary" id="header-add-new">
        <i class="bi bi-plus"></i> Add New
    </button>
</div>
{% endblock card_title %}
```

### 2. Header Controls Section

The header controls section contains search, filters, and action buttons with premium styling:

```html
<!-- Modern Header Controls -->
<div style="background: #ffffff; 
            padding: 2rem 2.5rem; 
            border-radius: 16px; 
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); 
            margin-bottom: 2rem; 
            border: 1px solid #e2e8f0; 
            backdrop-filter: blur(10px); 
            position: relative; 
            z-index: 1;">
    <div style="display: flex; align-items: center; gap: 24px; flex-wrap: wrap;">
        <!-- Components go here -->
    </div>
</div>
```

#### Search Bar Component
```html
<div style="position: relative; flex: 1; max-width: 400px; margin-right: 2rem;">
    <i class="bi bi-search" style="position: absolute; 
                                   left: 18px; 
                                   top: 50%; 
                                   transform: translateY(-50%); 
                                   color: #6b7280; 
                                   z-index: 10; 
                                   font-size: 16px; 
                                   font-weight: 500;"></i>
    <input type="text" 
           id="modern-search-input" 
           placeholder="Search [entities] by name, code, or other fields..."
           style="width: 100%; 
                  padding: 14px 20px 14px 52px; 
                  background-color: #ffffff; 
                  border: 2px solid #e5e7eb; 
                  border-radius: 12px; 
                  font-size: 15px; 
                  font-weight: 500; 
                  color: #1f2937; 
                  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); 
                  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06); 
                  font-family: 'Inter', system-ui, -apple-system, sans-serif; 
                  height: auto;"
           onfocus="this.style.borderColor='#3b82f6'; 
                    this.style.boxShadow='0 0 0 4px rgba(59, 130, 246, 0.1), 0 4px 6px -1px rgba(0, 0, 0, 0.1)'; 
                    this.style.transform='translateY(-1px)';"
           onblur="this.style.borderColor='#e5e7eb'; 
                   this.style.boxShadow='0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06)'; 
                   this.style.transform='translateY(0)';">
</div>
```

#### Filter Buttons
```html
<div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
    <!-- Active Filter Button (default state) -->
    <button class="filter-btn active-filter" 
            id="filter-all"
            style="padding: 10px 18px; 
                   border: 2px solid #e5e7eb; 
                   border-radius: 10px; 
                   background: #3b82f6; 
                   color: white; 
                   font-size: 14px; 
                   font-weight: 600; 
                   cursor: pointer; 
                   transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); 
                   display: inline-flex; 
                   align-items: center; 
                   gap: 8px; 
                   white-space: nowrap; 
                   box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.4), 0 2px 4px -1px rgba(59, 130, 246, 0.2); 
                   font-family: 'Inter', system-ui, -apple-system, sans-serif; 
                   letter-spacing: 0.025em; 
                   text-decoration: none; 
                   height: auto; 
                   line-height: normal; 
                   transform: translateY(-1px);"
            onmouseover="this.style.background='#2563eb'; 
                         this.style.transform='translateY(-2px)'; 
                         this.style.boxShadow='0 6px 8px -1px rgba(59, 130, 246, 0.5), 0 4px 6px -1px rgba(59, 130, 246, 0.3)';"
            onmouseout="if(this.classList.contains('active-filter')) { 
                            this.style.background='#3b82f6'; 
                            this.style.transform='translateY(-1px)'; 
                            this.style.boxShadow='0 4px 6px -1px rgba(59, 130, 246, 0.4), 0 2px 4px -1px rgba(59, 130, 246, 0.2)'; 
                        } else { 
                            this.style.background='#ffffff'; 
                            this.style.transform='translateY(0)'; 
                            this.style.boxShadow='0 1px 3px rgba(0, 0, 0, 0.1)'; 
                        }">
        <i class="bi bi-grid-3x3-gap"></i>
        All Items
    </button>
    
    <!-- Inactive Filter Button -->
    <button class="filter-btn" 
            id="filter-[type]"
            style="padding: 10px 18px; 
                   border: 2px solid #e5e7eb; 
                   border-radius: 10px; 
                   background: #ffffff; 
                   color: #6b7280; 
                   font-size: 14px; 
                   font-weight: 600; 
                   cursor: pointer; 
                   transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); 
                   display: inline-flex; 
                   align-items: center; 
                   gap: 8px; 
                   white-space: nowrap; 
                   box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1); 
                   font-family: 'Inter', system-ui, -apple-system, sans-serif; 
                   letter-spacing: 0.025em; 
                   text-decoration: none; 
                   height: auto; 
                   line-height: normal;"
            onmouseover="if(!this.classList.contains('active-filter')) { 
                            this.style.background='#f9fafb'; 
                            this.style.borderColor='#d1d5db'; 
                            this.style.color='#374151'; 
                            this.style.transform='translateY(-1px)'; 
                            this.style.boxShadow='0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'; 
                        }"
            onmouseout="if(!this.classList.contains('active-filter')) { 
                           this.style.background='#ffffff'; 
                           this.style.borderColor='#e5e7eb'; 
                           this.style.color='#6b7280'; 
                           this.style.transform='translateY(0)'; 
                           this.style.boxShadow='0 1px 3px rgba(0, 0, 0, 0.1)'; 
                       }">
        <i class="bi bi-[icon]"></i>
        Filter Name
    </button>
</div>
```

#### Action Buttons
```html
<div style="display: flex; align-items: center; gap: 12px; margin-left: auto;">
    <!-- Export Button -->
    <button id="export-btn"
            style="padding: 10px 18px; 
                   border: 2px solid #d1d5db; 
                   border-radius: 10px; 
                   background: #ffffff; 
                   color: #6b7280; 
                   font-size: 14px; 
                   font-weight: 600; 
                   cursor: pointer; 
                   transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); 
                   display: inline-flex; 
                   align-items: center; 
                   gap: 8px; 
                   white-space: nowrap; 
                   box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1); 
                   font-family: 'Inter', system-ui, -apple-system, sans-serif; 
                   letter-spacing: 0.025em; 
                   text-decoration: none; 
                   height: auto; 
                   line-height: normal;"
            onmouseover="this.style.background='#f9fafb'; 
                         this.style.borderColor='#9ca3af'; 
                         this.style.color='#374151'; 
                         this.style.transform='translateY(-1px)'; 
                         this.style.boxShadow='0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)';"
            onmouseout="this.style.background='#ffffff'; 
                        this.style.borderColor='#d1d5db'; 
                        this.style.color='#6b7280'; 
                        this.style.transform='translateY(0)'; 
                        this.style.boxShadow='0 1px 3px rgba(0, 0, 0, 0.1)';">
        <i class="bi bi-download"></i>
        Export
    </button>
    
    <!-- Add New Button -->
    <button id="add-new-btn"
            style="padding: 10px 18px; 
                   border: 2px solid #10b981; 
                   border-radius: 10px; 
                   background: #10b981; 
                   color: white; 
                   font-size: 14px; 
                   font-weight: 600; 
                   cursor: pointer; 
                   transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); 
                   display: inline-flex; 
                   align-items: center; 
                   gap: 8px; 
                   white-space: nowrap; 
                   box-shadow: 0 4px 6px -1px rgba(16, 185, 129, 0.4), 0 2px 4px -1px rgba(16, 185, 129, 0.2); 
                   font-family: 'Inter', system-ui, -apple-system, sans-serif; 
                   letter-spacing: 0.025em; 
                   text-decoration: none; 
                   height: auto; 
                   line-height: normal;"
            onmouseover="this.style.background='#059669'; 
                         this.style.transform='translateY(-1px)'; 
                         this.style.boxShadow='0 6px 8px -1px rgba(16, 185, 129, 0.5), 0 4px 6px -1px rgba(16, 185, 129, 0.3)';"
            onmouseout="this.style.background='#10b981'; 
                        this.style.transform='translateY(0)'; 
                        this.style.boxShadow='0 4px 6px -1px rgba(16, 185, 129, 0.4), 0 2px 4px -1px rgba(16, 185, 129, 0.2)';">
        <i class="bi bi-plus-lg"></i>
        Add [Entity]
    </button>
</div>
```

### 3. List Container

```html
<div class="premium-list" 
     style="background: #ffffff; 
            border-radius: 16px; 
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); 
            border: 1px solid #e5e7eb; 
            overflow: hidden; 
            backdrop-filter: blur(10px);">
    
    <!-- Table Header -->
    <div style="display: flex; 
                align-items: center; 
                min-height: 48px; 
                padding: 12px 16px; 
                background: #f8fafc; 
                border-bottom: 2px solid #e2e8f0; 
                font-weight: 600; 
                font-size: 13px; 
                color: #475569; 
                text-transform: uppercase; 
                letter-spacing: 0.05em; 
                font-family: 'Inter', system-ui, sans-serif;">
        <!-- Header columns -->
    </div>
    
    <!-- Content sections -->
    <div id="[entity]-loading" class="premium-loading">...</div>
    <div id="[entity]-list" class="d-none">...</div>
    <div id="[entity]-empty" class="premium-empty d-none">...</div>
</div>
```

### 4. List Item Row

```html
<div style="display: flex; 
            align-items: center; 
            min-height: 64px; 
            padding: 12px 16px; 
            border-bottom: 1px solid #f1f5f9; 
            background: white; 
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); 
            cursor: pointer; 
            opacity: 0; 
            animation: fadeInUp 0.5s ease forwards; 
            animation-delay: ${index * 0.03}s;"
     onmouseover="this.style.background='#f8fafc'; 
                  this.style.boxShadow='inset 3px 0 0 #3b82f6';"
     onmouseout="this.style.background='white'; 
                 this.style.boxShadow='none';"
     data-id="${item.id}">
    
    <!-- Avatar -->
    <div style="width: 48px; 
                height: 48px; 
                border-radius: 12px; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
                font-weight: 600; 
                font-size: 16px; 
                color: white; 
                margin-right: 16px; 
                flex-shrink: 0; 
                box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12); 
                background: ${avatarGradient};">
        ${initials}
    </div>
    
    <!-- Content Columns -->
    <div style="flex: 1; 
                min-width: 0; 
                display: grid; 
                grid-template-columns: [column-definition]; 
                gap: 16px; 
                align-items: center;">
        <!-- Column content -->
    </div>
    
    <!-- Status Badges -->
    <div style="display: flex; 
                align-items: center; 
                gap: 4px; 
                margin: 0 12px; 
                min-width: 150px; 
                justify-content: flex-end;">
        <!-- Badges -->
    </div>
    
    <!-- Action Buttons -->
    <div style="display: flex; gap: 4px;">
        <!-- Edit/View buttons -->
    </div>
</div>
```

### 5. Status Badges

```html
<!-- Active Badge -->
<span style="padding: 2px 8px; 
             border-radius: 4px; 
             font-size: 10px; 
             font-weight: 600; 
             letter-spacing: 0.025em; 
             text-transform: uppercase; 
             display: inline-flex; 
             align-items: center; 
             gap: 2px; 
             white-space: nowrap; 
             font-family: 'Inter', system-ui, sans-serif; 
             background: #dcfdf4; 
             color: #065f46;">
    ACTIVE
</span>

<!-- Inactive Badge -->
<span style="[base-badge-style] background: #fef2f2; color: #991b1b;">INACTIVE</span>

<!-- Info Badge -->
<span style="[base-badge-style] background: #e0f2fe; color: #0c4a6e;">INFO</span>

<!-- Warning Badge -->
<span style="[base-badge-style] background: #fef3c7; color: #92400e;">WARNING</span>

<!-- Custom Badge -->
<span style="[base-badge-style] background: #f3e8ff; color: #6b21a8;">CUSTOM</span>
```

### 6. Action Buttons

```html
<!-- Edit Button -->
<button onclick="edit[Entity](${item.id})" 
        title="Edit"
        style="width: 28px; 
               height: 28px; 
               border-radius: 5px; 
               border: 1px solid #e2e8f0; 
               background: white; 
               color: #64748b; 
               cursor: pointer; 
               transition: all 0.2s ease; 
               display: flex; 
               align-items: center; 
               justify-content: center; 
               font-size: 12px;"
        onmouseover="this.style.background='#f1f5f9'; 
                     this.style.borderColor='#cbd5e1'; 
                     this.style.color='#3b82f6';"
        onmouseout="this.style.background='white'; 
                    this.style.borderColor='#e2e8f0'; 
                    this.style.color='#64748b';">
    <i class="bi bi-pencil"></i>
</button>

<!-- View Button -->
<button onclick="view[Entity](${item.id})" 
        title="View"
        style="width: 28px; 
               height: 28px; 
               border-radius: 5px; 
               border: 1px solid #e2e8f0; 
               background: white; 
               color: #64748b; 
               cursor: pointer; 
               transition: all 0.2s ease; 
               display: flex; 
               align-items: center; 
               justify-content: center; 
               font-size: 12px;"
        onmouseover="this.style.background='#f1f5f9'; 
                     this.style.borderColor='#cbd5e1'; 
                     this.style.color='#10b981';"
        onmouseout="this.style.background='white'; 
                    this.style.borderColor='#e2e8f0'; 
                    this.style.color='#64748b';">
    <i class="bi bi-eye"></i>
</button>
```

### 7. Loading & Empty States

```html
<!-- Loading State -->
<div id="[entity]-loading" class="premium-loading" 
     style="padding: 80px 32px; 
            text-align: center; 
            color: #6b7280; 
            background: #f8fafc;">
    <div class="spinner-border" role="status" 
         style="color: #3b82f6; 
                width: 3rem; 
                height: 3rem; 
                border-width: 0.3em;">
        <span class="visually-hidden">Loading...</span>
    </div>
    <h5 style="color: #374151; 
               font-weight: 600; 
               margin-top: 1.5rem; 
               font-family: 'Inter', system-ui, -apple-system, sans-serif;">
        Loading [entities]...
    </h5>
    <p style="color: #9ca3af; 
              font-size: 15px; 
              margin-top: 0.5rem; 
              font-family: 'Inter', system-ui, -apple-system, sans-serif;">
        Please wait while we fetch your data
    </p>
</div>

<!-- Empty State -->
<div id="[entity]-empty" class="premium-empty d-none" 
     style="padding: 80px 32px; 
            text-align: center; 
            color: #6b7280; 
            background: #f8fafc;">
    <i class="bi bi-[icon]-exclamation" 
       style="font-size: 4rem; 
              color: #d1d5db; 
              margin-bottom: 1rem;"></i>
    <h5 style="color: #374151; 
               font-weight: 600; 
               margin-top: 1.5rem; 
               font-family: 'Inter', system-ui, -apple-system, sans-serif;">
        No [entities] found
    </h5>
    <p style="color: #9ca3af; 
              font-size: 15px; 
              margin-top: 0.5rem; 
              font-family: 'Inter', system-ui, -apple-system, sans-serif;">
        Try adjusting your search criteria or filters to find what you're looking for
    </p>
</div>
```

## JavaScript Patterns

### 1. Filter Management

```javascript
// Filter state management
let currentFilter = 'all';
let currentSearch = '';
let items = [];

// Set active filter button
function setActiveFilter(button) {
    // Reset all filter buttons
    $('.filter-btn').each(function() {
        $(this).removeClass('active-filter');
        this.style.background = '#ffffff';
        this.style.color = '#6b7280';
        this.style.borderColor = '#e5e7eb';
        this.style.transform = 'translateY(0)';
        this.style.boxShadow = '0 1px 3px rgba(0, 0, 0, 0.1)';
    });
    
    // Set active state
    $(button).addClass('active-filter');
    button.style.background = '#3b82f6';
    button.style.color = 'white';
    button.style.borderColor = '#3b82f6';
    button.style.transform = 'translateY(-1px)';
    button.style.boxShadow = '0 4px 6px -1px rgba(59, 130, 246, 0.4), 0 2px 4px -1px rgba(59, 130, 246, 0.2)';
}

// Filter click handlers
$('#filter-all').click(function() {
    if (currentFilter === 'all') return;
    setActiveFilter(this);
    currentFilter = 'all';
    applyFiltersAndRender();
});
```

### 2. Search Implementation

```javascript
// Search with debounce
let searchTimeout;
$('#modern-search-input').on('input', function() {
    clearTimeout(searchTimeout);
    const searchValue = $(this).val();
    searchTimeout = setTimeout(function() {
        currentSearch = searchValue;
        applyFiltersAndRender();
    }, 300);
});
```

### 3. Data Loading

```javascript
function loadItems() {
    $('#[entity]-loading').removeClass('d-none');
    $('#[entity]-list').addClass('d-none');
    $('#[entity]-empty').addClass('d-none');
    
    $.ajax({
        url: '{{ url("[app]:[entity]") }}?action=list',
        type: 'GET',
        success: function(response) {
            items = response.data || [];
            applyFiltersAndRender();
        },
        error: function(xhr, status, error) {
            $('#[entity]-loading').addClass('d-none');
            $('#[entity]-empty').removeClass('d-none');
        }
    });
}
```

### 4. Avatar Colors

```javascript
const avatarColors = {
    'avatar-blue': '#3b82f6',
    'avatar-green': '#10b981',
    'avatar-purple': '#8b5cf6',
    'avatar-orange': '#f59e0b',
    'avatar-pink': '#ec4899',
    'avatar-indigo': '#6366f1',
    'avatar-red': '#ef4444',
    'avatar-teal': '#14b8a6'
};

function getAvatarColor(name) {
    const colors = Object.values(avatarColors);
    const index = (name ? name.length : 0) % colors.length;
    return colors[index];
}

function getInitials(name) {
    if (!name) return 'NA';
    return name.split(' ')
        .map(word => word.charAt(0).toUpperCase())
        .join('')
        .substring(0, 2);
}
```

## CSS Animations

```css
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

@keyframes pulse {
    0%, 100% {
        opacity: 1;
    }
    50% {
        opacity: 0.7;
    }
}
```

## Color Palette

### Primary Colors
- **Blue**: #3b82f6 (primary actions)
- **Green**: #10b981 (success/add actions)
- **Gray**: #6b7280 (secondary text)
- **Light Gray**: #f8fafc (backgrounds)

### Status Colors
- **Active**: #dcfdf4 (bg) / #065f46 (text)
- **Inactive**: #fef2f2 (bg) / #991b1b (text)
- **Info**: #e0f2fe (bg) / #0c4a6e (text)
- **Warning**: #fef3c7 (bg) / #92400e (text)

### Solid Color Definitions
- **Primary Button**: #3b82f6
- **Success Button**: #10b981
- **Header Background**: #ffffff
- **Table Header**: #f8fafc

## Responsive Breakpoints

```css
/* Tablet */
@media (max-width: 1024px) {
    .modern-header-controls {
        padding: 1.5rem 2rem !important;
    }
    .modern-search {
        max-width: 350px !important;
    }
}

/* Mobile */
@media (max-width: 768px) {
    .modern-header-controls > div {
        flex-direction: column !important;
        gap: 1.5rem !important;
    }
    .modern-search {
        max-width: 100% !important;
        margin-right: 0 !important;
    }
}

/* Small Mobile */
@media (max-width: 640px) {
    .filter-btn {
        flex: 1 !important;
        min-width: 120px !important;
    }
    .modern-action-group {
        width: 100% !important;
    }
}
```

## Implementation Checklist

When implementing a new modern listview:

- [ ] Create template extending `base_list.html`
- [ ] Add card title with Classic/Modern view toggle
- [ ] Implement header controls section with inline styles
- [ ] Add search bar with icon and focus effects
- [ ] Create filter buttons with active/inactive states
- [ ] Add Export and Add New action buttons
- [ ] Create list container with gradient header
- [ ] Implement list items with avatar, content grid, badges, and actions
- [ ] Add loading and empty states
- [ ] Implement JavaScript for filters, search, and data loading
- [ ] Add responsive styles for mobile devices
- [ ] Test hover effects and animations
- [ ] Verify Django view supports `?template=true&modern=true` parameters

## Django View Integration

Update your Django view to make modern template the default:

```python
def get(self, request, *args, **kwargs):
    R = request.GET
    if R.get("template"):
        # Check if classic view is explicitly requested
        if R.get("classic"):
            return render(request, self.params["template_list"])
        # Default to modern view
        return render(request, "app/entity_list_modern.html")
```

## Usage Example

To access the modern listview (default):
```
http://127.0.0.1:8000/app/entity/?template=true
```

To switch to classic view:
```
http://127.0.0.1:8000/app/entity/?template=true&classic=true
```

## Notes

1. All styles are inline to prevent CSS conflicts
2. Use Bootstrap Icons (bi-*) for consistency
3. Inter font family for modern typography
4. Smooth cubic-bezier transitions for animations
5. Solid colors for clean, modern look
6. Shadow effects for depth perception
7. Hover states for all interactive elements
8. Mobile-first responsive design